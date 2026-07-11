from lingjing_ai.config.settings import AppSettings
from lingjing_ai.kg.extractor import KnowledgeGraphExtractor
from lingjing_ai.kg.store import DisabledKnowledgeGraphStore, Neo4jKnowledgeGraphStore, KnowledgeGraphStore


def build_knowledge_graph_store(settings: AppSettings) -> KnowledgeGraphStore:
    if not settings.kg_enabled:
        return DisabledKnowledgeGraphStore("Neo4j 未启用，请设置 KG_ENABLED=true。")
    if not settings.neo4j_uri or not settings.neo4j_user or not settings.neo4j_password:
        return DisabledKnowledgeGraphStore("Neo4j 未配置，请设置 NEO4J_URI、NEO4J_USER、NEO4J_PASSWORD。")
    try:
        return Neo4jKnowledgeGraphStore(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            database=settings.neo4j_database,
            schema_version=settings.kg_schema_version,
            extractor=KnowledgeGraphExtractor(
                max_relations_per_chunk=settings.kg_max_relations_per_chunk,
                enable_route_relations=settings.kg_enable_route_relations,
                enable_recommend_relations=settings.kg_enable_recommend_relations,
                enable_story_relations=settings.kg_enable_story_relations,
            ),
        )
    except ImportError:
        return DisabledKnowledgeGraphStore("未安装 neo4j Python 驱动，请先安装 neo4j。")
    except Exception as exc:
        return DisabledKnowledgeGraphStore(f"Neo4j 连接失败：{exc}")
