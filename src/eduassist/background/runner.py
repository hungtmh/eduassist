"""Worker: đọc outbox sự kiện và chạy agent theo lịch.

    uv run eduassist-worker                 # chạy mãi: outbox mỗi vài giây, lịch hằng ngày sau DAILY_RUN_HOUR
    uv run eduassist-worker --once          # chạy mọi agent đến lịch + xử lý outbox rồi thoát
    uv run eduassist-worker --agent cong_no # chạy ngay một agent

Mỗi lần chạy agent nằm trong MỘT transaction: lỗi giữa chừng thì không để lại đề xuất dở dang, và lỗi được
ghi vào lan_chay_agent ở transaction riêng.

Chạy nhiều worker cùng lúc (nhiều máy, hoặc một bản dự phòng) an toàn:
- outbox: mỗi sự kiện chỉ một worker lấy (FOR UPDATE SKIP LOCKED);
- agent theo lịch / chạy tay: khoá theo tên agent (pg_try_advisory_xact_lock) rồi kiểm tra lại "đã chạy hôm nay chưa"
  bên trong khoá -> hai worker không chạy trùng agent hằng ngày (không gửi trùng nhắc nợ). Khoá gắn với transaction
  nên dùng được qua PgBouncer chế độ transaction, và tự nhả khi worker chết giữa chừng;
- nút "Chạy ca ngay" trên web không chạy agent trong request API mà ghi yêu cầu vào outbox (RUN_REQUEST); worker
  nhận trong vài giây, chạy đúng một lần và ghi run_id vào yêu cầu để web theo dõi kết quả.
"""

import argparse
import json
import logging
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path

from eduassist.background.agents import AGENTS, EVENT_ROUTES
from eduassist.background.base import AgentRun
from eduassist.config import get_settings
from eduassist.db import app_pool
from eduassist.services import proposals
from eduassist.services.core import today

log = logging.getLogger("eduassist.worker")


RUN_REQUEST = "agent.run_requested"


def _lock_agent(conn, name: str) -> bool:
    """Khoá theo tên agent trong transaction hiện tại; False nếu worker / yêu cầu khác đang chạy agent này."""
    return conn.execute("SELECT pg_try_advisory_xact_lock(hashtext('agent:' || %s)) AS ok", (name,)).fetchone()["ok"]


def run_agent(name: str, trigger: str, event: dict | None = None, conn=None) -> dict:
    """Chạy một agent. conn=None: tự mở kết nối + transaction, có khoá chống chạy trùng. Truyền conn: chạy trong
    savepoint của người gọi (sự kiện outbox; mô phỏng/đánh giá chạy cả 30 ngày trong một transaction rồi rollback)."""
    agent = AGENTS[name]
    if conn is not None:
        with conn.transaction():
            run = AgentRun(conn, name, agent.role, trigger)
            summary = agent.run(conn, run, event)
            run.finish(summary)
        return {"agent": name, "run_id": run.id, "tom_tat": summary, "de_xuat": run.proposed, "tu_dong": run.auto}
    with app_pool().connection() as c:
        try:
            with c.transaction():
                if not _lock_agent(c, name):
                    log.info("agent %s đang chạy ở nơi khác - bỏ qua lần %s", name, trigger)
                    return {"agent": name, "bo_qua": "Agent này đang chạy (lịch hoặc người khác vừa bấm chạy)."}
                if trigger.startswith("lich:") and name not in due_agents(c, only=name):
                    return {"agent": name, "bo_qua": "Worker khác đã chạy ca theo lịch hôm nay."}
                run = AgentRun(c, name, agent.role, trigger)
                summary = agent.run(c, run, event)
                run.finish(summary)
            log.info("agent %s xong: %s", name, summary)
            return {"agent": name, "run_id": run.id, "tom_tat": summary, "de_xuat": run.proposed, "tu_dong": run.auto}
        except Exception as e:
            log.exception("agent %s lỗi", name)
            with c.transaction():
                run_id = c.execute(
                    """INSERT INTO lan_chay_agent (agent, kich_hoat, ngay_nghiep_vu, ket_thuc, trang_thai, loi)
                       VALUES (%s, %s, %s, now(), 'loi', %s) RETURNING id""",
                    (name, trigger, today(), "".join(traceback.format_exception_only(e)).strip()[:2000]),
                ).fetchone()["id"]
            return {"agent": name, "run_id": run_id, "loi": str(e)}


