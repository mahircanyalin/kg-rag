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

    # Kara liste (jenerik kelimeler, döküman adları, rakip ürünler, endeksler)
    blacklist = {
        # jenerik kategoriler
        "products", "services", "accessories", "wearables", "smartphone",
        "smartphones", "tablet", "tablets", "personal computer",
        "personal computers", "technology", "machine learning",
        "artificial intelligence", "semiconductor", "governmental authorities",
        "board", "total", "corporate", "notes",
        # rakip ürünler (Apple'ın değil)
        "windows", "android", "xbox", "playstation", "nintendo",
        # endeksler (şirket değil)
        "s&p 500 index", "dow jones u.s. technology total stock market index",
        # jenerik "şirket" olarak yanlış tiplenenler
        "global semiconductor industry", "audit and finance committee",
        "committee of sponsoring organizations of the treadway commission",
        # menkul kıymetler / finansal araçlar (ürün değil)
        "u.s. treasury securities", "u.s. agency securities",
        "non-u.s. government securities", "2022 employee stock plan",
        # döküman adları
        "2025 form 10-k", "2026 proxy statement",
    }
    if n.lower() in blacklist:
        return True

    return False


# ---------- TİP-KOŞULLU FİLTRE ----------
# Bazı isimler bir tipte geçerli, başka tipte çöp.
# Örn: "U.S. dollar" RiskFactor olarak doğru (döviz riski), Location olarak yanlış.
TYPE_CONDITIONAL_GARBAGE = {
    # isim (lowercase) -> bu tiplerde ATILIR
    "u.s. dollar": {"Location", "Product", "Company"},
    "foreign currencies": {"Location", "Company"},
    "europe": {"Regulator"},           # kıta regülatör olamaz
    "european union": {"Regulator"},
    "united states": {"Regulator"},
    "u.s.": {"Regulator"},
    "ireland": {"Regulator"},
}


def is_garbage_for_type(name: str, etype: str) -> bool:
    """İsim belirli bir tipte çöp mü? (tip-koşullu)"""
    bad_types = TYPE_CONDITIONAL_GARBAGE.get(name.lower().strip())
    if bad_types and etype in bad_types:
        return True
    return False


# ---------- KATMAN 2: KANONİKLEŞTİRME ----------

# Elle eşleme: varyasyon -> kanonik isim
ALIAS_MAP = {
    # şirketler
    "aapl": "Apple",
    "apple inc.": "Apple",
    "apple inc": "Apple",
    "google llc": "Google",
    "epic games, inc.": "Epic Games",
    "the nasdaq stock market llc": "Nasdaq",
    "ernst & young llp": "Ernst & Young",
    "the bank of new york mellon trust company, n.a.": "BNY Mellon",
    # regülatörler (kısaltma -> tam ad tutarlılığı: SEC'i kısa tutuyoruz)
    "securities and exchange commission": "SEC",
    "u.s. securities and exchange commission": "SEC",
    "doj": "Department of Justice",
    "u.s. department of justice": "Department of Justice",
    "ecj": "European Court of Justice",
    "dma": "Digital Markets Act",
    "fasb": "Financial Accounting Standards Board",
    "pcaob": "Public Company Accounting Oversight Board",
    "commission": "European Commission",
    # lokasyonlar
    "u.s.": "United States",
    "us": "United States",
    "eu": "European Union",
    "china mainland": "China",
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

    # entity adı -> tipi (tip-koşullu ilişki filtresi için)
    entity_type_map = {}

    for cid, data in results.items():
        clean_entities = []
        for e in data["entities"]:
            name = e["name"]
            etype = e.get("type", "")

            # genel çöp filtresi
            if is_garbage(name):
                garbage_count += 1
                continue
            # tip-koşullu çöp filtresi
            if is_garbage_for_type(name, etype):
                garbage_count += 1
                continue

            canonical = normalize(name)
            e["name"] = canonical
            entity_type_map[canonical] = etype
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