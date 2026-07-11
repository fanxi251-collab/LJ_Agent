from __future__ import annotations

import re
from typing import Protocol

from lingjing_ai.kg.models import KnowledgeGraphDocument, KnowledgeGraphEntity, KnowledgeGraphRelation


SCHEMA_VERSION = "scenic_v1"


class ChunkLike(Protocol):
    id: str
    document_id: str
    document_name: str
    content: str
    metadata: dict[str, str]


SPOT_TYPES: dict[str, str] = {
    "灵山大佛": "宗教文化",
    "九龙灌浴": "表演",
    "灵山梵宫": "建筑",
    "梵宫": "建筑",
    "五印坛城": "宗教文化",
    "祥符禅寺": "古迹",
    "古栈道": "自然",
    "观景台": "自然",
}

FACILITY_TYPES: dict[str, str] = {
    "观光车站": "观光车站",
    "观光车": "观光车站",
    "休息区": "休息区",
    "休息点": "休息区",
    "厕所": "厕所",
    "卫生间": "厕所",
    "餐厅": "餐厅",
    "餐饮": "餐厅",
    "游客服务中心": "服务中心",
    "停车场": "停车场",
}

PERSON_PROFILES: dict[str, dict[str, str]] = {
    "玄奘": {"dynasty": "唐代", "identity": "高僧"},
    "李白": {"dynasty": "唐代", "identity": "诗人"},
}

EVENT_PROFILES: dict[str, dict[str, str]] = {
    "小灵山传说": {"year": "唐代", "type": "传说"},
    "玄奘传说": {"year": "唐代", "type": "传说"},
}

TAG_PROFILES: dict[str, tuple[str, str]] = {
    "老人友好": ("人群", "老人"),
    "儿童友好": ("人群", "儿童"),
    "亲子": ("人群", "亲子"),
    "情侣": ("人群", "情侣"),
    "摄影": ("风格", "摄影"),
    "轻松": ("体力", "轻松"),
    "中等": ("体力", "中等"),
    "陡峭": ("体力", "陡峭"),
}

DYNAMIC_KEYWORDS = ("天气", "气温", "门票", "票价", "价格", "开放时间", "营业时间", "用户评论", "评论")


