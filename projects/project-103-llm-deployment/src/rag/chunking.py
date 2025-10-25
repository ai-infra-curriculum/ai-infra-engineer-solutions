"""
Document chunking strategies for RAG

Implements various chunking methods:
- Fixed size with overlap
- Sentence-based
- Semantic chunking
"""

import logging
from typing import List, Optional
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Text chunk with metadata"""

    text: str
    start_idx: int
    end_idx: int
    doc_id: str
    chunk_id: int
    metadata: dict


class TextChunker:
    """
    Text chunker with multiple strategies
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separator: str = "\n\n",
    ):
        """
        Initialize chunker

        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
            separator: Separator for splitting
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator

        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

    def chunk_text(
        self, text: str, doc_id: str, metadata: Optional[dict] = None
    ) -> List[Chunk]:
        """
        Chunk text with overlap

        Args:
            text: Text to chunk
            doc_id: Document identifier
            metadata: Additional metadata

        Returns:
            List of chunks
        """
        if not text:
            return []

        metadata = metadata or {}
        chunks = []
        start = 0
        chunk_id = 0

        while start < len(text):
            end = start + self.chunk_size

            # If not the last chunk, try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings in the last 100 characters
                search_start = max(end - 100, start)
                search_text = text[search_start:end]

                # Find last sentence ending
                matches = list(re.finditer(r'[.!?]\s+', search_text))
                if matches:
                    last_match = matches[-1]
                    end = search_start + last_match.end()

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunk = Chunk(
                    text=chunk_text,
                    start_idx=start,
                    end_idx=end,
                    doc_id=doc_id,
                    chunk_id=chunk_id,
                    metadata=metadata.copy(),
                )
                chunks.append(chunk)
                chunk_id += 1

            # Move start forward, accounting for overlap
            start = end - self.chunk_overlap

            # Ensure we make progress
            if start <= chunks[-1].start_idx if chunks else 0:
                start = end

        logger.debug(f"Created {len(chunks)} chunks from document {doc_id}")
        return chunks

    def chunk_by_sentences(
        self,
        text: str,
        doc_id: str,
        sentences_per_chunk: int = 5,
        metadata: Optional[dict] = None,
    ) -> List[Chunk]:
        """
        Chunk text by sentences

        Args:
            text: Text to chunk
            doc_id: Document identifier
            sentences_per_chunk: Number of sentences per chunk
            metadata: Additional metadata

        Returns:
            List of chunks
        """
        if not text:
            return []

        metadata = metadata or {}

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        chunk_id = 0

        for i in range(0, len(sentences), sentences_per_chunk):
            chunk_sentences = sentences[i : i + sentences_per_chunk]
            chunk_text = " ".join(chunk_sentences)

            # Find position in original text
            start_idx = text.find(chunk_sentences[0])
            end_idx = start_idx + len(chunk_text)

            chunk = Chunk(
                text=chunk_text,
                start_idx=start_idx if start_idx >= 0 else 0,
                end_idx=end_idx,
                doc_id=doc_id,
                chunk_id=chunk_id,
                metadata=metadata.copy(),
            )
            chunks.append(chunk)
            chunk_id += 1

        logger.debug(
            f"Created {len(chunks)} sentence-based chunks from document {doc_id}"
        )
        return chunks

    def chunk_by_separator(
        self,
        text: str,
        doc_id: str,
        separator: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> List[Chunk]:
        """
        Chunk text by separator (e.g., paragraphs)

        Args:
            text: Text to chunk
            doc_id: Document identifier
            separator: Separator pattern (uses default if None)
            metadata: Additional metadata

        Returns:
            List of chunks
        """
        if not text:
            return []

        separator = separator or self.separator
        metadata = metadata or {}

        # Split by separator
        sections = text.split(separator)
        sections = [s.strip() for s in sections if s.strip()]

        chunks = []
        chunk_id = 0
        current_pos = 0

        for section in sections:
            # Find position in original text
            start_idx = text.find(section, current_pos)
            end_idx = start_idx + len(section)

            chunk = Chunk(
                text=section,
                start_idx=start_idx if start_idx >= 0 else current_pos,
                end_idx=end_idx,
                doc_id=doc_id,
                chunk_id=chunk_id,
                metadata=metadata.copy(),
            )
            chunks.append(chunk)
            chunk_id += 1
            current_pos = end_idx

        logger.debug(
            f"Created {len(chunks)} separator-based chunks from document {doc_id}"
        )
        return chunks

    def chunk_with_context(
        self,
        text: str,
        doc_id: str,
        context_sentences: int = 1,
        metadata: Optional[dict] = None,
    ) -> List[Chunk]:
        """
        Chunk text with surrounding context

        Args:
            text: Text to chunk
            doc_id: Document identifier
            context_sentences: Number of context sentences before/after
            metadata: Additional metadata

        Returns:
            List of chunks with context
        """
        # First chunk by sentences
        sentence_chunks = self.chunk_by_sentences(
            text, doc_id, sentences_per_chunk=1, metadata=metadata
        )

        chunks = []
        chunk_id = 0

        for i, chunk in enumerate(sentence_chunks):
            # Get context
            context_before = []
            context_after = []

            for j in range(1, context_sentences + 1):
                if i - j >= 0:
                    context_before.insert(0, sentence_chunks[i - j].text)
                if i + j < len(sentence_chunks):
                    context_after.append(sentence_chunks[i + j].text)

            # Combine with context
            chunk_text = " ".join(
                context_before + [chunk.text] + context_after
            )

            new_chunk = Chunk(
                text=chunk_text,
                start_idx=chunk.start_idx,
                end_idx=chunk.end_idx,
                doc_id=doc_id,
                chunk_id=chunk_id,
                metadata={
                    **metadata,
                    "context_sentences": context_sentences,
                    "main_sentence": chunk.text,
                },
            )
            chunks.append(new_chunk)
            chunk_id += 1

        logger.debug(
            f"Created {len(chunks)} context-aware chunks from document {doc_id}"
        )
        return chunks


class TokenBasedChunker:
    """
    Chunk text based on token count instead of characters
    """

    def __init__(
        self,
        tokenizer,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        """
        Initialize token-based chunker

        Args:
            tokenizer: Tokenizer to use for counting tokens
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
        """
        self.tokenizer = tokenizer
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(
        self, text: str, doc_id: str, metadata: Optional[dict] = None
    ) -> List[Chunk]:
        """
        Chunk text by token count

        Args:
            text: Text to chunk
            doc_id: Document identifier
            metadata: Additional metadata

        Returns:
            List of chunks
        """
        if not text:
            return []

        metadata = metadata or {}

        # Tokenize entire text
        tokens = self.tokenizer.encode(text)
        chunks = []
        chunk_id = 0

        start_token = 0
        while start_token < len(tokens):
            end_token = start_token + self.chunk_size

            # Get chunk tokens
            chunk_tokens = tokens[start_token:end_token]

            # Decode back to text
            chunk_text = self.tokenizer.decode(
                chunk_tokens, skip_special_tokens=True
            )

            chunk = Chunk(
                text=chunk_text,
                start_idx=start_token,
                end_idx=end_token,
                doc_id=doc_id,
                chunk_id=chunk_id,
                metadata={
                    **metadata,
                    "token_count": len(chunk_tokens),
                },
            )
            chunks.append(chunk)
            chunk_id += 1

            # Move forward with overlap
            start_token = end_token - self.chunk_overlap

        logger.debug(
            f"Created {len(chunks)} token-based chunks from document {doc_id}"
        )
        return chunks
