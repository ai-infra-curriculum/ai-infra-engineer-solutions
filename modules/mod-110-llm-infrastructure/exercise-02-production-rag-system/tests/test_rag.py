"""Tests for the production RAG system."""

import pytest

from src.embeddings import (
    ChunkingConfig,
    Document,
    HashingEmbedder,
    chunk_document,
    cosine_similarity,
    embed_chunks,
)
from src.generator import (
    GeneratedAnswer,
    LLMRequest,
    LLMResponse,
    RAGGenerator,
    TemplateLLM,
    build_prompt,
    compute_grounding_score,
)
from src.retriever import (
    BenchmarkCase,
    BM25Scorer,
    HybridRetrievalConfig,
    HybridRetriever,
    benchmark_retrieval,
    rerank_score,
)
from src.vector_store import InMemoryVectorStore


def _doc(doc_id, text, *, meta=None):
    return Document(doc_id=doc_id, text=text, metadata=meta or {})


def _build_pipeline(corpus, *, chunk_size=120, chunk_overlap=20):
    embedder = HashingEmbedder(dimension=128)
    store = InMemoryVectorStore()
    all_chunks = []
    for doc in corpus:
        chunks = chunk_document(doc, ChunkingConfig(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        ))
        embed_chunks(chunks, embedder)
        store.upsert(chunks)
        all_chunks.extend(chunks)
    retriever = HybridRetriever(store, embedder, all_chunks)
    return store, retriever, embedder, all_chunks


class TestHashingEmbedder:
    def test_dimension_enforced(self):
        with pytest.raises(ValueError):
            HashingEmbedder(dimension=4)

    def test_deterministic(self):
        e = HashingEmbedder(dimension=64)
        a = e.embed("the quick brown fox")
        b = e.embed("the quick brown fox")
        assert a == b

    def test_empty_returns_zero_vector(self):
        e = HashingEmbedder(dimension=32)
        v = e.embed("")
        assert v == [0.0] * 32

    def test_similar_text_high_cosine(self):
        e = HashingEmbedder(dimension=128)
        a = e.embed("the model is retrained nightly on user-product interactions")
        b = e.embed("the model is trained on user-product interactions every night")
        assert cosine_similarity(a, b) > 0.4

    def test_unrelated_text_low_cosine(self):
        e = HashingEmbedder(dimension=128)
        a = e.embed("the fraud model is an xgboost classifier")
        b = e.embed("the weather in tokyo is sunny today")
        assert cosine_similarity(a, b) < 0.3

    def test_embed_batch(self):
        e = HashingEmbedder(dimension=32)
        vectors = e.embed_batch(["hello", "world", "again"])
        assert len(vectors) == 3
        assert all(len(v) == 32 for v in vectors)


class TestChunking:
    def test_short_doc_one_chunk(self):
        doc = _doc("d", "short text")
        chunks = chunk_document(doc)
        assert len(chunks) == 1
        assert chunks[0].text == "short text"

    def test_long_doc_multiple_chunks(self):
        doc = _doc("d", "x" * 1000)
        chunks = chunk_document(doc, ChunkingConfig(chunk_size=200, chunk_overlap=20))
        assert len(chunks) > 1

    def test_chunk_overlap_validated(self):
        doc = _doc("d", "text")
        with pytest.raises(ValueError):
            chunk_document(doc, ChunkingConfig(chunk_size=100, chunk_overlap=100))

    def test_empty_doc_no_chunks(self):
        doc = _doc("d", "")
        assert chunk_document(doc) == []

    def test_metadata_propagated(self):
        doc = _doc("d", "abc text content here", meta={"team": "x"})
        chunks = chunk_document(doc, ChunkingConfig(chunk_size=50, chunk_overlap=5))
        assert all(c.metadata == {"team": "x"} for c in chunks)


