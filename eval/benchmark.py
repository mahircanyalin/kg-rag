import sys
import json
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).parent.parent / "retrieval"))
from pipeline import ask  # hibrit sistem
from baseline import vector_only_ask  # sadece-vektör
EVAL_DIR = Path(__file__).parent


def check_answer(answer: str, keywords: list) -> bool:
    """Cevap beklenen anahtar kelimelerden en az yarısını içeriyor mu?"""
    answer_lower = answer.lower()
    hits = sum(1 for kw in keywords if kw.lower() in answer_lower)
    return hits >= (len(keywords) + 1) // 2  # en az yarısı


def run_benchmark():
    with open(EVAL_DIR / "questions.json", "r", encoding="utf-8") as f:
        questions = json.load(f)

    # Sonuçları hop sayısına göre topla
    hybrid_scores = defaultdict(lambda: {"correct": 0, "total": 0})
    baseline_scores = defaultdict(lambda: {"correct": 0, "total": 0})

    details = []

    for q in questions:
        question = q["question"]
        hops = q["hops"]
        keywords = q["expected_keywords"]

        # Hibrit sistem
        try:
            h_result = ask(question)
            h_correct = check_answer(h_result["answer"], keywords)
        except Exception as e:
            h_correct = False
            h_result = {"answer": f"HATA: {e}", "route": "error"}

        # Baseline (sadece-vektör)
        try:
            b_result = vector_only_ask(question)
            b_correct = check_answer(b_result["answer"], keywords)
        except Exception as e:
            b_correct = False
            b_result = {"answer": f"HATA: {e}"}

        hybrid_scores[hops]["total"] += 1
        hybrid_scores[hops]["correct"] += int(h_correct)
        baseline_scores[hops]["total"] += 1
        baseline_scores[hops]["correct"] += int(b_correct)

        details.append({
            "question": question,
            "hops": hops,
            "hybrid_correct": h_correct,
            "baseline_correct": b_correct,
            "route": h_result.get("route", "?"),
        })
        print(f"[{hops}-hop] {'✓' if h_correct else '✗'}H "
              f"{'✓' if b_correct else '✗'}B | {question[:50]}")

    # TABLO
    print("\n" + "="*60)
    print("BENCHMARK: Hibrit (Graf+Vektör) vs Sadece-Vektör")
    print("="*60)
    print(f"{'Hop':<6}{'Hibrit':<15}{'Baseline':<15}{'Δ Fark':<10}")
    print("-"*46)

    all_hops = sorted(set(list(hybrid_scores.keys()) + list(baseline_scores.keys())))
    for hop in all_hops:
        h = hybrid_scores[hop]
        b = baseline_scores[hop]
        h_pct = 100 * h["correct"] / h["total"] if h["total"] else 0
        b_pct = 100 * b["correct"] / b["total"] if b["total"] else 0
        delta = h_pct - b_pct
        print(f"{hop:<6}{h_pct:>5.0f}% ({h['correct']}/{h['total']})   "
              f"{b_pct:>5.0f}% ({b['correct']}/{b['total']})   "
              f"{delta:+.0f}%")

    # Sonuçları kaydet
    with open(EVAL_DIR / "results.json", "w", encoding="utf-8") as f:
        json.dump(details, f, ensure_ascii=False, indent=2)
    print(f"\nDetaylar: results.json")


if __name__ == "__main__":
    run_benchmark()