def request_run(conn, name: str, username: str) -> dict:
    """Ghi yêu cầu "chạy ngay" cho worker. Đã có yêu cầu chưa xử lý cho agent này thì trả lại yêu cầu đó."""
    row = conn.execute(
        f"""SELECT id, created_at FROM outbox_su_kien
            WHERE loai = '{RUN_REQUEST}' AND processed_at IS NULL AND payload->>'agent' = %s ORDER BY id LIMIT 1""",
        (name,),
    ).fetchone()
    if row is None:
        row = conn.execute(
            f"""INSERT INTO outbox_su_kien (loai, payload) VALUES ('{RUN_REQUEST}', jsonb_build_object('agent', %s::text,
                'nguoi_yeu_cau', %s::text)) RETURNING id, created_at""",
            (name, username),
        ).fetchone()
    return {"yeu_cau_id": row["id"], "agent": name, "trang_thai": "cho", "tao_luc": row["created_at"]}


def run_request_status(conn, request_id: int) -> dict | None:
    row = conn.execute(
        f"""SELECT o.id, o.payload, o.processed_at, o.error, r.trang_thai, r.tom_tat, r.loi, r.so_de_xuat, r.so_tu_dong
            FROM outbox_su_kien o LEFT JOIN lan_chay_agent r ON r.id = (o.payload->>'run_id')::int
            WHERE o.id = %s AND o.loai = '{RUN_REQUEST}'""",
        (request_id,),
    ).fetchone()
    if row is None:
        return None
    out = {"yeu_cau_id": row["id"], "agent": row["payload"].get("agent")}
    if row["processed_at"] is None:
        return {**out, "trang_thai": "cho"}
    if "bo_qua" in row["payload"]:
        return {**out, "trang_thai": "bo_qua", "loi": row["payload"]["bo_qua"]}
    if row["trang_thai"] is None:
        return {**out, "trang_thai": "dang_chay"}
    return {
        **out,
        "trang_thai": row["trang_thai"],
        "tom_tat": row["tom_tat"],
        "loi": row["loi"],
        "de_xuat": row["so_de_xuat"],
        "tu_dong": row["so_tu_dong"],
    }


def process_run_requests(limit: int = 5) -> int:
    """Chạy các yêu cầu "chạy ngay". Nhận yêu cầu (đánh dấu đã xử lý, commit) TRƯỚC rồi mới chạy: mỗi lần bấm
    chạy đúng một lần, kể cả khi worker chết giữa chừng (khi đó web báo lỗi thay vì chạy lại ngầm)."""
    done = 0
    for _ in range(limit):
        with app_pool().connection() as c:
            with c.transaction():
                req = c.execute(
                    f"""UPDATE outbox_su_kien SET processed_at = now(), attempts = attempts + 1
                        WHERE id = (SELECT id FROM outbox_su_kien WHERE loai = '{RUN_REQUEST}' AND processed_at IS NULL
                                    ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED)
                        RETURNING id, payload""",
                ).fetchone()
            if req is None:
                return done
            name = req["payload"].get("agent")
            if name not in AGENTS:
                res = {"bo_qua": "Không có agent này."}
            else:
                res = run_agent(name, f"thu_cong:{req['payload'].get('nguoi_yeu_cau', '?')}")
            extra = {"run_id": res["run_id"]} if "run_id" in res else {"bo_qua": res.get("bo_qua", "")}
            c.execute(
                "UPDATE outbox_su_kien SET payload = payload || %s::jsonb, error = %s WHERE id = %s",
                (json.dumps(extra), res.get("loi"), req["id"]),
            )
            done += 1
    return done


def process_outbox(limit: int = 50, conn=None) -> int:
    """Lấy sự kiện chưa xử lý (SKIP LOCKED: nhiều worker không tranh nhau), chạy agent đăng ký, đánh dấu xong."""

    def _do(c) -> int:
        with c.transaction():
            events = c.execute(
                f"""SELECT * FROM outbox_su_kien WHERE processed_at IS NULL AND attempts < 5 AND loai <> '{RUN_REQUEST}'
                   ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED""",
                (limit,),
            ).fetchall()
            for ev in events:
                error = None
                for name in EVENT_ROUTES.get(ev["loai"], []):
                    try:
                        with c.transaction():
                            res = run_agent(name, f"su_kien:{ev['loai']}", ev["payload"], conn=c)
                            log.info("sự kiện %s #%s -> %s", ev["loai"], ev["id"], res["tom_tat"])
                    except Exception as e:  # một agent lỗi không chặn agent khác
                        log.exception("sự kiện %s #%s: agent %s lỗi", ev["loai"], ev["id"], name)
                        error = f"{name}: {e}"
                c.execute(
                    """UPDATE outbox_su_kien SET attempts = attempts + 1, error = %s,
                              processed_at = CASE WHEN %s::text IS NULL THEN now() END WHERE id = %s""",
                    (error, error, ev["id"]),
                )
            return len(events)

    if conn is not None:
        return _do(conn)
    with app_pool().connection() as c:
        return _do(c)


