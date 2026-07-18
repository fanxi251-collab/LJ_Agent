from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Callable, Literal

from lingjing_ai.realtime.glossary import GlossarySnapshot, GlossaryTerm


CorrectionLevel = Literal["none", "high", "medium", "low"]
PROTECTED_PATTERN = re.compile(r"\d|[零一二三四五六七八九十百千万两]|不|没|未|别|莫")


@dataclass(frozen=True)
class TranscriptCorrection:
    original_text: str
    corrected_text: str
    level: CorrectionLevel
    score: float
    candidates: list[str]
    matched_terms: list[str]


class TranscriptNormalizer:
    """Corrects only glossary-backed spans to avoid rewriting the visitor's intent."""

    def __init__(
        self,
        snapshot_provider: Callable[[], GlossarySnapshot],
        pinyin_converter: Callable[[str], str] | None = None,
    ) -> None:
        self.snapshot_provider = snapshot_provider
        self.pinyin_converter = pinyin_converter or _to_pinyin

    def normalize(self, text: str) -> TranscriptCorrection:
        original = str(text or "").strip()
        if not original:
            return TranscriptCorrection("", "", "none", 0.0, [], [])
        terms = self.snapshot_provider().terms
        exact = _exact_alias_match(original, terms)
        if exact is not None:
            corrected, canonical = exact
            return TranscriptCorrection(original, corrected, "high", 1.0, [corrected], [canonical])

        matches = self._fuzzy_matches(original, terms)
        if not matches:
            return TranscriptCorrection(original, original, "none", 0.0, [], [])
        best = matches[0]
        runner_up = matches[1][0] if len(matches) > 1 else 0.0
        level = classify_confidence(best[0], runner_up)
        if level == "none":
            return TranscriptCorrection(original, original, "none", best[0], [], [])
        candidates = []
        for score, start, end, term in matches[:3]:
            candidate = f"{original[:start]}{term.canonical}{original[end:]}"
            if candidate not in candidates:
                candidates.append(candidate)
        return TranscriptCorrection(
            original,
            candidates[0],
            level,
            round(best[0], 4),
            candidates,
            [best[3].canonical],
        )

    def _fuzzy_matches(
        self, original: str, terms: tuple[GlossaryTerm, ...]
    ) -> list[tuple[float, int, int, GlossaryTerm]]:
        matches: list[tuple[float, int, int, GlossaryTerm]] = []
        for term in terms:
            target_pinyin = _compact_pinyin(term.pinyin or self.pinyin_converter(term.canonical))
            if not target_pinyin:
                continue
            best_for_term: tuple[float, int, int, GlossaryTerm] | None = None
            minimum = max(1, len(term.canonical) - 1)
            maximum = min(len(original), len(term.canonical) + 1)
            for length in range(minimum, maximum + 1):
                for start in range(0, len(original) - length + 1):
                    end = start + length
                    window = original[start:end]
                    if PROTECTED_PATTERN.search(window):
                        continue
                    source_pinyin = _compact_pinyin(self.pinyin_converter(window))
                    if not source_pinyin:
                        continue
                    similarity = SequenceMatcher(None, source_pinyin, target_pinyin).ratio()
                    weighted = min(1.0, similarity + max(0, term.weight - 3) * 0.01)
                    candidate = (weighted, start, end, term)
                    if best_for_term is None or candidate[0] > best_for_term[0]:
                        best_for_term = candidate
            if best_for_term and best_for_term[0] >= 0.65:
                matches.append(best_for_term)
        matches.sort(key=lambda item: (-item[0], -item[3].weight, item[1], item[3].canonical))
        return matches


def classify_confidence(score: float, runner_up_score: float) -> CorrectionLevel:
    if score < 0.65:
        return "none"
    gap = score - runner_up_score
    if score >= 0.90 and gap >= 0.10:
        return "high"
    if score >= 0.75 and gap >= 0.05:
        return "medium"
    return "low"


def _exact_alias_match(
    text: str, terms: tuple[GlossaryTerm, ...]
) -> tuple[str, str] | None:
    matches = []
    for term in terms:
        for alias in term.aliases:
            position = text.find(alias)
            if position >= 0:
                matches.append((term.weight, len(alias), position, alias, term.canonical))
    if not matches:
        return None
    _, _, position, alias, canonical = max(matches)
    end = position + len(alias)
    return f"{text[:position]}{canonical}{text[end:]}", canonical


def _compact_pinyin(value: str) -> str:
    return re.sub(r"[^a-z]", "", str(value or "").lower())


def _to_pinyin(text: str) -> str:
    try:
        from pypinyin import lazy_pinyin

        return " ".join(lazy_pinyin(text, errors=lambda value: list(value)))
    except ImportError:
        return ""
