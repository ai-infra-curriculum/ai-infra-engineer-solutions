"""Full RAG pipeline: hybrid retrieve → rerank → generate with citations."""
from __future__ import annotations

import httpx

from retrieve import hybrid_search
from rerank import rerank


CITATION_PROMPT = """Answer the question using ONLY the provided sources. Cite each fact with [source_id].

Sources:
{sources}

Question: {question}

Answer (with citations):"""


def answer(question: str, corpus_path: str = "data/corpus.tsv") -> dict:
    candidates = hybrid_search(question, corpus_path, k=20)
    top = rerank(question, candidates, top_k=5)
    sources = "\n\n".join(f"[{d.id}] {d.text[:300]}" for d in top)

    r = httpx.post("http://vllm:8000/v1/completions", json={
        "model": "mistralai/Mistral-7B-Instruct-v0.2",
        "prompt": CITATION_PROMPT.format(sources=sources, question=question),
        "max_tokens": 300,
        "temperature": 0,
    })
    return {
        "answer": r.json()["choices"][0]["text"],
        "cited_sources": [d.id for d in top],
    }
