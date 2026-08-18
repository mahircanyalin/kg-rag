import json

with open("data/apple_chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

print(f"Toplam {len(chunks)} chunk\n")

# Belirli aralıklarla chunk'lara göz at
for i in [0, 30, 50, 70, 90, 110, 130, 150]:
    if i < len(chunks):
        print(f"===== chunk_{i:04d} =====")
        print(chunks[i]["text"][:250])
        print()