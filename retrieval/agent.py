import sys
import json
from pathlib import Path
from typing import TypedDict
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
import os
from openai import OpenAI
from langgraph.graph import StateGraph, END
from agents_tool import graph_lookup, vector_lookup
from graph_query import QUERY_TEMPLATES

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MAX_STEPS = 5  # sonsuz döngü koruması


# ---------- STATE ----------
class AgentState(TypedDict):
    question: str
    gathered_facts: list
    steps: int
    next_action: dict
    answer: str
    citations: list
    tried_queries: list   # ← yeni: denenmiş sorgular


# ---------- REASON NODE ----------
REASON_PROMPT = f"""You are a reasoning agent answering questions over a knowledge graph
about Apple's SEC 10-K filing.

Available graph relationships (for graph_lookup): {list(QUERY_TEMPLATES.keys())}

You have two tools:
1. graph_lookup(entity, relationship) — follow ONE relationship from an entity.
   Chain these for multi-hop. E.g. to find "Apple's competitor's regulator":
   first graph_lookup("Apple", "COMPETES_WITH"), then graph_lookup(<result>, "REGULATED_BY").
2. vector_lookup(query) — semantic search for definitions/descriptions.

Given the question and facts gathered so far, decide the NEXT action.
Return JSON:
- To query: {{"action": "graph_lookup", "entity": "...", "relationship": "..."}}
- Or:       {{"action": "vector_lookup", "query": "..."}}
- When you have enough to answer: {{"action": "answer"}}

Think step by step. For multi-hop questions, gather each hop before answering.
Do not repeat a lookup you already did."""


def reason_node(state: AgentState) -> AgentState:
    facts_summary = json.dumps(state["gathered_facts"], ensure_ascii=False)
    tried = json.dumps(state.get("tried_queries", []), ensure_ascii=False)
    resp = client.chat.completions.create(
        model="gpt-4o",   # ← muhakeme için güçlü model
        temperature=0,
        messages=[
            {"role": "system", "content": REASON_PROMPT},
            {"role": "user", "content":
                f"Question: {state['question']}\n\n"
                f"Facts gathered: {facts_summary}\n\n"
                f"ALREADY TRIED (do NOT repeat these): {tried}\n\n"
                f"Steps: {state['steps']}/{MAX_STEPS}\n"
                f"Next action? If a lookup returned empty, try a DIFFERENT "
                f"relationship or entity. Available relationships include "
                f"COMPETES_WITH, DEPENDS_ON, REGULATED_BY, HAS_EXECUTIVE, etc."},
        ],
        response_format={"type": "json_object"},
    )
    state["next_action"] = json.loads(resp.choices[0].message.content)
    return state


# ---------- ACT NODE ----------
def act_node(state: AgentState) -> AgentState:
    action = state["next_action"]
    state["steps"] += 1

    # denenen sorguyu kaydet
    if "tried_queries" not in state:
        state["tried_queries"] = []

    if action["action"] == "graph_lookup":
        query_sig = f"{action['entity']} {action['relationship']}"
        state["tried_queries"].append(query_sig)
        result = graph_lookup(action["entity"], action["relationship"])
        state["gathered_facts"].append({
            "type": "graph",
            "query": query_sig,
            "results": result["results"],
            "chunk_ids": result["chunk_ids"],
        })
    elif action["action"] == "vector_lookup":
        state["tried_queries"].append(f"vector: {action['query']}")
        result = vector_lookup(action["query"])
        state["gathered_facts"].append({
            "type": "vector",
            "query": action["query"],
            "passages": result["passages"],
            "chunk_ids": result["chunk_ids"],
        })
    return state


# ---------- ANSWER NODE ----------
ANSWER_PROMPT = """Answer the question using ONLY the gathered facts.
Cite source chunk_ids like [chunk_0108] for every claim.
If facts are insufficient, say so honestly.
Return JSON: {"answer": "...", "cited_chunks": ["chunk_0108", ...]}"""


def answer_node(state: AgentState) -> AgentState:
    facts = json.dumps(state["gathered_facts"], ensure_ascii=False)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": ANSWER_PROMPT},
            {"role": "user", "content":
                f"Question: {state['question']}\n\nGathered facts: {facts}"},
        ],
        response_format={"type": "json_object"},
    )
    result = json.loads(resp.choices[0].message.content)
    state["answer"] = result.get("answer", "")
    state["citations"] = result.get("cited_chunks", [])
    return state


# ---------- KOŞULLU EDGE ----------
def should_continue(state: AgentState) -> str:
    """reason'dan sonra: act mı, answer mı?"""
    action = state["next_action"].get("action")
    if action == "answer" or state["steps"] >= MAX_STEPS:
        return "answer"
    return "act"


# ---------- GRAF KURULUMU ----------
def build_agent():
    graph = StateGraph(AgentState)
    graph.add_node("reason", reason_node)
    graph.add_node("act", act_node)
    graph.add_node("answer", answer_node)

    graph.set_entry_point("reason")
    graph.add_conditional_edges("reason", should_continue, {
        "act": "act",
        "answer": "answer",
    })
    graph.add_edge("act", "reason")   # ← DÖNGÜ: act'ten reason'a geri
    graph.add_edge("answer", END)

    return graph.compile()


agent = build_agent()


def ask_agent(question: str) -> dict:
    initial = {
        "question": question,
        "gathered_facts": [],
        "steps": 0,
        "next_action": {},
        "answer": "",
        "citations": [],
        "tried_queries": [],  # ← yeni
    }
    final = agent.invoke(initial)
    return {
        "question": question,
        "answer": final["answer"],
        "citations": final["citations"],
        "steps": final["steps"],
        "facts": final["gathered_facts"],
    }


if __name__ == "__main__":
    test = [
        "Who are Apple's executives?",
        "Who regulates Apple's competitors?",
        "What is Apple's relationship with Google, and who regulates Google?",  # ← bu zincir grafta VAR
    ]
    for soru in test:
        print("\n" + "="*60)
        print(f"SORU: {soru}")
        result = ask_agent(soru)
        print(f"ADIM SAYISI: {result['steps']}")
        print(f"CEVAP: {result['answer']}")
        print(f"KAYNAKLAR: {result['citations']}")
        print(f"\nİZLENEN YOL:")
        for f in result["facts"]:
            print(f"  → {f['query']}: {f.get('results', f.get('passages'))}")