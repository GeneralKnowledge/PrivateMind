from pathlib import Path


class WorkspaceLayout:
    """Isolated git workspaces under the agent data directory."""

    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir / "workspaces"
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, name: str) -> Path:
        safe = name.replace("/", "_").replace("..", "_").strip()
        if not safe:
            raise ValueError("Invalid workspace name")
        path = (self.root / safe).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
            raise ValueError("Workspace path escapes root")
        return path

    def list_workspaces(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())
