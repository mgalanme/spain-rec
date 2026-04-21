"""
SPAIN-REC LangGraph Orchestrator.

Graph topology:
  profile_analyst -> cohort_intelligence -> destination_matcher
  -> synthesiser -> hitl_review -> END
"""
from __future__ import annotations

import json
import os

import psycopg2
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from src.agents.state import (
    OrchestratorState,
    TouristContext,
    CohortContext,
    CandidateDestination,
    RecommendationOutput,
)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# ── Clients ───────────────────────────────────────────────────────────────────

def get_pg():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def get_neo4j():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
    )

def get_qdrant():
    return QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", 6333)),
    )

def get_llm():
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3,
    )

_embed_model = None
def get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(
            "nomic-ai/nomic-embed-text-v1", trust_remote_code=True
        )
    return _embed_model


# ── Node 1: Profile Analyst ───────────────────────────────────────────────────

def profile_analyst(state: OrchestratorState) -> OrchestratorState:
    print(f"\n[Profile Analyst] Analysing tourist {state.tourist_id}...")

    conn = get_pg()
    cur = conn.cursor()

    cur.execute("""
        SELECT t.id, t.first_name, t.last_name, t.country_code, t.country_name,
               t.age_bracket, t.travel_styles, t.cohort_id
        FROM tourists t WHERE t.id = %s
    """, (state.tourist_id,))
    row = cur.fetchone()
    if not row:
        state.errors.append(f"Tourist {state.tourist_id} not found.")
        conn.close()
        return state

    tid, fname, lname, cc, cn, ab, styles_raw, cohort_id = row
    styles = styles_raw if isinstance(styles_raw, list) else json.loads(styles_raw)

    cur.execute("""
        SELECT d.id, d.name FROM visit_events ve
        JOIN destinations d ON d.id = ve.destination_id
        WHERE ve.tourist_id = %s
    """, (state.tourist_id,))
    visits = cur.fetchall()
    visited_ids = [str(v[0]) for v in visits]
    visited_names = [v[1] for v in visits]
    conn.close()

    state.tourist_context = TouristContext(
        tourist_id=str(tid),
        first_name=fname,
        last_name=lname,
        country_code=cc,
        country_name=cn,
        age_bracket=ab,
        travel_styles=styles,
        cohort_id=str(cohort_id),
        visited_destination_ids=visited_ids,
        visited_destination_names=visited_names,
    )
    state.current_step = "profile_analyst_done"
    print(f"  Tourist: {fname} {lname} ({cc}), {len(visited_ids)} visits on record.")
    return state


# ── Node 2: Cohort Intelligence ───────────────────────────────────────────────

def cohort_intelligence(state: OrchestratorState) -> OrchestratorState:
    print(f"\n[Cohort Intelligence] Analysing cohort {state.tourist_context.cohort_id}...")

    driver = get_neo4j()
    with driver.session() as session:

        result = session.run("""
            MATCH (c:Cohort {id: $cohort_id})
            RETURN c.country_code AS cc, c.country_name AS cn, c.cultural_region AS cr
        """, cohort_id=state.tourist_context.cohort_id)
        cohort_row = result.single()
        if not cohort_row:
            state.errors.append("Cohort not found in Neo4j.")
            driver.close()
            return state

        result = session.run("""
            MATCH (c:Cohort {id: $cohort_id})-[a:AFFINITY_FOR]->(d:Destination)
            RETURN d.id AS did, d.name AS name, d.region AS region,
                   d.categories AS cats, a.score AS score
            ORDER BY score DESC LIMIT 10
        """, cohort_id=state.tourist_context.cohort_id)

        top_destinations = []
        for r in result:
            top_destinations.append({
                "destination_id": r["did"],
                "name": r["name"],
                "region": r["region"],
                "categories": r["cats"],
                "score": round(r["score"], 2),
            })

    driver.close()

    conn = get_pg()
    cur = conn.cursor()
    cur.execute("""
        SELECT dominant_travel_styles FROM cohorts WHERE id = %s
    """, (state.tourist_context.cohort_id,))
    row = cur.fetchone()
    styles = row[0] if isinstance(row[0], list) else json.loads(row[0])
    conn.close()

    state.cohort_context = CohortContext(
        cohort_id=state.tourist_context.cohort_id,
        country_code=cohort_row["cc"],
        country_name=cohort_row["cn"],
        cultural_region=cohort_row["cr"],
        top_destinations=top_destinations,
        dominant_styles=styles,
    )
    state.current_step = "cohort_intelligence_done"
    print(f"  Cohort: {cohort_row['cn']} — {len(top_destinations)} affinity destinations found.")
    return state


# ── Node 3: Destination Matcher ───────────────────────────────────────────────

