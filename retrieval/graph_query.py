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
# Multi-hop şablonları: iki ilişkiyi birleştiren zincir/kesişim sorguları
MULTIHOP_TEMPLATES = {
    # GERÇEK KESİŞİM: hem üretim hem operasyon olan yerler
    "MANUFACTURE_AND_OPERATE": """
        MATCH (a:Company {name: $entity})-[r1:MANUFACTURES_IN]->(loc)
        MATCH (a)-[r2:OPERATES_IN]->(loc)
        RETURN DISTINCT loc.name AS result, r1.chunk_id AS chunk_id
    """,
    # GERÇEK: rakipler (tek ilişki ama multi-hop soru olarak gelir)
    "COMPETITORS": """
        MATCH (a:Company {name: $entity})-[r:COMPETES_WITH]->(comp)
        RETURN comp.name AS result, r.chunk_id AS chunk_id
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

MULTIHOP_CLASSIFY_PROMPT = f"""You map a MULTI-HOP question to a query template.
Available templates: {list(MULTIHOP_TEMPLATES.keys())}

Template meanings:
- MANUFACTURE_AND_OPERATE: places Apple both manufactures in AND operates in
- REGULATOR_WITH_RISK: regulators and the risks mentioned alongside them
- COMPETITORS: Apple's competitors
- DEPENDENCY_CONTEXT: companies/entities Apple depends on

Return JSON: {{"entity": "Apple", "template": "<one of the template names>"}}
If none fit well, return {{"entity": "Apple", "template": "NONE"}}"""


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
def query_graph_multihop(question: str) -> dict:
    """Multi-hop soruyu zincirleme şablonla çöz."""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": MULTIHOP_CLASSIFY_PROMPT},
            {"role": "user", "content": question},
        ],
        response_format={"type": "json_object"},
    )
    mapping = json.loads(resp.choices[0].message.content)
    entity = mapping.get("entity", "Apple")
    template_name = mapping.get("template", "NONE")

    if template_name == "NONE" or template_name not in MULTIHOP_TEMPLATES:
        # Multi-hop çözülemezse tek-hop'a düş (fallback)
        return query_graph(question)

    template = MULTIHOP_TEMPLATES[template_name]
    with driver.session() as session:
        records = session.run(template, entity=entity)
        results = []
        chunk_ids = set()
        for rec in records:
            results.append(rec["result"])
            if rec["chunk_id"]:
                chunk_ids.add(rec["chunk_id"])

    return {
        "entity": entity,
        "template": template_name,
        "results": results,
        "chunk_ids": list(chunk_ids),
    }

# graph_query.py içinde geçici test
if __name__ == "__main__":
    test = [
        "Which countries where Apple manufactures are also regulatory concerns?",
        "What risks are related to countries where Apple manufactures?",
        "What products does Apple make in the countries it manufactures in?",
    ]
    for soru in test:
        print(f"\nSORU: {soru}")
        r = query_graph_multihop(soru)
        print(f"  Şablon: {r.get('template')}")
        print(f"  Sonuçlar: {r['results'][:10]}")
        print(f"  chunk'lar: {r['chunk_ids'][:5]}")