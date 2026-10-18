import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TrustedCore:
    fingerprint: str
    public_key_b64: str

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"fingerprint": self.fingerprint, "public_key_b64": self.public_key_b64}, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def load(path: Path) -> "TrustedCore":
        data = json.loads(path.read_text(encoding="utf-8"))
        return TrustedCore(fingerprint=data["fingerprint"], public_key_b64=data["public_key_b64"])
