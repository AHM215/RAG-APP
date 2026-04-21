# from pydantic import BaseModel, Field, validator
# from typing import Optional
# from bson.objectid import ObjectId

# class Project(BaseModel):
#     id: Optional[ObjectId] = Field(None, alias="_id")
#     project_id: str = Field(..., min_length=1)

#     @validator('project_id')
#     def validate_project_id(cls, value):
#         if not value.isalnum():
#             raise ValueError('project_id must be alphanumeric')
        
#         return value
    
#     @classmethod
#     def get_indexes(cls):
#         return [{
#             "key": [("project_id", 1)],
#             "name": "project_id_index_1",
#             "unique": True
#         }]

#     class Config:
#         arbitrary_types_allowed = True

## ----------------------------------------------------------
## usning SQLalchemy
from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.orm import relationship
from .minirag_base import SQLAlchemyBase
import re


class Project(SQLAlchemyBase):
    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True, autoincrement=True)
    project_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    chunks = relationship("DataChunk", back_populates="project")
    assets = relationship("Asset", back_populates="project")


