from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime


# ── WEBSITE SCHEMAS ───────────────────────────────────────────────────────────

class WebsiteCreate(BaseModel):
    name: str
    domain: str
    allowed_origins: Optional[List[str]] = []
    settings: Optional[dict] = {}


class WebsiteUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    allowed_origins: Optional[List[str]] = None
    settings: Optional[dict] = None


class WebsiteResponse(BaseModel):
    id: UUID
    name: str
    domain: str
    allowed_origins: List[str]
    api_key: str
    status: str
    settings: dict
    total_threads: int
    total_comments: int
    created_at: datetime

    model_config = {"from_attributes": True}


class WebsiteSecretResponse(WebsiteResponse):
    """Only returned once at creation — includes the api_secret."""
    api_secret: str


# ── THREAD SCHEMAS ────────────────────────────────────────────────────────────

class ThreadCreate(BaseModel):
    identifier: str
    title: Optional[str] = None
    url: Optional[str] = None


class ThreadResponse(BaseModel):
    id: UUID
    website_id: UUID
    identifier: str
    title: Optional[str]
    url: Optional[str]
    status: str
    comment_count: int
    approved_comment_count: int
    last_comment_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── COMMENT SCHEMAS ───────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    author_name: str
    author_email: Optional[str] = None
    author_website: Optional[str] = None
    content: str
    parent_id: Optional[UUID] = None


class CommentUpdate(BaseModel):
    content: str


class CommentResponse(BaseModel):
    id: UUID
    thread_id: UUID
    parent_id: Optional[UUID] = None
    author_name: str
    author_website: Optional[str] = None
    content: str
    content_html: Optional[str] = None
    status: str
    upvotes: int
    downvotes: int
    reply_count: int
    is_edited: bool
    edited_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentTreeResponse(CommentResponse):
    replies: Optional[List["CommentTreeResponse"]] = []


CommentTreeResponse.model_rebuild()


class VoteRequest(BaseModel):
    vote_type: str  # "upvote" or "downvote"
    voter_identifier: str


# ── PAGINATION ────────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int

# ── FLAG RESPONSE ───────────────────────────────────────────────────────────

class FlagRequest(BaseModel):
    reason: str  # spam, offensive, off_topic, misinformation, other
    reporter_identifier: str
    description: Optional[str] = None


class ModerationReportResponse(BaseModel):
    id: UUID
    comment_id: UUID
    reporter_identifier: Optional[str] = None
    reporter_email: Optional[str] = None
    reason: str
    description: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
