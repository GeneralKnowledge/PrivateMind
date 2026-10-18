"""Agent self-model skeleton — layers, needs, and routing graph (agent-maintained)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SELF_MODEL_REL = Path("docs/data/agent_self_model.json")


def self_model_path() -> Path:
    return Path(__file__).resolve().parents[3] / _SELF_MODEL_REL


def load_self_model(*, path: Path | None = None) -> dict[str, Any]:
    p = path or self_model_path()
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if "layers" not in data:
        raise ValueError("self-model file missing layers array")
    if "graph" not in data:
        raise ValueError("self-model file missing graph object")
    return data


def list_layers(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cat = data if data is not None else load_self_model()
    return [layer for layer in cat.get("layers", []) if isinstance(layer, dict)]


def self_model_status(*, path: Path | None = None) -> dict[str, Any]:
    """Summary for wake cycles — skeleton vs agent-populated content."""
    meta = load_self_model(path=path)
    graph = meta.get("graph") or {}
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    needs = meta.get("needs") or []
    policies = meta.get("routing_policies") or []
    extensions = meta.get("layer_extensions") or []
    modes = meta.get("activity_modes") or []

    populated = bool(needs or nodes or edges or policies or extensions or modes)
    return {
        "schema_version": meta.get("schema_version"),
        "layers_seed": [layer.get("id") for layer in list_layers(meta)],
        "counts": {
            "layer_extensions": len(extensions),
            "needs": len(needs),
            "activity_modes": len(modes),
            "graph_nodes": len(nodes),
            "graph_edges": len(edges),
            "routing_policies": len(policies),
        },
        "populated_by_agent": populated,
        "mind_layers_doc": meta.get("mind_layers_doc"),
        "food_metaphor": meta.get("food_metaphor"),
        "agent_action": (
            "If food (capability-gaps) is not urgent: set activity_modes and do "
            "maintain/improve/reflect work; extend needs/graph when blocked; "
            "see docs/AGENT_MIND_LAYERS.md"
            if not populated
            else "Keep graph and playbooks in sync; balance food asks with non-key cycles."
        ),
    }
