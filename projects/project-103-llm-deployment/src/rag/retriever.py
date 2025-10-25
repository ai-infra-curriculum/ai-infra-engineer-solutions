"""
Vector database retriever for RAG

Supports multiple vector databases:
- ChromaDB (local, embedded)
- Pinecone (cloud, managed)
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import numpy as np

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("ChromaDB not available")

try:
    import pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    logging.warning("Pinecone not available")

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result from vector retrieval"""

    text: str
    score: float
    metadata: Dict[str, Any]
    chunk_id: str


class VectorRetriever:
    """
    Base class for vector retrievers
    """

    def add_texts(
        self,
        texts: List[str],
        embeddings: np.ndarray,
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """Add texts with embeddings to the vector store"""
        raise NotImplementedError

    def search(
        self, query_embedding: np.ndarray, top_k: int = 5
    ) -> List[RetrievalResult]:
        """Search for similar texts"""
        raise NotImplementedError

    def delete_collection(self):
        """Delete the collection"""
        raise NotImplementedError


class ChromaDBRetriever(VectorRetriever):
    """
    ChromaDB-based retriever (local, embedded)
    """

    def __init__(
        self,
        collection_name: str = "rag_documents",
        persist_directory: str = "./chroma_db",
        embedding_function: Optional[Any] = None,
    ):
        """
        Initialize ChromaDB retriever

        Args:
            collection_name: Name of the collection
            persist_directory: Directory to persist data
            embedding_function: Optional embedding function
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB not available. Install with: pip install chromadb")

        self.collection_name = collection_name
        self.persist_directory = persist_directory

        logger.info(f"Initializing ChromaDB at {persist_directory}")

        # Initialize client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},  # Use cosine similarity
        )

        logger.info(f"ChromaDB collection '{collection_name}' ready")

    def add_texts(
        self,
        texts: List[str],
        embeddings: np.ndarray,
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """
        Add texts with embeddings to ChromaDB

        Args:
            texts: List of texts
            embeddings: Array of embeddings
            metadatas: Optional metadata for each text
            ids: Optional IDs for each text
        """
        if not texts:
            return

        # Generate IDs if not provided
        if ids is None:
            existing_count = self.collection.count()
            ids = [f"doc_{existing_count + i}" for i in range(len(texts))]

        # Prepare metadata
        if metadatas is None:
            metadatas = [{} for _ in texts]

        # Convert embeddings to list
        embeddings_list = embeddings.tolist()

        # Add to collection
        self.collection.add(
            documents=texts,
            embeddings=embeddings_list,
            metadatas=metadatas,
            ids=ids,
        )

        logger.info(f"Added {len(texts)} documents to ChromaDB")

    def search(
        self, query_embedding: np.ndarray, top_k: int = 5
    ) -> List[RetrievalResult]:
        """
        Search for similar texts

        Args:
            query_embedding: Query embedding
            top_k: Number of results to return

        Returns:
            List of retrieval results
        """
        # Query collection
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
        )

        # Parse results
        retrieval_results = []

        if results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                result = RetrievalResult(
                    text=results["documents"][0][i],
                    score=1.0 - results["distances"][0][i],  # Convert distance to similarity
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    chunk_id=results["ids"][0][i],
                )
                retrieval_results.append(result)

        logger.debug(f"Retrieved {len(retrieval_results)} results")
        return retrieval_results

    def delete_collection(self):
        """Delete the collection"""
        try:
            self.client.delete_collection(name=self.collection_name)
            logger.info(f"Deleted collection '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")

    def get_collection_info(self) -> dict:
        """Get collection information"""
        count = self.collection.count()
        return {
            "name": self.collection_name,
            "count": count,
            "persist_directory": self.persist_directory,
        }


class PineconeRetriever(VectorRetriever):
    """
    Pinecone-based retriever (cloud, managed)
    """

    def __init__(
        self,
        api_key: str,
        environment: str,
        index_name: str = "rag-documents",
        dimension: int = 384,
        metric: str = "cosine",
        namespace: str = "default",
    ):
        """
        Initialize Pinecone retriever

        Args:
            api_key: Pinecone API key
            environment: Pinecone environment
            index_name: Name of the index
            dimension: Embedding dimension
            metric: Similarity metric (cosine, euclidean, dotproduct)
            namespace: Namespace for vectors
        """
        if not PINECONE_AVAILABLE:
            raise ImportError("Pinecone not available. Install with: pip install pinecone-client")

        self.index_name = index_name
        self.namespace = namespace
        self.dimension = dimension

        logger.info(f"Initializing Pinecone index '{index_name}'")

        # Initialize Pinecone
        pinecone.init(api_key=api_key, environment=environment)

        # Create index if it doesn't exist
        if index_name not in pinecone.list_indexes():
            pinecone.create_index(
                name=index_name,
                dimension=dimension,
                metric=metric,
            )
            logger.info(f"Created Pinecone index '{index_name}'")

        self.index = pinecone.Index(index_name)
        logger.info(f"Pinecone index '{index_name}' ready")

    def add_texts(
        self,
        texts: List[str],
        embeddings: np.ndarray,
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """
        Add texts with embeddings to Pinecone

        Args:
            texts: List of texts
            embeddings: Array of embeddings
            metadatas: Optional metadata for each text
            ids: Optional IDs for each text
        """
        if not texts:
            return

        # Generate IDs if not provided
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in texts]

        # Prepare metadata
        if metadatas is None:
            metadatas = [{} for _ in texts]

        # Add text to metadata
        for i, text in enumerate(texts):
            metadatas[i]["text"] = text

        # Prepare vectors for upsert
        vectors = [
            (ids[i], embeddings[i].tolist(), metadatas[i])
            for i in range(len(texts))
        ]

        # Upsert in batches
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            self.index.upsert(vectors=batch, namespace=self.namespace)

        logger.info(f"Added {len(texts)} documents to Pinecone")

    def search(
        self, query_embedding: np.ndarray, top_k: int = 5
    ) -> List[RetrievalResult]:
        """
        Search for similar texts

        Args:
            query_embedding: Query embedding
            top_k: Number of results to return

        Returns:
            List of retrieval results
        """
        # Query index
        results = self.index.query(
            vector=query_embedding.tolist(),
            top_k=top_k,
            namespace=self.namespace,
            include_metadata=True,
        )

        # Parse results
        retrieval_results = []

        for match in results.matches:
            text = match.metadata.get("text", "")
            metadata = {k: v for k, v in match.metadata.items() if k != "text"}

            result = RetrievalResult(
                text=text,
                score=match.score,
                metadata=metadata,
                chunk_id=match.id,
            )
            retrieval_results.append(result)

        logger.debug(f"Retrieved {len(retrieval_results)} results")
        return retrieval_results

    def delete_collection(self):
        """Delete the index"""
        try:
            pinecone.delete_index(self.index_name)
            logger.info(f"Deleted Pinecone index '{self.index_name}'")
        except Exception as e:
            logger.error(f"Failed to delete index: {e}")

    def get_collection_info(self) -> dict:
        """Get index information"""
        stats = self.index.describe_index_stats()
        return {
            "name": self.index_name,
            "dimension": self.dimension,
            "namespace": self.namespace,
            "total_vector_count": stats.total_vector_count,
        }


def create_retriever(
    backend: str = "chromadb", **kwargs
) -> VectorRetriever:
    """
    Create a retriever instance

    Args:
        backend: "chromadb" or "pinecone"
        **kwargs: Backend-specific arguments

    Returns:
        Retriever instance
    """
    if backend == "chromadb":
        return ChromaDBRetriever(**kwargs)
    elif backend == "pinecone":
        return PineconeRetriever(**kwargs)
    else:
        raise ValueError(f"Unknown backend: {backend}")
