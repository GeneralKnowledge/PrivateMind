import re
from pathlib import Path
from typing import Any

from privatemind.improvement.paths import WorkspaceLayout
from privatemind.security.policy import is_sensitive_path, normalize_repo_path
from privatemind.security.redaction import redact
from privatemind.tools.types import ToolResult


def _safe_path(workspace: Path, relative_path: str) -> Path:
    rel = normalize_repo_path(relative_path)
    if rel.startswith("..") or "/../" in f"/{rel}/":
        raise ValueError("Path traversal not allowed")
    target = (workspace / rel).resolve()
    root = workspace.resolve()
    if root not in target.parents and target != root:
        raise ValueError("Path escapes workspace")
    return target


class RepoToolHandler:
    MAX_READ_BYTES = 64_000

    def __init__(self, layout: WorkspaceLayout) -> None:
        self._layout = layout
        self._handlers = {
            "repo_read_file": self._read_file,
            "repo_list_dir": self._list_dir,
            "repo_search": self._search,
            "repo_write_file": self._write_file,
        }

    def tool_names(self) -> list[str]:
        return sorted(self._handlers.keys())

    def invoke(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name not in self._handlers:
            return ToolResult(ok=False, output=None, detail=f"Unknown repo tool: {name}")
        try:
            return self._handlers[name](arguments)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, output=None, detail=str(exc))

    def _workspace(self, arguments: dict[str, Any]) -> Path:
        return self._layout.resolve(str(arguments["workspace"]))

    def _read_file(self, arguments: dict[str, Any]) -> ToolResult:
        ws = self._workspace(arguments)
        path = _safe_path(ws, str(arguments["path"]))
        if not path.is_file():
            return ToolResult(ok=False, output=None, detail="file not found")
        data = path.read_bytes()[: self.MAX_READ_BYTES]
        text = data.decode("utf-8", errors="replace")
        return ToolResult(
            ok=True,
            output={
                "path": normalize_repo_path(str(arguments["path"])),
                "content": redact(text),
                "truncated": path.stat().st_size > len(data),
            },
        )

    def _list_dir(self, arguments: dict[str, Any]) -> ToolResult:
        ws = self._workspace(arguments)
        rel = str(arguments.get("path", "."))
        path = _safe_path(ws, rel)
        if not path.is_dir():
            return ToolResult(ok=False, output=None, detail="not a directory")
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
        return ToolResult(ok=True, output={"path": normalize_repo_path(rel), "entries": entries[:200]})

    def _search(self, arguments: dict[str, Any]) -> ToolResult:
        ws = self._workspace(arguments)
        pattern = str(arguments["pattern"])
        if len(pattern) > 200:
            return ToolResult(ok=False, output=None, detail="pattern too long")
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return ToolResult(ok=False, output=None, detail=f"invalid pattern: {exc}")
        max_matches = int(arguments.get("max_matches", 20))
        matches: list[dict[str, str]] = []
        for file in ws.rglob("*"):
            if not file.is_file():
                continue
            if file.suffix in {".pyc", ".png", ".jpg"}:
                continue
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for idx, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    rel = file.relative_to(ws).as_posix()
                    matches.append({"path": rel, "line": str(idx), "text": redact(line[:300])})
                    if len(matches) >= max_matches:
                        break
            if len(matches) >= max_matches:
                break
        return ToolResult(ok=True, output={"matches": matches, "count": len(matches)})

    def _write_file(self, arguments: dict[str, Any]) -> ToolResult:
        ws = self._workspace(arguments)
        rel = normalize_repo_path(str(arguments["path"]))
        if is_sensitive_path(rel):
            return ToolResult(
                ok=False,
                output=None,
                detail="security_review_required: cannot write security-sensitive path via repo_write_file",
            )
        path = _safe_path(ws, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = str(arguments["content"])
        path.write_text(content, encoding="utf-8")
        return ToolResult(ok=True, output={"path": rel, "bytes_written": len(content.encode("utf-8"))})
