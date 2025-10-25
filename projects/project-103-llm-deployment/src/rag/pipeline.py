"""
RAG Pipeline orchestration

Combines retrieval, context augmentation, and LLM generation
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .embeddings import EmbeddingModel
from .retriever import VectorRetriever, RetrievalResult
from .chunking import TextChunker, Chunk

logger = logging.getLogger(__name__)


@dataclass
class RAGConfig:
    """Configuration for RAG pipeline"""

    top_k: int = 5  # Number of chunks to retrieve
    chunk_size: int = 512  # Chunk size for document processing
    chunk_overlap: int = 50  # Overlap between chunks
    min_similarity_score: float = 0.5  # Minimum similarity threshold
    max_context_length: int = 2048  # Maximum context length in tokens
    rerank: bool = False  # Enable reranking (if available)


@dataclass
class RAGResponse:
    """Response from RAG pipeline"""

    answer: str
    retrieved_chunks: List[RetrievalResult]
    context_used: str
    prompt: str
    metadata: Dict[str, Any]


class RAGPipeline:
    """
    Complete RAG pipeline
    """

    def __init__(
        self,
        embedding_model: EmbeddingModel,
        retriever: VectorRetriever,
        config: Optional[RAGConfig] = None,
    ):
        """
        Initialize RAG pipeline

        Args:
            embedding_model: Model for generating embeddings
            retriever: Vector retriever
            config: Pipeline configuration
        """
        self.embedding_model = embedding_model
        self.retriever = retriever
        self.config = config or RAGConfig()

        logger.info("RAG pipeline initialized")

    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        text_key: str = "text",
        id_key: str = "id",
        show_progress: bool = False,
    ) -> int:
        """
        Add documents to the vector store

        Args:
            documents: List of documents (dicts with text and metadata)
            text_key: Key for text content
            id_key: Key for document ID
            show_progress: Show progress bar

        Returns:
            Number of chunks added
        """
        logger.info(f"Adding {len(documents)} documents to vector store")

        chunker = TextChunker(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )

        all_chunks = []
        all_embeddings = []
        all_metadatas = []
        all_ids = []

        # Process each document
        for doc in documents:
            text = doc.get(text_key, "")
            doc_id = doc.get(id_key, f"doc_{len(all_chunks)}")

            if not text:
                continue

            # Extract metadata (everything except text and id)
            metadata = {
                k: v for k, v in doc.items() if k not in [text_key, id_key]
            }
            metadata["doc_id"] = doc_id

            # Chunk document
            chunks = chunker.chunk_text(text, doc_id, metadata)

            # Generate embeddings for chunks
            chunk_texts = [chunk.text for chunk in chunks]
            if chunk_texts:
                embeddings = self.embedding_model.encode(
                    chunk_texts, show_progress=show_progress
                )

                # Store chunks
                for i, chunk in enumerate(chunks):
                    all_chunks.append(chunk.text)
                    all_embeddings.append(embeddings[i])
                    all_metadatas.append(chunk.metadata)
                    all_ids.append(f"{doc_id}_chunk_{chunk.chunk_id}")

        # Add to vector store
        if all_chunks:
            import numpy as np

            embeddings_array = np.array(all_embeddings)
            self.retriever.add_texts(
                texts=all_chunks,
                embeddings=embeddings_array,
                metadatas=all_metadatas,
                ids=all_ids,
            )

        logger.info(f"Added {len(all_chunks)} chunks from {len(documents)} documents")
        return len(all_chunks)

    def retrieve(
        self, query: str, top_k: Optional[int] = None
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant chunks for query

        Args:
            query: Query text
            top_k: Number of results (uses config default if None)

        Returns:
            List of retrieval results
        """
        top_k = top_k or self.config.top_k

        # Generate query embedding
        query_embedding = self.embedding_model.encode_single(query)

        # Retrieve similar chunks
        results = self.retriever.search(query_embedding, top_k=top_k)

        # Filter by similarity threshold
        filtered_results = [
            r for r in results if r.score >= self.config.min_similarity_score
        ]

        logger.debug(
            f"Retrieved {len(filtered_results)} chunks (filtered from {len(results)})"
        )

        return filtered_results

    def build_context(
        self, retrieved_chunks: List[RetrievalResult], max_length: Optional[int] = None
    ) -> str:
        """
        Build context from retrieved chunks

        Args:
            retrieved_chunks: Retrieved chunks
            max_length: Maximum context length (uses config if None)

        Returns:
            Context string
        """
        max_length = max_length or self.config.max_context_length

        # Sort by score (highest first)
        sorted_chunks = sorted(retrieved_chunks, key=lambda x: x.score, reverse=True)

        # Build context
        context_parts = []
        current_length = 0

        for chunk in sorted_chunks:
            chunk_length = len(chunk.text)

            if current_length + chunk_length > max_length:
                # Try to fit partial chunk
                remaining = max_length - current_length
                if remaining > 100:  # Only add if meaningful amount remains
                    context_parts.append(chunk.text[:remaining] + "...")
                break

            context_parts.append(chunk.text)
            current_length += chunk_length

        context = "\n\n".join(context_parts)
        logger.debug(f"Built context with {len(context_parts)} chunks ({current_length} chars)")

        return context

    def create_rag_prompt(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Create RAG prompt with context

        Args:
            query: User query
            context: Retrieved context
            system_prompt: Optional system prompt

        Returns:
            Complete prompt
        """
        if system_prompt is None:
            system_prompt = (
                "You are a helpful assistant. Answer the question based on the provided context. "
                "If the answer cannot be found in the context, say so."
            )

        # Format prompt
        prompt = f"""{system_prompt}

Context:
{context}

Question: {query}

Answer:"""

        return prompt

    async def generate_answer(
        self,
        query: str,
        llm_server,
        system_prompt: Optional[str] = None,
        top_k: Optional[int] = None,
        **generation_kwargs,
    ) -> RAGResponse:
        """
        Generate answer using RAG

        Args:
            query: User query
            llm_server: LLM server instance
            system_prompt: Optional system prompt
            top_k: Number of chunks to retrieve
            **generation_kwargs: Additional generation parameters

        Returns:
            RAG response with answer and metadata
        """
        # Retrieve relevant chunks
        retrieved_chunks = self.retrieve(query, top_k=top_k)

        if not retrieved_chunks:
            logger.warning("No relevant chunks retrieved")
            # Generate without context
            context = "No relevant information found."
        else:
            # Build context from chunks
            context = self.build_context(retrieved_chunks)

        # Create RAG prompt
        prompt = self.create_rag_prompt(query, context, system_prompt)

        # Import here to avoid circular dependency
        from ..llm import GenerationRequest

        # Generate answer
        request = GenerationRequest(
            prompt=prompt,
            **generation_kwargs,
        )

        response = await llm_server.generate(request)

        # Create RAG response
        rag_response = RAGResponse(
            answer=response.text,
            retrieved_chunks=retrieved_chunks,
            context_used=context,
            prompt=prompt,
            metadata={
                "query": query,
                "num_chunks_retrieved": len(retrieved_chunks),
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "total_tokens": response.total_tokens,
                "model": response.model,
            },
        )

        return rag_response

    def get_pipeline_info(self) -> Dict[str, Any]:
        """Get pipeline information"""
        return {
            "embedding_model": self.embedding_model.get_model_info(),
            "retriever": self.retriever.get_collection_info(),
            "config": {
                "top_k": self.config.top_k,
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap,
                "min_similarity_score": self.config.min_similarity_score,
                "max_context_length": self.config.max_context_length,
            },
        }
