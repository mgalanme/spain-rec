"""
Synthetic data generator for SPAIN-REC.
Generates tourists, destinations, cohorts and visit events.
Seeds PostgreSQL directly and publishes events to Kafka.
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timedelta
from uuid import uuid4

from dotenv import load_dotenv
from faker import Faker
from kafka import KafkaProducer
import psycopg2

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

random.seed(42)
fake = Faker(["es_ES", "en_GB", "de_DE", "fr_FR", "it_IT"])
Faker.seed(42)

# ── Configuration ─────────────────────────────────────────────────────────────

NUM_COHORTS = 8
NUM_DESTINATIONS = 30
NUM_TOURISTS = 100
NUM_VISITS = 300

KAFKA_TOPIC = "tourist.visit.events"
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DATABASE_URL = os.getenv("DATABASE_URL")

# ── Cohort definitions ────────────────────────────────────────────────────────

COHORT_DEFINITIONS = [
    {
        "country_code": "DE",
        "country_name": "Germany",
        "cultural_region": "Central Europe",
        "avg_trip_duration_days": 10.5,
        "preferred_seasons": ["spring", "summer"],
        "dominant_travel_styles": ["cultural", "urban", "gastronomy"],
    },
    {
        "country_code": "FR",
        "country_name": "France",
        "cultural_region": "Western Europe",
        "avg_trip_duration_days": 8.0,
        "preferred_seasons": ["summer", "autumn"],
        "dominant_travel_styles": ["gastronomy", "cultural", "beach"],
    },
    {
        "country_code": "GB",
        "country_name": "United Kingdom",
        "cultural_region": "Northern Europe",
        "avg_trip_duration_days": 9.0,
        "preferred_seasons": ["summer"],
        "dominant_travel_styles": ["beach", "urban", "cultural"],
    },
    {
        "country_code": "US",
        "country_name": "United States",
        "cultural_region": "North America",
        "avg_trip_duration_days": 12.0,
        "preferred_seasons": ["spring", "summer", "autumn"],
        "dominant_travel_styles": ["cultural", "urban", "gastronomy"],
    },
    {
        "country_code": "IT",
        "country_name": "Italy",
        "cultural_region": "Southern Europe",
        "avg_trip_duration_days": 7.0,
        "preferred_seasons": ["spring", "summer"],
        "dominant_travel_styles": ["cultural", "gastronomy", "beach"],
    },
    {
        "country_code": "JP",
        "country_name": "Japan",
        "cultural_region": "East Asia",
        "avg_trip_duration_days": 14.0,
        "preferred_seasons": ["spring", "autumn"],
        "dominant_travel_styles": ["cultural", "urban", "gastronomy"],
    },
    {
        "country_code": "BR",
        "country_name": "Brazil",
        "cultural_region": "South America",
        "avg_trip_duration_days": 11.0,
        "preferred_seasons": ["summer", "winter"],
        "dominant_travel_styles": ["beach", "urban", "adventure"],
    },
    {
        "country_code": "NL",
        "country_name": "Netherlands",
        "cultural_region": "Northern Europe",
        "avg_trip_duration_days": 7.5,
        "preferred_seasons": ["spring", "summer"],
        "dominant_travel_styles": ["cultural", "nature", "urban"],
    },
]

# ── Destination definitions ───────────────────────────────────────────────────

DESTINATION_DEFINITIONS = [
    {"name": "Barcelona", "region": "Catalonia", "province": "Barcelona",
     "latitude": 41.3851, "longitude": 2.1734,
     "categories": ["urban", "coastal", "historical"],
     "description": "Vibrant coastal city famed for Gaudi architecture, Gothic Quarter and world-class gastronomy.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.8, "autumn": 0.9, "winter": 0.7}},
    {"name": "Madrid", "region": "Community of Madrid", "province": "Madrid",
     "latitude": 40.4168, "longitude": -3.7038,
     "categories": ["urban", "historical", "gastronomy_hub"],
     "description": "Spain's capital, home to the Prado, Reina Sofia and a legendary tapas culture.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.6, "autumn": 0.9, "winter": 0.7}},
    {"name": "Seville", "region": "Andalusia", "province": "Seville",
     "latitude": 37.3891, "longitude": -5.9845,
     "categories": ["historical", "urban", "gastronomy_hub"],
     "description": "Flamenco, the Alcazar palace and orange-scented streets define this Andalusian gem.",
     "seasonal_scores": {"spring": 1.0, "summer": 0.4, "autumn": 0.9, "winter": 0.8}},
    {"name": "Granada", "region": "Andalusia", "province": "Granada",
     "latitude": 37.1773, "longitude": -3.5986,
     "categories": ["historical", "unesco", "cultural"],
     "description": "The Alhambra palace complex and the Albaicin neighbourhood make Granada unmissable.",
     "seasonal_scores": {"spring": 1.0, "summer": 0.6, "autumn": 0.9, "winter": 0.8}},
    {"name": "Valencia", "region": "Valencian Community", "province": "Valencia",
     "latitude": 39.4699, "longitude": -0.3763,
     "categories": ["coastal", "urban", "gastronomy_hub"],
     "description": "Birthplace of paella, City of Arts and Sciences, and stunning Mediterranean beaches.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.8, "autumn": 0.9, "winter": 0.7}},
    {"name": "San Sebastian", "region": "Basque Country", "province": "Gipuzkoa",
     "latitude": 43.3183, "longitude": -1.9812,
     "categories": ["coastal", "gastronomy_hub", "urban"],
     "description": "World's highest concentration of Michelin stars per capita, set on a stunning bay.",
     "seasonal_scores": {"spring": 0.8, "summer": 0.9, "autumn": 0.8, "winter": 0.6}},
    {"name": "Bilbao", "region": "Basque Country", "province": "Biscay",
     "latitude": 43.2630, "longitude": -2.9350,
     "categories": ["urban", "historical", "gastronomy_hub"],
     "description": "Guggenheim Museum transformed this industrial city into a global design destination.",
     "seasonal_scores": {"spring": 0.8, "summer": 0.8, "autumn": 0.8, "winter": 0.6}},
    {"name": "Cordoba", "region": "Andalusia", "province": "Cordoba",
     "latitude": 37.8882, "longitude": -4.7794,
     "categories": ["historical", "unesco", "cultural"],
     "description": "The Mezquita-Cathedral and Jewish Quarter recall Cordoba's golden age as a world capital.",
     "seasonal_scores": {"spring": 1.0, "summer": 0.3, "autumn": 0.9, "winter": 0.8}},
    {"name": "Toledo", "region": "Castile-La Mancha", "province": "Toledo",
     "latitude": 39.8628, "longitude": -4.0273,
     "categories": ["historical", "unesco", "cultural"],
     "description": "City of three cultures — Christian, Muslim and Jewish heritage preserved in its medieval streets.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.5, "autumn": 0.9, "winter": 0.7}},
    {"name": "Mallorca", "region": "Balearic Islands", "province": "Mallorca",
     "latitude": 39.6953, "longitude": 3.0176,
     "categories": ["coastal", "natural_park", "rural"],
     "description": "Turquoise coves, the Serra de Tramuntana mountains and charming hilltop villages.",
     "seasonal_scores": {"spring": 0.9, "summer": 1.0, "autumn": 0.8, "winter": 0.5}},
    {"name": "Ibiza", "region": "Balearic Islands", "province": "Ibiza",
     "latitude": 38.9067, "longitude": 1.4206,
     "categories": ["coastal", "urban"],
     "description": "World-famous nightlife, stunning sunsets at Cafe del Mar and crystal-clear waters.",
     "seasonal_scores": {"spring": 0.7, "summer": 1.0, "autumn": 0.6, "winter": 0.3}},
    {"name": "Tenerife", "region": "Canary Islands", "province": "Santa Cruz de Tenerife",
     "latitude": 28.2916, "longitude": -16.6291,
     "categories": ["coastal", "natural_park", "adventure"],
     "description": "Mount Teide, whale watching, black sand beaches and year-round sunshine.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.8, "autumn": 0.9, "winter": 0.9}},
    {"name": "Santiago de Compostela", "region": "Galicia", "province": "A Coruna",
     "latitude": 42.8782, "longitude": -8.5448,
     "categories": ["historical", "unesco", "cultural"],
     "description": "End point of the Camino de Santiago pilgrimage, with a majestic Romanesque cathedral.",
     "seasonal_scores": {"spring": 0.8, "summer": 0.9, "autumn": 0.8, "winter": 0.6}},
    {"name": "Salamanca", "region": "Castile and Leon", "province": "Salamanca",
     "latitude": 40.9701, "longitude": -5.6635,
     "categories": ["historical", "unesco", "cultural"],
     "description": "One of Europe's oldest universities and a stunning Plaza Mayor of golden sandstone.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.6, "autumn": 0.9, "winter": 0.7}},
    {"name": "Segovia", "region": "Castile and Leon", "province": "Segovia",
     "latitude": 40.9429, "longitude": -4.1088,
     "categories": ["historical", "unesco", "cultural"],
     "description": "Roman aqueduct, a fairy-tale Alcazar and legendary roast suckling pig.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.7, "autumn": 0.9, "winter": 0.7}},
    {"name": "Ronda", "region": "Andalusia", "province": "Malaga",
     "latitude": 36.7466, "longitude": -5.1620,
     "categories": ["historical", "rural", "adventure"],
     "description": "Dramatic clifftop city with a gorge-spanning bridge and birthplace of modern bullfighting.",
     "seasonal_scores": {"spring": 1.0, "summer": 0.6, "autumn": 0.9, "winter": 0.8}},
    {"name": "Cadiz", "region": "Andalusia", "province": "Cadiz",
     "latitude": 36.5271, "longitude": -6.2886,
     "categories": ["coastal", "historical", "urban"],
     "description": "Europe's oldest continuously inhabited city, ringed by Atlantic beaches and sea walls.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.8, "autumn": 0.8, "winter": 0.7}},
    {"name": "Malaga", "region": "Andalusia", "province": "Malaga",
     "latitude": 36.7213, "longitude": -4.4214,
     "categories": ["coastal", "urban", "historical"],
     "description": "Picasso's birthplace, a buzzing contemporary art scene and the Costa del Sol gateway.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.9, "autumn": 0.8, "winter": 0.7}},
    {"name": "Zaragoza", "region": "Aragon", "province": "Zaragoza",
     "latitude": 41.6488, "longitude": -0.8891,
     "categories": ["historical", "urban", "gastronomy_hub"],
     "description": "Basilica del Pilar on the Ebro river and a rich tapas culture known as pincho de Aragon.",
     "seasonal_scores": {"spring": 0.8, "summer": 0.6, "autumn": 0.8, "winter": 0.6}},
    {"name": "Donostia-San Sebastian Old Town", "region": "Basque Country", "province": "Gipuzkoa",
     "latitude": 43.3250, "longitude": -1.9750,
     "categories": ["historical", "gastronomy_hub", "coastal"],
     "description": "The Parte Vieja is one of Europe's finest pintxos bar districts, steps from La Concha beach.",
     "seasonal_scores": {"spring": 0.8, "summer": 1.0, "autumn": 0.8, "winter": 0.5}},
    {"name": "Montserrat", "region": "Catalonia", "province": "Barcelona",
     "latitude": 41.5929, "longitude": 1.8383,
     "categories": ["natural_park", "cultural", "adventure"],
     "description": "Serrated mountain monastery rising above the Catalan hinterland, sacred and spectacular.",
     "seasonal_scores": {"spring": 1.0, "summer": 0.8, "autumn": 0.9, "winter": 0.6}},
    {"name": "Camino de Santiago (French Way)", "region": "Galicia", "province": "A Coruna",
     "latitude": 42.8800, "longitude": -8.5500,
     "categories": ["adventure", "cultural", "rural"],
     "description": "The world's most famous pilgrimage route, crossing northern Spain through forests and villages.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.9, "autumn": 0.8, "winter": 0.4}},
    {"name": "Picos de Europa", "region": "Asturias", "province": "Asturias",
     "latitude": 43.1900, "longitude": -4.8400,
     "categories": ["natural_park", "adventure", "rural"],
     "description": "Dramatic limestone peaks, deep gorges, and villages where the finest Spanish cheese is made.",
     "seasonal_scores": {"spring": 0.9, "summer": 1.0, "autumn": 0.8, "winter": 0.4}},
    {"name": "La Rioja Wine Region", "region": "La Rioja", "province": "La Rioja",
     "latitude": 42.4669, "longitude": -2.4398,
     "categories": ["rural", "gastronomy_hub", "cultural"],
     "description": "Rolling vineyards, world-renowned Tempranillo bodegas and a thriving wine tourism circuit.",
     "seasonal_scores": {"spring": 0.8, "summer": 0.7, "autumn": 1.0, "winter": 0.5}},
    {"name": "Costa Brava", "region": "Catalonia", "province": "Girona",
     "latitude": 41.9900, "longitude": 3.2100,
     "categories": ["coastal", "natural_park", "rural"],
     "description": "Rocky coves, medieval villages, Salvador Dali's theatre-museum and translucent waters.",
     "seasonal_scores": {"spring": 0.8, "summer": 1.0, "autumn": 0.7, "winter": 0.4}},
    {"name": "Extremadura (Merida & Caceres)", "region": "Extremadura", "province": "Caceres",
     "latitude": 39.4752, "longitude": -6.3724,
     "categories": ["historical", "unesco", "rural"],
     "description": "Spain's most complete Roman theatre, a perfectly preserved medieval walled city, and vast dehesa landscapes.",
     "seasonal_scores": {"spring": 1.0, "summer": 0.3, "autumn": 0.9, "winter": 0.7}},
    {"name": "Tarragona", "region": "Catalonia", "province": "Tarragona",
     "latitude": 41.1189, "longitude": 1.2445,
     "categories": ["historical", "coastal", "unesco"],
     "description": "Tarraco was the most important Roman city in the Iberian Peninsula; its ruins are UNESCO-listed.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.8, "autumn": 0.8, "winter": 0.6}},
    {"name": "Asturias Coast (Playa del Silencio)", "region": "Asturias", "province": "Asturias",
     "latitude": 43.3700, "longitude": -6.2700,
     "categories": ["coastal", "natural_park", "rural"],
     "description": "Wild Atlantic beaches framed by cliffs, green meadows and cider-house culture.",
     "seasonal_scores": {"spring": 0.7, "summer": 0.9, "autumn": 0.6, "winter": 0.3}},
    {"name": "Cuenca", "region": "Castile-La Mancha", "province": "Cuenca",
     "latitude": 40.0704, "longitude": -2.1374,
     "categories": ["historical", "unesco", "rural"],
     "description": "The Hanging Houses perched over gorges and an outstanding abstract art museum.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.7, "autumn": 0.9, "winter": 0.6}},
    {"name": "Lanzarote", "region": "Canary Islands", "province": "Las Palmas",
     "latitude": 28.9636, "longitude": -13.5477,
     "categories": ["coastal", "natural_park", "adventure"],
     "description": "Volcanic moonscapes, Cesar Manrique's organic architecture and year-round Atlantic warmth.",
     "seasonal_scores": {"spring": 0.9, "summer": 0.8, "autumn": 0.9, "winter": 0.9}},
]

ACTIVITY_POOL = [
    "museum visit", "cathedral tour", "tapas bar hopping", "beach day",
    "hiking", "wine tasting", "flamenco show", "cooking class",
    "cycling", "kayaking", "city walking tour", "market visit",
    "art gallery", "boat trip", "olive oil tasting", "photography walk",
]


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def get_kafka_producer():
    try:
        return KafkaProducer(
            bootstrap_servers=KAFKA_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        )
    except Exception as e:
        print(f"  Warning: Kafka not available ({e}). Skipping Kafka publish.")
        return None


def seed_cohorts(conn) -> dict[str, str]:
    """Insert cohorts and return mapping country_code -> id."""
    cur = conn.cursor()
    cohort_ids = {}
    print(f"Seeding {len(COHORT_DEFINITIONS)} cohorts...")
    for c in COHORT_DEFINITIONS:
        cid = str(uuid4())
        cur.execute("""
            INSERT INTO cohorts (id, country_code, country_name, cultural_region,
                avg_trip_duration_days, preferred_seasons, dominant_travel_styles, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            cid, c["country_code"], c["country_name"], c["cultural_region"],
            c["avg_trip_duration_days"],
            json.dumps(c["preferred_seasons"]),
            json.dumps(c["dominant_travel_styles"]),
            datetime.utcnow(),
        ))
        cohort_ids[c["country_code"]] = cid
    conn.commit()
    print(f"  {len(cohort_ids)} cohorts seeded.")
    return cohort_ids


