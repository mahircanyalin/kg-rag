# Hybrid Knowledge Graph + Vector RAG over SEC 10-K Filings

A retrieval system that answers questions over Apple's SEC 10-K filing by routing each
question to the right store: a **Neo4j knowledge graph** for relationship and multi-hop
questions, and a **pgvector** store for definitions and single-passage lookups. Every
answer is grounded in retrieved text and cites the source chunk it came from.

The point of the project is not "another vector RAG." It is to show *where embeddings
fail* — multi-hop questions that require following a chain across related entities — and
what to do about it.

## Benchmark: Hybrid vs. Vector-only Baseline

Both systems were run on the same 39-question set, stratified by hop count. Accuracy is
measured by keyword-match against expected answers. Out-of-scope questions (hop 0) test
whether the system correctly refuses to answer information not in the filing.

| Hops | Hybrid (Graph + Vector) | Vector-only Baseline | Δ |
|------|-------------------------|----------------------|-----|
| 0 (out-of-scope) | 100% (4/4) | 100% (4/4) | +0% |
| 1 (single-hop) | 80% (20/25) | 68% (17/25) | **+12%** |
| 2 (multi-hop) | 50% (5/10) | 30% (3/10) | **+20%** |

The expected shape holds: parity on out-of-scope questions (neither system hallucinates),
a modest edge on single-hop questions, and a **widening gap as hops increase**. That curve
is the whole story — the graph earns its cost precisely where vector search cannot follow
relationships across entities.

## What It Does

A standard vector RAG chunks documents, embeds them, and retrieves the passages most
similar to a question. This works well for single-fact questions like *"What is the State
Aid Decision?"* — the answer lives in one passage.

It fails on questions like *"Which countries where Apple manufactures are also regulatory
concerns?"* The answer isn't in any single passage; it requires intersecting two
relationships (manufacturing locations ∩ regulatory concerns). Embedding similarity can't
do this. A graph can.

This system combines both:

- **Knowledge Graph (Neo4j)** — entities as nodes, relationships as edges. Answers
  connection and multi-hop questions by traversing the graph.
- **Vector store (pgvector)** — semantic passage search. Answers definitions and
  single-fact lookups.
- **Router** — a lightweight classifier decides, per question, which store to use.
- **Grounded generation** — the LLM answers *only* from retrieved context and every
  citation is validated against chunks that were actually retrieved. Invented sources are
  rejected.

The key design decision: both stores share the same `chunk_id`. That shared key is what
lets the system cross from a graph path back to the original text, and cite the exact
source sentence for every claim.

## Architecture

```
INGESTION (once)
  SEC EDGAR 10-K ─► clean + chunk ─► LLM extraction ─► entity resolution
                                            │
                          ┌─────────────────┴─────────────────┐
                          ▼                                    ▼
                   Neo4j (graph)                      pgvector (embeddings)
                   relationships                      passages, HNSW index
                          └────────── shared chunk_id ─────────┘

QUERY (per question)
  question ─► router ─► graph query  (connection / multi-hop)
                    └─► vector query (definition / single-fact)
                                │
                                ▼
                    grounded answer + validated citations ─► FastAPI /ask
```

### Pipeline

1. **Ingestion** — Fetch the latest 10-K from SEC EDGAR, strip HTML, chunk with overlap,
   and assign each chunk a stable `chunk_id`.
2. **Extraction** — Each chunk is passed to `gpt-4o-mini` with a constrained ontology
   (7 entity types, 9 relationship types) and a strict JSON schema. Every response is
   validated against the ontology; garbage (dates, numbers, generic nouns) is filtered.
3. **Entity resolution** — Variants collapse to canonical names (`Apple Inc.`, `AAPL` →
   `Apple`) via a rule-based normalizer plus an alias map.
4. **Graph loading** — Entities become nodes and relationships become edges via `MERGE`
   (idempotent). Each edge carries the `chunk_id` that justified it.
5. **Vector loading** — The same chunks are embedded locally (`all-MiniLM-L6-v2`, 384-dim)
   into pgvector with an HNSW cosine index.
