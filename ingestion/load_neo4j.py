import os
import json
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
DATA_DIR = Path(__file__).parent / "data"

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)


def clear_graph(session):
    """Grafı sıfırla (tekrar çalıştırırken temiz başlangıç)."""
    session.run("MATCH (n) DETACH DELETE n")
    print("Graf temizlendi.")


def create_entity(session, name, etype):
    """Bir varlığı düğüm olarak ekler (MERGE = varsa bul, yoksa oluştur)."""
    # Etiket olarak entity type kullanıyoruz, ayrıca :Entity ortak etiketi
    query = f"""
    MERGE (e:Entity:{etype} {{name: $name}})
    RETURN e
    """
    session.run(query, name=name)


def create_relationship(session, source, rel_type, target, confidence, chunk_id):
    """İki düğüm arasına ilişki ekler."""
    query = f"""
    MATCH (a:Entity {{name: $source}})
    MATCH (b:Entity {{name: $target}})
    MERGE (a)-[r:{rel_type}]->(b)
    SET r.confidence = $confidence, r.chunk_id = $chunk_id
    """
    session.run(query, source=source, target=target,
                confidence=confidence, chunk_id=chunk_id)


def load_all():
    with open(DATA_DIR / "resolved.json", "r", encoding="utf-8") as f:
        results = json.load(f)

    with driver.session() as session:
        clear_graph(session)

        entity_count = 0
        rel_count = 0

        # Önce tüm varlıkları oluştur
        for cid, data in results.items():
            for e in data["entities"]:
                create_entity(session, e["name"], e["type"])
                entity_count += 1

        # Sonra ilişkileri oluştur (düğümler var olmalı)
        for cid, data in results.items():
            for r in data["relationships"]:
                try:
                    create_relationship(
                        session, r["source"], r["type"],
                        r["target"], r.get("confidence", 1.0),
                        r.get("chunk_id", cid)
                    )
                    rel_count += 1
                except Exception as ex:
                    print(f"İlişki hatası ({r['source']}->{r['target']}): {ex}")

        print(f"Yazıldı: {entity_count} varlık işlendi, {rel_count} ilişki.")

    driver.close()


if __name__ == "__main__":
    load_all()