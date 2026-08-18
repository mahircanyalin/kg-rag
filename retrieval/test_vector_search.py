import os
from dotenv import load_dotenv
import psycopg2
from sentence_transformers import SentenceTransformer

load_dotenv()
model = SentenceTransformer("all-MiniLM-L6-v2")

conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST"),
    port=os.getenv("POSTGRES_PORT"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    dbname=os.getenv("POSTGRES_DB")
)
cur = conn.cursor()


def search(question: str, k: int = 3):
    """Soruya en benzer k chunk'ı getir."""
    # Soruyu aynı modelle vektöre çevir
    q_embedding = model.encode(question).tolist()

    # Kosinüs mesafesine göre en yakın k chunk (<=> operatörü)
    cur.execute("""
        SELECT chunk_id, text, embedding <=> %s::vector AS distance
        FROM chunks
        ORDER BY distance
        LIMIT %s;
    """, (q_embedding, k))

    return cur.fetchall()


if __name__ == "__main__":
    sorular = [
        "Where does Apple manufacture its products?",
        "What are Apple's main risk factors?",
        "Who are Apple's executives?",
    ]

    for soru in sorular:
        print(f"\n{'='*60}")
        print(f"SORU: {soru}")
        print('='*60)
        for chunk_id, text, distance in search(soru):
            print(f"\n[{chunk_id}] mesafe: {distance:.4f}")
            print(f"  {text[:200]}...")

    cur.close()
    conn.close()