import json
import socket
from typing import Any


class WorkerTransportError(Exception):
    pass


def send_message(host: str, port: int, message: dict[str, Any], *, timeout: float = 30.0) -> dict[str, Any]:
    line = (json.dumps(message) + "\n").encode("utf-8")
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(line)
            sock.shutdown(socket.SHUT_WR)
            chunks: list[bytes] = []
            while True:
                part = sock.recv(65536)
                if not part:
                    break
                chunks.append(part)
    except OSError as exc:
        raise WorkerTransportError(str(exc)) from exc
    if not chunks:
        raise WorkerTransportError("no response from worker")
    try:
        return json.loads(b"".join(chunks).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkerTransportError("invalid JSON response") from exc
