import json
from collections import defaultdict

with open("/Users/canyalinn/PycharmProjects/kg-rag/ingestion/data/extractions.json", "r", encoding="utf-8") as f:
    results = json.load(f)

by_type = defaultdict(set)

for cid, data in results.items():
    for e in data["entities"]:
        by_type[e["type"]].add(e["name"])

for etype, names in by_type.items():
    print(f"\n===== {etype} ({len(names)} benzersiz) =====")
    for name in sorted(names):
        print(f"  {name}")