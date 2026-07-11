from __future__ import annotations

from typing import Protocol

from lingjing_ai.kg.extractor import SCHEMA_VERSION, ChunkLike, KnowledgeGraphExtractor
from lingjing_ai.models.rag import SourceChunk


SCENARIO_RELATION_TYPES: dict[str, tuple[str, ...]] = {
    "route": ("NEAR", "WALK_TO", "HAS_FACILITY", "PASS_BY"),
    "recommend": ("SUITABLE_FOR", "HAS_STYLE", "HAS_DIFFICULTY"),
    "story": ("RELATED_PERSON", "RELATED_EVENT", "PARTICIPATED_IN", "HAPPENED_AT"),
}


class KnowledgeGraphStore(Protocol):
    def index_chunks(self, chunks: list[ChunkLike]) -> None:
        ...

    def search(self, question: str, top_k: int, scenario: str = "") -> list[SourceChunk]:
        ...

    def delete_document(self, document_id: str) -> None:
        ...

    def clear_document(self, document_id: str) -> None:
        ...

    def status(self) -> dict:
        ...


class DisabledKnowledgeGraphStore:
    def __init__(self, message: str = "知识图谱未启用") -> None:
        self.message = message

    def index_chunks(self, chunks: list[ChunkLike]) -> None:
        return None

    def search(self, question: str, top_k: int, scenario: str = "") -> list[SourceChunk]:
        return []

    def delete_document(self, document_id: str) -> None:
        return None

    def clear_document(self, document_id: str) -> None:
        return None

    def status(self) -> dict:
        return {
            "enabled": False,
            "node_count": 0,
            "relationship_count": 0,
            "schema_version": SCHEMA_VERSION,
            "message": self.message,
        }


