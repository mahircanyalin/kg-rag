# Hybrid Knowledge Graph + Vector RAG with Agentic Multi-Hop Retrieval

A retrieval system over SEC 10-K filings that answers questions by combining a **Neo4j
knowledge graph** (for relationships and multi-hop reasoning) with a **pgvector** store
(for definitions and single-passage lookups). A **LangGraph ReAct agent** performs dynamic
multi-hop traversal — following chains across entities that neither vector search nor fixed
query templates can handle. Every answer is grounded in retrieved text and cites its source.

The goal isn't "another vector RAG." It's to show precisely *where embeddings fail*
(multi-hop questions) and to solve it with an agent that reasons over the graph step by step.

## Benchmark: Three Retrieval Strategies

All three systems were run on the same 60-question set, stratified by hop count. Accuracy is
keyword-match against expected answers; hop 0 questions are out-of-scope (testing whether the
system refuses to answer information not in the filing).

| Hops | Vector-only | Template-Hybrid | **Agent** |
|------|-------------|-----------------|-----------|
| 0 (out-of-scope) | 100% (6/6) | 100% (6/6) | **100% (6/6)** |
| 1 (single-hop) | 70% (21/30) | 80% (24/30) | **90% (27/30)** |
| 2 (multi-hop) | 50% (5/10) | 60% (6/10) | **100% (10/10)** |
| 3 (triple-hop) | 33% (1/3) | 0% (0/3) | **100% (3/3)** |
| **Overall** | **67% (33/49)** | **73% (36/49)** | **94% (46/49)** |

The story is in the last two rows. Fixed query templates score **0% on triple-hop** — they
can't compose arbitrary chains. Vector search degrades as hops increase. Only the agent,
which reasons over the graph and chains lookups dynamically, holds at 100%. All three refuse
out-of-scope questions correctly (no hallucination).

## What It Does

A standard vector RAG retrieves the passages most similar to a question. This works for
single-fact questions like *"What is the State Aid Decision?"* — the answer is in one passage.

It fails on *"Who regulates the company Apple depends on for search?"* The answer requires
following a chain: Apple -> depends on -> Google -> regulated by -> Department of Justice. No
single passage contains this; embedding similarity can't traverse it.

This system combines three ideas:

- **Knowledge Graph (Neo4j)** — entities as nodes, relationships as edges. Extracted with a
  multi-entity approach so the graph captures relationships between *any* two entities
  (e.g. `Google -> REGULATED_BY -> DOJ`), not just Apple-centric ones. This is what makes real
  chains possible.
- **Vector store (pgvector)** — semantic passage search for definitions and single facts.
- **LangGraph ReAct agent** — a reason -> act -> observe loop. The agent decides which lookup
  to run, inspects the result, and chains further lookups until it can answer. It uses the
  graph and vector queries as tools rather than following a fixed script.

Both stores share the same `chunk_id`, so every claim traces back to the exact source text.

## Architecture

```
INGESTION (once)
  SEC EDGAR 10-K -> clean + chunk -> GPT-4o extraction -> resolution + filtering
                                          |               (garbage, type-conditional,
                                          |                direction validation)
                        +-----------------+-----------------+
                        v                                   v
                 Neo4j (graph)                     pgvector (embeddings)
                 multi-entity relations            passages, HNSW index
                        +---------- shared chunk_id ---------+

QUERY - Agent (per question)
  question -> [reason] -> needs data? -> [act: graph_lookup / vector_lookup]
                 ^                              |
                 +------------- loop -----------+
                 |
                 +-> enough? -> [answer + validated citations] -> FastAPI /ask
```

### Agent loop

The agent's power is the loop. For *"Who regulates Google, which Apple depends on?"*:

1. **reason** -> "find what Apple depends on" -> `graph_lookup(Apple, DEPENDS_ON)` -> Google
2. **reason** -> "find Google's regulator" -> `graph_lookup(Google, REGULATED_BY)` -> DOJ
3. **reason** -> "enough" -> **answer** with citations

No template encodes this chain — the agent composes it. A deterministic guard prevents
repeating failed lookups, and the reasoning step runs on GPT-4o for reliable planning.

