"""Repository paths the self-improvement loop must not modify without human review."""

from privatemind.security.policy import SENSITIVE_PATH_PREFIXES, normalize_repo_path

# Extends sensitive prefixes with worker/trust/core authority surfaces.
PROTECTED_PATH_PREFIXES = SENSITIVE_PATH_PREFIXES + (
    "src/privatemind/worker/verifier.py",
    "src/privatemind/worker/hub.py",
    "src/privatemind/worker/pairing_store.py",
    "src/privatemind/worker/trust.py",
    "src/privatemind/tools/builtin.py",
    "src/privatemind/capabilities/registry.py",
    "src/privatemind/core/agent.py",
    "src/privatemind/improvement/workflow.py",
)


def is_protected_path(relative_path: str) -> bool:
    rel = normalize_repo_path(relative_path)
    for prefix in PROTECTED_PATH_PREFIXES:
        if rel == prefix.rstrip("/") or rel.startswith(prefix):
            return True
    return False


def find_protected_paths(paths: list[str]) -> list[str]:
    return [p for p in paths if is_protected_path(p)]


def diff_touches_protected(diff_text: str) -> list[str]:
    touched: set[str] = set()
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            touched.add(line[6:].strip())
        elif line.startswith("--- a/"):
            touched.add(line[6:].strip())
    return find_protected_paths(sorted(touched))
