import os
import sys
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

errors = []

print("── SPAIN-REC Connection Verification ──")
print()

# Neo4j
print("Testing Neo4j...", end=" ", flush=True)
try:
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
    )
    with driver.session() as session:
        result = session.run("RETURN 'Neo4j OK' AS msg")
        print(result.single()["msg"])
    driver.close()
except Exception as e:
    print(f"FAILED — {e}")
    errors.append("neo4j")

# PostgreSQL
print("Testing PostgreSQL...", end=" ", flush=True)
try:
    import psycopg2
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("SELECT 'PostgreSQL OK'")
    print(cur.fetchone()[0])
    conn.close()
except Exception as e:
    print(f"FAILED — {e}")
    errors.append("postgres")

# Qdrant
print("Testing Qdrant...", end=" ", flush=True)
try:
    from qdrant_client import QdrantClient
    client = QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", 6333))
    )
    info = client.get_collections()
    print(f"Qdrant OK — {len(info.collections)} collections")
except Exception as e:
    print(f"FAILED — {e}")
    errors.append("qdrant")

# Kafka
print("Testing Kafka...", end=" ", flush=True)
try:
    from kafka import KafkaAdminClient
    admin = KafkaAdminClient(
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        request_timeout_ms=5000
    )
    topics = admin.list_topics()
    print(f"Kafka OK — {len(topics)} topics")
    admin.close()
except Exception as e:
    print(f"FAILED — {e}")
    errors.append("kafka")

print()
if not errors:
    print("All connections OK ✓")
    sys.exit(0)
else:
    print(f"Failed services: {', '.join(errors)}")
    sys.exit(1)