def seed_destinations(conn) -> list[str]:
    """Insert destinations and return list of ids."""
    cur = conn.cursor()
    destination_ids = []
    print(f"Seeding {len(DESTINATION_DEFINITIONS)} destinations...")
    for d in DESTINATION_DEFINITIONS:
        did = str(uuid4())
        cur.execute("""
            INSERT INTO destinations (id, name, region, province, latitude, longitude,
                categories, description, seasonal_scores, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            did, d["name"], d["region"], d["province"],
            d["latitude"], d["longitude"],
            json.dumps(d["categories"]),
            d["description"],
            json.dumps(d["seasonal_scores"]),
            datetime.utcnow(),
        ))
        destination_ids.append(did)
    conn.commit()
    print(f"  {len(destination_ids)} destinations seeded.")
    return destination_ids


def seed_tourists(conn, cohort_ids: dict[str, str]) -> list[tuple[str, str]]:
    """Insert tourists and return list of (tourist_id, country_code) tuples."""
    cur = conn.cursor()
    tourist_records = []
    country_codes = list(cohort_ids.keys())
    age_brackets = ["18-24", "25-34", "35-44", "45-54", "55-64", "65-74"]
    travel_styles = [
        "cultural", "adventure", "gastronomy", "nature", "beach", "urban", "rural"
    ]
    print(f"Seeding {NUM_TOURISTS} tourists...")
    for _ in range(NUM_TOURISTS):
        tid = str(uuid4())
        country_code = random.choice(country_codes)
        cohort_id = cohort_ids[country_code]
        styles = random.sample(travel_styles, k=random.randint(1, 3))
        cur.execute("""
            INSERT INTO tourists (id, first_name, last_name, country_code, country_name,
                age_bracket, travel_styles, cohort_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            tid, fake.first_name(), fake.last_name(),
            country_code,
            next(c["country_name"] for c in COHORT_DEFINITIONS if c["country_code"] == country_code),
            random.choice(age_brackets),
            json.dumps(styles),
            cohort_id,
            datetime.utcnow(),
        ))
        tourist_records.append((tid, country_code))
    conn.commit()
    print(f"  {NUM_TOURISTS} tourists seeded.")
    return tourist_records


