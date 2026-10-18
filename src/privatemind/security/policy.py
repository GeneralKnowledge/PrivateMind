from pathlib import Path

# Paths requiring human review before commit (repository-relative POSIX paths).
SENSITIVE_PATH_PREFIXES = (
    "src/privatemind/vault/",
    "src/privatemind/security/",
    "credentials",
    "docs/THREAT_MODEL.md",
)


def normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def is_sensitive_path(relative_path: str) -> bool:
    rel = normalize_repo_path(relative_path)
    for prefix in SENSITIVE_PATH_PREFIXES:
        if rel == prefix.rstrip("/") or rel.startswith(prefix):
            return True
    return False


def find_sensitive_paths(paths: list[str]) -> list[str]:
    return [p for p in paths if is_sensitive_path(p)]


def diff_touches_sensitive(diff_text: str) -> list[str]:
    touched: set[str] = set()
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            touched.add(line[6:].strip())
        elif line.startswith("--- a/"):
            touched.add(line[6:].strip())
    return find_sensitive_paths(sorted(touched))
