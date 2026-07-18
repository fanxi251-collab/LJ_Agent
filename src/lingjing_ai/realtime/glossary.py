from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import time
from typing import Any, Callable

import yaml


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class GlossaryTerm:
    canonical: str
    aliases: tuple[str, ...]
    pinyin: str
    weight: int
    manual: bool


@dataclass(frozen=True)
class GlossarySnapshot:
    terms: tuple[GlossaryTerm, ...]


class GlossaryProvider:
    """Builds an immutable scenic glossary so each turn sees one consistent vocabulary."""

    def __init__(
        self,
        attraction_store: Any,
        document_manifest: Any,
        yaml_path: Path,
        ttl_seconds: int = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.attraction_store = attraction_store
        self.document_manifest = document_manifest
        self.yaml_path = Path(yaml_path)
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.clock = clock
        self._auto_terms: dict[str, GlossaryTerm] = {}
        self._auto_expires_at = 0.0
        self._manual_terms: dict[str, GlossaryTerm] = {}
        self._manual_mtime_ns: int | None = None

    def snapshot(self) -> GlossarySnapshot:
        now = self.clock()
        if now >= self._auto_expires_at:
            self._auto_terms = self._load_auto_terms()
            self._auto_expires_at = now + self.ttl_seconds
        self._reload_manual_if_changed()
        merged = {**self._auto_terms, **self._manual_terms}
        return GlossarySnapshot(tuple(sorted(merged.values(), key=lambda item: item.canonical)))

    def _load_auto_terms(self) -> dict[str, GlossaryTerm]:
        terms: dict[str, GlossaryTerm] = {}
        try:
            attractions = self.attraction_store.list_attractions(public_only=True)
        except Exception:
            attractions = []
            LOGGER.warning("ASR glossary could not read published attractions", exc_info=True)
        for attraction in attractions:
            self._add_auto(terms, getattr(attraction, "name", ""), weight=3)
            for tag in getattr(attraction, "tags", []) or []:
                self._add_auto(terms, tag, weight=2)
        try:
            records = self.document_manifest.list_records()
        except Exception:
            records = []
            LOGGER.warning("ASR glossary could not read document titles", exc_info=True)
        for record in records:
            name = Path(str(getattr(record, "document_name", ""))).stem
            self._add_auto(terms, name, weight=2)
        return terms

    def _add_auto(self, terms: dict[str, GlossaryTerm], value: str, weight: int) -> None:
        canonical = str(value or "").strip()
        if not canonical or len(canonical) > 40:
            return
        terms[canonical] = GlossaryTerm(canonical, (), _to_pinyin(canonical), weight, False)

    def _reload_manual_if_changed(self) -> None:
        try:
            mtime_ns = self.yaml_path.stat().st_mtime_ns
        except OSError:
            mtime_ns = None
        if mtime_ns == self._manual_mtime_ns:
            return
        self._manual_mtime_ns = mtime_ns
        self._manual_terms = self._load_manual_terms() if mtime_ns is not None else {}

    def _load_manual_terms(self) -> dict[str, GlossaryTerm]:
        try:
            payload = yaml.safe_load(self.yaml_path.read_text(encoding="utf-8")) or {}
        except Exception:
            LOGGER.warning("ASR glossary YAML is invalid; automatic terms remain active", exc_info=True)
            return {}
        if payload.get("version") != 1 or not isinstance(payload.get("terms", []), list):
            LOGGER.warning("ASR glossary YAML must contain version 1 and a terms list")
            return {}
        result: dict[str, GlossaryTerm] = {}
        for index, item in enumerate(payload.get("terms", [])):
            term = _manual_term(item)
            if term is None:
                LOGGER.warning("ASR glossary skipped invalid manual term at index %s", index)
                continue
            result[term.canonical] = term
        return result


def _manual_term(item: Any) -> GlossaryTerm | None:
    if not isinstance(item, dict) or item.get("enabled", True) is False:
        return None
    canonical = str(item.get("canonical") or "").strip()
    aliases = item.get("aliases")
    weight = item.get("weight", 3)
    if not canonical or not isinstance(aliases, list) or not aliases:
        return None
    try:
        normalized_weight = int(weight)
    except (TypeError, ValueError):
        return None
    if not 1 <= normalized_weight <= 5:
        return None
    normalized_aliases = tuple(
        dict.fromkeys(str(alias).strip() for alias in aliases if str(alias).strip())
    )
    if not normalized_aliases:
        return None
    pinyin = str(item.get("pinyin") or "").strip() or _to_pinyin(canonical)
    return GlossaryTerm(canonical, normalized_aliases, pinyin, normalized_weight, True)


def _to_pinyin(text: str) -> str:
    try:
        from pypinyin import lazy_pinyin

        return " ".join(lazy_pinyin(text, errors=lambda value: list(value)))
    except ImportError:
        # Exact manual aliases remain useful before optional dependencies are installed.
        return ""
