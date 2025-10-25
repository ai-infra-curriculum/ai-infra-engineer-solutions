"""
LLM Deployment Platform

A production-ready platform for deploying and serving Large Language Models
with RAG (Retrieval-Augmented Generation) capabilities.

Modules:
    - api: FastAPI REST API endpoints
    - llm: LLM model configuration and serving
    - rag: RAG pipeline components (chunking, embeddings, retrieval)
    - ingestion: Document ingestion and processing
    - monitoring: Metrics, logging, and observability

Example:
    Basic usage:

        from src.llm.server import LLMServer
        from src.rag.pipeline import RAGPipeline

        # Initialize LLM server
        server = LLMServer(model_name="gpt-3.5-turbo")

        # Create RAG pipeline
        rag = RAGPipeline(llm_server=server)

        # Query with context
        response = rag.query("What is machine learning?")
"""

__version__ = "1.0.0"
__author__ = "AI Infrastructure Curriculum"
__email__ = "ai-infra-curriculum@joshua-ferguson.com"

__all__ = [
    "__version__",
    "__author__",
    "__email__",
]
