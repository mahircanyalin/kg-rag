import json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "data"

with open(DATA_DIR / "resolved.json", "r", encoding="utf-8") as f:
    results = json.load(f)

# Tüm ilişkileri topla
all_rels = []
for cid, data in results.items():
    for r in data["relationships"]:
        all_rels.append(r)

print(f"Toplam ilişki: {len(all_rels)}\n")

# İlişki tipine göre dağılım
by_type = defaultdict(int)
for r in all_rels:
    by_type[r["type"]] += 1

print("=== İLİŞKİ TİPİ DAĞILIMI ===")
for rtype, count in sorted(by_type.items(), key=lambda x: -x[1]):
    print(f"  {rtype}: {count}")

# KRİTİK: Kaç ilişki Apple-merkezli DEĞİL? (multi-hop için)
non_apple = [r for r in all_rels if r["source"] != "Apple"]
print(f"\n=== APPLE-MERKEZLİ OLMAYAN İLİŞKİLER ({len(non_apple)}) ===")
print("(Bunlar multi-hop zincirini mümkün kılan kenarlar)")
for r in non_apple:
    print(f"  {r['source']} -[{r['type']}]-> {r['target']}")

# Kaynak düğüm çeşitliliği (kaç farklı düğümden ilişki çıkıyor?)
sources = set(r["source"] for r in all_rels)
print(f"\n=== KAYNAK DÜĞÜM ÇEŞİTLİLİĞİ ===")
print(f"Farklı kaynak sayısı: {len(sources)}")
print(f"Kaynaklar: {sorted(sources)}")