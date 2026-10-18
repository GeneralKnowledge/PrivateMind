from unittest.mock import patch

from privatemind.research.github_lists import (
    load_github_sources,
    provider_ids_in_text,
    sync_github_sources,
)
from privatemind.research.provider_catalog import catalog_provider_ids, load_catalog


def test_provider_ids_in_text_finds_sambanova_and_unorouter() -> None:
    text = """
    ## Free Providers
    ### SambaNova Cloud
    Limits: 20 RPM
    ### UnoRouter
    Use gpt-oss-120b:free
    """
    ids = provider_ids_in_text(text)
    assert "sambanova_cloud" in ids
    assert "unorouter" in ids


def test_catalog_includes_sambanova_and_unorouter() -> None:
    cat = load_catalog()
    ids = catalog_provider_ids(cat)
    assert "sambanova_cloud" in ids
    assert "unorouter" in ids


def test_sync_github_sources_with_mocked_fetch() -> None:
    cheahjs_body = "### SambaNova Cloud\n### Groq\n### UnoRouter\n"
    mnfst_body = "### NVIDIA NIM\n"

    def fake_fetch(
        *,
        repo: str,
        path: str,
        branch: str = "main",
        raw_url: str | None = None,
    ) -> str:
        if repo == "mnfst/awesome-free-llm-apis":
            return mnfst_body + cheahjs_body
        return ""

    with patch("privatemind.research.github_lists.fetch_github_markdown", side_effect=fake_fetch):
        out = sync_github_sources(source_id="mnfst-awesome-free", fetch=True)

    assert "sambanova_cloud" in out["mentioned_provider_ids"]
    assert "unorouter" in out["mentioned_provider_ids"]
    assert "mnfst-awesome-free" in out["by_source"]
    assert out["errors"] == {}


def test_github_sources_file_loads() -> None:
    meta = load_github_sources()
    assert len(meta.get("sources", [])) >= 5
