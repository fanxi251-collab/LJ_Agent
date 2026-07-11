from pathlib import Path
import os
import subprocess
import sys

from scripts.import_document import import_document, main


def test_import_document_indexes_file_into_workspace(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LJ_EMBEDDING_PROVIDER", "hashing")
    monkeypatch.setenv("LJ_EMBEDDING_DIMENSIONS", "64")
    source = tmp_path / "灵境山资料.md"
    source.write_text("灵境山以云海日出和古栈道闻名。", encoding="utf-8")

    result = import_document(source, tmp_path)

    assert result.document.name == "灵境山资料.md"
    assert Path(result.document.path).exists()
    assert result.vector_store_path == tmp_path / "qdrant_db"
    assert result.vector_store_path.exists()
    assert result.indexed_chunks == 1


def test_import_document_main_reports_missing_file(tmp_path: Path, capsys):
    exit_code = main(["missing.md", "--workspace", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "资料文件不存在" in captured.err


def test_import_document_script_runs_directly_from_project_root(tmp_path: Path):
    source = tmp_path / "青岚湖资料.md"
    source.write_text("青岚湖适合乘船观景。", encoding="utf-8")
    project_root = Path(__file__).resolve().parents[1]

    env = os.environ.copy()
    env["LJ_EMBEDDING_PROVIDER"] = "hashing"
    env["LJ_EMBEDDING_DIMENSIONS"] = "64"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/import_document.py",
            str(source),
            "--workspace",
            str(tmp_path),
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "资料导入完成" in result.stdout
    assert (tmp_path / "qdrant_db").exists()