class KnowledgeGraphExtractor:
    def __init__(
        self,
        max_relations_per_chunk: int = 8,
        enable_route_relations: bool = True,
        enable_recommend_relations: bool = True,
        enable_story_relations: bool = True,
    ) -> None:
        self.max_relations_per_chunk = max(1, max_relations_per_chunk)
        self.enable_route_relations = enable_route_relations
        self.enable_recommend_relations = enable_recommend_relations
        self.enable_story_relations = enable_story_relations

    def extract(self, chunks: list[ChunkLike]) -> KnowledgeGraphDocument:
        entity_by_key: dict[tuple[str, str], KnowledgeGraphEntity] = {}
        relation_by_key: dict[tuple[str, str, str, str], KnowledgeGraphRelation] = {}

        for chunk in chunks:
            entities = self._entities_for_chunk(chunk)
            for entity in entities:
                entity_by_key[(entity.name, entity.type)] = entity
            for relation in self._relations_for_chunk(chunk, entities):
                relation_by_key[(relation.source, relation.type, relation.target, relation.chunk_id)] = relation

        return KnowledgeGraphDocument(
            entities=list(entity_by_key.values()),
            relations=list(relation_by_key.values()),
        )

    def extract_query_terms(self, question: str) -> list[str]:
        entities = self._entities_in_text(question)
        terms = [entity.name for entity in entities]
        terms.extend(_query_words(question))
        unique: list[str] = []
        for term in terms:
            if term and term not in unique:
                unique.append(term)
        return unique[:12]

    def scenario_for_question(self, question: str) -> str:
        return classify_kg_scenario(question)

    def _entities_for_chunk(self, chunk: ChunkLike) -> list[KnowledgeGraphEntity]:
        text = f"{chunk.document_name} {chunk.content}"
        return self._entities_in_text(text)

    def _entities_in_text(self, text: str) -> list[KnowledgeGraphEntity]:
        found: list[KnowledgeGraphEntity] = []

        for name, spot_type in SPOT_TYPES.items():
            if name == "梵宫" and "灵山梵宫" in text:
                continue
            if name in text:
                found.append(
                    KnowledgeGraphEntity(
                        name=name,
                        type="景点",
                        properties={"type": spot_type, "difficulty": _difficulty_for_spot(name, text)},
                    )
                )

        for name, facility_type in FACILITY_TYPES.items():
            if name in text:
                canonical = _canonical_facility_name(name)
                found.append(KnowledgeGraphEntity(canonical, "设施", {"type": facility_type}))

        for name, properties in PERSON_PROFILES.items():
            if name in text:
                found.append(KnowledgeGraphEntity(name, "人物", dict(properties)))

        for name, properties in EVENT_PROFILES.items():
            if name in text or (name == "玄奘传说" and "小灵山传说" not in text and "玄奘" in text and "传说" in text):
                found.append(KnowledgeGraphEntity(name, "事件", dict(properties)))

        for tag_name, (category, trigger) in TAG_PROFILES.items():
            if trigger in text:
                found.append(KnowledgeGraphEntity(tag_name, "标签", {"category": category}))

        for route_name in re.findall(r"[\u4e00-\u9fff]{1,8}路线", text):
            if route_name in {"推荐路线", "游览路线", "轻松路线", "经典路线"}:
                continue
            found.append(KnowledgeGraphEntity(route_name, "路线", {"type": "游览路线"}))

        return _dedupe_entities(found)

    def _relations_for_chunk(
        self,
        chunk: ChunkLike,
        entities: list[KnowledgeGraphEntity],
    ) -> list[KnowledgeGraphRelation]:
        route_relations: list[tuple[KnowledgeGraphEntity, str, KnowledgeGraphEntity]] = []
        recommend_relations: list[tuple[KnowledgeGraphEntity, str, KnowledgeGraphEntity]] = []
        story_relations: list[tuple[KnowledgeGraphEntity, str, KnowledgeGraphEntity]] = []
        text = chunk.content
        spots = [entity for entity in entities if entity.type == "景点"]
        facilities = [entity for entity in entities if entity.type == "设施"]
        tags = [entity for entity in entities if entity.type == "标签"]
        people = [entity for entity in entities if entity.type == "人物"]
        events = [entity for entity in entities if entity.type == "事件"]
        routes = [entity for entity in entities if entity.type == "路线"]

        if self.enable_route_relations:
            route_relations = self._route_relations(text, spots, facilities, routes)
        if self.enable_recommend_relations:
            recommend_relations = self._recommend_relations(text, spots, tags)
        if self.enable_story_relations:
            story_relations = self._story_relations(text, spots, people, events)

        limited = _balanced_relations(
            [route_relations, recommend_relations, story_relations],
            self.max_relations_per_chunk,
        )
        return [
            KnowledgeGraphRelation(
                source=source.name,
                source_type=source.type,
                type=relation_type,
                target=target.name,
                target_type=target.type,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                chunk_id=chunk.id,
                evidence=_evidence(chunk.content),
            )
            for source, relation_type, target in limited
            if source.name != target.name
        ]

    def _route_relations(
        self,
        text: str,
        spots: list[KnowledgeGraphEntity],
        facilities: list[KnowledgeGraphEntity],
        routes: list[KnowledgeGraphEntity],
    ) -> list[tuple[KnowledgeGraphEntity, str, KnowledgeGraphEntity]]:
        relations: list[tuple[KnowledgeGraphEntity, str, KnowledgeGraphEntity]] = []
        if any(keyword in text for keyword in ("挨着", "相邻", "附近", "旁边")):
            pairs = _spot_pairs(spots)
            relations.extend((left, "NEAR", right) for left, right in pairs[:1])
        if any(keyword in text for keyword in ("附近", "提供", "有", "设有")):
            for spot in _facility_spots(text, spots):
                relations.extend((spot, "HAS_FACILITY", facility) for facility in facilities)
        for route in routes:
            relations.extend((route, "PASS_BY", spot) for spot in spots)
        if any(keyword in text for keyword in ("步行", "怎么走", "省力", "轻松")):
            relations.extend((left, "WALK_TO", right) for left, right in _spot_pairs(spots))
        if any(keyword in text for keyword in ("挨着", "相邻", "附近", "旁边")):
            relations.extend((left, "NEAR", right) for left, right in _spot_pairs(spots)[1:])
        return relations

    def _recommend_relations(
        self,
        text: str,
        spots: list[KnowledgeGraphEntity],
        tags: list[KnowledgeGraphEntity],
    ) -> list[tuple[KnowledgeGraphEntity, str, KnowledgeGraphEntity]]:
        relations: list[tuple[KnowledgeGraphEntity, str, KnowledgeGraphEntity]] = []
        suitable_added = False
        target_spots = _recommend_priority_spots(text, spots)
        for spot in target_spots:
            for tag in tags:
                if tag.properties.get("category") == "人群" and any(keyword in text for keyword in ("适合", "推荐", "友好")):
                    relations.append((spot, "SUITABLE_FOR", tag))
                    suitable_added = True
                elif tag.properties.get("category") == "风格":
                    relations.append((spot, "HAS_STYLE", tag))
                elif tag.properties.get("category") == "体力" and not suitable_added:
                    relations.append((spot, "HAS_DIFFICULTY", tag))
        return relations

    def _story_relations(
        self,
        text: str,
        spots: list[KnowledgeGraphEntity],
        people: list[KnowledgeGraphEntity],
        events: list[KnowledgeGraphEntity],
    ) -> list[tuple[KnowledgeGraphEntity, str, KnowledgeGraphEntity]]:
        relations: list[tuple[KnowledgeGraphEntity, str, KnowledgeGraphEntity]] = []
        if not any(keyword in text for keyword in ("历史", "传说", "相关", "文化", "典故")):
            return relations
        for person in people:
            relations.extend((person, "PARTICIPATED_IN", event) for event in events)
        for event in events:
            if spots:
                relations.append((event, "HAPPENED_AT", spots[0]))
        for spot in spots:
            relations.extend((spot, "RELATED_PERSON", person) for person in people)
            relations.extend((spot, "RELATED_EVENT", event) for event in events)
        return relations


