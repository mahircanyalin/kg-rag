import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from router import route_question
from vector_query import query_vector
from graph_query import query_graph, query_graph_multihop
from answer import generate_answer, format_graph_context, format_vector_context


def ask(question: str) -> dict:
    routing = route_question(question)
    route = routing["route"]

    if route == "graph":
        # Multi-hop mu diye kontrol et (basit sezgi: soruda iki ilişki var mı)
        multihop_signals = ["and", "both", "related to", "where", "connection",
                            "relate", "involved in", "also"]
        is_multihop = sum(1 for s in multihop_signals if s in question.lower()) >= 2

        if is_multihop:
            graph_result = query_graph_multihop(question)
        else:
            graph_result = query_graph(question)

        context = format_graph_context(graph_result)
        chunk_ids = graph_result["chunk_ids"]
    else:
        vector_result = query_vector(question)
        context = format_vector_context(vector_result)
        chunk_ids = vector_result["chunk_ids"]

    answer_result = generate_answer(question, context, chunk_ids)
    return {
        "question": question,
        "route": route,
        "route_reason": routing.get("reason", ""),
        "answer": answer_result["answer"],
        "citations": answer_result["valid_citations"],
        "invalid_citations": answer_result["invalid_citations"],
    }

if __name__ == "__main__":
    sorular = [
        "Who are Apple's executives?",
        "What is the State Aid Decision?",
        "Which countries does Apple manufacture in?",
        "What are Apple's risk factors?",
        "Does Apple compete with Google?",
    ]

    for soru in sorular:
        print("\n" + "="*60)
        result = ask(soru)
        print(f"SORU: {result['question']}")
        print(f"YÖNLENDİRME: {result['route'].upper()} ({result['route_reason']})")
        print(f"CEVAP: {result['answer']}")
        print(f"KAYNAKLAR: {result['citations']}")
        if result['invalid_citations']:
            print(f"⚠️  UYDURULMUŞ: {result['invalid_citations']}")