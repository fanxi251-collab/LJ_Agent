from __future__ import annotations

from pathlib import Path
import uuid

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from lingjing_ai.services.food_store import FoodImageRecord, FoodRecord, FoodStore


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


class FoodPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=10000)
    scope: str = Field(pattern="^(inside|nearby)$")
    category: str = Field(min_length=1, max_length=80)
    taste_tags: list[str] = Field(default_factory=list, max_length=20)
    signature_dishes: list[str] = Field(default_factory=list, max_length=20)
    price_level: int = Field(ge=1, le=4)
    vegetarian_friendly: bool = False
    address: str = Field(min_length=1, max_length=300)
    opening_hours: str = Field(default="", max_length=300)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    source_url: str = Field(default="", max_length=500)
    verified_at: str = Field(default="", max_length=10, pattern=r"^(|\d{4}-\d{2}-\d{2})$")
    is_featured: bool = False
    sort_order: int = Field(default=0, ge=-100000, le=100000)
    status: str = Field(default="draft", pattern="^(draft|published|archived)$")


class FoodImageResponse(BaseModel):
    image_id: str
    food_id: str
    url: str
    is_cover: bool
    sort_order: int


class FoodImageUpdate(BaseModel):
    is_cover: bool = False
    sort_order: int = Field(default=0, ge=-100000, le=100000)


class FoodResponse(BaseModel):
    food_id: str
    name: str
    summary: str
    description: str
    scope: str
    category: str
    taste_tags: list[str]
    signature_dishes: list[str]
    price_level: int
    vegetarian_friendly: bool
    address: str
    opening_hours: str
    longitude: float
    latitude: float
    source_url: str
    verified_at: str
    is_featured: bool
    sort_order: int
    status: str
    cover_image_url: str
    images: list[FoodImageResponse]
    created_at: str
    updated_at: str


class FoodListResponse(BaseModel):
    foods: list[FoodResponse]


class FoodActionResponse(BaseModel):
    food_id: str
    message: str


def build_food_router(store: FoodStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/visitor/foods", response_model=FoodListResponse)
    def list_visitor_foods(
        q: str = "",
        scope: str = "",
        category: str = "",
        taste: str = "",
        price_level: int | None = Query(default=None, ge=1, le=4),
        vegetarian: bool | None = None,
        featured: bool | None = None,
    ) -> FoodListResponse:
        records = store.list_foods(
            public_only=True,
            q=q,
            scope=scope,
            category=category,
            taste=taste,
            price_level=price_level,
            vegetarian=vegetarian,
            featured=featured,
        )
        return FoodListResponse(foods=[_to_response(record) for record in records])

    @router.get("/api/visitor/foods/{food_id}", response_model=FoodResponse)
    def get_visitor_food(food_id: str) -> FoodResponse:
        return _required_food(store, food_id, public_only=True)

    @router.get("/api/admin/foods", response_model=FoodListResponse)
    def list_admin_foods(q: str = "", status: str = "") -> FoodListResponse:
        records = store.list_foods(q=q, status=status)
        return FoodListResponse(foods=[_to_response(record) for record in records])

    @router.get("/api/admin/foods/{food_id}", response_model=FoodResponse)
    def get_admin_food(food_id: str) -> FoodResponse:
        return _required_food(store, food_id)

    @router.post("/api/admin/foods", response_model=FoodResponse, status_code=201)
    def create_admin_food(payload: FoodPayload) -> FoodResponse:
        if payload.status == "published":
            # 新记录还没有封面，先保留为草稿才能满足发布完整性约束。
            payload = _copy_payload(payload, status="draft")
        return _to_response(store.create_food(_dump_payload(payload)))

    @router.put("/api/admin/foods/{food_id}", response_model=FoodResponse)
    def update_admin_food(food_id: str, payload: FoodPayload) -> FoodResponse:
        if payload.status == "published":
            _validate_publishable(store, food_id, payload)
        record = store.update_food(food_id, _dump_payload(payload))
        if record is None:
            raise HTTPException(status_code=404, detail="美食内容不存在。")
        return _to_response(record)

    @router.delete("/api/admin/foods/{food_id}", response_model=FoodActionResponse)
    def archive_admin_food(food_id: str) -> FoodActionResponse:
        if not store.archive_food(food_id):
            raise HTTPException(status_code=404, detail="美食内容不存在。")
        return FoodActionResponse(food_id=food_id, message="美食内容已归档")

    @router.post(
        "/api/admin/foods/{food_id}/images",
        response_model=FoodImageResponse,
        status_code=201,
    )
    async def upload_food_image(
        food_id: str,
        file: UploadFile = File(...),
        is_cover: bool = Query(default=False),
        sort_order: int = Query(default=0),
    ) -> FoodImageResponse:
        if store.get_food(food_id) is None:
            raise HTTPException(status_code=404, detail="美食内容不存在。")
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail="仅支持 JPG、PNG 或 WebP 图片。")
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="图片内容不能为空。")
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="图片大小不能超过 5 MB。")
        filename = f"{uuid.uuid4().hex}{suffix}"
        (store.image_dir / filename).write_bytes(content)
        return _to_image_response(store.add_image(food_id, filename, is_cover, sort_order))

    @router.put(
        "/api/admin/foods/{food_id}/images/{image_id}",
        response_model=FoodImageResponse,
    )
    def update_food_image(food_id: str, image_id: str, payload: FoodImageUpdate) -> FoodImageResponse:
        image = store.update_image(food_id, image_id, payload.is_cover, payload.sort_order)
        if image is None:
            raise HTTPException(status_code=404, detail="美食图片不存在。")
        return _to_image_response(image)

    @router.delete(
        "/api/admin/foods/{food_id}/images/{image_id}",
        response_model=FoodImageResponse,
    )
    def delete_food_image(food_id: str, image_id: str) -> FoodImageResponse:
        image = store.delete_image(food_id, image_id)
        if image is None:
            raise HTTPException(status_code=404, detail="美食图片不存在。")
        return _to_image_response(image)

    return router