def _dedupe_entities(entities: list[KnowledgeGraphEntity]) -> list[KnowledgeGraphEntity]:
    result: list[KnowledgeGraphEntity] = []
    seen: set[tuple[str, str]] = set()
    for entity in entities:
        key = (entity.name, entity.type)
        if key in seen:
            continue
        seen.add(key)
        result.append(entity)
    return result


def _spot_pairs(spots: list[KnowledgeGraphEntity]) -> list[tuple[KnowledgeGraphEntity, KnowledgeGraphEntity]]:
    return [(spots[index], spots[index + 1]) for index in range(len(spots) - 1)]


def _facility_priority_spots(text: str, spots: list[KnowledgeGraphEntity]) -> list[KnowledgeGraphEntity]:
    return sorted(
        spots,
        key=lambda spot: (f"{spot.name}附近" in text or f"{spot.name}设有" in text or f"{spot.name}有" in text),
        reverse=True,
    )


def _facility_spots(text: str, spots: list[KnowledgeGraphEntity]) -> list[KnowledgeGraphEntity]:
    explicit = [
        spot
        for spot in spots
        if f"{spot.name}附近" in text or f"{spot.name}设有" in text or f"{spot.name}有" in text
    ]
    return explicit or _facility_priority_spots(text, spots)


def _balanced_relations(
    groups: list[list[tuple[KnowledgeGraphEntity, str, KnowledgeGraphEntity]]],
    limit: int,
) -> list[tuple[KnowledgeGraphEntity, str, KnowledgeGraphEntity]]:
    selected: list[tuple[KnowledgeGraphEntity, str, KnowledgeGraphEntity]] = []
    for index in range(2):
        for group in groups:
            if len(selected) >= limit:
                return selected
            if index < len(group):
                selected.append(group[index])
    for group in groups:
        for relation in group[2:]:
            if len(selected) >= limit:
                return selected
            selected.append(relation)
    return selected


def _recommend_priority_spots(text: str, spots: list[KnowledgeGraphEntity]) -> list[KnowledgeGraphEntity]:
    explicit = [
        spot
        for spot in spots
        if f"{spot.name}适合" in text or f"{spot.name}推荐" in text or f"{spot.name}友好" in text
    ]
    return explicit or spots[:1]


def _canonical_facility_name(name: str) -> str:
    if name in {"观光车"}:
        return "观光车站"
    if name in {"休息点"}:
        return "休息区"
    if name in {"卫生间"}:
        return "厕所"
    if name in {"餐饮"}:
        return "餐厅"
    return name


def _difficulty_for_spot(name: str, text: str) -> str:
    if "陡峭" in text or "台阶" in text:
        return "陡峭"
    if "中等" in text or name in {"灵山大佛", "古栈道"}:
        return "中等"
    return "轻松"


def _evidence(content: str) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    for keyword in DYNAMIC_KEYWORDS:
        compact = compact.replace(keyword, "")
    return compact[:180]


def _query_words(question: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]+", question.lower())
        if word not in {"什么", "如何", "怎么", "哪些", "一下", "请问"}
    ]


def classify_kg_scenario(question: str) -> str:
    if any(keyword in question for keyword in ("路线", "怎么走", "怎么去", "怎么安排", "省力", "轻松", "半日", "顺序")):
        return "route"
    if any(keyword in question for keyword in ("适合", "推荐", "老人", "儿童", "孩子", "亲子", "情侣", "拍照", "摄影")):
        return "recommend"
    if any(keyword in question for keyword in ("历史", "传说", "人物", "名人", "典故", "文化", "玄奘", "李白", "关系")):
        return "story"
    return ""
