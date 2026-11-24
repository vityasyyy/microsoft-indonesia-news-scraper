import os
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_legacy_workflow_is_manual_only_with_expected_jobs():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "legacy.yml").read_text())
    trigger = workflow.get("on") or workflow.get(True)
    assert list(trigger) == ["workflow_dispatch"]
    assert set(workflow["jobs"]) == {"legacy-import", "corpus", "publish"}
    corpus = workflow["jobs"]["corpus"]
    assert corpus["strategy"]["matrix"]["index"] == [0, 1, 2]
    assert corpus["strategy"]["max-parallel"] == 2
    assert corpus["strategy"]["fail-fast"] is False
    assert corpus["env"]["CORPUS_WORKERS"] == 4
    assert workflow["jobs"]["legacy-import"]["steps"][-1]["with"]["name"] == "legacy-output"
    assert workflow["jobs"]["publish"]["needs"] == "corpus"
    upload = workflow["jobs"]["corpus"]["steps"][-1]
    assert upload["with"]["path"] == "corpus-batch-${{ matrix.index }}/"


def test_fetch_legacy_script_is_executable_and_uses_exact_asset():
    script = ROOT / "scripts" / "fetch_legacy.sh"
    assert os.access(script, os.X_OK)
    text = script.read_text()
    assert "articles-2025-4" in text
    assert (
        "https://github.com/vityasyyy/microsoft-indonesia-news-scraper/releases/download/"
        "articles-2025-4/articles-2025.xlsx"
    ) in text
    assert "output/legacy/articles-2025-4.xlsx" in text
    assert "--retry 3" in text
    assert "1a7bb86ae68043567f997fac08f32b891ecdbefc270d488ed2b0c2840c6f5bc5" in text
    assert "shasum -a 256 -c" in text


def test_makefile_has_legacy_target():
    makefile = (ROOT / "Makefile").read_text()
    assert "legacy:" in makefile
    assert "./scripts/fetch_legacy.sh" in makefile
    assert "src.import_legacy" in makefile
