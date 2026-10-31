"""Truy vấn trên pgvector: tài liệu chính sách (hybrid search) và kho ví dụ SQL (few-shot động)."""

import re

import numpy as np

from eduassist.db import app_pool
from eduassist.rag.embeddings import get_embeddings

# Hư từ tiếng Việt hay gặp trong câu hỏi - bỏ đi để tìm từ khoá không bị nhiễu
_STOPWORDS_TEXT = """
có không được là của và thì mà cho tôi em mình bạn ạ à nhé
nhỉ gì nào bao nhiêu thế sao như này với các những một khi nếu ở
trong ra vào lên muốn hỏi cần xin vậy đó kia ai làm bị đã sẽ
đang rồi
"""
STOPWORDS = frozenset(_STOPWORDS_TEXT.split())
RRF_K = 60  # hằng số chuẩn của Reciprocal Rank Fusion


def _vec(text: str) -> np.ndarray:
    return np.array(get_embeddings().embed_query(text), dtype=np.float32)


def keyword_query(text: str) -> str:
    """'Có cho trả góp không?' -> 'trả | góp'  (tsquery OR, chỉ giữ chữ/số để không lỗi cú pháp)."""
    words = [w for w in re.findall(r"\w+", text.lower()) if w not in STOPWORDS and len(w) > 1]
    return " | ".join(dict.fromkeys(words))


def search_policies(query: str, k: int = 4) -> list[dict]:
    """Hybrid search: gộp xếp hạng theo vector (ngữ nghĩa) và full-text (từ khoá) bằng RRF.

    Model embedding nhỏ đôi khi bỏ lỡ từ khoá quan trọng ("trả góp"); full-text bù lại.
    Ngược lại vector bắt được câu hỏi diễn đạt khác hẳn tài liệu ("nghỉ giữa chừng có lấy lại tiền").
    """
    kw = keyword_query(query)
    with app_pool().connection() as conn:
        return conn.execute(
            f"""
            WITH v AS (
                SELECT id, row_number() OVER (ORDER BY embedding <=> %(vec)s) AS r
                FROM policy_chunks ORDER BY embedding <=> %(vec)s LIMIT 10
            ), kw AS (
                SELECT id, row_number() OVER (ORDER BY ts_rank(tsv, q) DESC) AS r
                FROM policy_chunks, to_tsquery('simple', %(kw)s) q
                WHERE %(kw)s <> '' AND tsv @@ q
                ORDER BY ts_rank(tsv, q) DESC LIMIT 10
            )
            SELECT p.source, p.section, p.content,
                   coalesce(1.0 / ({RRF_K} + v.r), 0) + coalesce(1.0 / ({RRF_K} + kw.r), 0) AS score
            FROM policy_chunks p
            LEFT JOIN v ON v.id = p.id
            LEFT JOIN kw ON kw.id = p.id
            WHERE v.id IS NOT NULL OR kw.id IS NOT NULL
            ORDER BY score DESC LIMIT %(k)s
            """,
            {"vec": _vec(query), "kw": kw, "k": k},
        ).fetchall()


def similar_sql_examples(question: str, k: int = 3) -> list[dict]:
    with app_pool().connection() as conn:
        return conn.execute(
            """SELECT question, sql_text, embedding <=> %s AS distance
               FROM sql_examples ORDER BY distance LIMIT %s""",
            (_vec(question), k),
        ).fetchall()


def add_sql_example(question: str, sql_text: str, source: str, created_by: str) -> bool:
    """Thêm ví dụ vào kho few-shot. Trả về False nếu câu hỏi đã có."""
    with app_pool().connection() as conn:
        cur = conn.execute(
            """INSERT INTO sql_examples (question, sql_text, source, created_by, embedding)
               VALUES (%s, %s, %s, %s, %s) ON CONFLICT (question) DO NOTHING""",
            (question, sql_text, source, created_by, _vec(question)),
        )
        return cur.rowcount == 1