6. **Routing & retrieval** — The router classifies each question. Graph questions run
   **parameterized Cypher templates** (the model never writes raw Cypher — a security and
   reproducibility control). Multi-hop questions run chained/intersection templates.
7. **Answer generation** — Retrieved context is passed to the LLM with instructions to
   answer only from context and cite every claim; citations are validated post-hoc.

## Tech Stack

- **Python**, **FastAPI** — API layer
- **Neo4j** — knowledge graph, Cypher queries
- **PostgreSQL + pgvector** — vector store, HNSW index
- **OpenAI `gpt-4o-mini`** — extraction, routing, answer generation
- **sentence-transformers** (`all-MiniLM-L6-v2`) — local embeddings (no API cost)
- **Docker** — Neo4j and pgvector containers

## Setup

**Prerequisites:** Docker, Python 3.11+, an OpenAI API key.

```bash
# 1. Start databases
docker run -d --name neo4j-rag -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password123 neo4j:5-community

docker run -d --name pgvector-rag -p 5433:5432 \
  -e POSTGRES_PASSWORD=password123 pgvector/pgvector:pg16

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure .env (see .env.example)
#    OPENAI_API_KEY, NEO4J_*, POSTGRES_*
```

### Run the pipeline

```bash
# Ingestion (Phase 1-2)
python ingestion/fetch_sec.py          # download 10-K
python ingestion/clean_and_chunk.py    # clean + chunk
python ingestion/extract.py            # LLM extraction
python ingestion/resolve_entities.py   # entity resolution
python ingestion/load_neo4j.py         # load graph
python retrieval/load_pgvector.py      # load vectors

# Serve the API
cd api && python -m uvicorn main:app --reload
# then open http://localhost:8000/docs

# Run the benchmark
cd eval && python benchmark.py
```

### Example query

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Who are Apple'\''s executives?"}'
```

```json
{
  "question": "Who are Apple's executives?",
  "route": "graph",
  "answer": "Apple's executives include Timothy D. Cook, Kevan Parekh, Chris Kondo, ... [chunk_0258].",
  "citations": ["chunk_0258"],
  "invalid_citations": []
}
```

## Ontology

**Entity types (7):** Company, Person, Product, Location, RiskFactor, Regulator,
BusinessSegment

**Relationship types (9):** OPERATES_IN, DEPENDS_ON, MANUFACTURES_IN, PRODUCES,
FACES_RISK, REGULATED_BY, COMPETES_WITH, HAS_EXECUTIVE, ACQUIRED

The ontology is deliberately constrained. An open-ended "extract all entities" prompt
produces a graph nobody can query; a closed list keeps the graph clean and queryable.

## Honest Limitations

This is a working system, not a polished product. Where it falls short is documented
because that's what makes the accuracy claim credible:

- **Multi-hop is template-based, not general.** Chained queries work for the intersection
  patterns defined as templates (manufacturing ∩ regulation, competitors in legal
  proceedings). Truly arbitrary multi-hop reasoning isn't solved — see the two 2-hop
  questions the hybrid still loses.
- **Extraction noise remains.** LLM extraction over a 10-K leaves a small amount of
  mis-typed entities (e.g. a law tagged as both Regulator and RiskFactor, a duplicate
  node). Filtering catches most, not all.
- **Single document.** The current graph is built from one Apple 10-K. The architecture
  supports multiple filings (entity resolution and `MERGE` are already idempotent), but
  cross-company relationships aren't exercised yet.

## Roadmap / Stretch Goals

- **LangGraph orchestration** — the pipeline is currently a linear function chain. Moving
  to LangGraph would enable a low-confidence fallback (run both paths and merge), a retry
  node on failed citation validation, and true multi-step multi-hop traversal. The
  benchmark's 2-hop results are the concrete motivation for this.
- **Incremental graph updates** instead of full re-ingestion.
- **Expand the corpus** to multiple companies' filings to exercise cross-entity multi-hop.
- **LLM-as-judge evaluation** to complement the current keyword-match scoring.