class TestVectorStore:
    def test_upsert_requires_embedding(self):
        store = InMemoryVectorStore()
        doc = _doc("d", "text")
        chunks = chunk_document(doc)
        with pytest.raises(ValueError):
            store.upsert(chunks)

    def test_upsert_and_search(self):
        embedder = HashingEmbedder(dimension=64)
        store = InMemoryVectorStore()
        chunks = chunk_document(_doc("d", "the fraud model is xgboost"))
        embed_chunks(chunks, embedder)
        store.upsert(chunks)
        query_vec = embedder.embed("xgboost fraud")
        hits = store.search(query_vec, k=1)
        assert hits
        assert hits[0].chunk.doc_id == "d"

    def test_metadata_filter(self):
        embedder = HashingEmbedder(dimension=64)
        store = InMemoryVectorStore()
        for i, team in enumerate(("ml", "data", "support")):
            doc = _doc(f"d{i}", "text content here", meta={"team": team})
            chunks = chunk_document(doc, ChunkingConfig(chunk_size=200))
            embed_chunks(chunks, embedder)
            store.upsert(chunks)
        results = store.search(embedder.embed("text"), k=5, where={"team": "ml"})
        assert all(h.chunk.metadata["team"] == "ml" for h in results)

    def test_delete_document(self):
        embedder = HashingEmbedder(dimension=64)
        store = InMemoryVectorStore()
        chunks = chunk_document(_doc("d", "text"))
        embed_chunks(chunks, embedder)
        store.upsert(chunks)
        removed = store.delete_document("d")
        assert removed == len(chunks)
        assert store.count() == 0


class TestBM25Scorer:
    def test_high_score_for_query_terms_in_doc(self):
        embedder = HashingEmbedder(dimension=64)
        doc = _doc("d1", "the fraud model is xgboost classifier", meta={})
        chunks = chunk_document(doc)
        embed_chunks(chunks, embedder)
        bm25 = BM25Scorer(chunks)
        scores = bm25.score("fraud classifier")
        assert scores
        assert all(s >= 0 for s in scores.values())
        assert any(s > 0 for s in scores.values())

    def test_empty_query_zero_scores(self):
        chunks = chunk_document(_doc("d", "text"))
        bm25 = BM25Scorer(chunks)
        scores = bm25.score("")
        assert all(s == 0 for s in scores.values())


class TestRerankScore:
    def test_high_overlap_high_score(self):
        score = rerank_score(
            "fraud detection xgboost model",
            "the fraud detection xgboost model classifies transactions",
        )
        assert score > 0.5

    def test_no_overlap_zero(self):
        score = rerank_score(
            "fraud detection",
            "the weather is sunny",
        )
        assert score == 0.0

    def test_empty_returns_zero(self):
        assert rerank_score("", "hello") == 0.0


class TestHybridRetriever:
    def test_retrieve_returns_top_k(self):
        corpus = [
            _doc("d1", "the fraud detection model uses xgboost"),
            _doc("d2", "billing tickets route to finance"),
            _doc("d3", "the data pipeline writes to s3 in parquet"),
        ]
        store, retriever, _, _ = _build_pipeline(corpus)
        hits = retriever.retrieve("how does the fraud model work?", k=2)
        assert len(hits) <= 2
        assert hits[0].chunk.doc_id == "d1"

    def test_combined_score_components_present(self):
        corpus = [_doc("d1", "the fraud detection model uses xgboost")]
        _, retriever, _, _ = _build_pipeline(corpus)
        hits = retriever.retrieve("fraud xgboost", k=1)
        assert hits
        hit = hits[0]
        assert hit.dense_score > 0
        assert hit.combined_score >= 0
        assert hit.reranker_score >= 0

    def test_metadata_filter_passes_through(self):
        corpus = [
            _doc("d1", "fraud xgboost", meta={"team": "ml"}),
            _doc("d2", "fraud xgboost", meta={"team": "data"}),
        ]
        _, retriever, _, _ = _build_pipeline(corpus)
        hits = retriever.retrieve("fraud", k=5, where={"team": "ml"})
        assert all(h.chunk.metadata["team"] == "ml" for h in hits)


class TestBenchmark:
    def test_hit_at_k_for_correct_retrieval(self):
        corpus = [
            _doc("d1", "the fraud detection model uses xgboost"),
            _doc("d2", "billing tickets route to finance"),
        ]
        _, retriever, _, chunks = _build_pipeline(corpus)
        cases = [
            BenchmarkCase(
                query="fraud xgboost",
                relevant_chunk_ids=[c.chunk_id for c in chunks if c.doc_id == "d1"],
            ),
        ]
        report = benchmark_retrieval(retriever, cases, k=3)
        assert report.hit_at_k == 1.0
        assert report.mean_reciprocal_rank == 1.0

    def test_no_hits_when_query_unrelated(self):
        corpus = [_doc("d1", "the data pipeline writes to s3")]
        _, retriever, _, chunks = _build_pipeline(corpus)
        cases = [
            BenchmarkCase(
                query="some completely different unrelated content",
                relevant_chunk_ids=["nonexistent"],
            ),
        ]
        report = benchmark_retrieval(retriever, cases, k=3)
        assert report.hit_at_k == 0.0

    def test_empty_cases(self):
        corpus = [_doc("d1", "text")]
        _, retriever, _, _ = _build_pipeline(corpus)
        report = benchmark_retrieval(retriever, [], k=3)
        assert report.hit_at_k == 0.0


