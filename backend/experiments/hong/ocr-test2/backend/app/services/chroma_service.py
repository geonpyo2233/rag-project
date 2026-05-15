from __future__ import annotations

import re
from uuid import uuid4

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import settings


class ChromaService:
    def __init__(self) -> None:
        """임베딩 모델과 Chroma 컬렉션을 초기화한다."""
        self.client = chromadb.PersistentClient(path=settings.chroma_dir)
        self.embedder = SentenceTransformer(settings.embedding_model_name)
        sample_dim = len(self.embedder.encode("차원 확인", normalize_embeddings=True).tolist())
        self.raw_collection_name = f"raw_documents_{sample_dim}"
        self.summary_collection_name = f"summary_documents_{sample_dim}"
        self.raw_collection = self.client.get_or_create_collection(name=self.raw_collection_name)
        self.summary_collection = self.client.get_or_create_collection(name=self.summary_collection_name)

    def save_raw(self, filename: str, raw_text: str, ocr_text: str, merged_text: str) -> str:
        """원문(병합 텍스트)을 벡터와 함께 저장한다."""
        doc_id = str(uuid4())
        embedding = self._embed_document(merged_text)
        self.raw_collection.add(
            ids=[doc_id],
            documents=[merged_text],
            embeddings=[embedding],
            metadatas=[
                {
                    "filename": filename,
                    "raw_text": raw_text,
                    "ocr_text": ocr_text,
                }
            ],
        )
        return doc_id

    def save_summary(self, source_id: str, filename: str, summary: str, category: str) -> str:
        """요약/카테고리 결과를 벡터와 함께 저장한다."""
        summary_id = str(uuid4())
        embedding = self._embed_document(summary)
        self.summary_collection.add(
            ids=[summary_id],
            documents=[summary],
            embeddings=[embedding],
            metadatas=[{"source_id": source_id, "filename": filename, "category": category}],
        )
        return summary_id

    def search_raw(self, query: str, limit: int = 5) -> dict:
        """질의 벡터 기반 유사 문서 검색."""
        query_embedding = self._embed_query(query)
        try:
            return self.raw_collection.query(
                query_embeddings=[query_embedding],
                n_results=max(1, limit),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            if "dimension" in str(exc).lower():
                self._rebind_collections_by_query_dim(len(query_embedding))
                return self.raw_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=max(1, limit),
                    include=["documents", "metadatas", "distances"],
                )
            raise

    def _embed_document(self, text: str) -> list[float]:
        return self.embedder.encode(self._with_doc_prefix(text), normalize_embeddings=True).tolist()

    def _embed_query(self, text: str) -> list[float]:
        return self.embedder.encode(self._with_query_prefix(text), normalize_embeddings=True).tolist()

    def _with_doc_prefix(self, text: str) -> str:
        mode = settings.embedding_prefix_mode.lower()
        if mode == "e5":
            return f"passage: {text}"
        return text

    def _with_query_prefix(self, text: str) -> str:
        mode = settings.embedding_prefix_mode.lower()
        if mode == "e5":
            return f"query: {text}"
        if mode == "bge":
            return f"Represent this sentence for searching relevant passages: {text}"
        return text

    def _rebind_collections_by_query_dim(self, dim: int) -> None:
        self.raw_collection_name = f"raw_documents_{dim}"
        self.summary_collection_name = f"summary_documents_{dim}"
        self.raw_collection = self.client.get_or_create_collection(name=self.raw_collection_name)
        self.summary_collection = self.client.get_or_create_collection(name=self.summary_collection_name)
