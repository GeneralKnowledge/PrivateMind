import re

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{10,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:OPENSSH |RSA )?PRIVATE KEY-----[\s\S]*?-----END (?:OPENSSH |RSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|passphrase|password|secret)\s*[:=]\s*\S+"),
]


def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def redact_mapping(data: dict) -> dict:
    clean: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            clean[key] = redact(value)
        else:
            clean[key] = value
    return clean
