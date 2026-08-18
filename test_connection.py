import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
import psycopg2
load_dotenv()
conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST"),
    port=os.getenv("POSTGRES_PORT"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    dbname=os.getenv("POSTGRES_DB")
)
cur = conn.cursor()

# pgvector eklentisini aktifle (bir kez yapılır)
cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
conn.commit()

cur.execute("SELECT 'PostgreSQL baglantisi calisiyor!';")
print(cur.fetchone()[0])

# pgvector'ın aktif olduğunu doğrula
cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
print("pgvector aktif:", cur.fetchone() is not None)

cur.close()
conn.close()