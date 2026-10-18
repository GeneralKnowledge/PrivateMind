import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from privatemind.worker.identity import NodeIdentity, sign_message, verify_message


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WireMessage:
    v: int
    msg_id: str
    sent_at: str
    sender_id: str
    recipient_id: str
    payload_type: str
    payload: dict[str, Any]
    signature: str = ""

    def signing_bytes(self) -> bytes:
        body = {
            "v": self.v,
            "msg_id": self.msg_id,
            "sent_at": self.sent_at,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "payload_type": self.payload_type,
            "payload": self.payload,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign_with(self, identity: NodeIdentity) -> None:
        self.signature = sign_message(identity.private_key(), self.signing_bytes())

    def verify_with(self, public_key_b64: str) -> bool:
        import base64 as b64

        pub = b64.b64decode(public_key_b64)
        return verify_message(pub, self.signing_bytes(), self.signature)

    def to_dict(self) -> dict[str, Any]:
        return {
            "v": self.v,
            "msg_id": self.msg_id,
            "sent_at": self.sent_at,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "payload_type": self.payload_type,
            "payload": self.payload,
            "signature": self.signature,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "WireMessage":
        return WireMessage(
            v=int(data["v"]),
            msg_id=str(data["msg_id"]),
            sent_at=str(data["sent_at"]),
            sender_id=str(data["sender_id"]),
            recipient_id=str(data["recipient_id"]),
            payload_type=str(data["payload_type"]),
            payload=data.get("payload") or {},
            signature=str(data.get("signature", "")),
        )


def new_message(
    *,
    sender: NodeIdentity,
    recipient_id: str,
    payload_type: str,
    payload: dict[str, Any],
) -> WireMessage:
    msg = WireMessage(
        v=1,
        msg_id=str(uuid.uuid4()),
        sent_at=utc_now(),
        sender_id=sender.fingerprint,
        recipient_id=recipient_id,
        payload_type=payload_type,
        payload=payload,
    )
    msg.sign_with(sender)
    return msg
