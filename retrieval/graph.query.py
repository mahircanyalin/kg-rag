import os
import json
from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

# Şablon kütüphanesi: ilişki tipi -> hazır Cypher
# Model ASLA ham Cypher yazmaz, sadece bu şablonlardan seçer.
QUERY_TEMPLATES = {
    "HAS_EXECUTIVE": """
        MATCH (c:Company {name: $entity})-[r:HAS_EXECUTIVE]->(p:Person)
        RETURN p.name AS result, r.chunk_id AS chunk_id
    """,
    "MANUFACTURES_IN": """
        MATCH (c:Company {name: $entity})-[r:MANUFACTURES_IN]->(loc:Location)
        RETURN loc.name AS result, r.chunk_id AS chunk_id
    """,
    "OPERATES_IN": """
        MATCH (c:Company {name: $entity})-[r:OPERATES_IN]->(x)
        RETURN x.name AS result, r.chunk_id AS chunk_id
    """,
    "REGULATED_BY": """
        MATCH (c:Company {name: $entity})-[r:REGULATED_BY]->(reg)
        RETURN reg.name AS result, r.chunk_id AS chunk_id
    """,
    "FACES_RISK": """
        MATCH (c:Company {name: $entity})-[r:FACES_RISK]->(risk:RiskFactor)
        RETURN risk.name AS result, r.chunk_id AS chunk_id
    """,
    "COMPETES_WITH": """
        MATCH (c:Company {name: $entity})-[r:COMPETES_WITH]->(comp:Company)
        RETURN comp.name AS result, r.chunk_id AS chunk_id
    """,
    "DEPENDS_ON": """
        MATCH (c:Company {name: $entity})-[r:DEPENDS_ON]->(x)
        RETURN x.name AS result, r.chunk_id AS chunk_id
    """,
    "PRODUCES": """
        MATCH (c:Company {name: $entity})-[r:PRODUCES]->(p:Product)
        RETURN p.name AS result, r.chunk_id AS chunk_id
    """,
}

# Modelin soruyu hangi şablona eşleyeceğini seçtiren prompt
CLASSIFY_PROMPT = f"""You map a question to a graph query template.
Available relationship types: {list(QUERY_TEMPLATES.keys())}

Given a question about a company, return JSON:
{{"entity": "the company name (usually Apple)", "relationship": "<one of the relationship types>"}}

Examples:
Q: "Who are Apple's executives?" -> {{"entity": "Apple", "relationship": "HAS_EXECUTIVE"}}
Q: "Where does Apple manufacture?" -> {{"entity": "Apple", "relationship": "MANUFACTURES_IN"}}
Q: "Who regulates Apple?" -> {{"entity": "Apple", "relationship": "REGULATED_BY"}}
Q: "What risks does Apple face?" -> {{"entity": "Apple", "relationship": "FACES_RISK"}}"""


def classify_to_template(question: str) -> dict:
    """Soruyu bir şablon + varlığa eşle."""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": CLASSIFY_PROMPT},
            {"role": "user", "content": question},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def query_graph(question: str) -> dict:
    """Grafı sorgula, sonuçları ve kaynak chunk'ları döndür."""
    mapping = classify_to_template(question)
    entity = mapping["entity"]
    relationship = mapping["relationship"]

    if relationship not in QUERY_TEMPLATES:
        return {"results": [], "chunk_ids": [], "error": f"Bilinmeyen ilişki: {relationship}"}

    template = QUERY_TEMPLATES[relationship]

    with driver.session() as session:
        # Parametreli sorgu — entity bir parametre, injection yok
        records = session.run(template, entity=entity)
        results = []
        chunk_ids = set()
        for rec in records:
            results.append(rec["result"])
            if rec["chunk_id"]:
                chunk_ids.add(rec["chunk_id"])

    return {
        "entity": entity,
        "relationship": relationship,
        "results": results,
        "chunk_ids": list(chunk_ids),
    }


if __name__ == "__main__":
    test_sorular = [
        "Who are Apple's executives?",
        "Which countries does Apple manufacture in?",
        "What regulators oversee Apple?",
        "Does Apple compete with anyone?",
        "What risks does Apple face?",
    ]

    for soru in test_sorular:
        print(f"\nSORU: {soru}")
        result = query_graph(soru)
        print(f"  İlişki: {result.get('relationship')}")
        print(f"  Sonuçlar: {result['results']}")
        print(f"  Kaynak chunk'lar: {result['chunk_ids']}")