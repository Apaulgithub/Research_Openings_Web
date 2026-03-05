"""Pydantic models for the Research Openings API."""
from typing import Optional
from pydantic import BaseModel


class Opening(BaseModel):
    """Schema for a single research opening."""
    institute: str
    network: str = ""
    department: str = ""
    title: str
    position_type: str
    deadline: str = ""
    detail_url: str = ""
    raw_text: str = ""
    hash: str = ""


class OpeningResponse(BaseModel):
    """Response envelope for listing openings."""
    total: int
    page: int
    page_size: int
    results: list[Opening]
