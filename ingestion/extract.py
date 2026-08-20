import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Ontolojimiz — modele bu kapalı listeyi dayatıyoruz
ENTITY_TYPES = ["Company", "Person", "Product", "Location",
                "RiskFactor", "Regulator", "BusinessSegment"]
RELATION_TYPES = ["OPERATES_IN", "DEPENDS_ON", "MANUFACTURES_IN",
                  "PRODUCES", "FACES_RISK", "REGULATED_BY",
                  "COMPETES_WITH", "HAS_EXECUTIVE", "ACQUIRED"]

SYSTEM_PROMPT = f"""You are an information extraction system for SEC 10-K filings.
Extract entities and relationships from the given text chunk.

CONTEXT: This filing is Apple Inc.'s 10-K. When the text says "the Company",
"we", "our", or "the Registrant", it refers to Apple. Use "Apple" as its canonical name.

MULTI-ENTITY EXTRACTION — this is critical:
Extract relationships between ANY two named entities, not just Apple. If the text
says "Google is under investigation by the DOJ", extract (Google)-[REGULATED_BY]->(DOJ),
even though Apple is not involved. Capture the full web of relationships in the text.
- The SOURCE of a relationship is whoever the text says performs/holds it.
- Do NOT force Apple to be the source. Google, Epic Games, regulators, and other
  entities can all be sources of their own relationships.

CRITICAL RULE — ONLY PROPER NOUNS:
Extract ONLY specific, named entities (proper nouns). NEVER extract generic
category words (competitors, suppliers, customers, employees, government, etc.).

ENTITY TYPE DEFINITIONS (with what to EXCLUDE):
- Company: A specifically named business (Apple, Google, Epic Games, Ernst & Young).
  EXCLUDE generic terms, stock indices (S&P 500), and industry names.
- Person: A named individual human (Timothy D. Cook). EXCLUDE roles without names,
  groups, and dates.
- Product: A specifically named Apple product/service (iPhone, iCloud, App Store).
  EXCLUDE financial instruments, stock plans, dates, generic terms, and COMPETITOR
  products (Windows, Android, Xbox belong to others).
- Location: A named geographic place. EXCLUDE generic words and court names.
- Regulator: A named government body or authority (SEC, European Commission, DOJ).
  EXCLUDE generic terms, laws/acts, single letters, and countries/regions.
- RiskFactor: A specifically named risk (ransomware attacks, foreign exchange rates).
  EXCLUDE law acronyms and section titles.
- BusinessSegment: A named reportable segment ONLY (Americas, Greater China, Services).

RELATIONSHIP RULES:
- Only use these relationship types: {RELATION_TYPES}
- Both entities in a relationship must pass the rules above.
- A relationship can exist between any two entities (not only Apple).

Relationship usage guide:
- OPERATES_IN: a company sells/does business in a region
- MANUFACTURES_IN: a company produces/sources goods in a location
- DEPENDS_ON: a company relies on a named supplier or partner
- FACES_RISK: an entity is exposed to a named risk
- PRODUCES: a company makes a named product
- REGULATED_BY: an entity is regulated/investigated by a named authority
- COMPETES_WITH: a company competes with another company
- HAS_EXECUTIVE: a company has a named executive (target must be a PERSON)
- ACQUIRED: a company acquired another company

RELATIONSHIP DIRECTION:
- Direction follows the text: (subject)-[RELATION]->(object).
- HAS_EXECUTIVE target must be a named PERSON, never a company.
- REGULATED_BY target must be a named BODY/AUTHORITY, never a country or region.
- A continent or region is a Location, never a Regulator.

Return ONLY valid JSON, no markdown, no explanation.
Output JSON schema:
{{
  "entities": [{{"name": "...", "type": "<entity type>"}}],
  "relationships": [{{"source": "...", "type": "<relation type>", "target": "...", "confidence": 0.0-1.0}}]
}}"""

def extract_from_chunk(chunk_text: str):
    """Tek bir chunk'tan varlık ve ilişki çıkarır."""
    resp = client.chat.completions.create(
        model="gpt-4o",  # gpt-4o-mini -> gpt-4o
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": chunk_text},
        ],
        response_format={"type": "json_object"},
    )

    raw = resp.choices[0].message.content
    data = json.loads(raw)

    # Token kullanımı (maliyet ölçümü için)
    usage = resp.usage
    return data, usage

import time

def validate_extraction(data: dict) -> dict:
    """Ontoloji dışı varlık/ilişkileri eler."""
    clean_entities = [
        e for e in data.get("entities", [])
        if e.get("type") in ENTITY_TYPES and e.get("name")
        and e["name"].lower() not in ("company", "we", "our", "the company")
    ]
    clean_relationships = [
        r for r in data.get("relationships", [])
        if r.get("type") in RELATION_TYPES
        and r.get("source") and r.get("target")
    ]
    return {"entities": clean_entities, "relationships": clean_relationships}


def extract_all(chunks, start_index=25, cache_path="data/extractions.json"):
    """Tüm chunk'ları işler, cache ile devam edebilir."""
    # Varsa önceki sonuçları yükle (kaldığın yerden devam)
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            results = json.load(f)
    else:
        results = {}

    total_cost = 0.0

    for chunk in chunks[start_index:]:
        cid = chunk["chunk_id"]

        # Zaten işlenmişse atla (cache)
        if cid in results:
            continue

        # Retry mantığı
        for attempt in range(3):
            try:
                data, usage = extract_from_chunk(chunk["text"])
                data = validate_extraction(data)

                cost = (usage.prompt_tokens * 2.50 + usage.completion_tokens * 10.0) / 1_000_000
                total_cost += cost

                # chunk_id'yi her ilişkiye ekle (izlenebilirlik!)
                for r in data["relationships"]:
                    r["chunk_id"] = cid

                results[cid] = data
                print(f"{cid}: {len(data['entities'])} varlık, "
                      f"{len(data['relationships'])} ilişki")
                break  # başarılı, retry'dan çık

            except Exception as e:
                print(f"{cid} hata (deneme {attempt+1}): {e}")
                time.sleep(2)  # biraz bekle, tekrar dene

        # Her 20 chunk'ta bir cache'e yaz (ara kayıt)
        if len(results) % 20 == 0:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

    # Son kayıt
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n=== TAMAMLANDI ===")
    print(f"İşlenen chunk: {len(results)}")
    print(f"Toplam maliyet: ${total_cost:.4f}")
    return results

if __name__ == "__main__":
    with open("/Users/canyalinn/PycharmProjects/kg-rag/ingestion/data/apple_chunks.json", "r", encoding="utf-8") as f:
        chunks = json.load(f)
    extract_all(chunks, start_index=20)