"""Khung chạy agent nền: ghi lan_chay_agent, đếm đề xuất, LLM soạn lời văn có kiểm chứng và bản dự phòng."""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from eduassist.config import get_settings
from eduassist.services import proposals
from eduassist.services.core import Actor, Role, agent_actor, today

log = logging.getLogger("eduassist.background")


class AgentRun:
    def __init__(self, conn, agent: str, role: Role, trigger: str):
        self.conn = conn
        self.agent = agent
        self.actor: Actor = agent_actor(agent, role)
        self.proposed = 0
        self.auto = 0
        self.skipped = 0
        self.id = conn.execute(
            "INSERT INTO lan_chay_agent (agent, kich_hoat, ngay_nghiep_vu) VALUES (%s, %s, %s) RETURNING id",
            (agent, trigger, today()),
        ).fetchone()["id"]

    def submit(
        self, action_type: str, title: str, summary: str, data: dict, evidence=None, dedupe_key=None, params=None
    ):
        p = proposals.submit(
            self.conn, self.actor, action_type, title, summary, data, evidence, params, dedupe_key, self.id
        )
        if p is None:
            self.skipped += 1
        elif p["nguoi_duyet"] == proposals.AUTO:
            self.auto += 1
        else:
            self.proposed += 1
        return p

    def finish(self, summary: str) -> None:
        self.conn.execute(
            """UPDATE lan_chay_agent SET trang_thai = 'xong', ket_thuc = now(), so_de_xuat = %s, so_tu_dong = %s,
                      tom_tat = %s WHERE id = %s""",
            (self.proposed, self.auto, summary, self.id),
        )


@dataclass(frozen=True)
class BackgroundAgent:
    name: str
    label: str
    role: Role
    run: Callable  # (conn, AgentRun, event | None) -> tóm tắt
    events: tuple[str, ...] = ()
    schedule: str = "daily"  # daily | weekly
    description: str = ""
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------- LLM soạn lời văn
_NUM = re.compile(r"\d[\d.,]{3,}\d")


def numbers_faithful(text: str, source: str) -> bool:
    """Mọi số >= 4 chữ số trong văn bản LLM viết phải có trong dữ liệu đưa vào (chống bịa số)."""
    allowed = {re.sub(r"\D", "", n) for n in _NUM.findall(source)}
    return all(re.sub(r"\D", "", n) in allowed for n in _NUM.findall(text))


def draft_text(system: str, user: str, fallback: str, max_chars: int = 900) -> tuple[str, bool]:
    """(văn bản, có dùng LLM không). LLM lỗi / tắt / viết sai -> dùng bản mẫu do code soạn."""
    s = get_settings()
    if not s.background_llm or not s.groq_api_key.get_secret_value():
        return fallback, False
    try:
        from eduassist.llm import chat_model

        out = chat_model(temperature=0.3, background=True).invoke([("system", system), ("user", user)]).content
        out = (out if isinstance(out, str) else "").strip()
    except Exception:
        log.warning("LLM không soạn được - dùng bản mẫu", exc_info=True)
        return fallback, False
    if not 40 <= len(out) <= max_chars or "{" in out or not numbers_faithful(out, user):
        log.info("bản LLM không đạt kiểm tra (độ dài / số liệu) - dùng bản mẫu")
        return fallback, False
    return out, True