def destination_matcher(state: OrchestratorState) -> OrchestratorState:
    print(f"\n[Destination Matcher] Finding semantic matches...")

    tc = state.tourist_context
    cc = state.cohort_context

    query_text = (
        f"search_query: Tourist from {tc.country_name} interested in "
        f"{', '.join(tc.travel_styles)}. "
        f"Cohort prefers {', '.join(cc.dominant_styles)}. "
        f"Looking for new experiences in Spain."
    )

    model = get_embed_model()
    vector = model.encode(query_text, normalize_embeddings=True).tolist()

    client = get_qdrant()
    results = client.query_points(
        collection_name="destinations-index",
        query=vector,
        limit=10,
    ).points

    visited_ids = set(tc.visited_destination_ids)
    candidates = []
    for r in results:
        if r.payload["destination_id"] in visited_ids:
            continue
        candidates.append(CandidateDestination(
            destination_id=r.payload["destination_id"],
            name=r.payload["name"],
            region=r.payload["region"],
            categories=r.payload["categories"],
            description=r.payload["description"],
            score=round(r.score, 3),
        ))
        if len(candidates) >= 5:
            break

    # Enrich with cohort affinity scores from Neo4j context
    cohort_affinity_names = {d["name"] for d in cc.top_destinations}
    for c in candidates:
        if c.name in cohort_affinity_names:
            c.reason = f"High affinity among {tc.country_name} visitors"
        else:
            c.reason = f"Strong semantic match for {', '.join(tc.travel_styles)} interests"

    state.candidate_destinations = candidates
    state.current_step = "destination_matcher_done"
    print(f"  Found {len(candidates)} candidate destinations (excluding already visited).")
    for c in candidates:
        print(f"    {c.score:.3f} — {c.name} ({c.region})")
    return state


# ── Node 4: Recommendation Synthesiser ───────────────────────────────────────

def recommendation_synthesiser(state: OrchestratorState) -> OrchestratorState:
    print(f"\n[Recommendation Synthesiser] Generating narrative recommendation...")

    tc = state.tourist_context
    candidates_text = "\n".join([
        f"- {c.name} ({c.region}): {c.description} [score: {c.score}, reason: {c.reason}]"
        for c in state.candidate_destinations
    ])
    visited_text = ", ".join(tc.visited_destination_names[:5]) or "none on record"

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert Spanish tourism advisor. 
Write a warm, knowledgeable, and personalised recommendation for a tourist returning to Spain.
Be specific about why each destination suits this particular person.
Write in British English. Keep the tone friendly and inspiring, not generic.
Structure your response as:
1. A brief personal intro (2 sentences)
2. Three destination recommendations, each with a specific reason why it suits this tourist
3. A closing sentence encouraging their return"""),
        ("human", """Tourist profile:
- Name: {first_name} {last_name}
- From: {country_name}
- Travel interests: {travel_styles}
- Previously visited in Spain: {visited}

Top candidate destinations for recommendation:
{candidates}

Write the personalised recommendation.""")
    ])

    llm = get_llm()
    chain = prompt | llm | StrOutputParser()

    justification = chain.invoke({
        "first_name": tc.first_name,
        "last_name": tc.last_name,
        "country_name": tc.country_name,
        "travel_styles": ", ".join(tc.travel_styles),
        "visited": visited_text,
        "candidates": candidates_text,
    })

    state.recommendation = RecommendationOutput(
        destinations=state.candidate_destinations[:3],
        justification=justification,
        approved=False,
    )
    state.current_step = "synthesiser_done"
    print("  Recommendation generated.")
    return state


# ── Node 5: HITL Review ───────────────────────────────────────────────────────

def hitl_review(state: OrchestratorState) -> OrchestratorState:
    print("\n" + "="*60)
    print("HITL REVIEW — Human approval required")
    print("="*60)
    print(f"\nTourist: {state.tourist_context.first_name} {state.tourist_context.last_name}")
    print(f"From: {state.tourist_context.country_name}")
    print(f"\nRecommended destinations:")
    for i, d in enumerate(state.recommendation.destinations, 1):
        print(f"  {i}. {d.name} ({d.region}) — score: {d.score}")
    print(f"\nJustification:\n{state.recommendation.justification}")
    print("\n" + "-"*60)

    response = input("Approve this recommendation? [y/n]: ").strip().lower()
    if response == "y":
        state.hitl_approved = True
        state.recommendation.approved = True
        state.current_step = "approved"
        print("  Recommendation approved.")
    else:
        feedback = input("Feedback for improvement (optional): ").strip()
        state.hitl_approved = False
        state.hitl_feedback = feedback
        state.current_step = "rejected"
        print("  Recommendation rejected.")

    return state


# ── Routing ───────────────────────────────────────────────────────────────────

def route_after_hitl(state: OrchestratorState) -> str:
    return "approved" if state.hitl_approved else "rejected"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph():
    builder = StateGraph(OrchestratorState)

    builder.add_node("profile_analyst", profile_analyst)
    builder.add_node("cohort_intelligence", cohort_intelligence)
    builder.add_node("destination_matcher", destination_matcher)
    builder.add_node("recommendation_synthesiser", recommendation_synthesiser)
    builder.add_node("hitl_review", hitl_review)

    builder.add_edge(START, "profile_analyst")
    builder.add_edge("profile_analyst", "cohort_intelligence")
    builder.add_edge("cohort_intelligence", "destination_matcher")
    builder.add_edge("destination_matcher", "recommendation_synthesiser")
    builder.add_edge("recommendation_synthesiser", "hitl_review")
    builder.add_conditional_edges(
        "hitl_review",
        route_after_hitl,
        {"approved": END, "rejected": END},
    )

    return builder.compile()


graph = build_graph()
