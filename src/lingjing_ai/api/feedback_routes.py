from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from lingjing_ai.services.feedback_store import FeedbackRecord, FeedbackStore


CATEGORY_PATTERN = "^(service|environment|facility|food|guide|other)$"
STATUS_PATTERN = "^(pending|processing|resolved)$"


class FeedbackCreate(BaseModel):
    visitor_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    rating: int = Field(ge=1, le=5)
    category: str = Field(pattern=CATEGORY_PATTERN)
    content: str = Field(min_length=10, max_length=1000)
    contact: str = Field(default="", max_length=120)


class FeedbackUpdate(BaseModel):
    status: str = Field(pattern=STATUS_PATTERN)
    admin_reply: str = Field(default="", max_length=1000)


class VisitorFeedbackResponse(BaseModel):
    feedback_id: str
    rating: int
    category: str
    content: str
    status: str
    admin_reply: str
    created_at: str
    updated_at: str


class VisitorFeedbackListResponse(BaseModel):
    feedback: list[VisitorFeedbackResponse]


class AdminFeedbackResponse(VisitorFeedbackResponse):
    visitor_id: str
    request_id: str
    contact: str


class AdminFeedbackListResponse(BaseModel):
    feedback: list[AdminFeedbackResponse]


def build_feedback_router(store: FeedbackStore) -> APIRouter:
    router = APIRouter()

    @router.post("/api/visitor/feedback", response_model=VisitorFeedbackResponse, status_code=201)
    def create_feedback(payload: FeedbackCreate) -> VisitorFeedbackResponse:
        return _to_visitor_response(store.create_feedback(_dump_payload(payload)))

    @router.get("/api/visitor/feedback", response_model=VisitorFeedbackListResponse)
    def list_visitor_feedback(visitor_id: str = Query(min_length=1, max_length=128)) -> VisitorFeedbackListResponse:
        return VisitorFeedbackListResponse(
            feedback=[_to_visitor_response(record) for record in store.list_for_visitor(visitor_id)]
        )

    @router.get("/api/admin/feedback", response_model=AdminFeedbackListResponse)
    def list_admin_feedback(
        q: str = "",
        status: str = Query(default="", pattern=f"^$|{STATUS_PATTERN[1:-1]}"),
        category: str = Query(default="", pattern=f"^$|{CATEGORY_PATTERN[1:-1]}"),
        rating: int | None = Query(default=None, ge=1, le=5),
    ) -> AdminFeedbackListResponse:
        records = store.list_feedback(q=q, status=status, category=category, rating=rating)
        return AdminFeedbackListResponse(feedback=[_to_admin_response(record) for record in records])

    @router.patch("/api/admin/feedback/{feedback_id}", response_model=AdminFeedbackResponse)
    def update_admin_feedback(feedback_id: str, payload: FeedbackUpdate) -> AdminFeedbackResponse:
        record = store.update_feedback(feedback_id, payload.status, payload.admin_reply)
        if record is None:
            raise HTTPException(status_code=404, detail="反馈不存在。")
        return _to_admin_response(record)

    return router


def _to_visitor_response(record: FeedbackRecord) -> VisitorFeedbackResponse:
    # 游客响应故意不包含联系方式，避免历史列表反复暴露隐私字段。
    return VisitorFeedbackResponse(
        feedback_id=record.feedback_id,
        rating=record.rating,
        category=record.category,
        content=record.content,
        status=record.status,
        admin_reply=record.admin_reply,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_admin_response(record: FeedbackRecord) -> AdminFeedbackResponse:
    return AdminFeedbackResponse(
        **_model_dump(_to_visitor_response(record)),
        visitor_id=record.visitor_id,
        request_id=record.request_id,
        contact=record.contact,
    )


def _dump_payload(payload: BaseModel) -> dict:
    return _model_dump(payload)


def _model_dump(model: BaseModel) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()
