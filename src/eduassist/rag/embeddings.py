"""Embedding chạy local bằng FastEmbed: miễn phí, không gửi dữ liệu ra ngoài."""

from functools import lru_cache

from langchain_core.embeddings import Embeddings

from eduassist.config import get_settings

DIM = 384  # khớp với vector(384) trong sql/schema.sql


class LocalEmbeddings(Embeddings):
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self.model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@lru_cache
def get_embeddings() -> LocalEmbeddings:
    return LocalEmbeddings(get_settings().embedding_model)
