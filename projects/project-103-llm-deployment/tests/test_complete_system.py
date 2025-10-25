"""
Comprehensive system tests for LLM deployment platform

Tests:
- LLM serving
- RAG pipeline
- API endpoints
- Document ingestion
- Monitoring and cost tracking
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
import numpy as np


# Test LLM Components
class TestLLMServing:
    """Test LLM serving functionality"""

    @pytest.mark.asyncio
    async def test_model_config_validation(self, mock_model_config):
        """Test model configuration validation"""
        mock_model_config.validate()
        assert mock_model_config.dtype in ["float16", "float32"]
        assert 0 < mock_model_config.gpu_memory_utilization <= 1.0

    @pytest.mark.asyncio
    async def test_model_initialization(self, mock_llm_server):
        """Test model initialization"""
        assert mock_llm_server.model is not None
        assert mock_llm_server.tokenizer is not None

    @pytest.mark.asyncio
    async def test_generation(self, mock_llm_server):
        """Test text generation"""
        from src.llm import GenerationRequest

        request = GenerationRequest(
            prompt="Hello, world!", max_tokens=10, temperature=0.7
        )

        response = await mock_llm_server.generate(request)

        assert response.text is not None
        assert len(response.text) > 0
        assert response.total_tokens > 0
        assert response.prompt_tokens > 0
        assert response.completion_tokens > 0

    @pytest.mark.asyncio
    async def test_health_check(self, mock_llm_server):
        """Test health check"""
        is_healthy = await mock_llm_server.health_check()
        assert is_healthy

    def test_model_info(self, mock_llm_server):
        """Test model info retrieval"""
        info = mock_llm_server.get_model_info()
        assert "model_name" in info
        assert "backend" in info
        assert "dtype" in info


# Test RAG Components
class TestRAGSystem:
    """Test RAG system components"""

    def test_embedding_generation(self, embedding_model):
        """Test embedding generation"""
        texts = ["Hello world", "Machine learning is great"]
        embeddings = embedding_model.encode(texts)

        assert embeddings.shape[0] == 2
        assert embeddings.shape[1] == embedding_model.embedding_dim

    def test_embedding_similarity(self, embedding_model):
        """Test embedding similarity calculation"""
        text1 = "Machine learning"
        text2 = "Deep learning"
        text3 = "Pizza recipe"

        emb1 = embedding_model.encode_single(text1)
        emb2 = embedding_model.encode_single(text2)
        emb3 = embedding_model.encode_single(text3)

        # Similar texts should have higher similarity
        sim_ml_dl = embedding_model.similarity(emb1, emb2)
        sim_ml_pizza = embedding_model.similarity(emb1, emb3)

        assert sim_ml_dl > sim_ml_pizza

    def test_text_chunking(self, sample_text):
        """Test text chunking"""
        from src.rag import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_text(sample_text, "test_doc")

        assert len(chunks) > 0
        assert all(chunk.doc_id == "test_doc" for chunk in chunks)
        assert all(len(chunk.text) > 0 for chunk in chunks)

    def test_vector_storage_retrieval(self, chroma_retriever, embedding_model):
        """Test vector storage and retrieval"""
        # Add some texts
        texts = [
            "Machine learning is awesome",
            "Deep learning uses neural networks",
            "Python is a programming language",
        ]

        embeddings = embedding_model.encode(texts)

        chroma_retriever.add_texts(
            texts=texts,
            embeddings=embeddings,
            ids=["doc1", "doc2", "doc3"],
        )

        # Query
        query = "What is machine learning?"
        query_embedding = embedding_model.encode_single(query)
        results = chroma_retriever.search(query_embedding, top_k=2)

        assert len(results) == 2
        assert results[0].score > 0
        # Should retrieve the ML-related text
        assert "machine learning" in results[0].text.lower()

    def test_rag_document_ingestion(self, rag_pipeline, sample_documents):
        """Test RAG document ingestion"""
        chunks_added = rag_pipeline.add_documents(sample_documents)

        assert chunks_added > 0
        assert chunks_added >= len(sample_documents)

    def test_rag_retrieval(self, rag_pipeline, sample_documents):
        """Test RAG retrieval"""
        # Add documents
        rag_pipeline.add_documents(sample_documents)

        # Retrieve
        query = "What is machine learning?"
        results = rag_pipeline.retrieve(query, top_k=2)

        assert len(results) > 0
        assert results[0].score > 0

    def test_rag_context_building(self, rag_pipeline, sample_documents):
        """Test RAG context building"""
        from src.rag import RetrievalResult

        # Create mock retrieval results
        results = [
            RetrievalResult(
                text="Machine learning is great",
                score=0.9,
                metadata={},
                chunk_id="chunk1",
            ),
            RetrievalResult(
                text="Deep learning is powerful",
                score=0.8,
                metadata={},
                chunk_id="chunk2",
            ),
        ]

        context = rag_pipeline.build_context(results)

        assert len(context) > 0
        assert "Machine learning" in context
        assert "Deep learning" in context


# Test Document Ingestion
class TestDocumentIngestion:
    """Test document ingestion components"""

    def test_text_loader(self, temp_dir):
        """Test text file loading"""
        from src.ingestion import TextLoader
        from pathlib import Path

        # Create a test file
        test_file = Path(temp_dir) / "test.txt"
        test_content = "This is a test document."
        with open(test_file, "w") as f:
            f.write(test_content)

        # Load
        loader = TextLoader()
        documents = loader.load(str(test_file))

        assert len(documents) == 1
        assert documents[0].text == test_content

    def test_markdown_loader(self, sample_markdown_path):
        """Test Markdown file loading"""
        from src.ingestion import MarkdownLoader

        loader = MarkdownLoader()
        documents = loader.load(sample_markdown_path)

        assert len(documents) == 1
        assert "# Sample Document" in documents[0].text

    def test_document_processor(self):
        """Test document processing"""
        from src.ingestion import DocumentProcessor, Document

        processor = DocumentProcessor(
            remove_extra_whitespace=True, min_length=5
        )

        doc = Document(
            text="This   is   a   test.     \n\n\n\nWith extra whitespace.",
            doc_id="test",
        )

        processed = processor.process(doc)

        assert processed is not None
        assert "  " not in processed.text  # Extra spaces removed
        assert "\n\n\n" not in processed.text

    def test_document_deduplication(self):
        """Test document deduplication"""
        from src.ingestion import DocumentDeduplicator, Document

        deduplicator = DocumentDeduplicator()

        docs = [
            Document(text="Hello world", doc_id="doc1"),
            Document(text="Hello world", doc_id="doc2"),  # Duplicate
            Document(text="Goodbye world", doc_id="doc3"),
        ]

        unique_docs = deduplicator.deduplicate(docs)

        assert len(unique_docs) == 2
        assert unique_docs[0].text == "Hello world"
        assert unique_docs[1].text == "Goodbye world"


# Test Monitoring
class TestMonitoring:
    """Test monitoring and cost tracking"""

    def test_metrics_collection(self, metrics_collector):
        """Test metrics collection"""
        # Record some requests
        metrics_collector.record_request(
            endpoint="/generate", duration=1.5, status="success", tokens=100
        )

        metrics_collector.record_request(
            endpoint="/generate", duration=2.0, status="success", tokens=150
        )

        # Get metrics
        metrics_data = metrics_collector.get_metrics()

        assert metrics_data is not None
        assert b"llm_requests_total" in metrics_data
        assert b"llm_request_duration_seconds" in metrics_data

    def test_cost_tracking(self, mock_cost_tracker):
        """Test cost tracking"""
        # Record some requests
        mock_cost_tracker.record_request(
            tokens=100, duration=2.0, vector_db_queries=1
        )

        mock_cost_tracker.record_request(
            tokens=150, duration=3.0, vector_db_queries=2
        )

        # Get metrics
        current = mock_cost_tracker.get_current_metrics()

        assert current.num_requests == 2
        assert current.total_tokens == 250
        assert current.total_cost > 0

    def test_cost_breakdown(self, mock_cost_tracker):
        """Test cost breakdown"""
        mock_cost_tracker.record_request(tokens=100, duration=1.0)

        breakdown = mock_cost_tracker.get_cost_breakdown()

        assert "current_period" in breakdown
        assert "cost_breakdown" in breakdown
        assert "estimated_monthly" in breakdown

    def test_cost_recommendations(self, mock_cost_tracker):
        """Test cost optimization recommendations"""
        # Record many expensive requests
        for _ in range(100):
            mock_cost_tracker.record_request(tokens=500, duration=10.0)

        recommendations = mock_cost_tracker.get_optimization_recommendations()

        assert isinstance(recommendations, list)

    def test_cost_persistence(self, mock_cost_tracker):
        """Test cost data persistence"""
        mock_cost_tracker.record_request(tokens=100, duration=1.0)

        # Save
        mock_cost_tracker.save()

        # Load
        mock_cost_tracker.load()

        # Should still have data
        current = mock_cost_tracker.get_current_metrics()
        assert current.num_requests > 0


# Test API
class TestAPI:
    """Test FastAPI endpoints"""

    @pytest.fixture
    def api_client(self):
        """Create test client"""
        # Note: This would require mocking the lifespan
        # For actual testing, we'd need to set up proper mocks
        from src.api import app

        # We'll skip this for now as it requires complex setup
        # In real tests, you'd mock the llm_server and rag_pipeline
        pytest.skip("API tests require full application setup")

    def test_health_endpoint_structure(self):
        """Test health endpoint response structure"""
        from src.api.models import HealthResponse

        response = HealthResponse(
            status="healthy",
            model_loaded=True,
            gpu_available=False,
            vector_db_status="healthy",
        )

        assert response.status == "healthy"
        assert response.model_loaded is True

    def test_generate_request_validation(self):
        """Test generate request validation"""
        from src.api.models import GenerateRequest

        request = GenerateRequest(
            prompt="Hello",
            max_tokens=100,
            temperature=0.7,
        )

        assert request.prompt == "Hello"
        assert 1 <= request.max_tokens <= 4096
        assert 0.0 <= request.temperature <= 2.0

    def test_rag_request_validation(self):
        """Test RAG request validation"""
        from src.api.models import RAGGenerateRequest

        request = RAGGenerateRequest(
            query="What is AI?",
            top_k_retrieval=5,
        )

        assert request.query == "What is AI?"
        assert 1 <= request.top_k_retrieval <= 20


# Integration Tests
class TestIntegration:
    """Integration tests for complete workflows"""

    @pytest.mark.asyncio
    async def test_end_to_end_rag(
        self, mock_llm_server, rag_pipeline, sample_documents
    ):
        """Test complete RAG workflow"""
        # 1. Ingest documents
        chunks_added = rag_pipeline.add_documents(sample_documents)
        assert chunks_added > 0

        # 2. Generate answer
        query = "What is machine learning?"
        rag_response = await rag_pipeline.generate_answer(
            query=query,
            llm_server=mock_llm_server,
            max_tokens=50,
        )

        # 3. Verify response
        assert rag_response.answer is not None
        assert len(rag_response.answer) > 0
        assert len(rag_response.retrieved_chunks) > 0
        assert rag_response.metadata["total_tokens"] > 0

    def test_chunking_and_embedding(self, embedding_model, sample_text):
        """Test chunking followed by embedding"""
        from src.rag import TextChunker

        # Chunk
        chunker = TextChunker(chunk_size=200, chunk_overlap=20)
        chunks = chunker.chunk_text(sample_text, "test_doc")

        # Embed
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = embedding_model.encode(chunk_texts)

        assert len(embeddings) == len(chunks)
        assert embeddings.shape[1] == embedding_model.embedding_dim

    def test_document_pipeline(self, temp_dir):
        """Test complete document processing pipeline"""
        from src.ingestion import (
            TextLoader,
            DocumentProcessor,
            DocumentDeduplicator,
        )
        from pathlib import Path

        # Create test files
        for i in range(3):
            test_file = Path(temp_dir) / f"test{i}.txt"
            with open(test_file, "w") as f:
                f.write(f"Test document {i} with some content.")

        # Load
        loader = TextLoader()
        documents = loader.load_batch(
            [str(Path(temp_dir) / f"test{i}.txt") for i in range(3)]
        )

        # Process
        processor = DocumentProcessor()
        processed = processor.process_batch(documents)

        # Deduplicate
        deduplicator = DocumentDeduplicator()
        unique = deduplicator.deduplicate(processed)

        assert len(unique) == 3


# Performance Tests
class TestPerformance:
    """Basic performance tests"""

    def test_embedding_batch_performance(self, embedding_model):
        """Test batch embedding performance"""
        import time

        texts = ["Test text " + str(i) for i in range(100)]

        start = time.time()
        embeddings = embedding_model.encode(texts)
        duration = time.time() - start

        # Should complete in reasonable time (< 10 seconds for 100 texts)
        assert duration < 10.0
        assert len(embeddings) == 100

    @pytest.mark.asyncio
    async def test_generation_performance(self, mock_llm_server):
        """Test generation performance"""
        import time
        from src.llm import GenerationRequest

        request = GenerationRequest(
            prompt="Write a short poem.", max_tokens=50
        )

        start = time.time()
        response = await mock_llm_server.generate(request)
        duration = time.time() - start

        # Should complete in reasonable time (< 30 seconds)
        assert duration < 30.0
        assert len(response.text) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
