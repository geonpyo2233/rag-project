from __future__ import annotations

import re
from uuid import uuid4

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import settings


class ChromaService:
    def __init__(self) -> None:
        """?꾨쿋??紐⑤뜽怨?Chroma 而щ젆?섏쓣 珥덇린?뷀븳??"""
        self.client = chromadb.PersistentClient(path=settings.chroma_dir)
        self.embedder = SentenceTransformer(settings.embedding_model_name)
        sample_dim = len(self.embedder.encode("李⑥썝 ?뺤씤", normalize_embeddings=True).tolist())
        self.raw_collection_name = f"raw_documents_{sample_dim}"
        self.summary_collection_name = f"summary_documents_{sample_dim}"
        self.raw_collection = self.client.get_or_create_collection(name=self.raw_collection_name)
        self.summary_collection = self.client.get_or_create_collection(name=self.summary_collection_name)

    def save_raw(self, filename: str, raw_text: str, ocr_text: str, merged_text: str) -> str:
        """?먮Ц(蹂묓빀 ?띿뒪????臾몄옣 ?⑥쐞濡?泥?궧?섏뿬 ??ν븳??"""
        source_id = str(uuid4())

        chunks = self._split_sentences(merged_text)
        if not chunks:
            chunks = [merged_text.strip()] if merged_text.strip() else [""]

        ids = [str(uuid4()) for _ in chunks]
        embeddings = [self._embed_document(chunk) for chunk in chunks]
        metadatas = [
            {
                "source_id": source_id,
                "filename": filename,
                "raw_text": raw_text,
                "ocr_text": ocr_text,
                "chunk_type": "sentence",
                "chunk_index": idx,
            }
            for idx, _ in enumerate(chunks)
        ]

        self.raw_collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return source_id

    def save_summary(self, source_id: str, filename: str, summary: str, category: str, main_category: str = "기타", sub_category: str = "미상", confidence: float = 0.0, category_reason: str = "") -> str:
        """?붿빟/移댄뀒怨좊━ 寃곌낵瑜?踰≫꽣濡?蹂?섑빐 ??ν븳??"""
        summary_id = str(uuid4())
        embedding = self._embed_document(summary)
        self.summary_collection.add(
            ids=[summary_id],
            documents=[summary],
            embeddings=[embedding],
            metadatas=[{"source_id": source_id, "filename": filename, "category": category, "main_category": main_category, "sub_category": sub_category, "confidence": confidence, "category_reason": category_reason}],
        )
        return summary_id

    def search_raw(self, query: str, limit: int = 5) -> dict:
        """吏덉쓽 踰≫꽣 湲곕컲 ?좎궗 臾몄꽌 寃??"""
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

    def _split_sentences(self, text: str) -> list[str]:
        """媛꾨떒 洹쒖튃 湲곕컲 臾몄옣 遺꾨━."""
        if not text:
            return []
        parts = re.split(r"(?<=[.!?])\s+|\n+", text)
        sentences = [p.strip() for p in parts if p and p.strip()]
        return [s for s in sentences if len(s) >= 5]

