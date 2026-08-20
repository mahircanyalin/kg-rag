import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from graph_query import QUERY_TEMPLATES, driver
from vector_query import query_vector


def graph_lookup(entity: str, relationship: str) -> dict:
    """Bir düğümden bir ilişkiyi takip et (tek-hop). Agent bunu zincirler."""
    if relationship not in QUERY_TEMPLATES:
        return {
            "results": [],
            "chunk_ids": [],
            "note": f"Unknown relationship '{relationship}'. Valid: {list(QUERY_TEMPLATES.keys())}"
        }

    template = QUERY_TEMPLATES[relationship]
    with driver.session() as session:
        records = session.run(template, entity=entity)
        results, chunk_ids = [], set()
        for rec in records:
            results.append(rec["result"])
            if rec["chunk_id"]:
                chunk_ids.add(rec["chunk_id"])

    return {
        "results": results,
        "chunk_ids": list(chunk_ids),
        "note": f"{entity} {relationship} -> {len(results)} results"
    }


def vector_lookup(query: str) -> dict:
    """Anlamsal arama (tek-fact/tanım soruları için)."""
    result = query_vector(query, k=2)
    return {
        "passages": [p["text"][:300] for p in result["passages"]],
        "chunk_ids": result["chunk_ids"],
    }


if __name__ == "__main__":
    # Hızlı test
    print(graph_lookup("Apple", "COMPETES_WITH"))
    print(graph_lookup("Google", "REGULATED_BY"))