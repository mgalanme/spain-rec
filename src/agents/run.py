"""
Entry point for SPAIN-REC recommendation pipeline.
Picks a random tourist and runs the full LangGraph pipeline.
Usage: python3 src/agents/run.py [tourist_id]
"""
from __future__ import annotations

import os
import sys
import psycopg2
import random
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from src.agents.orchestrator import graph
from src.agents.state import OrchestratorState


def get_random_tourist_id() -> str:
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("SELECT id FROM tourists ORDER BY RANDOM() LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return str(row[0])


def main():
    if len(sys.argv) > 1:
        tourist_id = sys.argv[1]
    else:
        tourist_id = get_random_tourist_id()
        print(f"No tourist_id provided — using random: {tourist_id}")

    print("\n── SPAIN-REC Recommendation Pipeline ──\n")

    initial_state = OrchestratorState(tourist_id=tourist_id)
    final_state = graph.invoke(initial_state)

    print("\n── Pipeline complete ──")
    print(f"Status: {final_state['current_step']}")
    if final_state.get("errors"):
        print(f"Errors: {final_state['errors']}")


if __name__ == "__main__":
    main()
