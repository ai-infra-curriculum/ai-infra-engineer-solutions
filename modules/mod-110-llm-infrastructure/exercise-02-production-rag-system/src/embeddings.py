"""
Embeddings + Document Chunking

Text-to-vector embedding interface (Embedder Protocol) with a
deterministic in-process implementation (HashingEmbedder) suitable
for tests, CI, and curriculum demos that should not depend on a
GPU runtime or sentence-transformers downloads.

Also ships the document-chunking helpers used by the RAG pipeline:
token-windowed chunking with configurable overlap, sentence-boundary
preferential splitting, and metadata-preserving Chunk records.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Protocol


# -- Document + Chunk types ---------------------------------------------


@dataclass(frozen=True)
class Document:
    """One source document fed into the ingestion pipeline."""

    doc_id: str
    text: str
    source: str = ""  # e.g., 'pdf', 'html', 'markdown'
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class Chunk:
    """A chunk + its embedding."""

    chunk_id: str
    doc_id: str
    text: str
    start_offset: int  # within source doc
    end_offset: int
    embedding: List[float] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return self.end_offset - self.start_offset


# -- Embedder protocol --------------------------------------------------


class Embedder(Protocol):
    """Convert text → fixed-dimension vector."""

    dimension: int

    def embed(self, text: str) -> List[float]: ...

    def embed_batch(self, texts: List[str]) -> List[List[float]]: ...


class HashingEmbedder:
    """
    Deterministic hashing-based embedder.

    Hashes word bigrams + unigrams into the embedding vector via a
    feature-hashing trick (similar to scikit-learn's HashingVectorizer)
    and L2-normalises the result. Embedding similarity for related
    text is reliably positive; unrelated text gets near-zero cosine
    similarity.

    This is intentionally cheap + reproducible so the curriculum
    solution's tests and CLI demos run identically everywhere without
    requiring sentence-transformers + a model download.
    """

    def __init__(self, *, dimension: int = 64, ngram_range: tuple[int, int] = (1, 2)):
        if dimension < 8:
            raise ValueError("dimension must be >= 8")
        self.dimension = dimension
        self.ngram_range = ngram_range

    def embed(self, text: str) -> List[float]:
        tokens = _tokenize(text)
        if not tokens:
            return [0.0] * self.dimension
        vec = [0.0] * self.dimension
        for low, high in [self.ngram_range]:
            for n in range(low, high + 1):
                for i in range(len(tokens) - n + 1):
                    ngram = " ".join(tokens[i:i + n])
                    idx, sign = _feature_index(ngram, self.dimension)
                    vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            return vec
        return [x / norm for x in vec]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


def _tokenize(text: str) -> List[str]:
    text = text.lower()
    return re.findall(r"[a-z0-9]+", text)


def _feature_index(ngram: str, dimension: int) -> tuple[int, int]:
    h = int(hashlib.sha256(ngram.encode()).hexdigest(), 16)
    sign = 1 if (h & 1) == 0 else -1
    idx = (h >> 1) % dimension
    return idx, sign


# -- Distance / similarity helpers -------------------------------------


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# -- Chunking -----------------------------------------------------------


_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class ChunkingConfig:
    """Tuning knobs for chunking."""

    chunk_size: int = 256  # characters
    chunk_overlap: int = 32
    respect_sentence_boundaries: bool = True


def chunk_document(
    document: Document,
    config: Optional[ChunkingConfig] = None,
) -> List[Chunk]:
    """Split a Document into Chunks with overlap + sentence boundaries."""
    config = config or ChunkingConfig()
    text = document.text
    if not text:
        return []
    if config.chunk_overlap >= config.chunk_size:
        raise ValueError("chunk_overlap must be < chunk_size")

    chunks: List[Chunk] = []
    step = config.chunk_size - config.chunk_overlap
    pos = 0
    chunk_index = 0
    while pos < len(text):
        end = min(len(text), pos + config.chunk_size)
        if config.respect_sentence_boundaries and end < len(text):
            # Try to extend or shorten to a sentence boundary near `end`.
            window = text[pos:end]
            match = list(_SENTENCE_END_RE.finditer(window))
            if match:
                # Snap to last sentence-end inside the window.
                end = pos + match[-1].end()
        chunk_text = text[pos:end].strip()
        if chunk_text:
            chunks.append(Chunk(
                chunk_id=f"{document.doc_id}-c{chunk_index:04d}",
                doc_id=document.doc_id,
                text=chunk_text,
                start_offset=pos,
                end_offset=end,
                metadata=dict(document.metadata),
            ))
            chunk_index += 1
        if end <= pos:
            # Safety net for pathological text.
            pos = end + 1
        else:
            pos += max(step, 1)
            if config.respect_sentence_boundaries:
                # Always advance from the chosen end boundary instead of
                # plain step when the sentence-aware end shortened us.
                pos = max(pos, end - config.chunk_overlap)
    return chunks


def embed_chunks(chunks: List[Chunk], embedder: Embedder) -> List[Chunk]:
    """Compute embeddings for a chunk list in batch and return the same list."""
    texts = [c.text for c in chunks]
    vectors = embedder.embed_batch(texts)
    for chunk, vec in zip(chunks, vectors):
        chunk.embedding = vec
    return chunks
