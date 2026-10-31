"""Nạp tài liệu chính sách + ví dụ SQL mẫu vào pgvector.

Cắt tài liệu theo heading "## ..." để mỗi chunk là MỘT mục trọn vẹn -> trích nguồn chính xác
("03_bao_luu_hoan_tien.md › Hoàn học phí") thay vì cắt máy móc theo số ký tự.
"""

import json
import logging
import re
from pathlib import Path

import numpy as np

from eduassist.db import app_pool
from eduassist.rag.embeddings import get_embeddings

log = logging.getLogger("eduassist.ingest")
ROOT = Path(__file__).resolve().parents[3]
POLICY_DIR = ROOT / "data" / "policies"
SQL_EXAMPLES_FILE = ROOT / "data" / "sql_examples.json"
MAX_CHUNK_CHARS = 1200


def split_markdown(text: str) -> list[tuple[str, str]]:
    """-> [(section, content)]. Mục quá dài được chia tiếp theo đoạn văn."""
    title = re.search(r"^# (.+)$", text, re.M)
    doc_title = title.group(1).strip() if title else ""
    chunks = []
    for part in re.split(r"^## ", text, flags=re.M)[1:]:
        heading, _, body = part.partition("\n")
        body = body.strip()
        if not body:
            continue
        section = f"{doc_title} › {heading.strip()}" if doc_title else heading.strip()
        buf = ""
        for para in body.split("\n\n"):
            if buf and len(buf) + len(para) > MAX_CHUNK_CHARS:
                chunks.append((section, buf.strip()))
                buf = ""
            buf += para + "\n\n"
        if buf.strip():
            chunks.append((section, buf.strip()))
    return chunks


def ingest_policies() -> int:
    rows = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        for section, content in split_markdown(path.read_text(encoding="utf-8")):
            rows.append((path.name, section, content))
    # Embed cả tiêu đề mục + nội dung: câu hỏi "hoàn tiền thế nào" khớp tốt hơn với heading "Hoàn học phí"
    vectors = get_embeddings().embed_documents([f"{s}\n{c}" for _, s, c in rows])
    with app_pool().connection() as conn, conn.transaction():
        conn.execute("TRUNCATE policy_chunks RESTART IDENTITY")
        for (source, section, content), vec in zip(rows, vectors, strict=True):
            conn.execute(
                "INSERT INTO policy_chunks (source, section, content, embedding) VALUES (%s, %s, %s, %s)",
                (source, section, content, np.array(vec, dtype=np.float32)),
            )
    log.info("policy_chunks: %d đoạn từ %d tài liệu", len(rows), len(list(POLICY_DIR.glob("*.md"))))
    return len(rows)


def ingest_seed_sql_examples() -> int:
    """Ví dụ SQL mẫu do người viết sẵn. Ví dụ học từ feedback (source='feedback') được GIỮ NGUYÊN."""
    examples = json.loads(SQL_EXAMPLES_FILE.read_text(encoding="utf-8"))
    vectors = get_embeddings().embed_documents([e["question"] for e in examples])
    with app_pool().connection() as conn, conn.transaction():
        conn.execute("DELETE FROM sql_examples WHERE source = 'seed'")
        for e, vec in zip(examples, vectors, strict=True):
            conn.execute(
                """INSERT INTO sql_examples (question, sql_text, source, created_by, embedding)
                   VALUES (%s, %s, 'seed', 'system', %s) ON CONFLICT (question) DO NOTHING""",
                (e["question"], e["sql"], np.array(vec, dtype=np.float32)),
            )
    log.info("sql_examples (seed): %d ví dụ", len(examples))
    return len(examples)


def ingest_all() -> None:
    ingest_policies()
    ingest_seed_sql_examples()
