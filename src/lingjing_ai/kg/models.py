from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnowledgeGraphEntity:
    name: str
    type: str
    properties: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeGraphRelation:
    source: str
    source_type: str
    type: str
    target: str
    target_type: str
    document_id: str
    document_name: str
    chunk_id: str
    evidence: str


@dataclass(frozen=True)
class KnowledgeGraphDocument:
    entities: list[KnowledgeGraphEntity]
    relations: list[KnowledgeGraphRelation]
