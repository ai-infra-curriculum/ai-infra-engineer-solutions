"""
RAG Generator

Composes the retriever + an LLM call to produce a grounded answer with
inline citations. The LLM is a pluggable Protocol so production swaps
in a real client (vLLM / OpenAI); the in-memory TemplateLLM is used
by tests + demos.

Produces a GeneratedAnswer with the text + source citations + grounding
metrics (citation coverage + retrieval scores) that the caller can
display or feed into a hallucination detector.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Protocol

from .embeddings import _tokenize
from .retriever import HybridRetriever, RetrievalHit


logger = logging.getLogger(__name__)


# -- LLM client abstraction --------------------------------------------


@dataclass
class LLMRequest:
    """Input to the LLM."""

    prompt: str
    model: str = "fake-llm"
    temperature: float = 0.2
    max_tokens: int = 512


@dataclass
class LLMResponse:
    """Output from the LLM."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str


class LLMClient(Protocol):
    """Pluggable LLM."""

    def generate(self, request: LLMRequest) -> LLMResponse: ...


class TemplateLLM:
    """Deterministic in-memory LLM that quotes the supplied context.

    Returns a synthesized answer that concatenates sentences from the
    provided context with citation markers, suitable for tests + CLI
    demos where determinism + traceability matter.
    """

    def __init__(self, *, max_sentences: int = 3):
        self.max_sentences = max_sentences

    def generate(self, request: LLMRequest) -> LLMResponse:
        # Extract context block (everything after "Context:" and before
        # "Question:") from the prompt and answer by quoting the first
        # N sentences.
        context_match = re.search(
            r"Context:\n(.*?)\n\nQuestion:", request.prompt, re.DOTALL,
        )
        context = context_match.group(1) if context_match else ""
        question_match = re.search(r"Question:\s*(.*?)$", request.prompt, re.DOTALL)
        question = (question_match.group(1).strip() if question_match
                    else "the question")

        sentences = _split_sentences(context)
        relevant = sentences[: self.max_sentences] if sentences else []
        if relevant:
            answer = (
                f"Based on the provided context: " + " ".join(relevant)
                + f" (re: '{question}')"
            )
        else:
            answer = (
                f"I don't have enough context to answer '{question}' "
                "reliably."
            )
        return LLMResponse(
            text=answer,
            prompt_tokens=len(_tokenize(request.prompt)),
            completion_tokens=len(_tokenize(answer)),
            model=request.model,
        )


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


# -- Prompt assembly ---------------------------------------------------


def build_prompt(question: str, hits: List[RetrievalHit]) -> str:
    """Build a context-injected prompt with numbered citation markers."""
    if not hits:
        return (
            "You are a helpful assistant. Answer based ONLY on context.\n\n"
            "Context:\n(no relevant context retrieved)\n\n"
            f"Question: {question}\nAnswer:"
        )
    context_lines = []
    for i, hit in enumerate(hits, start=1):
        context_lines.append(f"[{i}] (score={hit.combined_score:.3f}) {hit.chunk.text}")
    context = "\n\n".join(context_lines)
    return (
        "You are a helpful assistant. Answer based ONLY on the provided "
        "context. Cite sources by [number]. If the context does not contain "
        "the answer, say so.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\nAnswer:"
    )


# -- Grounded answer + grounding check ---------------------------------


@dataclass
class Citation:
    """One source citation."""

    index: int  # 1-based reference number in the prompt
    chunk_id: str
    doc_id: str
    source_text_preview: str


@dataclass
class GeneratedAnswer:
    """The output of one RAG call."""

    question: str
    answer: str
    citations: List[Citation]
    retrieval_hits: List[RetrievalHit]
    grounding_score: float  # 0..1 — fraction of answer tokens supported by context
    llm_response: LLMResponse
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def compute_grounding_score(answer: str, hits: List[RetrievalHit]) -> float:
    """Fraction of answer tokens that also appear in the retrieved context."""
    if not hits or not answer:
        return 0.0
    context_tokens = set()
    for hit in hits:
        context_tokens.update(_tokenize(hit.chunk.text))
    answer_tokens = _tokenize(answer)
    if not answer_tokens:
        return 0.0
    supported = sum(1 for t in answer_tokens if t in context_tokens)
    return round(supported / len(answer_tokens), 4)


class RAGGenerator:
    """End-to-end RAG: retrieve → prompt → generate → ground-check."""

    def __init__(
        self,
        retriever: HybridRetriever,
        llm: LLMClient,
        *,
        top_k: int = 5,
        min_grounding_score: float = 0.2,
    ):
        self.retriever = retriever
        self.llm = llm
        self.top_k = top_k
        self.min_grounding_score = min_grounding_score

    def ask(
        self,
        question: str,
        *,
        where: Optional[Dict[str, str]] = None,
        model: str = "fake-llm",
    ) -> GeneratedAnswer:
        hits = self.retriever.retrieve(question, k=self.top_k, where=where)
        prompt = build_prompt(question, hits)
        llm_response = self.llm.generate(LLMRequest(prompt=prompt, model=model))
        citations = [
            Citation(
                index=i + 1,
                chunk_id=hit.chunk.chunk_id,
                doc_id=hit.chunk.doc_id,
                source_text_preview=hit.chunk.text[:120],
            )
            for i, hit in enumerate(hits)
        ]
        grounding = compute_grounding_score(llm_response.text, hits)
        # Strip the answer down to the "I don't know" template when the
        # grounding score is below the minimum.
        if hits and grounding < self.min_grounding_score:
            llm_response = LLMResponse(
                text=(
                    "I don't have enough confidence in the retrieved context to "
                    f"answer '{question}' reliably (grounding={grounding:.2f})."
                ),
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=0,
                model=llm_response.model,
            )
            grounding = 0.0
        return GeneratedAnswer(
            question=question,
            answer=llm_response.text,
            citations=citations,
            retrieval_hits=hits,
            grounding_score=grounding,
            llm_response=llm_response,
        )
