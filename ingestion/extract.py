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
"we", "our", or "the Registrant", it refers to Apple. Always use "Apple" as
the canonical name.

CRITICAL RULE — ONLY PROPER NOUNS:
Extract ONLY specific, named entities (proper nouns). NEVER extract generic
category words. 
- REJECT generic words like: competitors, suppliers, vendors, customers,
  employees, government, regulators, third parties, international, corporate,
  manufacturing, technology, services, accessories, raw materials.
- If a word is a common noun describing a class of things, do NOT extract it.

ENTITY TYPE DEFINITIONS (with what to EXCLUDE):
- Company: A specifically named business (e.g. "Apple", "Google", "Epic Games").
  EXCLUDE generic terms like "suppliers", "competitors", "vendors".
- Person: A named individual human (e.g. "Timothy D. Cook", "Kevan Parekh").
  EXCLUDE roles without names ("CEO", "Board"), groups ("customers",
  "employees"), and dates.
- Product: A specifically named Apple product or service line (e.g. "iPhone",
  "Apple Watch", "iCloud", "App Store"). 
  EXCLUDE: financial instruments (notes, bonds), stock plans, dates, generic
  terms ("smartphone", "services", "technology"), and COMPETITOR products
  (Windows, Android, Xbox, PlayStation belong to other companies, not Apple).
  MERGE product variants: "iPhone 17 Pro Max" -> "iPhone". Use the product FAMILY.
- Location: A named geographic place (country, region, state, city).
  EXCLUDE: generic words ("international", "corporate", "manufacturing"),
  and court names (those are not locations).
- Regulator: A named government body or regulatory authority (e.g. "SEC",
  "European Commission", "Department of Justice").
  EXCLUDE: generic terms ("government", "governmental authorities"),
  laws/acts (those are not regulators), single letters.
- RiskFactor: A specifically named risk or threat (e.g. "ransomware attacks",
  "foreign exchange rates", "natural disasters").
  EXCLUDE: acronyms of laws ("GAAP", "TCJA"), section titles ("Risk Factors").
- BusinessSegment: A named reportable business segment ONLY (e.g. "Americas",
  "Greater China", "Services", "Europe", "Japan", "Rest of Asia Pacific").
  EXCLUDE everything else — customer types, teams, committees, partner types.

RELATIONSHIP RULES:
- Only use these relationship types: {RELATION_TYPES}
- Only create a relationship if BOTH entities pass the rules above.

Relationship usage guide:
- OPERATES_IN: Apple sells/does business in a region (market presence)
- MANUFACTURES_IN: Apple produces/sources goods in a location
- DEPENDS_ON: Apple relies on a named supplier or partner
- FACES_RISK: Apple is exposed to a named risk
- PRODUCES: Apple makes a named product
- REGULATED_BY: Apple is regulated by a named authority
- COMPETES_WITH: Apple competes with a named company
- HAS_EXECUTIVE: Apple has a named executive
- ACQUIRED: Apple acquired a named company

Return ONLY valid JSON, no markdown, no explanation.
Output JSON schema:
{{
  "entities": [
    {{"name": "...", "type": "<one of entity types>"}}
  ],
  "relationships": [
    {{"source": "...", "type": "<one of relation types>", "target": "...", "confidence": 0.0-1.0}}
  ]
}}"""


def extract_from_chunk(chunk_text: str):
    """Tek bir chunk'tan varlık ve ilişki çıkarır."""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,  # tutarlılık için sıfır
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": chunk_text},
        ],
        response_format={"type": "json_object"},  # JSON zorla
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

                cost = (usage.prompt_tokens * 0.15 +
                        usage.completion_tokens * 0.60) / 1_000_000
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

    extract_all(chunks, start_index=25)