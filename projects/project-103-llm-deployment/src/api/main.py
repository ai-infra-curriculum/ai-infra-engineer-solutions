"""
FastAPI application for LLM serving

Provides endpoints for:
- Direct LLM generation
- RAG-augmented generation
- Document ingestion
- Health checks and metrics
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from ..llm import LLMServer, GenerationRequest as LLMGenerationRequest, ModelConfig
from ..rag import (
    RAGPipeline,
    RAGConfig,
    EmbeddingModel,
    ChromaDBRetriever,
)
from ..monitoring import get_metrics_collector, RequestTimer, CostTracker, CostConfig
from .models import (
    GenerateRequest,
    GenerateResponse,
    RAGGenerateRequest,
    RAGGenerateResponse,
    IngestRequest,
    IngestResponse,
    HealthResponse,
    ModelInfo,
    CostBreakdown,
    RetrievedChunk,
)
from .middleware import add_middlewares

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global instances
llm_server: Optional[LLMServer] = None
rag_pipeline: Optional[RAGPipeline] = None
metrics_collector = None
cost_tracker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    global llm_server, rag_pipeline, metrics_collector, cost_tracker

    logger.info("Starting LLM deployment platform...")

    # Get configuration from environment
    model_config_name = os.getenv("MODEL_CONFIG", "tiny-llama")
    embedding_model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    vector_db_backend = os.getenv("VECTOR_DB_BACKEND", "chromadb")
    chroma_persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

    try:
        # Initialize LLM server
        logger.info(f"Initializing LLM server with config: {model_config_name}")
        from ..llm import get_config

        model_config = get_config(model_config_name)
        llm_server = LLMServer(model_config)
        await llm_server.initialize()

        # Initialize embedding model
        logger.info(f"Initializing embedding model: {embedding_model_name}")
        from ..rag import get_embedding_model

        embedding_model = get_embedding_model(embedding_model_name)

        # Initialize retriever
        logger.info(f"Initializing vector database: {vector_db_backend}")
        if vector_db_backend == "chromadb":
            retriever = ChromaDBRetriever(persist_directory=chroma_persist_dir)
        else:
            raise ValueError(f"Unsupported vector DB backend: {vector_db_backend}")

        # Initialize RAG pipeline
        rag_config = RAGConfig(
            top_k=int(os.getenv("RAG_TOP_K", "5")),
            chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "512")),
            chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "50")),
        )
        rag_pipeline = RAGPipeline(embedding_model, retriever, rag_config)

        # Initialize monitoring
        logger.info("Initializing monitoring...")
        metrics_collector = get_metrics_collector(model_name=model_config.model_name)
        metrics_collector.set_model_info(llm_server.get_model_info())

        # Initialize cost tracking
        cost_config = CostConfig(
            gpu_cost_per_hour=float(os.getenv("GPU_COST_PER_HOUR", "1.0")),
        )
        cost_tracker = CostTracker(config=cost_config, persist_file="./cost_data.json")

        logger.info("LLM deployment platform started successfully!")

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down LLM deployment platform...")
    if cost_tracker:
        cost_tracker.save()


# Create FastAPI app
app = FastAPI(
    title="LLM Deployment Platform",
    description="Production-ready LLM serving with RAG support",
    version="1.0.0",
    lifespan=lifespan,
)

# Add middlewares
add_middlewares(app)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint"""
    return {
        "message": "LLM Deployment Platform",
        "version": "1.0.0",
        "endpoints": {
            "generate": "/generate",
            "rag_generate": "/rag-generate",
            "ingest": "/ingest",
            "health": "/health",
            "ready": "/ready",
            "metrics": "/metrics",
            "models": "/models",
            "cost": "/cost",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health():
    """Health check endpoint"""
    model_loaded = llm_server is not None
    gpu_available = False
    vector_db_status = "unknown"

    if llm_server:
        import torch

        gpu_available = torch.cuda.is_available()

    if rag_pipeline:
        try:
            info = rag_pipeline.retriever.get_collection_info()
            vector_db_status = "healthy"
        except:
            vector_db_status = "unhealthy"

    status = "healthy" if model_loaded else "unhealthy"

    return HealthResponse(
        status=status,
        model_loaded=model_loaded,
        gpu_available=gpu_available,
        vector_db_status=vector_db_status,
    )


@app.get("/ready", tags=["health"])
async def ready():
    """Readiness check endpoint"""
    if llm_server is None:
        raise HTTPException(status_code=503, detail="LLM server not ready")

    # Test model
    is_healthy = await llm_server.health_check()

    if not is_healthy:
        raise HTTPException(status_code=503, detail="LLM server health check failed")

    return {"status": "ready"}


@app.get("/models", response_model=ModelInfo, tags=["info"])
async def get_models():
    """Get model information"""
    if llm_server is None:
        raise HTTPException(status_code=503, detail="LLM server not initialized")

    info = llm_server.get_model_info()

    return ModelInfo(
        model_name=info["model_name"],
        backend=info["backend"],
        dtype=info["dtype"],
        gpu_name=info.get("gpu_name"),
        max_tokens=info["max_model_len"],
    )


@app.post("/generate", response_model=GenerateResponse, tags=["generation"])
async def generate(request: GenerateRequest):
    """Generate text from prompt"""
    if llm_server is None:
        raise HTTPException(status_code=503, detail="LLM server not initialized")

    # Create LLM request
    llm_request = LLMGenerationRequest(
        prompt=request.prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
        top_k=request.top_k,
        repetition_penalty=request.repetition_penalty,
        stream=False,
        stop_sequences=request.stop_sequences,
    )

    # Track request
    with RequestTimer(metrics_collector, "generate") as timer:
        try:
            response = await llm_server.generate(llm_request)
            timer.set_tokens(response.completion_tokens)

            # Track cost
            if cost_tracker:
                # Estimate duration from tokens (rough approximation)
                duration = response.completion_tokens / 50.0  # Assume 50 tokens/sec
                cost_tracker.record_request(
                    tokens=response.total_tokens, duration=duration
                )

            return GenerateResponse(
                text=response.text,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                finish_reason=response.finish_reason,
                model=response.model,
            )

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/stream", tags=["generation"])
async def generate_stream(request: GenerateRequest):
    """Generate text with streaming"""
    if llm_server is None:
        raise HTTPException(status_code=503, detail="LLM server not initialized")

    # Create LLM request
    llm_request = LLMGenerationRequest(
        prompt=request.prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
        top_k=request.top_k,
        repetition_penalty=request.repetition_penalty,
        stream=True,
        stop_sequences=request.stop_sequences,
    )

    async def generate():
        try:
            async for chunk in await llm_server.generate(llm_request):
                yield f"data: {chunk}\n\n"
        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/rag-generate", response_model=RAGGenerateResponse, tags=["rag"])
async def rag_generate(request: RAGGenerateRequest):
    """Generate answer using RAG"""
    if llm_server is None or rag_pipeline is None:
        raise HTTPException(status_code=503, detail="Services not initialized")

    with RequestTimer(metrics_collector, "rag_generate") as timer:
        try:
            # Generate answer with RAG
            rag_response = await rag_pipeline.generate_answer(
                query=request.query,
                llm_server=llm_server,
                system_prompt=request.system_prompt,
                top_k=request.top_k_retrieval,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
            )

            timer.set_tokens(rag_response.metadata["completion_tokens"])

            # Track cost
            if cost_tracker:
                duration = rag_response.metadata["completion_tokens"] / 50.0
                cost_tracker.record_request(
                    tokens=rag_response.metadata["total_tokens"],
                    duration=duration,
                    vector_db_queries=1,
                )

            # Convert retrieved chunks
            chunks = [
                RetrievedChunk(
                    text=chunk.text,
                    score=chunk.score,
                    metadata=chunk.metadata,
                    chunk_id=chunk.chunk_id,
                )
                for chunk in rag_response.retrieved_chunks
            ]

            return RAGGenerateResponse(
                answer=rag_response.answer,
                retrieved_chunks=chunks,
                context_length=len(rag_response.context_used),
                prompt_tokens=rag_response.metadata["prompt_tokens"],
                completion_tokens=rag_response.metadata["completion_tokens"],
                total_tokens=rag_response.metadata["total_tokens"],
                model=rag_response.metadata["model"],
            )

        except Exception as e:
            logger.error(f"RAG generation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest", response_model=IngestResponse, tags=["rag"])
async def ingest_documents(request: IngestRequest):
    """Ingest documents into vector database"""
    if rag_pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized")

    try:
        chunks_added = rag_pipeline.add_documents(
            documents=request.documents,
            text_key=request.text_key,
            id_key=request.id_key,
        )

        return IngestResponse(
            chunks_added=chunks_added, documents_processed=len(request.documents)
        )

    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics", tags=["monitoring"])
async def metrics():
    """Prometheus metrics endpoint"""
    if metrics_collector is None:
        raise HTTPException(status_code=503, detail="Metrics collector not initialized")

    metrics_data = metrics_collector.get_metrics()
    return Response(content=metrics_data, media_type="text/plain")


@app.get("/cost", response_model=CostBreakdown, tags=["monitoring"])
async def get_cost():
    """Get cost breakdown and recommendations"""
    if cost_tracker is None:
        raise HTTPException(status_code=503, detail="Cost tracker not initialized")

    breakdown = cost_tracker.get_cost_breakdown()
    recommendations = cost_tracker.get_optimization_recommendations()

    current = breakdown["current_period"]

    return CostBreakdown(
        total_cost=current["total_cost"],
        cost_per_request=current["cost_per_request"],
        cost_per_1k_tokens=current["cost_per_1k_tokens"],
        estimated_monthly=breakdown["estimated_monthly"],
        recommendations=recommendations,
    )


def main():
    """Run the application"""
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