def seed_visits(conn, tourist_records: list[tuple], destination_ids: list[str],
                producer) -> int:
    """Insert visit events and publish to Kafka."""
    cur = conn.cursor()
    print(f"Seeding {NUM_VISITS} visit events...")
    count = 0
    for _ in range(NUM_VISITS):
        vid = str(uuid4())
        tourist_id, _ = random.choice(tourist_records)
        destination_id = random.choice(destination_ids)
        arrived = datetime.utcnow() - timedelta(days=random.randint(30, 730))
        duration = timedelta(days=random.randint(1, 14))
        departed = arrived + duration
        rating = round(random.uniform(2.5, 5.0), 1)
        activities = random.sample(ACTIVITY_POOL, k=random.randint(1, 4))
        review_options = [
            "Absolutely loved it, would come back.",
            "Beautiful place, highly recommended.",
            "Good experience overall, some crowds.",
            "Hidden gem, exceeded expectations.",
            "Nice but a bit overrated.",
            "Fantastic food and culture.",
            "Great for families, very welcoming.",
        ]
        review = random.choice(review_options) if random.random() > 0.3 else None

        cur.execute("""
            INSERT INTO visit_events (id, tourist_id, destination_id, arrived_at,
                departed_at, rating, review, activities, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            vid, tourist_id, destination_id,
            arrived, departed, rating, review,
            json.dumps(activities), datetime.utcnow(),
        ))

        if producer:
            event = {
                "event_id": str(uuid4()),
                "event_type": "visit.created",
                "payload": {
                    "id": vid,
                    "tourist_id": tourist_id,
                    "destination_id": destination_id,
                    "arrived_at": arrived.isoformat(),
                    "departed_at": departed.isoformat(),
                    "rating": rating,
                    "review": review,
                    "activities": activities,
                },
                "produced_at": datetime.utcnow().isoformat(),
            }
            producer.send(KAFKA_TOPIC, event)
        count += 1

    conn.commit()
    if producer:
        producer.flush()
    print(f"  {count} visit events seeded.")
    return count


def main():
    print("── SPAIN-REC Synthetic Data Generator ──")
    print()

    conn = get_db_connection()
    producer = get_kafka_producer()

    cohort_ids = seed_cohorts(conn)
    destination_ids = seed_destinations(conn)
    tourist_records = seed_tourists(conn, cohort_ids)
    visit_count = seed_visits(conn, tourist_records, destination_ids, producer)

    conn.close()
    if producer:
        producer.close()

    print()
    print("Generation complete:")
    print(f"  Cohorts:      {len(cohort_ids)}")
    print(f"  Destinations: {len(destination_ids)}")
    print(f"  Tourists:     {len(tourist_records)}")
    print(f"  Visit events: {visit_count}")


if __name__ == "__main__":
    main()
