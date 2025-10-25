"""
Pydantic models for API requests and responses
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class GenerateRequest(BaseModel):
    """Request for text generation"""

    prompt: str = Field(..., description="Input prompt for generation")
    max_tokens: int = Field(512, ge=1, le=4096, description="Maximum tokens to generate")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    top_k: int = Field(50, ge=0, description="Top-k sampling parameter")
    repetition_penalty: float = Field(
        1.1, ge=1.0, le=2.0, description="Repetition penalty"
    )
    stream: bool = Field(False, description="Stream response")
    stop_sequences: Optional[List[str]] = Field(None, description="Stop sequences")


class GenerateResponse(BaseModel):
    """Response from text generation"""

    text: str = Field(..., description="Generated text")
    prompt_tokens: int = Field(..., description="Number of prompt tokens")
    completion_tokens: int = Field(..., description="Number of completion tokens")
    total_tokens: int = Field(..., description="Total tokens")
    finish_reason: str = Field(..., description="Reason for completion")
    model: str = Field(..., description="Model used")


class RAGGenerateRequest(BaseModel):
    """Request for RAG-augmented generation"""

    query: str = Field(..., description="User query")
    max_tokens: int = Field(512, ge=1, le=4096, description="Maximum tokens to generate")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    top_k_retrieval: int = Field(
        5, ge=1, le=20, description="Number of chunks to retrieve"
    )
    stream: bool = Field(False, description="Stream response")
    system_prompt: Optional[str] = Field(None, description="Optional system prompt")


class RetrievedChunk(BaseModel):
    """Retrieved chunk information"""

    text: str = Field(..., description="Chunk text")
    score: float = Field(..., description="Similarity score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    chunk_id: str = Field(..., description="Chunk identifier")


class RAGGenerateResponse(BaseModel):
    """Response from RAG-augmented generation"""

    answer: str = Field(..., description="Generated answer")
    retrieved_chunks: List[RetrievedChunk] = Field(
        ..., description="Retrieved chunks used"
    )
    context_length: int = Field(..., description="Context length in characters")
    prompt_tokens: int = Field(..., description="Number of prompt tokens")
    completion_tokens: int = Field(..., description="Number of completion tokens")
    total_tokens: int = Field(..., description="Total tokens")
    model: str = Field(..., description="Model used")


class IngestRequest(BaseModel):
    """Request for document ingestion"""

    documents: List[Dict[str, Any]] = Field(..., description="Documents to ingest")
    text_key: str = Field("text", description="Key for text content in documents")
    id_key: str = Field("id", description="Key for document ID")


class IngestResponse(BaseModel):
    """Response from document ingestion"""

    chunks_added: int = Field(..., description="Number of chunks added")
    documents_processed: int = Field(..., description="Number of documents processed")


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(..., description="Service status")
    model_loaded: bool = Field(..., description="Whether model is loaded")
    gpu_available: bool = Field(..., description="Whether GPU is available")
    vector_db_status: str = Field(..., description="Vector database status")


class ModelInfo(BaseModel):
    """Model information"""

    model_name: str
    backend: str
    dtype: str
    gpu_name: Optional[str]
    max_tokens: int


class CostBreakdown(BaseModel):
    """Cost breakdown"""

    total_cost: float
    cost_per_request: float
    cost_per_1k_tokens: float
    estimated_monthly: float
    recommendations: List[Dict[str, Any]]
