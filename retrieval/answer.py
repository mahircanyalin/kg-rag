import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from graph_query import query_graph
from vector_query import query_vector

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ANSWER_PROMPT = """You answer questions about Apple's SEC 10-K filing.
You are given retrieved context (either graph facts or text passages).

STRICT RULES:
- Answer ONLY using the provided context. Never use outside knowledge.
- If the context does not contain the answer, say "The filing does not provide this information."
- Cite the source chunk_id for every claim, like [chunk_0049].
- Be concise and factual.

Return JSON:
{"answer": "your answer with [chunk_id] citations", "cited_chunks": ["chunk_0049", ...]}"""


def format_graph_context(graph_result: dict) -> str:
    """Graf sonucunu okunabilir metne çevir."""
    entity = graph_result.get("entity", "Apple")
    rel = graph_result.get("relationship", "")
    results = graph_result.get("results", [])
    chunk_ids = graph_result.get("chunk_ids", [])

    # Graf ilişkisini cümleye çevir
    lines = [f"Graph facts about {entity} ({rel}):"]
    for r in results:
        lines.append(f"- {entity} {rel} {r}")
    lines.append(f"Source chunks: {chunk_ids}")
    return "\n".join(lines)


def format_vector_context(vector_result: dict) -> str:
    """Vektör pasajlarını metne çevir."""
    lines = ["Retrieved passages:"]
    for p in vector_result.get("passages", []):
        lines.append(f"[{p['chunk_id']}] {p['text']}")
    return "\n".join(lines)


def generate_answer(question: str, context: str, available_chunks: list) -> dict:
    """Context'e dayanarak kaynaklı cevap üret, citation'ları doğrula."""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": ANSWER_PROMPT},
            {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}"},
        ],
        response_format={"type": "json_object"},
    )
    result = json.loads(resp.choices[0].message.content)

    # CITATION DOĞRULAMA: her citation gerçekten var olan bir chunk mı?
    cited = result.get("cited_chunks", [])
    valid_citations = [c for c in cited if c in available_chunks]
    invalid_citations = [c for c in cited if c not in available_chunks]

    result["valid_citations"] = valid_citations
    result["invalid_citations"] = invalid_citations  # uydurulmuş kaynaklar
    return result


if __name__ == "__main__":

    # Graf örneği
    print("="*60)
    print("GRAF ÖRNEĞİ")
    print("="*60)
    soru1 = "Which countries does Apple manufacture in?"
    g = query_graph(soru1)
    ctx1 = format_graph_context(g)
    ans1 = generate_answer(soru1, ctx1, g["chunk_ids"])
    print(f"\nSORU: {soru1}")
    print(f"CEVAP: {ans1['answer']}")
    print(f"Geçerli kaynaklar: {ans1['valid_citations']}")
    print(f"Uydurulmuş kaynaklar: {ans1['invalid_citations']}")

    # Vektör örneği
    print("\n" + "="*60)
    print("VEKTÖR ÖRNEĞİ")
    print("="*60)
    soru2 = "What is the State Aid Decision?"
    v = query_vector(soru2)
    ctx2 = format_vector_context(v)
    ans2 = generate_answer(soru2, ctx2, v["chunk_ids"])
    print(f"\nSORU: {soru2}")
    print(f"CEVAP: {ans2['answer']}")
    print(f"Geçerli kaynaklar: {ans2['valid_citations']}")
    print(f"Uydurulmuş kaynaklar: {ans2['invalid_citations']}")