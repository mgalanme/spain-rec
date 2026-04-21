from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column, String, Float, Boolean, Text,
    DateTime, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class CohortRow(Base):
    __tablename__ = "cohorts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    country_code = Column(String(3), nullable=False, unique=True)
    country_name = Column(String(100), nullable=False)
    cultural_region = Column(String(100), nullable=False)
    avg_trip_duration_days = Column(Float, nullable=False)
    preferred_seasons = Column(JSON, nullable=False)
    dominant_travel_styles = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tourists = relationship("TouristRow", back_populates="cohort")


class TouristRow(Base):
    __tablename__ = "tourists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    country_code = Column(String(3), nullable=False)
    country_name = Column(String(100), nullable=False)
    age_bracket = Column(String(10), nullable=False)
    travel_styles = Column(JSON, nullable=False)
    cohort_id = Column(UUID(as_uuid=True), ForeignKey("cohorts.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    cohort = relationship("CohortRow", back_populates="tourists")
    visits = relationship("VisitEventRow", back_populates="tourist")
    recommendations = relationship("RecommendationRow", back_populates="tourist")


class DestinationRow(Base):
    __tablename__ = "destinations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(200), nullable=False)
    region = Column(String(100), nullable=False)
    province = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    categories = Column(JSON, nullable=False)
    description = Column(Text, nullable=False)
    seasonal_scores = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    visits = relationship("VisitEventRow", back_populates="destination")


class VisitEventRow(Base):
    __tablename__ = "visit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tourist_id = Column(UUID(as_uuid=True), ForeignKey("tourists.id"), nullable=False)
    destination_id = Column(UUID(as_uuid=True), ForeignKey("destinations.id"), nullable=False)
    arrived_at = Column(DateTime, nullable=False)
    departed_at = Column(DateTime, nullable=False)
    rating = Column(Float, nullable=False)
    review = Column(Text, nullable=True)
    activities = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tourist = relationship("TouristRow", back_populates="visits")
    destination = relationship("DestinationRow", back_populates="visits")


class RecommendationRow(Base):
    __tablename__ = "recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tourist_id = Column(UUID(as_uuid=True), ForeignKey("tourists.id"), nullable=False)
    cohort_id = Column(UUID(as_uuid=True), ForeignKey("cohorts.id"), nullable=False)
    destinations = Column(JSON, nullable=False)
    justification = Column(Text, nullable=False)
    approved = Column(Boolean, default=False, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tourist = relationship("TouristRow", back_populates="recommendations")
    feedback = relationship("FeedbackSignalRow", back_populates="recommendation")


class FeedbackSignalRow(Base):
    __tablename__ = "feedback_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    recommendation_id = Column(UUID(as_uuid=True), ForeignKey("recommendations.id"), nullable=False)
    tourist_id = Column(UUID(as_uuid=True), ForeignKey("tourists.id"), nullable=False)
    destination_id = Column(UUID(as_uuid=True), ForeignKey("destinations.id"), nullable=False)
    signal_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    recommendation = relationship("RecommendationRow", back_populates="feedback")


class PipelineRunRow(Base):
    __tablename__ = "pipeline_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tourist_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(String(20), nullable=False)
    agent_outputs = Column(JSON, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
