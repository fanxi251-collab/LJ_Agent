from pathlib import Path
from types import SimpleNamespace

from lingjing_ai.realtime.glossary import GlossaryProvider


class FakeAttractionStore:
    def list_attractions(self, public_only=False):
        assert public_only is True
        return [SimpleNamespace(name="鼋头渚", tags=["太湖风光", "樱花"])]


class FakeManifestStore:
    def list_records(self):
        return [SimpleNamespace(document_name="灵山胜境游览指南.md")]


def test_glossary_merges_database_terms_and_manual_yaml_with_manual_precedence(tmp_path: Path):
    yaml_path = tmp_path / "asr_glossary.yml"
    yaml_path.write_text(
        """
version: 1
terms:
  - canonical: 鼋头渚
    aliases: [园头渚, 源头渚]
    pinyin: yuan tou zhu
    weight: 5
    enabled: true
""".strip(),
        encoding="utf-8",
    )
    provider = GlossaryProvider(
        FakeAttractionStore(), FakeManifestStore(), yaml_path, ttl_seconds=60
    )

    snapshot = provider.snapshot()
    terms = {term.canonical: term for term in snapshot.terms}

    assert {"鼋头渚", "太湖风光", "樱花", "灵山胜境游览指南"} <= set(terms)
    assert terms["鼋头渚"].aliases == ("园头渚", "源头渚")
    assert terms["鼋头渚"].manual is True
    assert terms["鼋头渚"].weight == 5


def test_glossary_skips_invalid_yaml_entries_without_losing_valid_or_auto_terms(tmp_path: Path):
    yaml_path = tmp_path / "asr_glossary.yml"
    yaml_path.write_text(
        """
version: 1
terms:
  - canonical: 无效词条
    aliases: not-a-list
    weight: 9
  - canonical: 拈花湾
    aliases: [年华湾]
    weight: 4
""".strip(),
        encoding="utf-8",
    )

    terms = {
        term.canonical: term
        for term in GlossaryProvider(
            FakeAttractionStore(), FakeManifestStore(), yaml_path
        ).snapshot().terms
    }

    assert "无效词条" not in terms
    assert terms["拈花湾"].aliases == ("年华湾",)
    assert "鼋头渚" in terms