## Engineering Iterations

This system went through measured iterations, each validated against the benchmark:

1. **Baseline (GPT-4o-mini extraction):** Worked, but the graph carried extraction noise
   (mis-typed entities, laws tagged as regulators).
2. **Upgraded to GPT-4o + type-conditional filtering:** Cleaner graph (Company nodes 13->6),
   1-hop accuracy rose to +20% over baseline. A value like `U.S. dollar` is kept as a
   RiskFactor but dropped as a Location — filtering by context, not blanket blacklist.
3. **Discovered template-based multi-hop was fragile:** Some "intersection" templates were
   actually producing meaningless cartesian products. Measured this, removed them.
4. **Made extraction multi-entity:** Relationships now flow between any two entities, not
   just from Apple. This added the real chains (`Google -> DOJ`) that multi-hop needs.
5. **Added direction validation:** Freeing the source introduced reversed edges
   (`Regulator -> Company`). A deterministic rule — only Company/Person can be a relationship
   source — fixed this without another extraction pass.
6. **Built the LangGraph agent:** Replaced fixed templates with dynamic traversal. Triple-hop
   went from 0% (templates) to 100% (agent).

## Tech Stack

- **Python**, **FastAPI** — API layer
- **LangGraph** — ReAct agent orchestration (StateGraph, conditional edges, loop)
- **Neo4j** — knowledge graph, parameterized Cypher
- **PostgreSQL + pgvector** — vector store, HNSW cosine index
- **OpenAI GPT-4o / GPT-4o-mini** — extraction, reasoning, generation
- **sentence-transformers** (`all-MiniLM-L6-v2`) — local embeddings, no API cost
- **Docker** — Neo4j and pgvector containers

## Setup

**Prerequisites:** Docker, Python 3.11+, an OpenAI API key.

```bash
# Databases
docker run -d --name neo4j-rag -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/yourpassword neo4j:5-community
docker run -d --name pgvector-rag -p 5433:5432 \
  -e POSTGRES_PASSWORD=yourpassword pgvector/pgvector:pg16

pip install -r requirements.txt
# configure .env: OPENAI_API_KEY, NEO4J_*, POSTGRES_*
```

### Run

```bash
# Ingestion
python ingestion/fetch_sec.py
python ingestion/clean_and_chunk.py
python ingestion/extract.py
python ingestion/resolve_entities.py
python ingestion/load_neo4j.py
python retrieval/load_pgvector.py

# Agent (interactive)
cd retrieval && python agent.py

# API
cd api && python -m uvicorn main:app --reload    # http://localhost:8000/docs

# Benchmark (all three systems)
cd eval && python benchmark_triple.py
```

## Ontology

**Entities (7):** Company, Person, Product, Location, RiskFactor, Regulator, BusinessSegment

**Relationships (9):** OPERATES_IN, DEPENDS_ON, MANUFACTURES_IN, PRODUCES, FACES_RISK,
REGULATED_BY, COMPETES_WITH, HAS_EXECUTIVE, ACQUIRED

The ontology is deliberately constrained. An open-ended "extract everything" prompt produces
an unqueryable graph; a closed schema keeps it clean.

## Honest Limitations

Documented because it's what makes the accuracy numbers credible:

- **Multi-hop is bounded by graph density.** The agent can only traverse edges that exist.
  From a single filing, some chains are sparse — e.g. Epic Games has no regulator edge, so
  "who regulates Apple's competitor?" correctly returns "not found." A multi-document corpus
  would enrich the graph naturally.
- **Extraction noise remains.** A few mis-typed entities survive filtering (a court tagged as
  both Location and Regulator). LLM extraction is not perfect; the filters catch most.
- **Agent latency and cost.** Each multi-hop question is several LLM calls (reasoning on
  GPT-4o). Fine for accuracy-critical use, not for high-throughput low-latency serving.

## Roadmap

- **Multi-document corpus** to exercise cross-company chains and denser graphs.
- **Confidence-weighted edges** so the agent prefers high-confidence relationships.
- **Caching / smaller reasoning model** to reduce agent latency and cost.
- **LLM-as-judge evaluation** to complement keyword-match scoring.