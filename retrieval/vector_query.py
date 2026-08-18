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


def query_vector(question: str, k: int = 3) -> dict:
    """Soruya en benzer k chunk'ı getir, graf ile aynı formatta döndür."""
    q_embedding = model.encode(question).tolist()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT chunk_id, text, embedding <=> %s::vector AS distance
            FROM chunks
            ORDER BY distance
            LIMIT %s;
        """, (q_embedding, k))
        rows = cur.fetchall()

    passages = []
    chunk_ids = []
    for chunk_id, text, distance in rows:
        passages.append({"chunk_id": chunk_id, "text": text, "distance": float(distance)})
        chunk_ids.append(chunk_id)

    return {
        "passages": passages,
        "chunk_ids": chunk_ids,
    }


if __name__ == "__main__":
    test_sorular = [
        "What are Apple's risk factors?",
        "What is the State Aid Decision?",
        "How does Apple handle cybersecurity?",
    ]

    for soru in test_sorular:
        print(f"\nSORU: {soru}")
        result = query_vector(soru)
        for p in result["passages"]:
            print(f"  [{p['chunk_id']}] mesafe: {p['distance']:.4f}")
            print(f"    {p['text'][:150]}...")