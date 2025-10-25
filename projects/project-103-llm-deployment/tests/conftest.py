"""
Pytest configuration and fixtures
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir():
    """Create temporary directory"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_documents():
    """Sample documents for testing"""
    return [
        {
            "id": "doc1",
            "text": "Machine learning is a subset of artificial intelligence that focuses on building systems that can learn from data.",
            "title": "Introduction to ML",
        },
        {
            "id": "doc2",
            "text": "Deep learning uses neural networks with multiple layers to process data and make predictions.",
            "title": "Deep Learning Basics",
        },
        {
            "id": "doc3",
            "text": "Natural language processing enables computers to understand and generate human language.",
            "title": "NLP Overview",
        },
    ]


@pytest.fixture
def mock_model_config():
    """Mock model configuration"""
    from src.llm import ModelConfig

    return ModelConfig.mock_model()


@pytest.fixture
async def mock_llm_server(mock_model_config):
    """Mock LLM server for testing"""
    from src.llm import LLMServer

    server = LLMServer(mock_model_config)
    await server.initialize()
    return server


@pytest.fixture
def embedding_model():
    """Small embedding model for testing"""
    from src.rag import get_embedding_model

    return get_embedding_model("all-MiniLM-L6-v2")


@pytest.fixture
def chroma_retriever(temp_dir):
    """ChromaDB retriever for testing"""
    from src.rag import ChromaDBRetriever

    return ChromaDBRetriever(
        collection_name="test_collection", persist_directory=temp_dir
    )


@pytest.fixture
def rag_pipeline(embedding_model, chroma_retriever):
    """RAG pipeline for testing"""
    from src.rag import RAGPipeline, RAGConfig

    config = RAGConfig(top_k=3, chunk_size=256, chunk_overlap=20)
    return RAGPipeline(embedding_model, chroma_retriever, config)


@pytest.fixture
def sample_text():
    """Sample text for testing"""
    return """
    Artificial Intelligence (AI) is transforming the world. Machine learning, a subset of AI,
    enables computers to learn from data without being explicitly programmed.

    Deep learning, which uses neural networks with multiple layers, has achieved remarkable
    success in image recognition, natural language processing, and game playing.

    The future of AI holds great promise, but also raises important ethical questions about
    bias, privacy, and the impact on employment.
    """


@pytest.fixture
def sample_pdf_path(temp_dir):
    """Create a sample PDF file for testing"""
    # Create a simple text file (mock PDF)
    pdf_path = Path(temp_dir) / "sample.pdf"
    with open(pdf_path, "w") as f:
        f.write("This is a sample PDF content for testing.")
    return str(pdf_path)


@pytest.fixture
def sample_markdown_path(temp_dir):
    """Create a sample Markdown file"""
    md_path = Path(temp_dir) / "sample.md"
    content = """# Sample Document

This is a sample markdown document.

## Section 1
Some content here.

## Section 2
More content here.
"""
    with open(md_path, "w") as f:
        f.write(content)
    return str(md_path)


@pytest.fixture
def mock_cost_tracker(temp_dir):
    """Mock cost tracker for testing"""
    from src.monitoring import CostTracker, CostConfig

    config = CostConfig(gpu_cost_per_hour=1.0)
    persist_file = str(Path(temp_dir) / "cost_test.json")
    return CostTracker(config=config, persist_file=persist_file)


@pytest.fixture
def metrics_collector():
    """Metrics collector for testing"""
    from src.monitoring import MetricsCollector

    return MetricsCollector(model_name="test_model")


# Mock functions for testing without actual models


class MockLLMResponse:
    """Mock LLM response"""

    def __init__(self, text="This is a test response.", tokens=10):
        self.text = text
        self.prompt_tokens = tokens // 2
        self.completion_tokens = tokens // 2
        self.total_tokens = tokens
        self.finish_reason = "stop"
        self.model = "mock-model"


@pytest.fixture
def mock_llm_response():
    """Mock LLM response fixture"""
    return MockLLMResponse()
