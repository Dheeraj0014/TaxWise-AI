"""Domain ports (§2.2) — interfaces the domain depends on, implemented by
infrastructure adapters and bound at startup. Swapping OpenAI->Anthropic or
Qdrant->Pinecone touches only the adapter, never the domain.

These are Protocols so adapters need only structural conformance. The RAG /
agent / OCR features are out of the MVP slice; the ports fix their contracts so
those adapters can be dropped in without touching domain code.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMPort(Protocol):
    def complete(self, prompt: str, *, system: str | None = None) -> str: ...


@runtime_checkable
class EmbeddingPort(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class VectorStorePort(Protocol):
    def upsert(self, ids: list[str], vectors: list[list[float]],
               metadata: list[dict]) -> None: ...

    def search(self, vector: list[float], *, top_k: int = 5,
               filters: dict | None = None) -> list[dict]: ...


@runtime_checkable
class OCRPort(Protocol):
    def extract(self, document_bytes: bytes, *, content_type: str) -> dict: ...


@runtime_checkable
class ObjectStoragePort(Protocol):
    def put(self, key: str, data: bytes) -> str: ...

    def presigned_url(self, key: str, *, expires_s: int = 3600) -> str: ...
