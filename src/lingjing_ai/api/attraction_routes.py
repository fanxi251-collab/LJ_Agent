from __future__ import annotations

from pathlib import Path
import uuid

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from lingjing_ai.services.attraction_store import (
    AttractionImageRecord,
    AttractionRecord,
    AttractionStore,
)


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


class AttractionPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=10000)
    category: str = Field(default="", max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=20)
    address: str = Field(default="", max_length=300)
    opening_hours: str = Field(default="", max_length=300)
    suggested_duration_minutes: int = Field(default=0, ge=0, le=1440)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    is_featured: bool = False
    sort_order: int = Field(default=0, ge=-100000, le=100000)
    status: str = Field(default="draft", pattern="^(draft|published|archived)$")


class AttractionImageResponse(BaseModel):
    image_id: str
    attraction_id: str
    url: str
    is_cover: bool
    sort_order: int


class AttractionImageUpdate(BaseModel):
    is_cover: bool = False
    sort_order: int = Field(default=0, ge=-100000, le=100000)


class AttractionResponse(BaseModel):
    attraction_id: str
    name: str
    summary: str
    description: str
    category: str
    tags: list[str]
    address: str
    opening_hours: str
    suggested_duration_minutes: int
    longitude: float
    latitude: float
    is_featured: bool
    sort_order: int
    status: str
    cover_image_url: str
    images: list[AttractionImageResponse]
    created_at: str
    updated_at: str


class AttractionListResponse(BaseModel):
    attractions: list[AttractionResponse]


class AttractionActionResponse(BaseModel):
    attraction_id: str
    message: str


def build_attraction_router(store: AttractionStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/visitor/attractions", response_model=AttractionListResponse)
    def list_visitor_attractions(
        q: str = "",
        category: str = "",
        featured: bool | None = None,
    ) -> AttractionListResponse:
        records = store.list_attractions(
            public_only=True,
            q=q,
            category=category,
            featured=featured,
        )
        return AttractionListResponse(attractions=[_to_response(record) for record in records])

    @router.get("/api/visitor/attractions/{attraction_id}", response_model=AttractionResponse)
    def get_visitor_attraction(attraction_id: str) -> AttractionResponse:
        return _required_attraction(store, attraction_id, public_only=True)

    @router.get("/api/admin/attractions", response_model=AttractionListResponse)
    def list_admin_attractions(q: str = "", status: str = "") -> AttractionListResponse:
        records = store.list_attractions(q=q, status=status)
        return AttractionListResponse(attractions=[_to_response(record) for record in records])

    @router.get("/api/admin/attractions/{attraction_id}", response_model=AttractionResponse)
    def get_admin_attraction(attraction_id: str) -> AttractionResponse:
        return _required_attraction(store, attraction_id)

    @router.post("/api/admin/attractions", response_model=AttractionResponse, status_code=201)
    def create_admin_attraction(payload: AttractionPayload) -> AttractionResponse:
        if payload.status == "published":
            # 新建记录尚未拥有图片，因此先落为草稿；管理员上传封面后再发布更可靠。
            payload = _copy_payload(payload, status="draft")
        return _to_response(store.create_attraction(_dump_payload(payload)))

    @router.put("/api/admin/attractions/{attraction_id}", response_model=AttractionResponse)
    def update_admin_attraction(attraction_id: str, payload: AttractionPayload) -> AttractionResponse:
        if payload.status == "published" and not store.has_cover(attraction_id):
            raise HTTPException(status_code=400, detail="发布景点前必须上传并设置封面图片。")
        record = store.update_attraction(attraction_id, _dump_payload(payload))
        if record is None:
            raise HTTPException(status_code=404, detail="景点不存在。")
        return _to_response(record)

    @router.delete("/api/admin/attractions/{attraction_id}", response_model=AttractionActionResponse)
    def archive_admin_attraction(attraction_id: str) -> AttractionActionResponse:
        if not store.archive_attraction(attraction_id):
            raise HTTPException(status_code=404, detail="景点不存在。")
        return AttractionActionResponse(attraction_id=attraction_id, message="景点已归档")

    @router.post(
        "/api/admin/attractions/{attraction_id}/images",
        response_model=AttractionImageResponse,
        status_code=201,
    )
    async def upload_attraction_image(
        attraction_id: str,
        file: UploadFile = File(...),
        is_cover: bool = Query(default=False),
        sort_order: int = Query(default=0),
    ) -> AttractionImageResponse:
        if store.get_attraction(attraction_id) is None:
            raise HTTPException(status_code=404, detail="景点不存在。")
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail="仅支持 JPG、PNG 或 WebP 图片。")
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="图片内容不能为空。")
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="图片大小不能超过 5 MB。")
        filename = f"{uuid.uuid4().hex}{suffix}"
        image_path = store.image_dir / filename
        image_path.write_bytes(content)
        image = store.add_image(attraction_id, filename, is_cover=is_cover, sort_order=sort_order)
        return _to_image_response(image)

    @router.delete(
        "/api/admin/attractions/{attraction_id}/images/{image_id}",
        response_model=AttractionImageResponse,
    )
    def delete_attraction_image(attraction_id: str, image_id: str) -> AttractionImageResponse:
        image = store.delete_image(attraction_id, image_id)
        if image is None:
            raise HTTPException(status_code=404, detail="景点图片不存在。")
        return _to_image_response(image)

    @router.put(
        "/api/admin/attractions/{attraction_id}/images/{image_id}",
        response_model=AttractionImageResponse,
    )
    def update_attraction_image(
        attraction_id: str,
        image_id: str,
        payload: AttractionImageUpdate,
    ) -> AttractionImageResponse:
        image = store.update_image(
            attraction_id,
            image_id,
            is_cover=payload.is_cover,
            sort_order=payload.sort_order,
        )
        if image is None:
            raise HTTPException(status_code=404, detail="景点图片不存在。")
        return _to_image_response(image)

    return router


def _required_attraction(
    store: AttractionStore,
    attraction_id: str,
    public_only: bool = False,
) -> AttractionResponse:
    record = store.get_attraction(attraction_id, public_only=public_only)
    if record is None:
        raise HTTPException(status_code=404, detail="景点不存在。")
    return _to_response(record)


def _to_response(record: AttractionRecord) -> AttractionResponse:
    return AttractionResponse(
        attraction_id=record.attraction_id,
        name=record.name,
        summary=record.summary,
        description=record.description,
        category=record.category,
        tags=record.tags,
        address=record.address,
        opening_hours=record.opening_hours,
        suggested_duration_minutes=record.suggested_duration_minutes,
        longitude=record.longitude,
        latitude=record.latitude,
        is_featured=record.is_featured,
        sort_order=record.sort_order,
        status=record.status,
        cover_image_url=record.cover_image_url,
        images=[_to_image_response(image) for image in record.images],
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_image_response(image: AttractionImageRecord) -> AttractionImageResponse:
    return AttractionImageResponse(
        image_id=image.image_id,
        attraction_id=image.attraction_id,
        url=image.url,
        is_cover=image.is_cover,
        sort_order=image.sort_order,
    )


def _dump_payload(payload: AttractionPayload) -> dict:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()


def _copy_payload(payload: AttractionPayload, **changes) -> AttractionPayload:
    if hasattr(payload, "model_copy"):
        return payload.model_copy(update=changes)
    return payload.copy(update=changes)
