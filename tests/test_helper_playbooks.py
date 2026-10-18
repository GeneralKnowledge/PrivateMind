from privatemind.research.helper_playbooks import list_playbooks, load_helper_playbooks


def test_load_helper_playbooks_empty_index() -> None:
    data = load_helper_playbooks()
    assert data["playbooks"] == []
    assert "non_key_help_examples" in data
    assert list_playbooks(data) == []
