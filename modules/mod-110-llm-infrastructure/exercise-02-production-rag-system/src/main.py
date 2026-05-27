"""
Production RAG System CLI

Subcommands:
    ingest        Ingest a built-in document set and report store size.
    ask           Ask a question against the corpus and print grounded answer.
    benchmark     Run a labeled retrieval benchmark and print Hit@k + MRR.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import List

import click

from .embeddings import (
    ChunkingConfig,
    Document,
    HashingEmbedder,
    chunk_document,
    embed_chunks,
)
from .generator import (
    RAGGenerator,
    TemplateLLM,
)
from .retriever import (
    BenchmarkCase,
    HybridRetrievalConfig,
    HybridRetriever,
    benchmark_retrieval,
)
from .vector_store import InMemoryVectorStore


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


_CORPUS: List[Document] = [
    Document(
        doc_id="doc-1",
        text=(
            "SmartRecs uses a recommendation pipeline backed by collaborative "
            "filtering. The model is retrained nightly on user-product "
            "interactions. The fraud detection model uses a separate XGBoost "
            "classifier trained on transaction features."
        ),
        source="wiki",
        metadata={"team": "ml-platform", "domain": "product"},
    ),
    Document(
        doc_id="doc-2",
        text=(
            "Customer support tickets are routed by intent classification. "
            "Tickets tagged 'billing' go to the finance team. Tickets tagged "
            "'technical' go to the engineering team. Escalation happens after "
            "two hours without a response."
        ),
        source="runbook",
        metadata={"team": "support", "domain": "operations"},
    ),
    Document(
        doc_id="doc-3",
        text=(
            "The data pipeline ingests events from Kafka and writes them to "
            "S3 in Parquet format. Daily aggregations run via Airflow at "
            "03:00 UTC. The feature store is refreshed nightly using the "
            "previous day's data."
        ),
        source="runbook",
        metadata={"team": "data", "domain": "operations"},
    ),
]


def _build_pipeline():
    store = InMemoryVectorStore()
    embedder = HashingEmbedder(dimension=128)
    all_chunks = []
    for doc in _CORPUS:
        chunks = chunk_document(doc, ChunkingConfig(chunk_size=160, chunk_overlap=24))
        embed_chunks(chunks, embedder)
        store.upsert(chunks)
        all_chunks.extend(chunks)
    retriever = HybridRetriever(store, embedder, all_chunks)
    generator = RAGGenerator(retriever, TemplateLLM(), top_k=3,
                              min_grounding_score=0.15)
    return store, retriever, generator


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """Production RAG system."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
def ingest() -> None:
    """Ingest the built-in demo corpus and print store state."""
    store, _, _ = _build_pipeline()
    click.echo(f"Documents:    {len(_CORPUS)}")
    click.echo(f"Vector store: {store.count()} chunks")


@cli.command()
@click.argument("question")
@click.option("--top-k", default=3, type=int)
def ask(question: str, top_k: int) -> None:
    """Ask a question against the demo corpus."""
    _, _, generator = _build_pipeline()
    generator.top_k = top_k
    answer = generator.ask(question)
    click.echo(f"Q: {answer.question}")
    click.echo(f"A: {answer.answer}")
    click.echo(f"\nGrounding score: {answer.grounding_score}")
    click.echo("Citations:")
    for c in answer.citations:
        click.echo(f"  [{c.index}] {c.doc_id}/{c.chunk_id} :: {c.source_text_preview}")


@cli.command()
def benchmark() -> None:
    """Run a labeled retrieval benchmark against the demo corpus."""
    store, retriever, _ = _build_pipeline()
    chunk_ids_by_doc = {}
    for doc in _CORPUS:
        chunks = chunk_document(doc, ChunkingConfig(chunk_size=160, chunk_overlap=24))
        chunk_ids_by_doc[doc.doc_id] = [c.chunk_id for c in chunks]

    cases = [
        BenchmarkCase(query="How does SmartRecs recommend products?",
                      relevant_chunk_ids=chunk_ids_by_doc["doc-1"]),
        BenchmarkCase(query="Where do billing tickets get routed?",
                      relevant_chunk_ids=chunk_ids_by_doc["doc-2"]),
        BenchmarkCase(query="Where are events written after Kafka?",
                      relevant_chunk_ids=chunk_ids_by_doc["doc-3"]),
        BenchmarkCase(query="When does the feature store refresh?",
                      relevant_chunk_ids=chunk_ids_by_doc["doc-3"]),
    ]
    report = benchmark_retrieval(retriever, cases, k=3)
    click.echo(f"Hit@3:           {report.hit_at_k:.4f}")
    click.echo(f"MRR:             {report.mean_reciprocal_rank:.4f}")
    click.echo(f"Avg Recall@3:    {report.average_recall_at_k:.4f}")
    click.echo("\nPer-query:")
    for q in report.per_query:
        click.echo(
            f"  hit={q['hit']!s:<5s} recall={q['recall_at_k']:.4f}  '{q['query']}'"
        )


if __name__ == "__main__":
    cli()
