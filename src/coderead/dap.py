from __future__ import annotations

import json
from typing import Any


HEADER_SEPARATOR = b"\r\n\r\n"


def encode_message(message: dict[str, Any]) -> bytes:
    body = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


class DapMessageBuffer:
    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        self._buffer.extend(data)
        messages = []

        while True:
            header_end = self._buffer.find(HEADER_SEPARATOR)
            if header_end == -1:
                break

            header_bytes = bytes(self._buffer[:header_end])
            content_length = _parse_content_length(header_bytes)
            body_start = header_end + len(HEADER_SEPARATOR)
            body_end = body_start + content_length
            if len(self._buffer) < body_end:
                break

            body = bytes(self._buffer[body_start:body_end])
            del self._buffer[:body_end]
            messages.append(json.loads(body.decode("utf-8")))

        return messages


def _parse_content_length(header: bytes) -> int:
    for line in header.decode("ascii").split("\r\n"):
        name, _, value = line.partition(":")
        if name.lower() == "content-length":
            return int(value.strip())
    raise ValueError("DAP message missing Content-Length header")
