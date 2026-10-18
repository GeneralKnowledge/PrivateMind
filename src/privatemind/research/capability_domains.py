"""Agent capability domains — what the executive should pursue vs vault reality."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from privatemind.vault.store import CredentialVault

_DOMAINS_REL = Path("docs/data/agent_capability_domains.json")


def domains_path() -> Path:
    return Path(__file__).resolve().parents[3] / _DOMAINS_REL


def load_capability_domains(*, path: Path | None = None) -> dict[str, Any]:
    p = path or domains_path()
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if "domains" not in data:
        raise ValueError("capability domains file missing domains array")
    return data


def list_domains(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cat = data if data is not None else load_capability_domains()
    return [d for d in cat.get("domains", []) if isinstance(d, dict)]


def capability_gaps(vault: CredentialVault | None = None) -> dict[str, Any]:
    """Compare desired domains to vault account kinds (today's schema)."""
    meta = load_capability_domains()
    present_kinds: set[str] = set()
    if vault is not None:
        for acct in vault.list_accounts():
            if acct.enabled:
                present_kinds.add(acct.kind.value)

    satisfied: list[str] = []
    missing: list[dict[str, Any]] = []

    for dom in list_domains(meta):
        dom_id = str(dom.get("id") or "")
        kind_today = dom.get("vault_kind_today")
        if kind_today is None:
            missing.append(
                {
                    "domain_id": dom_id,
                    "label": dom.get("label"),
                    "priority": dom.get("priority"),
                    "vault_kind_planned": dom.get("vault_kind_planned"),
                    "trust_level_required": dom.get("trust_level_required"),
                    "operator_deliverable": dom.get("operator_deliverable"),
                    "discovery": dom.get("discovery"),
                }
            )
            continue
        if kind_today in present_kinds:
            satisfied.append(dom_id)
        else:
            missing.append(
                {
                    "domain_id": dom_id,
                    "label": dom.get("label"),
                    "priority": dom.get("priority"),
                    "vault_kind_today": kind_today,
                    "reason": "no_enabled_vault_account_for_kind",
                }
            )

    return {
        "schema_version": meta.get("schema_version"),
        "vault_kinds_present": sorted(present_kinds),
        "satisfied_domain_ids": sorted(set(satisfied)),
        "missing_domains": missing,
        "high_priority_missing": [
            m for m in missing if str(m.get("priority")) in ("critical", "high")
        ],
        "agent_action": "Request operator provisioning for missing domains; discover free tiers first.",
    }
