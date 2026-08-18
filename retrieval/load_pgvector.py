import os
import json
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from sentence_transformers import SentenceTransformer

load_dotenv()
DATA_DIR = Path(__file__).parent.parent / "ingestion" / "data"

# Yerel embedding modeli (384 boyut) — Faz 0'da test etmiştik
model = SentenceTransformer("all-MiniLM-L6-v2")

conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST"),
    port=os.getenv("POSTGRES_PORT"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    dbname=os.getenv("POSTGRES_DB")
)
cur = conn.cursor()


def setup_table():
    """chunks tablosunu ve HNSW indeksini oluştur."""
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Temiz başlangıç (geliştirme için)
    cur.execute("DROP TABLE IF EXISTS chunks;")

    cur.execute("""
        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            embedding vector(384),
            start_char INT,
            end_char INT
        );
    """)
    conn.commit()
    print("Tablo oluşturuldu.")


def load_chunks():
    """Tüm chunk'ları embedding'e çevirip pgvector'a yaz."""
    with open(DATA_DIR / "apple_chunks.json", "r", encoding="utf-8") as f:
        chunks = json.load(f)

    for chunk in chunks:
        text = chunk["text"]
        # Metni 384 boyutlu vektöre çevir
        embedding = model.encode(text).tolist()

        cur.execute("""
            INSERT INTO chunks (chunk_id, text, embedding, start_char, end_char)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (chunk_id) DO UPDATE
            SET text = EXCLUDED.text, embedding = EXCLUDED.embedding;
        """, (
            chunk["chunk_id"], text, embedding,
            chunk.get("start_char"), chunk.get("end_char")
        ))

    conn.commit()
    print(f"{len(chunks)} chunk pgvector'a yazıldı.")


def create_index():
    """HNSW indeksi — hızlı benzerlik araması için."""
    cur.execute("""
        CREATE INDEX IF NOT EXISTS chunks_embedding_idx
        ON chunks USING hnsw (embedding vector_cosine_ops);
    """)
    conn.commit()
    print("HNSW indeksi oluşturuldu.")


if __name__ == "__main__":
    setup_table()
    load_chunks()
    create_index()
    cur.close()
    conn.close()