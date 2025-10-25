"""
Embedding generation for RAG system

Supports multiple embedding models and batch processing
"""

import logging
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import torch

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """
    Embedding model for generating vector representations of text
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: Optional[str] = None,
        batch_size: int = 32,
    ):
        """
        Initialize embedding model

        Args:
            model_name: Name of sentence-transformers model
            device: Device to run on (cuda/cpu), auto-detected if None
            batch_size: Batch size for encoding
        """
        self.model_name = model_name
        self.batch_size = batch_size

        # Auto-detect device
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        logger.info(f"Loading embedding model: {model_name} on {device}")

        try:
            self.model = SentenceTransformer(model_name, device=device)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(
                f"Embedding model loaded. Dimension: {self.embedding_dim}"
            )
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def encode(
        self,
        texts: List[str],
        show_progress: bool = False,
        normalize: bool = True,
    ) -> np.ndarray:
        """
        Encode texts to embeddings

        Args:
            texts: List of texts to encode
            show_progress: Show progress bar
            normalize: Normalize embeddings to unit length

        Returns:
            Array of embeddings (num_texts, embedding_dim)
        """
        if not texts:
            return np.array([])

        try:
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=show_progress,
                normalize_embeddings=normalize,
                convert_to_numpy=True,
            )

            return embeddings

        except Exception as e:
            logger.error(f"Failed to encode texts: {e}")
            raise

    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """
        Encode single text to embedding

        Args:
            text: Text to encode
            normalize: Normalize embedding to unit length

        Returns:
            Embedding vector
        """
        embeddings = self.encode([text], normalize=normalize)
        return embeddings[0]

    def encode_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Encode texts in batches

        Args:
            texts: List of texts to encode
            batch_size: Batch size (uses default if None)
            show_progress: Show progress bar

        Returns:
            Array of embeddings
        """
        batch_size = batch_size or self.batch_size
        return self.encode(texts, show_progress=show_progress)

    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Cosine similarity score (0-1)
        """
        # Normalize if not already
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 > 0:
            embedding1 = embedding1 / norm1
        if norm2 > 0:
            embedding2 = embedding2 / norm2

        return float(np.dot(embedding1, embedding2))

    def get_model_info(self) -> dict:
        """Get model information"""
        return {
            "model_name": self.model_name,
            "embedding_dim": self.embedding_dim,
            "device": self.device,
            "batch_size": self.batch_size,
        }


# Predefined models
EMBEDDING_MODELS = {
    "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",  # 384 dim, fast
    "all-mpnet-base-v2": "sentence-transformers/all-mpnet-base-v2",  # 768 dim, better quality
    "e5-base-v2": "intfloat/e5-base-v2",  # 768 dim, good for retrieval
    "gte-base": "thenlper/gte-base",  # 768 dim, state-of-the-art
}


def get_embedding_model(
    model_key: str = "all-MiniLM-L6-v2", **kwargs
) -> EmbeddingModel:
    """
    Get embedding model by key

    Args:
        model_key: Key from EMBEDDING_MODELS
        **kwargs: Additional arguments for EmbeddingModel

    Returns:
        Initialized embedding model
    """
    if model_key not in EMBEDDING_MODELS:
        raise ValueError(
            f"Unknown model key: {model_key}. "
            f"Available: {list(EMBEDDING_MODELS.keys())}"
        )

    model_name = EMBEDDING_MODELS[model_key]
    return EmbeddingModel(model_name=model_name, **kwargs)
