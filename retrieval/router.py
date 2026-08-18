import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ROUTER_PROMPT = """You are a query router for a hybrid retrieval system over SEC 10-K filings.
Decide whether a question should be answered using the GRAPH or the VECTOR store.

Use GRAPH for:
- Questions about relationships or connections between entities
- Multi-hop questions (following a chain across entities)
- "Who are the executives", "which countries", "which regulators"
- Aggregations over relationships ("how many suppliers", "list all...")
- Comparisons across entities

Use VECTOR for:
- Definitions and explanations ("what is...", "describe...")
- Single-fact lookups from a passage
- Policy or risk descriptions ("what are the risk factors")
- Questions answered by a single paragraph of text

Respond with ONLY valid JSON:
{"route": "graph" or "vector", "confidence": 0.0-1.0, "reason": "brief reason"}"""

# Gerçek verimizden türetilmiş few-shot örnekler
FEW_SHOT = [
    {"role": "user", "content": "Who are Apple's executives?"},
    {"role": "assistant", "content": '{"route": "graph", "confidence": 0.95, "reason": "Executive relationships are structured in the graph"}'},
    {"role": "user", "content": "What are Apple's main risk factors?"},
    {"role": "assistant", "content": '{"route": "vector", "confidence": 0.9, "reason": "Risk factors are described in text passages"}'},
    {"role": "user", "content": "Which countries does Apple manufacture in?"},
    {"role": "assistant", "content": '{"route": "graph", "confidence": 0.9, "reason": "Manufacturing locations are graph relationships"}'},
    {"role": "user", "content": "What is the Digital Markets Act?"},
    {"role": "assistant", "content": '{"route": "vector", "confidence": 0.85, "reason": "Definitional question answered by a passage"}'},
]


def route_question(question: str) -> dict:
    """Soruyu graf veya vektöre yönlendir."""
    messages = [{"role": "system", "content": ROUTER_PROMPT}]
    messages.extend(FEW_SHOT)
    messages.append({"role": "user", "content": question})

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=messages,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


if __name__ == "__main__":
    test_sorular = [
        "Who are Apple's executives?",
        "What are Apple's risk factors?",
        "Which countries does Apple manufacture in?",
        "What regulators oversee Apple?",
        "What is the State Aid Decision?",
        "Does Apple compete with Google?",
    ]

    for soru in test_sorular:
        result = route_question(soru)
        print(f"\nSORU: {soru}")
        print(f"  → {result['route'].upper()} "
              f"(güven: {result['confidence']}) — {result['reason']}")