def _validate_publishable(store: FoodStore, food_id: str, payload: FoodPayload) -> None:
    if not store.has_cover(food_id):
        raise HTTPException(status_code=400, detail="发布美食内容前必须上传并设置封面图片。")
    if not payload.verified_at:
        raise HTTPException(status_code=400, detail="发布美食内容前必须填写核验日期。")
    if payload.longitude == 0 and payload.latitude == 0:
        raise HTTPException(status_code=400, detail="发布美食内容前必须填写有效位置。")


def _required_food(store: FoodStore, food_id: str, public_only: bool = False) -> FoodResponse:
    record = store.get_food(food_id, public_only=public_only)
    if record is None:
        raise HTTPException(status_code=404, detail="美食内容不存在。")
    return _to_response(record)


def _to_response(record: FoodRecord) -> FoodResponse:
    return FoodResponse(
        food_id=record.food_id,
        name=record.name,
        summary=record.summary,
        description=record.description,
        scope=record.scope,
        category=record.category,
        taste_tags=record.taste_tags,
        signature_dishes=record.signature_dishes,
        price_level=record.price_level,
        vegetarian_friendly=record.vegetarian_friendly,
        address=record.address,
        opening_hours=record.opening_hours,
        longitude=record.longitude,
        latitude=record.latitude,
        source_url=record.source_url,
        verified_at=record.verified_at,
        is_featured=record.is_featured,
        sort_order=record.sort_order,
        status=record.status,
        cover_image_url=record.cover_image_url,
        images=[_to_image_response(image) for image in record.images],
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_image_response(image: FoodImageRecord | None) -> FoodImageResponse:
    if image is None:
        raise HTTPException(status_code=404, detail="美食图片不存在。")
    return FoodImageResponse(
        image_id=image.image_id,
        food_id=image.food_id,
        url=image.url,
        is_cover=image.is_cover,
        sort_order=image.sort_order,
    )


def _dump_payload(payload: FoodPayload) -> dict:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()


def _copy_payload(payload: FoodPayload, **changes) -> FoodPayload:
    if hasattr(payload, "model_copy"):
        return payload.model_copy(update=changes)
    return payload.copy(update=changes)

