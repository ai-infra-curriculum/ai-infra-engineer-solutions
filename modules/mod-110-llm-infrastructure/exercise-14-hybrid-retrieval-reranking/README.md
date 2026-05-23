# Hybrid Retrieval + Reranking — Solution

Reference for [learning exercise-14](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-110-llm-infrastructure/exercises/exercise-14-hybrid-retrieval-reranking/README.md).

## Layout

```
exercise-14-hybrid-retrieval-reranking/
├── README.md, RESULTS.md
├── retrieve.py            # BM25 + dense, then RRF fusion
├── rerank.py              # cross-encoder reranker
├── eval.py                # recall@k + nDCG against golden set
└── pipeline.py            # full RAG: retrieve + rerank + generate with citations
```
