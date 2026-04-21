"""
Ingest pipeline for SPAIN-REC.
Reads data from PostgreSQL and populates:
  - Neo4j: graph of tourists, destinations, cohorts and visit relationships
  - Qdrant: semantic embeddings of destination descriptions
"""
from __future__ import annotations

import json
import os

import psycopg2
from dotenv import load_dotenv
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USERNAME")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

COLLECTION_NAME = "destinations-index"
EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1"
EMBEDDING_DIM = 768


# ── PostgreSQL helpers ────────────────────────────────────────────────────────

def fetch_all(conn, query: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute(query)
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ── Neo4j ingestion ───────────────────────────────────────────────────────────

def ingest_neo4j(conn):
    print("── Neo4j ingestion ──")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

    cohorts = fetch_all(conn, "SELECT id, country_code, country_name, cultural_region FROM cohorts")
    destinations = fetch_all(conn, "SELECT id, name, region, province, categories FROM destinations")
    tourists = fetch_all(conn, "SELECT id, first_name, last_name, country_code, cohort_id, travel_styles FROM tourists")
    visits = fetch_all(conn, "SELECT id, tourist_id, destination_id, rating, activities FROM visit_events")

    with driver.session() as session:

        # Clear existing data for idempotent runs
        session.run("MATCH (n) DETACH DELETE n")
        print("  Cleared existing Neo4j graph.")

        # Cohort nodes
        print(f"  Creating {len(cohorts)} Cohort nodes...")
        for c in cohorts:
            session.run("""
                MERGE (:Cohort {
                    id: $id,
                    country_code: $country_code,
                    country_name: $country_name,
                    cultural_region: $cultural_region
                })
            """, **c)

        # Destination nodes
        print(f"  Creating {len(destinations)} Destination nodes...")
        for d in destinations:
            categories = d["categories"] if isinstance(d["categories"], list) else json.loads(d["categories"])
            session.run("""
                MERGE (:Destination {
                    id: $id,
                    name: $name,
                    region: $region,
                    province: $province,
                    categories: $categories
                })
            """, id=d["id"], name=d["name"], region=d["region"],
                province=d["province"], categories=categories)

        # Tourist nodes + BELONGS_TO cohort
        print(f"  Creating {len(tourists)} Tourist nodes...")
        for t in tourists:
            styles = t["travel_styles"] if isinstance(t["travel_styles"], list) else json.loads(t["travel_styles"])
            session.run("""
                MERGE (t:Tourist {
                    id: $id,
                    first_name: $first_name,
                    last_name: $last_name,
                    country_code: $country_code,
                    travel_styles: $styles
                })
                WITH t
                MATCH (c:Cohort {id: $cohort_id})
                MERGE (t)-[:BELONGS_TO]->(c)
            """, id=t["id"], first_name=t["first_name"], last_name=t["last_name"],
                country_code=t["country_code"], styles=styles, cohort_id=t["cohort_id"])

        # VISITED relationships
        print(f"  Creating {len(visits)} VISITED relationships...")
        for v in visits:
            activities = v["activities"] if isinstance(v["activities"], list) else json.loads(v["activities"])
            session.run("""
                MATCH (t:Tourist {id: $tourist_id})
                MATCH (d:Destination {id: $destination_id})
                MERGE (t)-[:VISITED {
                    visit_id: $visit_id,
                    rating: $rating,
                    activities: $activities
                }]->(d)
            """, tourist_id=v["tourist_id"], destination_id=v["destination_id"],
                visit_id=v["id"], rating=float(v["rating"]),
                activities=activities)

        # SIMILAR_TO relationships between destinations sharing categories
        print("  Creating SIMILAR_TO relationships between destinations...")
        session.run("""
            MATCH (a:Destination), (b:Destination)
            WHERE a.id <> b.id
            AND ANY(cat IN a.categories WHERE cat IN b.categories)
            MERGE (a)-[:SIMILAR_TO]->(b)
        """)

        # AFFINITY_FOR: cohort -> destination based on visit ratings
        print("  Creating AFFINITY_FOR relationships (cohort -> destination)...")
        session.run("""
            MATCH (t:Tourist)-[:BELONGS_TO]->(c:Cohort)
            MATCH (t)-[v:VISITED]->(d:Destination)
            WITH c, d, avg(v.rating) AS avg_rating
            WHERE avg_rating >= 3.5
            MERGE (c)-[:AFFINITY_FOR {score: avg_rating}]->(d)
        """)

        # Verify
        result = session.run("""
            MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count
            ORDER BY label
        """)
        print("\n  Graph summary:")
        for record in result:
            print(f"    {record['label']}: {record['count']} nodes")

        result = session.run("""
            MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS count
            ORDER BY rel
        """)
        print("  Relationships:")
        for record in result:
            print(f"    {record['rel']}: {record['count']}")

    driver.close()
    print("  Neo4j ingestion complete.")


# ── Qdrant ingestion ──────────────────────────────────────────────────────────

def ingest_qdrant(conn):
    print("\n── Qdrant ingestion ──")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    print(f"  Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=True)

    # Recreate collection for idempotent runs
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        client.delete_collection(COLLECTION_NAME)
        print(f"  Deleted existing collection '{COLLECTION_NAME}'.")

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
    print(f"  Created collection '{COLLECTION_NAME}' (dim={EMBEDDING_DIM}, cosine).")

    destinations = fetch_all(conn, "SELECT id, name, region, province, categories, description FROM destinations")

    texts = []
    for d in destinations:
        categories = d["categories"] if isinstance(d["categories"], list) else json.loads(d["categories"])
        text = (
            f"search_document: {d['name']} is located in {d['region']}, {d['province']}. "
            f"Categories: {', '.join(categories)}. {d['description']}"
        )
        texts.append(text)

    print(f"  Encoding {len(texts)} destination descriptions...")
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    points = []
    for i, (d, embedding) in enumerate(zip(destinations, embeddings)):
        categories = d["categories"] if isinstance(d["categories"], list) else json.loads(d["categories"])
        points.append(PointStruct(
            id=i,
            vector=embedding.tolist(),
            payload={
                "destination_id": d["id"],
                "name": d["name"],
                "region": d["region"],
                "province": d["province"],
                "categories": categories,
                "description": d["description"],
            }
        ))

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"  Upserted {len(points)} destination vectors to Qdrant.")

    count = client.count(collection_name=COLLECTION_NAME).count
    print(f"  Collection '{COLLECTION_NAME}' now has {count} vectors.")

    # Smoke test: semantic search with new API (qdrant-client >= 1.17)
    from sentence_transformers import SentenceTransformer as ST
    test_model = ST(EMBEDDING_MODEL, trust_remote_code=True)
    test_vector = test_model.encode("search_query: beach southern Spain", normalize_embeddings=True).tolist()
    results = client.query_points(collection_name=COLLECTION_NAME, query=test_vector, limit=3).points
    print("  Smoke test — top 3 results for 'beach southern Spain':")
    for r in results:
        print(f"    {r.score:.3f} — {r.payload['name']}")
    print("  Qdrant ingestion complete.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("── SPAIN-REC Ingest Pipeline ──")
    print()
    conn = psycopg2.connect(DATABASE_URL)
    ingest_neo4j(conn)
    ingest_qdrant(conn)
    conn.close()
    print("\nAll ingestion complete.")


if __name__ == "__main__":
    main()
