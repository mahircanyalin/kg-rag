import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "retrieval"))
from agent import ask_agent

with open("questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)

# sadece out-of-scope soruları
oos = [q for q in questions if q["type"] == "out_of_scope"]

for q in oos:
    result = ask_agent(q["question"])
    print(f"\nSORU: {q['question']}")
    print(f"CEVAP: {result['answer']}")
    print(f"KAYNAKLAR: {result['citations']}")
    print(f"ADIM: {result['steps']}")
    print(f"İZLENEN YOL: {[f['query'] for f in result['facts']]}")