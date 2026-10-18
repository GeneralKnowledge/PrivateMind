from privatemind.research.self_model import (
    list_layers,
    load_self_model,
    self_model_status,
)


def test_load_self_model_has_three_layers() -> None:
    data = load_self_model()
    layer_ids = {layer["id"] for layer in list_layers(data)}
    assert layer_ids == {"needs", "executive", "floor"}


def test_self_model_status_empty_graph() -> None:
    status = self_model_status()
    assert status["counts"]["needs"] == 0
    assert status["counts"]["graph_nodes"] == 0
    assert status["populated_by_agent"] is False
    assert "needs" in status["layers_seed"]
    assert status["counts"]["activity_modes"] == 0
