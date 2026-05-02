"""本地图谱构建器：分块 → 并行抽取 → 写入 Neo4j（+可选 Qdrant）"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger
from .text_processor import TextProcessor
from .local_graph_extractor import LocalGraphExtractor
from .local_graph_store import LocalEntity, LocalNeo4jGraphStore, LocalRelation
from .entity_type_normalizer import canonicalize_entity_type
from .local_vector_store import QdrantChunkStore

logger = get_logger("minifish.local_graph_builder")


def _now_iso() -> str:
    return datetime.now().isoformat()


class LocalGraphBuilderService:
    def __init__(self):
        self.store = LocalNeo4jGraphStore()
        self.extractor = LocalGraphExtractor()
        self.vector_store = None

    def _get_vector_store(self) -> Optional[QdrantChunkStore]:
        if Config.VECTOR_BACKEND != "qdrant":
            return None
        if self.vector_store is not None:
            return self.vector_store
        try:
            self.vector_store = QdrantChunkStore()
        except Exception as e:
            logger.warning(f"Qdrant init failed, vector features disabled: {e}")
            self.vector_store = None
        return self.vector_store

    def create_graph(self, project_id: str, name: str, ontology: Optional[Dict[str, Any]] = None) -> str:
        return self.store.create_graph(project_id=project_id, name=name, ontology=ontology)

    def delete_graph(self, graph_id: str):
        return self.store.delete_graph(graph_id)

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        return self.store.get_graph_data(graph_id)

    def build_graph_from_text(
        self,
        project_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        on_graph_id: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        if progress_callback:
            progress_callback("创建本地图谱（Neo4j）...", 0.02)

        graph_id = self.create_graph(project_id=project_id, name=graph_name, ontology=ontology)
        if on_graph_id:
            try:
                on_graph_id(graph_id)
            except Exception as e:
                logger.warning(f"on_graph_id callback failed: {e}")

        chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
        total = max(len(chunks), 1)
        failed_extract_chunks = 0
        concurrency = Config.EXTRACTION_CONCURRENCY

        completed_count = 0
        count_lock = Lock()

        def process_chunk(idx: int, chunk: str):
            chunk_id = f"chunk_{uuid.uuid4().hex[:12]}"
            self.store.upsert_chunk(project_id=project_id, graph_id=graph_id, chunk_id=chunk_id, text=chunk)

            vector_store = self._get_vector_store()
            if vector_store is not None:
                try:
                    vector_store.add_chunk(
                        project_id=project_id,
                        graph_id=graph_id,
                        chunk_id=chunk_id,
                        text=chunk,
                        extra_payload={"type": "chunk"},
                    )
                except Exception as e:
                    logger.warning(f"Qdrant add_chunk failed, continue without vectors: {e}")

            try:
                extracted = self.extractor.extract(chunk, ontology=ontology)
            except Exception as e:
                logger.warning(f"Extractor failed for chunk {idx+1}/{total}; skipping: {e}")
                return idx, None, chunk_id

            return idx, extracted, chunk_id

        futures = {}
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            for idx, chunk in enumerate(chunks):
                future = executor.submit(process_chunk, idx, chunk)
                futures[future] = idx

            for future in as_completed(futures):
                idx, extracted, chunk_id = future.result()

                if extracted is None:
                    failed_extract_chunks += 1
                else:
                    entities_in_chunk = extracted.get("entities") or []
                    relations_in_chunk = extracted.get("relations") or []

                    entities: List[LocalEntity] = []
                    for ent in entities_in_chunk:
                        raw_type = ent.get("type", "")
                        canonical_type = canonicalize_entity_type(raw_type)
                        entities.append(
                            LocalEntity(
                                project_id=project_id,
                                graph_id=graph_id,
                                name=ent.get("name", ""),
                                entity_type=canonical_type,
                                summary=ent.get("summary", ""),
                                attributes=ent.get("attributes") or {},
                                source_entity_types=[raw_type] if raw_type else [],
                                created_at=_now_iso(),
                            )
                        )

                    entity_uuids = self.store.upsert_entities(entities)
                    self.store.link_mentions(chunk_id=chunk_id, entity_uuids=entity_uuids, graph_id=graph_id)

                    uuid_by_key: Dict[str, str] = {}
                    for ent in entities:
                        uuid_by_key[f"{ent.entity_type}:{ent.name}".lower()] = ent.uuid

                    relations: List[LocalRelation] = []
                    for rel in relations_in_chunk:
                        s_type = canonicalize_entity_type(rel.get("source_type"))
                        t_type = canonicalize_entity_type(rel.get("target_type"))
                        s_key = f"{s_type}:{rel.get('source')}".lower()
                        t_key = f"{t_type}:{rel.get('target')}".lower()
                        source_uuid = uuid_by_key.get(s_key)
                        target_uuid = uuid_by_key.get(t_key)
                        if not source_uuid or not target_uuid:
                            continue
                        relations.append(
                            LocalRelation(
                                project_id=project_id,
                                graph_id=graph_id,
                                source_uuid=source_uuid,
                                target_uuid=target_uuid,
                                relation_name=rel.get("relation", ""),
                                fact=rel.get("fact", ""),
                                attributes=rel.get("attributes") or {},
                                created_at=_now_iso(),
                            )
                        )

                    self.store.upsert_relations(relations)

                with count_lock:
                    completed_count += 1
                    done = completed_count
                if progress_callback:
                    ratio = done / total
                    progress_callback(f"抽取实体/关系: {done}/{total}", 0.05 + ratio * 0.85)

        if progress_callback:
            progress_callback("读取图谱数据...", 0.95)

        graph_data = self.get_graph_data(graph_id)
        if failed_extract_chunks:
            graph_data["build_warnings"] = [
                f"Extractor failed for {failed_extract_chunks}/{total} chunks; graph may be incomplete."
            ]
        if progress_callback:
            progress_callback("完成", 1.0)

        return graph_id, graph_data
