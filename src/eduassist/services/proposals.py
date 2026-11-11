"""Hộp duyệt và mức tự chủ (mục 6.3, 6.5 của đề xuất).

Vòng đời đề xuất:  goi_y -> da_xem                                     (L0: chỉ báo, không hành động)
                   cho_duyet -> da_duyet -> da_thuc_hien | that_bai     (L1: người có quyền quyết định)
                   cho_duyet -> tu_choi | het_han
                   (L2: tạo thẳng ở da_duyet bởi 'auto:L2' rồi thực thi, nếu còn trong hạn mức ngày)

Mức tự chủ cấu hình theo TỪNG LOẠI THAO TÁC (bảng chinh_sach_tu_chu), không theo cả agent.
"""

import json
from datetime import timedelta

from eduassist.services import rules
from eduassist.services.actions import ACTIONS, FORBIDDEN_FOREVER, apply_edits
from eduassist.services.core import (
    ROLES,
    Actor,
    Forbidden,
    NotFound,
    RuleViolation,
    audit,
    check_transition,
    emit_event,
    has_perm,
    one,
    require,
    to_json,
    today,
)

PENDING_TTL = timedelta(days=3)
AUTO = "auto:L2"


# ---------------------------------------------------------------- chính sách tự chủ
def ensure_default_policies(conn) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO chinh_sach_tu_chu (loai_hanh_dong, muc, han_muc_ngay, mo_ta) VALUES (%s, %s, %s, %s)
               ON CONFLICT (loai_hanh_dong) DO NOTHING""",
            [(a.key, a.default_level, a.default_limit, a.description) for a in ACTIONS.values()],
        )


def list_policies(conn, actor: Actor) -> list[dict]:
    require(actor, "chat.data")
    rows = conn.execute("SELECT * FROM chinh_sach_tu_chu ORDER BY loai_hanh_dong").fetchall()
    for r in rows:
        a = ACTIONS.get(r["loai_hanh_dong"])
        r["ten"] = a.label if a else r["loai_hanh_dong"]
        r["khoa_cung"] = r["loai_hanh_dong"] in FORBIDDEN_FOREVER
        r["chi_canh_bao"] = bool(a and a.execute is None and not r["khoa_cung"])
        r["dung_hom_nay"] = _auto_units_today(conn, r["loai_hanh_dong"])
    return rows


def update_policy(conn, actor: Actor, action_type: str, level: str, daily_limit: int) -> dict:
    """Agent không tự đổi được mức tự chủ (autonomy.write thuộc AGENT_FORBIDDEN)."""
    require(actor, "autonomy.write")
    if action_type in FORBIDDEN_FOREVER:
        raise RuleViolation("Thao tác thuộc mức Cấm cố định, không cấu hình được.")
    if action_type not in ACTIONS:
        raise NotFound("Không có loại thao tác này.")
    if level not in ("L0", "L1", "L2"):
        raise RuleViolation("Mức tự chủ là L0, L1 hoặc L2.")
    if ACTIONS[action_type].execute is None and level != "L0":
        raise RuleViolation("Loại này chỉ là cảnh báo, chỉ đặt được mức L0.")
    if level == "L2" and daily_limit <= 0:
        raise RuleViolation("Mức L2 cần hạn mức mỗi ngày lớn hơn 0.")
    before = one(conn, "SELECT * FROM chinh_sach_tu_chu WHERE loai_hanh_dong = %s FOR UPDATE", (action_type,))
    conn.execute(
        """UPDATE chinh_sach_tu_chu SET muc = %s, han_muc_ngay = %s, updated_by = %s, updated_at = now()
           WHERE loai_hanh_dong = %s""",
        (level, daily_limit, actor.id, action_type),
    )
    audit(
        conn,
        actor,
        "doi_muc_tu_chu",
        "chinh_sach_tu_chu",
        action_type,
        before={"muc": before["muc"], "han_muc_ngay": before["han_muc_ngay"]},
        after={"muc": level, "han_muc_ngay": daily_limit},
    )
    return one(conn, "SELECT * FROM chinh_sach_tu_chu WHERE loai_hanh_dong = %s", (action_type,))


def _policy(conn, action_type: str) -> dict:
    if action_type in FORBIDDEN_FOREVER:
        return {"muc": "cam", "han_muc_ngay": 0}
    row = conn.execute(
        "SELECT muc, han_muc_ngay FROM chinh_sach_tu_chu WHERE loai_hanh_dong = %s", (action_type,)
    ).fetchone()
    if row is None:
        a = ACTIONS[action_type]
        return {"muc": a.default_level, "han_muc_ngay": a.default_limit}
    return row


def _units(data: dict) -> int:
    return len(data["items"]) if isinstance(data.get("items"), list) else 1


def _auto_units_today(conn, action_type: str) -> int:
    rows = conn.execute(
        """SELECT du_lieu FROM de_xuat_agent WHERE loai_hanh_dong = %s AND nguoi_duyet = %s
           AND ngay_nghiep_vu = %s AND trang_thai = 'da_thuc_hien'""",
        (action_type, AUTO, today()),
    ).fetchall()
    return sum(_units(r["du_lieu"]) for r in rows)


# ---------------------------------------------------------------- tạo đề xuất
def item_already_proposed(conn, action_types: list[str], item: dict) -> bool:
    """Mục (VD: một đợt học phí ở một bậc) đã nằm trong đề xuất nào chưa bị huỷ? -> chống làm lặp một việc.
    Đề xuất hết hạn thì được đề xuất lại; bị TỪ CHỐI thì không (con người đã quyết)."""
    return (
        conn.execute(
            """SELECT 1 FROM de_xuat_agent WHERE loai_hanh_dong = ANY(%s) AND trang_thai <> 'het_han'
               AND du_lieu -> 'items' @> %s::jsonb LIMIT 1""",
            (action_types, json.dumps([item])),
        ).fetchone()
        is not None
    )


def submit(
    conn,
    requester: Actor,
    action_type: str,
    title: str,
    summary: str,
    data: dict,
    evidence: list | None = None,
    params: dict | None = None,
    dedupe_key: str | None = None,
    run_id: int | None = None,
) -> dict | None:
    """Agent đề xuất một thao tác. Mức tự chủ quyết định: L0 ghi gợi ý; L1 chờ duyệt; L2 tự thực thi nếu còn hạn mức.
    Trả đề xuất (dict) hoặc None nếu trùng khoá chống trùng."""
    if action_type not in ACTIONS:
        raise RuleViolation(f"Loại thao tác không tồn tại: {action_type}.")
    action = ACTIONS[action_type]
    policy = _policy(conn, action_type)
    if policy["muc"] == "cam":
        audit(conn, requester, "chan_thao_tac_cam", "de_xuat_agent", None, after={"loai": action_type}, reason=title)
        raise Forbidden(f"'{action.label}' thuộc mức Cấm: agent không bao giờ được làm, kể cả khi được yêu cầu.")
    # Kiểm tra trước ở phía agent: vai trò của agent phải có quyền làm việc này (cùng luật với nhân viên)
    require(requester, action.perm)
    level = policy["muc"]
    note = ""
    status = {"L0": "goi_y", "L1": "cho_duyet", "L2": "da_duyet"}[level]
    if level == "L2":
        used = _auto_units_today(conn, action_type)
        if used + _units(data) > policy["han_muc_ngay"]:
            status, level = "cho_duyet", "L1"
            note = f" (Vượt hạn mức tự động {policy['han_muc_ngay']}/ngày, đã dùng {used} -> chuyển sang chờ duyệt.)"
    row = conn.execute(
        """INSERT INTO de_xuat_agent (agent, loai_hanh_dong, tieu_de, tom_tat, tham_so, du_lieu, can_cu, muc_tu_chu,
                                      trang_thai, khoa_chong_trung, nguoi_yeu_cau, vai_tro_thuc_thi, nguoi_duyet,
                                      lan_chay_id, ngay_nghiep_vu, het_han_luc, decided_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   CASE WHEN %s = 'cho_duyet' THEN now() + %s END,
                   CASE WHEN %s = 'da_duyet' THEN now() END)
           ON CONFLICT (khoa_chong_trung) DO NOTHING RETURNING id""",
        (
            requester.id.removeprefix("agent:") if requester.id.startswith("agent:") else "van_hanh",
            action_type,
            title,
            summary + note,
            to_json(params or {}),
            to_json(data),
            to_json(evidence or []),
            level,
            status,
            dedupe_key,
            requester.id,
            requester.role,
            AUTO if status == "da_duyet" else None,
            run_id,
            today(),
            status,
            PENDING_TTL,
            status,
        ),
    ).fetchone()
    if row is None:
        return None
    pid = row["id"]
    audit(
        conn,
        requester,
        "tao_de_xuat",
        "de_xuat_agent",
        pid,
        after={"loai": action_type, "muc": level, "tieu_de": title},
    )
    if status == "da_duyet":
        _execute(conn, pid)
    elif status == "cho_duyet":
        emit_event(conn, "proposal.created", de_xuat_id=pid, loai=action_type)
    return get(conn, None, pid)


def _executor_actor(p: dict, approved_by: str) -> Actor:
    """Thực thi với vai trò của bên đề xuất (agent / người ra lệnh qua chat), LUÔN đánh dấu is_agent:
    hành động do LLM khởi xướng thì chịu cả danh sách Cấm."""
    return Actor(id=p["nguoi_yeu_cau"], role=p["vai_tro_thuc_thi"], is_agent=True).executing(p["id"], approved_by)


def _execute(conn, pid: int) -> dict:
    p = one(conn, "SELECT * FROM de_xuat_agent WHERE id = %s FOR UPDATE", (pid,), "đề xuất")
    check_transition("đề xuất", rules.PROPOSAL_TRANSITIONS, p["trang_thai"], "da_thuc_hien")
    action = ACTIONS[p["loai_hanh_dong"]]
    actor = _executor_actor(p, p["nguoi_duyet"])
    try:
        with conn.transaction():  # savepoint: thất bại thì huỷ phần đã làm dở, vẫn lưu trạng thái that_bai
            result = action.execute(conn, actor, p["du_lieu"], pid)
        status = "da_thuc_hien"
    except (RuleViolation, Forbidden, NotFound) as e:
        result, status = f"Không thực hiện được: {e.message}", "that_bai"
    conn.execute(
        "UPDATE de_xuat_agent SET trang_thai = %s, ket_qua = %s, executed_at = now() WHERE id = %s",
        (status, result, pid),
    )
    audit(conn, actor, "thuc_thi_de_xuat", "de_xuat_agent", pid, after={"trang_thai": status, "ket_qua": result})
    return {"trang_thai": status, "ket_qua": result}


# ---------------------------------------------------------------- quyết định của con người
def _can_decide(actor: Actor, p: dict) -> bool:
    if actor.is_agent:
        return False
    if has_perm(actor, "proposal.decide_any"):
        return True
    return has_perm(actor, ACTIONS[p["loai_hanh_dong"]].perm) and (
        p["vai_tro_thuc_thi"] == actor.role or p["nguoi_yeu_cau"] == actor.id
    )


def approve(conn, actor: Actor, pid: int, edits: dict | None = None) -> dict:
    p = one(conn, "SELECT * FROM de_xuat_agent WHERE id = %s FOR UPDATE", (pid,), "đề xuất")
    if not _can_decide(actor, p):
        raise Forbidden("Bạn không có quyền duyệt đề xuất này.")
    if p["trang_thai"] == "cho_duyet" and p["het_han_luc"] and _expired(conn, p):
        conn.execute("UPDATE de_xuat_agent SET trang_thai = 'het_han' WHERE id = %s", (pid,))
        raise RuleViolation("Đề xuất đã hết hạn duyệt; agent sẽ đề xuất lại nếu vẫn cần.")
    check_transition("đề xuất", rules.PROPOSAL_TRANSITIONS, p["trang_thai"], "da_duyet")
    data = p["du_lieu"]
    if edits:
        data = apply_edits(ACTIONS[p["loai_hanh_dong"]], data, edits)
    conn.execute(
        """UPDATE de_xuat_agent SET trang_thai = 'da_duyet', nguoi_duyet = %s, decided_at = now(), du_lieu = %s,
                  da_sua = %s WHERE id = %s""",
        (actor.id, to_json(data), bool(edits), pid),
    )
    audit(
        conn,
        actor,
        "duyet_de_xuat",
        "de_xuat_agent",
        pid,
        before={"du_lieu": p["du_lieu"]} if edits else None,
        after={"da_sua": bool(edits), "du_lieu": data} if edits else None,
    )
    _execute(conn, pid)
    return get(conn, actor, pid)


def reject(conn, actor: Actor, pid: int, reason: str = "") -> dict:
    p = one(conn, "SELECT * FROM de_xuat_agent WHERE id = %s FOR UPDATE", (pid,), "đề xuất")
    if not _can_decide(actor, p):
        raise Forbidden("Bạn không có quyền từ chối đề xuất này.")
    check_transition("đề xuất", rules.PROPOSAL_TRANSITIONS, p["trang_thai"], "tu_choi")
    conn.execute(
        "UPDATE de_xuat_agent SET trang_thai = 'tu_choi', nguoi_duyet = %s, ly_do_tu_choi = %s, decided_at = now()"
        " WHERE id = %s",
        (actor.id, reason or None, pid),
    )
    audit(conn, actor, "tu_choi_de_xuat", "de_xuat_agent", pid, reason=reason or None)
    return get(conn, actor, pid)


def dismiss(conn, actor: Actor, pid: int) -> dict:
    p = one(conn, "SELECT * FROM de_xuat_agent WHERE id = %s FOR UPDATE", (pid,), "đề xuất")
    require(actor, ACTIONS[p["loai_hanh_dong"]].perm)
    check_transition("gợi ý", rules.PROPOSAL_TRANSITIONS, p["trang_thai"], "da_xem")
    conn.execute(
        "UPDATE de_xuat_agent SET trang_thai = 'da_xem', nguoi_duyet = %s, decided_at = now() WHERE id = %s",
        (actor.id, pid),
    )
    return get(conn, actor, pid)


def bulk_decide(conn, actor: Actor, ids: list[int], approve_all: bool, reason: str = "") -> list[dict]:
    out = []
    for pid in ids:
        try:
            with conn.transaction():
                p = approve(conn, actor, pid) if approve_all else reject(conn, actor, pid, reason)
            out.append({"id": pid, "ok": True, "trang_thai": p["trang_thai"], "ket_qua": p.get("ket_qua")})
        except (RuleViolation, Forbidden, NotFound) as e:
            out.append({"id": pid, "ok": False, "loi": e.message})
    return out


def _expired(conn, p: dict) -> bool:
    return conn.execute("SELECT %s < now() AS x", (p["het_han_luc"],)).fetchone()["x"]


def expire_stale(conn) -> int:
    rows = conn.execute(
        "UPDATE de_xuat_agent SET trang_thai = 'het_han' WHERE trang_thai = 'cho_duyet' AND het_han_luc < now()"
        " RETURNING id"
    ).fetchall()
    return len(rows)


# ---------------------------------------------------------------- đọc
LIST_SQL = """SELECT id, agent, loai_hanh_dong, tieu_de, tom_tat, muc_tu_chu, trang_thai, nguoi_yeu_cau,
                     vai_tro_thuc_thi, nguoi_duyet, da_sua, ket_qua, created_at, decided_at, executed_at, het_han_luc,
                     ngay_nghiep_vu, jsonb_array_length(coalesce(du_lieu -> 'items', '[]')) AS so_muc
              FROM de_xuat_agent"""


def list_proposals(conn, actor: Actor, status: str | None = None, agent: str | None = None, limit: int = 100):
    require(actor, "chat.data")
    where, params = ["true"], {"limit": limit}
    if status == "can_xu_ly":
        where.append("trang_thai IN ('cho_duyet', 'goi_y')")
    elif status:
        where.append("trang_thai = %(st)s")
        params["st"] = status
    if agent:
        where.append("agent = %(agent)s")
        params["agent"] = agent
    if not has_perm(actor, "proposal.decide_any"):
        perms = [k for k, a in ACTIONS.items() if has_perm(actor, a.perm)]
        where.append("(loai_hanh_dong = ANY(%(perms)s) OR nguoi_yeu_cau = %(me)s)")
        params.update(perms=perms, me=actor.id)
    rows = conn.execute(
        LIST_SQL
        + " WHERE "
        + " AND ".join(where)
        + " ORDER BY CASE trang_thai WHEN 'cho_duyet' THEN 0 WHEN 'goi_y' THEN 1 ELSE 2 END, created_at DESC"
        " LIMIT %(limit)s",
        params,
    ).fetchall()
    for r in rows:
        r["ten_hanh_dong"] = ACTIONS[r["loai_hanh_dong"]].label
        r["co_the_duyet"] = _can_decide(actor, r) if r["trang_thai"] == "cho_duyet" else False
    return rows


def get(conn, actor: Actor | None, pid: int) -> dict:
    p = one(conn, "SELECT * FROM de_xuat_agent WHERE id = %s", (pid,), "đề xuất")
    if actor is not None:
        require(actor, "chat.data")
        if not (
            has_perm(actor, "proposal.decide_any")
            or has_perm(actor, ACTIONS[p["loai_hanh_dong"]].perm)
            or p["nguoi_yeu_cau"] == actor.id
        ):
            raise Forbidden("Bạn không xem được đề xuất này.")
    action = ACTIONS[p["loai_hanh_dong"]]
    p["ten_hanh_dong"] = action.label
    p["truong_sua_duoc"] = list(action.editable) + (["keep_items"] if action.has_items else [])
    p["khoa_muc"] = action.item_key if action.has_items else None
    p["co_the_duyet"] = actor is not None and p["trang_thai"] == "cho_duyet" and _can_decide(actor, p)
    return p


def counts(conn, actor: Actor) -> dict:
    rows = list_proposals(conn, actor, "can_xu_ly", limit=1000)
    return {
        "cho_duyet": sum(r["trang_thai"] == "cho_duyet" for r in rows),
        "goi_y": sum(r["trang_thai"] == "goi_y" for r in rows),
    }


def stats(conn, actor: Actor, days: int = 30) -> list[dict]:
    """Chỉ số cho đánh giá agent: số đề xuất, tỉ lệ duyệt không sửa, tự động, thất bại - theo agent."""
    require(actor, "report.read")
    return conn.execute(
        """SELECT agent, count(*)::int AS tong,
                  count(*) FILTER (WHERE nguoi_duyet = 'auto:L2')::int AS tu_dong,
                  count(*) FILTER (WHERE trang_thai IN ('da_thuc_hien', 'that_bai') AND nguoi_duyet <> 'auto:L2')::int
                      AS da_duyet,
                  count(*) FILTER (WHERE trang_thai IN ('da_thuc_hien', 'that_bai') AND nguoi_duyet <> 'auto:L2'
                                   AND NOT da_sua)::int AS duyet_khong_sua,
                  count(*) FILTER (WHERE trang_thai = 'tu_choi')::int AS tu_choi,
                  count(*) FILTER (WHERE trang_thai = 'cho_duyet')::int AS cho_duyet,
                  count(*) FILTER (WHERE trang_thai = 'that_bai')::int AS that_bai
           FROM de_xuat_agent WHERE created_at > now() - make_interval(days => %s) GROUP BY agent ORDER BY agent""",
        (days,),
    ).fetchall()


__all__ = ["ROLES", "ensure_default_policies", "submit", "approve", "reject"]
