from lingjing_ai.realtime.glossary import GlossarySnapshot, GlossaryTerm
from lingjing_ai.realtime.transcript import (
    TranscriptNormalizer,
    classify_confidence,
)


def snapshot(*terms):
    return GlossarySnapshot(tuple(terms))


def test_manual_alias_is_corrected_with_high_confidence_and_protected_tokens_are_unchanged():
    normalizer = TranscriptNormalizer(
        lambda: snapshot(
            GlossaryTerm(
                canonical="鼋头渚",
                aliases=("园头渚",),
                pinyin="yuan tou zhu",
                weight=5,
                manual=True,
            )
        )
    )

    result = normalizer.normalize("园头渚10点不开门吗")

    assert result.corrected_text == "鼋头渚10点不开门吗"
    assert result.level == "high"
    assert result.score == 1.0
    assert result.matched_terms == ["鼋头渚"]


def test_pinyin_candidate_replaces_only_the_matching_scenic_term():
    pinyin = {
        "源头主": "yuan tou zhu",
        "鼋头渚": "yuan tou zhu",
        "请问源头主几点开放": "qing wen yuan tou zhu ji dian kai fang",
    }
    normalizer = TranscriptNormalizer(
        lambda: snapshot(
            GlossaryTerm("鼋头渚", (), "yuan tou zhu", 5, False)
        ),
        pinyin_converter=lambda text: pinyin.get(text, "different"),
    )

    result = normalizer.normalize("请问源头主几点开放")

    assert result.corrected_text == "请问鼋头渚几点开放"
    assert result.level == "high"
    assert result.candidates[0] == "请问鼋头渚几点开放"


def test_confidence_thresholds_cover_none_high_medium_and_low():
    assert classify_confidence(0.64, 0) == "none"
    assert classify_confidence(0.94, 0.80) == "high"
    assert classify_confidence(0.82, 0.75) == "medium"
    assert classify_confidence(0.72, 0.69) == "low"
