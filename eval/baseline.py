import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "retrieval"))

from vector_query import query_vector
from answer import generate_answer, format_vector_context


def vector_only_ask(question: str) -> dict:
    """Baseline: her soruyu SADECE vektöre sor (graf yok)."""
    vector_result = query_vector(question)
    context = format_vector_context(vector_result)
    answer_result = generate_answer(question, context, vector_result["chunk_ids"])
    return {
        "question": question,
        "answer": answer_result["answer"],
        "citations": answer_result["valid_citations"],
    }