def due_agents(conn, only: str | None = None) -> list[str]:
    """Agent đến lịch: daily = chưa chạy theo lịch hôm nay; weekly = thứ Hai (hoặc chưa chạy trong tuần này)."""
    t = today()
    out = []
    for name, a in AGENTS.items():
        if only is not None and name != only:
            continue
        last = conn.execute(
            """SELECT max(ngay_nghiep_vu) AS d FROM lan_chay_agent
               WHERE agent = %s AND kich_hoat LIKE 'lich:%%' AND trang_thai = 'xong'""",
            (name,),
        ).fetchone()["d"]
        new_week = last is None or (last.isocalendar()[:2] != t.isocalendar()[:2] and t.weekday() == 0)
        if (a.schedule == "daily" and last != t) or (a.schedule == "weekly" and new_week):
            out.append(name)
    return out


def run_due(conn=None) -> list[dict]:
    if conn is None:
        with app_pool().connection() as c, c.transaction():
            names = due_agents(c)
            expired = proposals.expire_stale(c)
    else:
        names = due_agents(conn)
        expired = proposals.expire_stale(conn)
    if expired:
        log.info("%d đề xuất hết hạn duyệt", expired)
    # conn=None: run_agent tự khoá theo tên agent và kiểm tra lại lịch bên trong khoá (nhiều worker không chạy trùng)
    return [run_agent(n, f"lich:{AGENTS[n].schedule}", conn=conn) for n in names]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from eduassist.observability import init_sentry

    init_sentry("worker")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true", help="chạy agent đến lịch + outbox một lần rồi thoát")
    parser.add_argument("--agent", choices=sorted(AGENTS), help="chạy ngay một agent")
    args = parser.parse_args()
    s = get_settings()
    if args.agent:
        print(run_agent(args.agent, "thu_cong:cli"))
        return
    if args.once:
        for r in run_due():
            print(r)
        print(f"chạy theo yêu cầu: {process_run_requests()}, outbox: {process_outbox()} sự kiện")
        return
    log.info("worker chạy: outbox mỗi %ss, lịch hằng ngày sau %sh", s.worker_poll_seconds, s.daily_run_hour)
    beat()
    while True:
        try:
            process_run_requests()
            process_outbox()
            if datetime.now().hour >= s.daily_run_hour:
                run_due()
        except Exception:
            log.exception("vòng lặp worker lỗi - thử lại sau")
        beat()
        time.sleep(s.worker_poll_seconds)


def heartbeat_path() -> Path:
    return Path(get_settings().worker_heartbeat_file or Path(tempfile.gettempdir()) / "eduassist-worker.alive")


def beat() -> None:
    """Ghi nhịp tim sau mỗi vòng. Vòng lặp treo (VD kẹt ở một câu SQL) thì file không được cập nhật nữa."""
    try:
        heartbeat_path().write_text(str(int(time.time())))
    except OSError:
        log.warning("không ghi được nhịp tim worker vào %s", heartbeat_path())


def heartbeat_ok() -> None:
    """eduassist-worker-alive: thoát mã 0 nếu nhịp tim còn mới. K8s gọi lệnh này làm liveness probe (worker không có
    HTTP để hỏi); quá hạn thì K8s khởi động lại worker."""
    s = get_settings()
    max_age = s.worker_poll_seconds + s.worker_heartbeat_grace_seconds
    try:
        age = time.time() - heartbeat_path().stat().st_mtime
    except OSError:
        print("chưa có nhịp tim")
        raise SystemExit(1) from None
    print(f"nhịp tim cách đây {age:.0f}s (tối đa {max_age}s)")
    raise SystemExit(0 if age <= max_age else 1)


if __name__ == "__main__":
    main()
