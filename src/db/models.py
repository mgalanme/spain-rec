from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ── Enumerations ─────────────────────────────────────────────────────────────

class TravelStyle(str, Enum):
    cultural = "cultural"
    adventure = "adventure"
    gastronomy = "gastronomy"
    nature = "nature"
    beach = "beach"
    urban = "urban"
    rural = "rural"


class DestinationCategory(str, Enum):
    coastal = "coastal"
    urban = "urban"
    rural = "rural"
    unesco = "unesco"
    gastronomy_hub = "gastronomy_hub"
    natural_park = "natural_park"
    historical = "historical"


class Season(str, Enum):
    spring = "spring"
    summer = "summer"
    autumn = "autumn"
    winter = "winter"


class SignalType(str, Enum):
    accepted = "accepted"
    ignored = "ignored"
    booked = "booked"


# ── Core entities ─────────────────────────────────────────────────────────────

class Cohort(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    country_code: str = Field(..., min_length=2, max_length=3)
    country_name: str
    cultural_region: str
    avg_trip_duration_days: float = Field(ge=1.0)
    preferred_seasons: list[Season]
    dominant_travel_styles: list[TravelStyle]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class Tourist(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    first_name: str
    last_name: str
    country_code: str = Field(..., min_length=2, max_length=3)
    country_name: str
    age_bracket: str = Field(..., pattern=r"^\d{2}-\d{2}$")
    travel_styles: list[TravelStyle]
    cohort_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class Destination(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    region: str
    province: str
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    categories: list[DestinationCategory]
    description: str
    seasonal_scores: dict[Season, float] = Field(
        description="Affinity score per season, 0.0 to 1.0"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class VisitEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tourist_id: UUID
    destination_id: UUID
    arrived_at: datetime
    departed_at: datetime
    rating: float = Field(ge=1.0, le=5.0)
    review: str | None = None
    activities: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def duration_days(self) -> float:
        delta = self.departed_at - self.arrived_at
        return delta.total_seconds() / 86400

    model_config = {"from_attributes": True}


class Recommendation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tourist_id: UUID
    cohort_id: UUID
    destinations: list[UUID] = Field(
        description="Ordered list of recommended destination IDs"
    )
    justification: str = Field(
        description="Narrative explanation produced by the CrewAI synthesiser"
    )
    approved: bool = False
    approved_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class FeedbackSignal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    recommendation_id: UUID
    tourist_id: UUID
    destination_id: UUID
    signal_type: SignalType
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


# ── Kafka message envelopes ───────────────────────────────────────────────────

class KafkaVisitEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = "visit.created"
    payload: VisitEvent
    produced_at: datetime = Field(default_factory=datetime.utcnow)


class KafkaRecommendationRequest(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = "recommendation.requested"
    tourist_id: UUID
    produced_at: datetime = Field(default_factory=datetime.utcnow)


class KafkaRecommendationOutput(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = "recommendation.completed"
    payload: Recommendation
    produced_at: datetime = Field(default_factory=datetime.utcnow)
