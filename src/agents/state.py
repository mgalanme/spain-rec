"""
Shared state for the SPAIN-REC LangGraph orchestrator.
All agents read from and write to this state object.
"""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages


class TouristContext(BaseModel):
    tourist_id: str
    first_name: str
    last_name: str
    country_code: str
    country_name: str
    age_bracket: str
    travel_styles: list[str]
    cohort_id: str
    visited_destination_ids: list[str] = Field(default_factory=list)
    visited_destination_names: list[str] = Field(default_factory=list)


class CohortContext(BaseModel):
    cohort_id: str
    country_code: str
    country_name: str
    cultural_region: str
    top_destinations: list[dict] = Field(default_factory=list)
    dominant_styles: list[str] = Field(default_factory=list)


class CandidateDestination(BaseModel):
    destination_id: str
    name: str
    region: str
    categories: list[str]
    description: str
    score: float
    reason: str = ""


class RecommendationOutput(BaseModel):
    destinations: list[CandidateDestination]
    justification: str
    approved: bool = False


class OrchestratorState(BaseModel):
    """Shared state passed between all LangGraph nodes."""

    # Input
    tourist_id: str

    # Populated by Profile Analyst Agent
    tourist_context: TouristContext | None = None

    # Populated by Cohort Intelligence Agent
    cohort_context: CohortContext | None = None

    # Populated by Destination Matcher Agent
    candidate_destinations: list[CandidateDestination] = Field(default_factory=list)

    # Populated by Recommendation Synthesiser
    recommendation: RecommendationOutput | None = None

    # HITL
    hitl_approved: bool = False
    hitl_feedback: str = ""

    # Pipeline metadata
    errors: list[str] = Field(default_factory=list)
    current_step: str = "start"
