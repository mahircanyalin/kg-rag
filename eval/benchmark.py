import sys
import json
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).parent.parent / "retrieval"))

from pipeline import ask                 # template-hybrid (router + graf/vektör)
from baseline import vector_only_ask     # sadece-vektör
from agent import ask_agent              # LangGraph agent

EVAL_DIR = Path(__file__).parent


def check_answer(answer: str, keywords: list, is_oos: bool = False) -> bool:
    """Cevap doğru mu kontrol et.
    Normal soru: keyword'lerin en az yarısı olmalı.
    Out-of-scope: ret ifadelerinden HERHANGİ biri yeterli."""
    a = answer.lower()
    hits = sum(1 for kw in keywords if kw.lower() in a)
    if is_oos:
        return hits >= 1   # tek ret ifadesi yeter
    return hits >= (len(keywords) + 1) // 2


def run_benchmark():
    with open(EVAL_DIR / "questions.json", "r", encoding="utf-8") as f:
        questions = json.load(f)

    # sistem -> hop -> {correct, total}
    scores = {
        "vector": defaultdict(lambda: {"c": 0, "t": 0}),
        "hybrid": defaultdict(lambda: {"c": 0, "t": 0}),
        "agent": defaultdict(lambda: {"c": 0, "t": 0}),
    }
    details = []

    for i, q in enumerate(questions):
        question = q["question"]
        hops = q["hops"]
        kw = q["expected_keywords"]

        # üç sistemi de çalıştır
        is_oos = q["type"] == "out_of_scope"
        try:
            v = vector_only_ask(question)
            v_ok = check_answer(v["answer"], kw, is_oos)
        except Exception:
            v_ok = False
        try:
            h = ask(question)
            h_ok = check_answer(h["answer"], kw, is_oos)
        except Exception:
            h_ok = False
        try:
            a = ask_agent(question)
            a_ok = check_answer(a["answer"], kw, is_oos)
        except Exception:
            a_ok = False

        for sys_name, ok in [("vector", v_ok), ("hybrid", h_ok), ("agent", a_ok)]:
            scores[sys_name][hops]["t"] += 1
            scores[sys_name][hops]["c"] += int(ok)

        details.append({
            "question": question, "hops": hops,
            "vector": v_ok, "hybrid": h_ok, "agent": a_ok,
        })
        print(f"[{hops}h] V{'✓' if v_ok else '✗'} "
              f"H{'✓' if h_ok else '✗'} A{'✓' if a_ok else '✗'} | {question[:45]}")

    # TABLO
    print("\n" + "="*66)
    print("ÜÇLÜ BENCHMARK: Vector-only vs Template-Hybrid vs Agent")
    print("="*66)
    print(f"{'Hop':<6}{'Vector':<16}{'Hybrid':<16}{'Agent':<16}")
    print("-"*54)

    all_hops = sorted(set(h for s in scores.values() for h in s))
    for hop in all_hops:
        row = f"{hop:<6}"
        for sys_name in ["vector", "hybrid", "agent"]:
            s = scores[sys_name][hop]
            pct = 100 * s["c"] / s["t"] if s["t"] else 0
            row += f"{pct:>4.0f}% ({s['c']}/{s['t']})    "
        print(row)

    # genel toplam
    print("-"*54)
    row = f"{'TÜM':<6}"
    for sys_name in ["vector", "hybrid", "agent"]:
        tc = sum(s["c"] for s in scores[sys_name].values())
        tt = sum(s["t"] for s in scores[sys_name].values())
        pct = 100 * tc / tt if tt else 0
        row += f"{pct:>4.0f}% ({tc}/{tt})   "
    print(row)

    with open(EVAL_DIR / "results_triple.json", "w", encoding="utf-8") as f:
        json.dump(details, f, ensure_ascii=False, indent=2)
    print(f"\nDetaylar: results_triple.json")


if __name__ == "__main__":
    run_benchmark()