from .minirag_base import SQLAlchemyBase
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

class DataChunk(SQLAlchemyBase):
    __tablename__ = "data_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True)
    chunk_text = Column(String, nullable=False)
    chunk_metadata = Column(JSONB, nullable=False)
    chunk_order = Column(Integer, nullable=False)
    chunk_project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    chunk_asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    project = relationship("Project", back_populates="chunks")
    asset = relationship("Asset", back_populates="chunks")

    __table_args__ = (
        Index('ix_chunk_project_id',chunk_project_id),
        Index('ix_chunk_asset_id',chunk_asset_id)
    )


class RetrievedDocument(BaseModel):
    text: str
    score: float
    chunk_id: int | None = None
    rerank_score: float | None = None
    metadata: dict | None = None


