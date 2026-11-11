"""Worker: đọc outbox sự kiện và chạy agent theo lịch.

    uv run eduassist-worker                 # chạy mãi: outbox mỗi vài giây, lịch hằng ngày sau DAILY_RUN_HOUR
    uv run eduassist-worker --once          # chạy mọi agent đến lịch + xử lý outbox rồi thoát
    uv run eduassist-worker --agent cong_no # chạy ngay một agent

Mỗi lần chạy agent nằm trong MỘT transaction: lỗi giữa chừng thì không để lại đề xuất dở dang, và lỗi được
ghi vào lan_chay_agent ở transaction riêng.
"""

import argparse
import logging
import time
import traceback
from datetime import datetime

from eduassist.background.agents import AGENTS, EVENT_ROUTES
from eduassist.background.base import AgentRun
from eduassist.config import get_settings
from eduassist.db import app_pool
from eduassist.services import proposals
from eduassist.services.core import today

log = logging.getLogger("eduassist.worker")


def run_agent(name: str, trigger: str, event: dict | None = None, conn=None) -> dict:
    """Chạy một agent. conn=None: tự mở kết nối + transaction. Truyền conn: chạy trong savepoint của người gọi
    (mô phỏng/đánh giá chạy cả 30 ngày trong một transaction rồi rollback)."""
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
                run = AgentRun(c, name, agent.role, trigger)
                summary = agent.run(c, run, event)
                run.finish(summary)
            log.info("agent %s xong: %s", name, summary)
            return {"agent": name, "run_id": run.id, "tom_tat": summary, "de_xuat": run.proposed, "tu_dong": run.auto}
        except Exception as e:
            log.exception("agent %s lỗi", name)
            with c.transaction():
                c.execute(
                    """INSERT INTO lan_chay_agent (agent, kich_hoat, ngay_nghiep_vu, ket_thuc, trang_thai, loi)
                       VALUES (%s, %s, %s, now(), 'loi', %s)""",
                    (name, trigger, today(), "".join(traceback.format_exception_only(e)).strip()[:2000]),
                )
            return {"agent": name, "loi": str(e)}


def process_outbox(limit: int = 50, conn=None) -> int:
    """Lấy sự kiện chưa xử lý (SKIP LOCKED: nhiều worker không tranh nhau), chạy agent đăng ký, đánh dấu xong."""

    def _do(c) -> int:
        with c.transaction():
            events = c.execute(
                """SELECT * FROM outbox_su_kien WHERE processed_at IS NULL AND attempts < 5
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


def due_agents(conn) -> list[str]:
    """Agent đến lịch: daily = chưa chạy theo lịch hôm nay; weekly = thứ Hai (hoặc chưa chạy trong tuần này)."""
    t = today()
    out = []
    for name, a in AGENTS.items():
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
    return [run_agent(n, f"lich:{AGENTS[n].schedule}", conn=conn) for n in names]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
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
        print(f"outbox: {process_outbox()} sự kiện")
        return
    log.info("worker chạy: outbox mỗi %ss, lịch hằng ngày sau %sh", s.worker_poll_seconds, s.daily_run_hour)
    while True:
        try:
            process_outbox()
            if datetime.now().hour >= s.daily_run_hour:
                run_due()
        except Exception:
            log.exception("vòng lặp worker lỗi - thử lại sau")
        time.sleep(s.worker_poll_seconds)


if __name__ == "__main__":
    main()