class Neo4jKnowledgeGraphStore:
    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        schema_version: str = SCHEMA_VERSION,
        extractor: KnowledgeGraphExtractor | None = None,
    ) -> None:
        from neo4j import GraphDatabase

        self.uri = uri
        self.database = database
        self.schema_version = schema_version
        self.extractor = extractor or KnowledgeGraphExtractor()
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.driver.verify_connectivity()

    def index_chunks(self, chunks: list[ChunkLike]) -> None:
        if not chunks:
            return
        document_ids = sorted({chunk.document_id for chunk in chunks})
        for document_id in document_ids:
            self.clear_document(document_id)
        graph = self.extractor.extract(chunks)
        entity_by_key = {(entity.name, entity.type): entity for entity in graph.entities}
        with self.driver.session(database=self.database) as session:
            for relation in graph.relations:
                source_entity = entity_by_key.get((relation.source, relation.source_type))
                target_entity = entity_by_key.get((relation.target, relation.target_type))
                # Use one stable relationship label and keep the Chinese relation type as data,
                # because Neo4j cannot parameterize relationship labels safely.
                session.run(
                    """
                    MERGE (source:KGEntity {name: $source, type: $source_type})
                    MERGE (target:KGEntity {name: $target, type: $target_type})
                    SET source += $source_properties,
                        target += $target_properties
                    MERGE (source)-[relation:KG_RELATION {
                        type: $relation_type,
                        document_id: $document_id,
                        chunk_id: $chunk_id,
                        target: $target
                    }]->(target)
                    SET relation.document_name = $document_name,
                        relation.evidence = $evidence,
                        relation.schema_version = $schema_version,
                        relation.updated_at = datetime()
                    """,
                    source=relation.source,
                    source_type=relation.source_type,
                    target=relation.target,
                    target_type=relation.target_type,
                    source_properties=_neo4j_properties(source_entity.properties if source_entity else {}),
                    target_properties=_neo4j_properties(target_entity.properties if target_entity else {}),
                    relation_type=relation.type,
                    document_id=relation.document_id,
                    document_name=relation.document_name,
                    chunk_id=relation.chunk_id,
                    evidence=relation.evidence,
                    schema_version=self.schema_version,
                )

    def search(self, question: str, top_k: int, scenario: str = "") -> list[SourceChunk]:
        terms = self.extractor.extract_query_terms(question)
        if not terms:
            return []
        active_scenario = scenario or self.extractor.scenario_for_question(question)
        relation_types = SCENARIO_RELATION_TYPES.get(active_scenario, ())
        with self.driver.session(database=self.database) as session:
            rows = session.run(
                """
                MATCH (source:KGEntity)-[relation:KG_RELATION]->(target:KGEntity)
                WHERE relation.schema_version = $schema_version
                  AND (size($relation_types) = 0 OR relation.type IN $relation_types)
                  AND any(term IN $terms WHERE
                    source.name CONTAINS term OR
                    target.name CONTAINS term OR
                    relation.type CONTAINS term OR
                    relation.evidence CONTAINS term
                )
                RETURN source.name AS source,
                       source.type AS source_type,
                       relation.type AS relation_type,
                       target.name AS target,
                       target.type AS target_type,
                       relation.document_id AS document_id,
                       relation.document_name AS document_name,
                       relation.chunk_id AS chunk_id,
                       relation.evidence AS evidence
                LIMIT $limit
                """,
                terms=terms,
                relation_types=list(relation_types),
                schema_version=self.schema_version,
                limit=max(1, top_k * 3),
            )
            facts = [dict(row) for row in rows]
        return self._to_sources(facts, question, top_k, active_scenario)

    def delete_document(self, document_id: str) -> None:
        self.clear_document(document_id)

    def clear_document(self, document_id: str) -> None:
        with self.driver.session(database=self.database) as session:
            session.run(
                """
                MATCH ()-[relation:KG_RELATION {document_id: $document_id}]-()
                DELETE relation
                """,
                document_id=document_id,
            )
            session.run(
                """
                MATCH (entity:KGEntity)
                WHERE NOT (entity)--()
                DELETE entity
                """
            )

    def status(self) -> dict:
        with self.driver.session(database=self.database) as session:
            node_count = session.run("MATCH (entity:KGEntity) RETURN count(entity) AS count").single()["count"]
            relationship_count = session.run("MATCH ()-[relation:KG_RELATION]->() RETURN count(relation) AS count").single()["count"]
        return {
            "enabled": True,
            "node_count": node_count,
            "relationship_count": relationship_count,
            "schema_version": self.schema_version,
            "message": "Neo4j 知识图谱已启用",
        }

    def _to_sources(self, facts: list[dict], question: str, top_k: int, scenario: str) -> list[SourceChunk]:
        grouped: dict[tuple[str, str], list[dict]] = {}
        for fact in facts:
            key = (fact["document_id"], fact["chunk_id"])
            grouped.setdefault(key, []).append(fact)

        sources: list[SourceChunk] = []
        for (document_id, chunk_id), chunk_facts in grouped.items():
            fact_lines = [
                f"{fact['source']} {fact['relation_type']} {fact['target']}"
                for fact in chunk_facts[:6]
            ]
            evidence = chunk_facts[0].get("evidence") or ""
            score = _graph_score(question, " ".join(fact_lines) + evidence)
            sources.append(
                SourceChunk(
                    chunk_id=f"kg_{chunk_id}",
                    document_id=document_id,
                    document_name=chunk_facts[0].get("document_name") or "知识图谱",
                    content=f"图谱事实：{'；'.join(fact_lines)}。\n来源片段：{evidence}",
                    score=score,
                    metadata={"source_type": "knowledge_graph", "scenario": scenario},
                )
            )
        sources.sort(key=lambda source: source.score, reverse=True)
        return sources[:top_k]


def _graph_score(question: str, text: str) -> float:
    hits = sum(1 for char in set(question) if char.strip() and char in text)
    return min(0.98, 0.66 + hits / max(1, len(set(question))) * 0.30)


def _neo4j_properties(properties: dict[str, str]) -> dict[str, str]:
    normalized = dict(properties)
    if "type" in normalized:
        normalized["semantic_type"] = normalized.pop("type")
    return normalized
