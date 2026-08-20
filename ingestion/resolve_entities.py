import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


# ---------- KATMAN 1: ÇÖP FİLTRESİ ----------

def is_garbage(name: str) -> bool:
    """İsim tarih, sayı, döküman referansı gibi çöpse True döner."""
    n = name.strip()

    if len(n) < 2:
        return True
    if re.match(r"^[€$£]?\s*[\d.,]+\s*%?$", n):
        return True
    if re.search(r"\d+\s*%", n):
        return True
    if re.match(r"^€|^\$", n):
        return True

    months = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    if re.search(months, n):
        return True
    if re.match(r"^\d{4}$", n):
        return True
    if re.match(r"^Fiscal Year", n):
        return True
    if re.match(r"^September \d", n):
        return True

    doc_refs = ["Item ", "Part ", "Form 10-K", "Regulation S-K",
                "Section ", "ASU ", "Rule ", "§", "Note ", "Notes"]
    if any(n.startswith(ref) or n == ref.strip() for ref in doc_refs):
        return True

    blacklist = {
        "products", "services", "accessories", "wearables", "smartphone",
        "smartphones", "tablet", "tablets", "personal computer",
        "personal computers", "technology", "machine learning",
        "artificial intelligence", "semiconductor", "governmental authorities",
        "board", "total", "corporate", "notes",
        "windows", "android", "xbox", "playstation", "nintendo",
        "s&p 500 index", "dow jones u.s. technology total stock market index",
        "global semiconductor industry", "audit and finance committee",
        "committee of sponsoring organizations of the treadway commission",
        "u.s. treasury securities", "u.s. agency securities",
        "non-u.s. government securities", "2022 employee stock plan",
        "2025 form 10-k", "2026 proxy statement",
        "outsourcing partners",  # jenerik, gerçek şirket değil
    }
    if n.lower() in blacklist:
        return True

    return False


# ---------- TİP-KOŞULLU FİLTRE ----------
TYPE_CONDITIONAL_GARBAGE = {
    "u.s. dollar": {"Location", "Product", "Company"},
    "foreign currencies": {"Location", "Company"},
    "europe": {"Regulator"},
    "european union": {"Regulator"},
    "united states": {"Regulator"},
    "u.s.": {"Regulator"},
    "ireland": {"Regulator"},
}


def is_garbage_for_type(name: str, etype: str) -> bool:
    bad_types = TYPE_CONDITIONAL_GARBAGE.get(name.lower().strip())
    if bad_types and etype in bad_types:
        return True
    return False


# ---------- KATMAN 2: KANONİKLEŞTİRME ----------

ALIAS_MAP = {
    "aapl": "Apple",
    "apple inc.": "Apple",
    "apple inc": "Apple",
    "google llc": "Google",
    "epic games, inc.": "Epic Games",
    "the nasdaq stock market llc": "Nasdaq",
    "ernst & young llp": "Ernst & Young",
    "the bank of new york mellon trust company, n.a.": "BNY Mellon",
    "securities and exchange commission": "SEC",
    "u.s. securities and exchange commission": "SEC",
    "doj": "Department of Justice",
    "u.s. department of justice": "Department of Justice",
    "ecj": "European Court of Justice",
    "dma": "Digital Markets Act",
    "fasb": "Financial Accounting Standards Board",
    "pcaob": "Public Company Accounting Oversight Board",
    "commission": "European Commission",
    "u.s.": "United States",
    "us": "United States",
    "eu": "European Union",
    "china mainland": "China",
}


def normalize(name: str) -> str:
    n = name.strip()
    if n.lower() in ALIAS_MAP:
        return ALIAS_MAP[n.lower()]
    n = re.sub(r",?\s+(Inc\.?|LLC|Corp\.?|Ltd\.?|N\.A\.?|LLP)$", "", n)
    return n.strip()


# ---------- KATMAN 3: YÖN DOĞRULAMA ----------
# Sadece Company ve Person bir ilişkinin KAYNAĞI olabilir.
# Bir Regulator/RiskFactor/Location/Segment/Product kaynaksa, yön terstir → at.
VALID_SOURCE_TYPES = {"Company", "Person"}

# Bazı ilişkilerin hedefi belirli tipte olmalı (ekstra doğrulama)
EXPECTED_TARGET_TYPE = {
    "HAS_EXECUTIVE": "Person",       # hedef kişi olmalı
    "REGULATED_BY": "Regulator",     # hedef kurum olmalı
    "FACES_RISK": "RiskFactor",      # hedef risk olmalı
    "PRODUCES": "Product",           # hedef ürün olmalı
    "MANUFACTURES_IN": "Location",   # hedef yer olmalı
}


def resolve_all():
    with open(DATA_DIR / "extractions.json", "r", encoding="utf-8") as f:
        results = json.load(f)

    # ÖNCE: tüm entity'lerin kanonik ad -> tip haritasını çıkar
    entity_type_map = {}
    for cid, data in results.items():
        for e in data["entities"]:
            name = e["name"]
            etype = e.get("type", "")
            if is_garbage(name) or is_garbage_for_type(name, etype):
                continue
            entity_type_map[normalize(name)] = etype

    clean_results = {}
    garbage_count = 0
    direction_dropped = 0

    for cid, data in results.items():
        # entity temizliği
        clean_entities = []
        for e in data["entities"]:
            name = e["name"]
            etype = e.get("type", "")
            if is_garbage(name) or is_garbage_for_type(name, etype):
                garbage_count += 1
                continue
            e["name"] = normalize(name)
            clean_entities.append(e)

        # ilişki temizliği + YÖN DOĞRULAMA
        clean_relationships = []
        for r in data["relationships"]:
            src = normalize(r["source"])
            tgt = normalize(r["target"])

            # çöp uç kontrolü
            if is_garbage(r["source"]) or is_garbage(r["target"]):
                garbage_count += 1
                continue

            # YÖN DOĞRULAMA: kaynak Company/Person mı?
            src_type = entity_type_map.get(src)
            if src_type is not None and src_type not in VALID_SOURCE_TYPES:
                # kaynak geçersiz tipte (Regulator/RiskFactor/Location...) → ters yön → at
                direction_dropped += 1
                continue

            r["source"] = src
            r["target"] = tgt
            clean_relationships.append(r)

        clean_results[cid] = {
            "entities": clean_entities,
            "relationships": clean_relationships,
        }

    with open(DATA_DIR / "resolved.json", "w", encoding="utf-8") as f:
        json.dump(clean_results, f, ensure_ascii=False, indent=2)

    print(f"Filtrelenen çöp: {garbage_count}")
    print(f"Ters yön nedeniyle atılan ilişki: {direction_dropped}")
    print(f"Kaydedildi: resolved.json")
    return clean_results


if __name__ == "__main__":
    resolve_all()