import importlib
import pathlib

import pytest

from src import language


def test_detect_indonesian():
    assert language.detect_lang("Kerja sama Microsoft dengan pemerintah Indonesia") == "id"


def test_detect_english():
    assert language.detect_lang("Microsoft launched its first cloud region in Indonesia") == "en"


def test_detect_other_language():
    text = "Microsoft et le gouvernement francais ont annonce un nouveau partenariat dans le cloud"
    assert language.detect_lang(text) == "other"


def test_short_text_is_unknown_not_coerced():
    assert language.detect_lang("") == "unknown"
    assert language.detect_lang("microsoft") == "unknown"


def test_clean_html_strips_tags_scripts_and_entities():
    raw = '<a href="https://news.google.com/x">Microsoft&nbsp;Indonesia</a><script>evil()</script><style>.x{}</style>'
    assert language.clean_html(raw) == "Microsoft Indonesia"


def test_strip_scripts_keeps_article_markup():
    raw = "<html><script>evil()</script><body><p>Berita</p></body></html>"
    cleaned = language.strip_scripts(raw)
    assert "evil()" not in cleaned
    assert "<p>Berita</p>" in cleaned


def test_language_detection_is_seeded():
    from langdetect import DetectorFactory

    assert DetectorFactory.seed == 0
    runs = {
        language.detect_lang("Microsoft Indonesia mengumumkan pembangunan pusat data nasional")
        for _ in range(3)
    }
    assert runs == {"id"}


def test_no_translation_module_exists():
    removed = "src." + "trans" + "lator"
    with pytest.raises(ImportError):
        importlib.import_module(removed)


def test_pyproject_has_no_argos_dependency():
    import tomllib

    data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = [dependency.lower() for dependency in data["project"]["dependencies"]]
    assert not any(dependency.startswith("argos") for dependency in dependencies)
    assert any(dependency.startswith("requests") for dependency in dependencies)
