import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


# ---------- KATMAN 1: ÇÖP FİLTRESİ ----------

def is_garbage(name: str) -> bool:
    """İsim tarih, sayı, döküman referansı gibi çöpse True döner."""
    n = name.strip()

    # Boş veya çok kısa
    if len(n) < 2:
        return True

    # Sadece sayı, yüzde, para (örn. "2024", "4.07 %", "€500 million")
    if re.match(r"^[€$£]?\s*[\d.,]+\s*%?$", n):
        return True
    if re.search(r"\d+\s*%", n):  # yüzde içeren
        return True
    if re.match(r"^€|^\$", n):  # para ile başlayan
        return True

    # Tarihler (örn. "September 27, 2025", "May 2025", "2024")
    months = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    if re.search(months, n):
        return True
    if re.match(r"^\d{4}$", n):  # tek başına yıl
        return True
    if re.match(r"^Fiscal Year", n):
        return True
    if re.match(r"^September \d", n):
        return True

    # Döküman/bölüm referansları
    doc_refs = ["Item ", "Part ", "Form 10-K", "Regulation S-K",
                "Section ", "ASU ", "Rule ", "§", "Note ", "Notes"]
    if any(n.startswith(ref) or n == ref.strip() for ref in doc_refs):
        return True

    # Kara liste (jenerik kelimeler, döküman adları)
    blacklist = {
        "products", "services", "accessories", "wearables", "smartphone",
        "smartphones", "tablet", "tablets", "personal computer",
        "personal computers", "technology", "machine learning",
        "artificial intelligence", "semiconductor", "governmental authorities",
        "board", "total", "corporate", "notes",
        "s&p 500 index", "dow jones u.s. technology total stock market index",
        "windows", "android", "xbox", "playstation", "nintendo",
        "2025 form 10-k", "2026 proxy statement",
    }
    if n.lower() in blacklist:
        return True

    return False


# ---------- KATMAN 2: KANONİKLEŞTİRME ----------

# Elle eşleme: varyasyon -> kanonik isim
ALIAS_MAP = {
    "aapl": "Apple",
    "apple inc.": "Apple",
    "apple inc": "Apple",
    "google llc": "Google",
    "epic games, inc.": "Epic Games",
    "eu": "European Union",
    "sec": "SEC",
    "securities and exchange commission": "SEC",
    "u.s. securities and exchange commission": "SEC",
    "doj": "Department of Justice",
    "u.s. department of justice": "Department of Justice",
    "ecj": "European Court of Justice",
    "dma": "Digital Markets Act",
    "fasb": "Financial Accounting Standards Board",
    "pcaob": "Public Company Accounting Oversight Board",
    "u.s.": "United States",
    "us": "United States",
}


def normalize(name: str) -> str:
    """İsmi kanonik forma indirir."""
    n = name.strip()

    # Önce elle eşleme sözlüğüne bak
    if n.lower() in ALIAS_MAP:
        return ALIAS_MAP[n.lower()]

    # Şirket eklerini at (Inc., LLC, Corp., N.A., LLP)
    n = re.sub(r",?\s+(Inc\.?|LLC|Corp\.?|Ltd\.?|N\.A\.?|LLP)$", "", n)

    return n.strip()


def resolve_all():
    """Tüm çıkarımları oku, filtrele, kanonikleştir, kaydet."""
    with open(DATA_DIR / "extractions.json", "r", encoding="utf-8") as f:
        results = json.load(f)

    clean_results = {}
    garbage_count = 0

    for cid, data in results.items():
        clean_entities = []
        for e in data["entities"]:
            name = e["name"]
            if is_garbage(name):
                garbage_count += 1
                continue
            e["name"] = normalize(name)  # kanonik isme çevir
            clean_entities.append(e)

        clean_relationships = []
        for r in data["relationships"]:
            src, tgt = r["source"], r["target"]
            # İki uç da çöp değilse ilişkiyi tut
            if is_garbage(src) or is_garbage(tgt):
                garbage_count += 1
                continue
            r["source"] = normalize(src)
            r["target"] = normalize(tgt)
            clean_relationships.append(r)

        clean_results[cid] = {
            "entities": clean_entities,
            "relationships": clean_relationships,
        }

    # Kaydet
    with open(DATA_DIR / "resolved.json", "w", encoding="utf-8") as f:
        json.dump(clean_results, f, ensure_ascii=False, indent=2)

    print(f"Filtrelenen çöp: {garbage_count}")
    print(f"Kaydedildi: resolved.json")
    return clean_results


if __name__ == "__main__":
    resolve_all()