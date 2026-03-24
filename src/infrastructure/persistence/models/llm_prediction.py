"""LLM Prediction storage model."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from src.infrastructure.persistence.database import Base


class LLMPredictionDB(Base):
    """Database model for LLM predictions."""

    __tablename__ = "llm_predictions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Model info
    model_id = Column(PGUUID(as_uuid=True), nullable=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(20), default="1.0.0")

    # Input/Output
    prompt = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)

    # Metrics
    confidence = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=False)

    # Token usage
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    # Parameters used
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=512)

    # Metadata
    extra_data = Column(JSONB, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
