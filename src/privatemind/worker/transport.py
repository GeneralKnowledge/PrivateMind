import json
import socket
import ssl
from typing import Any


class WorkerTransportError(Exception):
    pass


def send_message(
    host: str,
    port: int,
    message: dict[str, Any],
    *,
    timeout: float = 30.0,
    ssl_context: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    line = (json.dumps(message) + "\n").encode("utf-8")
    try:
        if ssl_context is not None:
            sock = ssl_context.wrap_socket(socket.socket(), server_hostname=host)
            sock.settimeout(timeout)
            sock.connect((host, port))
        else:
            sock = socket.create_connection((host, port), timeout=timeout)
        try:
            sock.sendall(line)
            buffer = b""
            while b"\n" not in buffer:
                chunk = sock.read(4096) if isinstance(sock, ssl.SSLSocket) else sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
            if isinstance(sock, ssl.SSLSocket):
                sock.shutdown(socket.SHUT_RDWR)
            else:
                sock.shutdown(socket.SHUT_WR)
            chunks = [buffer.split(b"\n", 1)[0] + b"\n"] if buffer else []
        finally:
            sock.close()
    except OSError as exc:
        raise WorkerTransportError(str(exc)) from exc
    if not chunks:
        raise WorkerTransportError("no response from worker")
    try:
        return json.loads(b"".join(chunks).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkerTransportError("invalid JSON response") from exc