class TestPromptAndGrounding:
    def test_prompt_includes_context(self):
        corpus = [_doc("d1", "the fraud model uses xgboost")]
        _, retriever, _, _ = _build_pipeline(corpus)
        hits = retriever.retrieve("fraud", k=1)
        prompt = build_prompt("how does fraud detection work?", hits)
        assert "Context:" in prompt
        assert "Question: how does fraud detection work?" in prompt

    def test_empty_context_prompt(self):
        prompt = build_prompt("what is x?", [])
        assert "no relevant context retrieved" in prompt

    def test_grounding_high_when_answer_matches(self):
        from src.embeddings import Chunk
        from src.retriever import RetrievalHit
        chunk = Chunk(
            chunk_id="c1", doc_id="d1", text="the fraud model uses xgboost",
            start_offset=0, end_offset=30, embedding=[0.1] * 16,
        )
        hits = [RetrievalHit(
            chunk=chunk, dense_score=0.9, keyword_score=1.0,
            reranker_score=1.0, combined_score=0.95,
        )]
        score = compute_grounding_score("xgboost fraud model", hits)
        assert score > 0.8

    def test_grounding_zero_for_unrelated(self):
        from src.embeddings import Chunk
        from src.retriever import RetrievalHit
        chunk = Chunk(
            chunk_id="c1", doc_id="d1", text="alpha beta gamma",
            start_offset=0, end_offset=20, embedding=[0.1] * 16,
        )
        hits = [RetrievalHit(
            chunk=chunk, dense_score=0.1, keyword_score=0.1,
            reranker_score=0.0, combined_score=0.1,
        )]
        score = compute_grounding_score("delta epsilon zeta", hits)
        assert score == 0.0


class TestTemplateLLM:
    def test_generate_includes_context(self):
        llm = TemplateLLM()
        prompt = (
            "You are a helpful assistant.\n\n"
            "Context:\nThe fraud model uses xgboost.\n\n"
            "Question: what model is used?"
        )
        response = llm.generate(LLMRequest(prompt=prompt))
        assert "fraud" in response.text.lower() or "xgboost" in response.text.lower()
        assert response.prompt_tokens > 0
        assert response.completion_tokens > 0

    def test_generate_handles_no_context(self):
        llm = TemplateLLM()
        prompt = "Context:\n(no relevant context retrieved)\n\nQuestion: x"
        response = llm.generate(LLMRequest(prompt=prompt))
        assert "context" in response.text.lower() or "don't" in response.text.lower()


class TestRAGGenerator:
    def _setup(self, corpus):
        _, retriever, _, _ = _build_pipeline(corpus)
        return RAGGenerator(retriever, TemplateLLM(), top_k=3,
                            min_grounding_score=0.05)

    def test_end_to_end(self):
        corpus = [_doc("d1", "the fraud model uses xgboost. it is retrained nightly.")]
        gen = self._setup(corpus)
        answer = gen.ask("how is the fraud model trained?")
        assert answer.answer
        assert answer.citations
        assert answer.citations[0].doc_id == "d1"

    def test_low_grounding_returns_idk_message(self):
        corpus = [_doc("d1", "alpha beta gamma delta")]
        _, retriever, _, _ = _build_pipeline(corpus)
        gen = RAGGenerator(retriever, TemplateLLM(), top_k=1,
                            min_grounding_score=0.95)
        answer = gen.ask("epsilon zeta")
        assert "don't have enough confidence" in answer.answer.lower()
        assert answer.grounding_score == 0.0

    def test_no_results_returns_no_context_message(self):
        embedder = HashingEmbedder(dimension=64)
        store = InMemoryVectorStore()
        retriever = HybridRetriever(store, embedder, [])
        gen = RAGGenerator(retriever, TemplateLLM(), top_k=3)
        answer = gen.ask("any question")
        assert answer.citations == []
