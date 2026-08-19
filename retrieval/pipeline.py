import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from router import route_question
from graph_query import query_graph
from vector_query import query_vector
from answer import generate_answer, format_graph_context, format_vector_context


def ask(question: str) -> dict:
    """Tam pipeline: router -> sorgu -> kaynaklı cevap."""
    # 1. Router karar verir
    routing = route_question(question)
    route = routing["route"]

    # 2. Seçilen yola göre sorgula
    if route == "graph":
        graph_result = query_graph(question)
        context = format_graph_context(graph_result)
        chunk_ids = graph_result["chunk_ids"]
    else:  # vector
        vector_result = query_vector(question)
        context = format_vector_context(vector_result)
        chunk_ids = vector_result["chunk_ids"]

    # 3. Kaynaklı cevap üret
    answer_result = generate_answer(question, context, chunk_ids)

    # 4. Her şeyi tek pakette döndür
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