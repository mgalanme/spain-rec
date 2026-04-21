"""
SPAIN-REC FastAPI application.
Exposes the recommendation pipeline as a REST API.
"""
from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# In-memory store for pipeline run status (sufficient for demo)
_runs: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("SPAIN-REC API starting up...")
    yield
    print("SPAIN-REC API shutting down...")


app = FastAPI(
    title="SPAIN-REC",
    description="Agentic tourism recommendation system for Spain",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    tourist_id: str | None = None


class RecommendResponse(BaseModel):
    run_id: str
    tourist_id: str
    status: str
    message: str


class RunStatusResponse(BaseModel):
    run_id: str
    tourist_id: str
    status: str
    current_step: str | None = None
    recommendation: dict | None = None
    errors: list[str] = []


class FeedbackRequest(BaseModel):
    recommendation_id: str
    tourist_id: str
    destination_id: str
    signal_type: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_random_tourist_id() -> str:
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("SELECT id FROM tourists ORDER BY RANDOM() LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return str(row[0])


def run_pipeline_sync(run_id: str, tourist_id: str):
    """Run the LangGraph pipeline synchronously in a background thread."""
    from src.agents.orchestrator import graph
    from src.agents.state import OrchestratorState

    _runs[run_id]["status"] = "running"
    try:
        initial_state = OrchestratorState(tourist_id=tourist_id)
        # In API mode we auto-approve (no interactive HITL)
        # HITL is available when running via CLI (run.py)
        final_state = graph.invoke(initial_state)

        rec = final_state.get("recommendation")
        _runs[run_id].update({
            "status": "completed",
            "current_step": final_state.get("current_step"),
            "recommendation": {
                "destinations": [
                    {
                        "name": d.name if hasattr(d, "name") else d["name"],
                        "region": d.region if hasattr(d, "region") else d["region"],
                        "score": d.score if hasattr(d, "score") else d["score"],
                        "reason": d.reason if hasattr(d, "reason") else d.get("reason", ""),
                    }
                    for d in (rec.destinations if rec else [])
                ],
                "justification": rec.justification if rec else "",
                "approved": rec.approved if rec else False,
            } if rec else None,
            "errors": final_state.get("errors", []),
        })
    except Exception as e:
        _runs[run_id].update({
            "status": "failed",
            "errors": [str(e)],
        })


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "spain-rec"}


@app.post("/recommend", response_model=RecommendResponse)
def trigger_recommendation(req: RecommendRequest, background_tasks: BackgroundTasks):
    tourist_id = req.tourist_id or get_random_tourist_id()
    run_id = str(uuid.uuid4())

    _runs[run_id] = {
        "run_id": run_id,
        "tourist_id": tourist_id,
        "status": "queued",
        "current_step": None,
        "recommendation": None,
        "errors": [],
    }

    background_tasks.add_task(run_pipeline_sync, run_id, tourist_id)

    return RecommendResponse(
        run_id=run_id,
        tourist_id=tourist_id,
        status="queued",
        message="Pipeline started. Poll /recommend/status/{run_id} for results.",
    )


@app.get("/recommend/status/{run_id}", response_model=RunStatusResponse)
def get_run_status(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    run = _runs[run_id]
    return RunStatusResponse(**run)


@app.get("/tourists")
def list_tourists(limit: int = 10):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("""
        SELECT id, first_name, last_name, country_name, age_bracket
        FROM tourists LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": str(r[0]),
            "first_name": r[1],
            "last_name": r[2],
            "country_name": r[3],
            "age_bracket": r[4],
        }
        for r in rows
    ]


@app.get("/destinations")
def list_destinations():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("SELECT id, name, region, province FROM destinations ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": str(r[0]), "name": r[1], "region": r[2], "province": r[3]}
        for r in rows
    ]


@app.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    valid_signals = {"accepted", "ignored", "booked"}
    if req.signal_type not in valid_signals:
        raise HTTPException(
            status_code=400,
            detail=f"signal_type must be one of {valid_signals}"
        )
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO feedback_signals (id, recommendation_id, tourist_id, destination_id, signal_type, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (
        str(uuid.uuid4()),
        req.recommendation_id,
        req.tourist_id,
        req.destination_id,
        req.signal_type,
    ))
    conn.commit()
    conn.close()
    return {"status": "ok", "signal_type": req.signal_type}
