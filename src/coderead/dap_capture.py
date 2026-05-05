from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from coderead.dap import DapMessageBuffer, encode_message
from coderead.models import StackFrame, TraceEvent


STEP_COMMANDS = {"next", "stepIn", "stepOut", "continue", "pause"}


@dataclass
class PendingStop:
    reason: str
    thread_id: int
    command_before_stop: str | None


class DapTraceCapture:
    def __init__(self, session_id: str, adapter: str) -> None:
        self.session_id = session_id
        self.adapter = adapter
        self.last_step_command: str | None = None
        self._client_buffer = DapMessageBuffer()
        self._adapter_buffer = DapMessageBuffer()
        self._next_seq = 1
        self._pending_stack_requests: dict[int, PendingStop] = {}
        self._event_counter = 0
        self._events: list[TraceEvent] = []

    def observe_client_bytes(self, data: bytes) -> list[bytes]:
        for message in self._client_buffer.feed(data):
            if message.get("type") == "request" and message.get("command") in STEP_COMMANDS:
                self.last_step_command = message["command"]
        return []

    def observe_adapter_bytes(self, data: bytes) -> list[bytes]:
        injected = []
        for message in self._adapter_buffer.feed(data):
            if message.get("type") == "event" and message.get("event") == "stopped":
                injected.append(self._handle_stopped(message))
            elif message.get("type") == "response" and message.get("command") == "stackTrace":
                self._handle_stack_trace_response(message)
        return injected

    def pop_events(self) -> list[TraceEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def _handle_stopped(self, message: dict[str, Any]) -> bytes:
        body = message.get("body", {})
        thread_id = int(body.get("threadId", 0))
        seq = self._next_seq
        self._next_seq += 1
        self._pending_stack_requests[seq] = PendingStop(
            reason=body.get("reason", ""),
            thread_id=thread_id,
            command_before_stop=self.last_step_command,
        )
        return encode_message(
            {
                "seq": seq,
                "type": "request",
                "command": "stackTrace",
                "arguments": {"threadId": thread_id},
            }
        )

    def _handle_stack_trace_response(self, message: dict[str, Any]) -> None:
        request_seq = int(message.get("request_seq", 0))
        pending = self._pending_stack_requests.pop(request_seq, None)
        if pending is None or not message.get("success", False):
            return

        frames = [
            _stack_frame_from_dap(frame)
            for frame in message.get("body", {}).get("stackFrames", [])
        ]
        if not frames:
            return

        self._event_counter += 1
        self._events.append(
            TraceEvent(
                id=f"evt_{self._event_counter:06d}",
                session_id=self.session_id,
                timestamp=datetime.now(UTC).isoformat(),
                adapter=self.adapter,
                event_type="stopped",
                reason=pending.reason,
                command_before_stop=pending.command_before_stop,
                thread_id=pending.thread_id,
                top_frame=frames[0],
                stack=frames,
                metadata={"source": "dap"},
            )
        )


def _stack_frame_from_dap(frame: dict[str, Any]) -> StackFrame:
    source = frame.get("source") or {}
    path = source.get("path") or source.get("name") or "<unknown>"
    return StackFrame(
        function=frame.get("name", "<unknown>"),
        file=path,
        line=int(frame.get("line", 0)),
        column=int(frame.get("column", 0)),
        language=_language_from_path(path),
    )


def _language_from_path(path: str) -> str:
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "py": "python",
        "cpp": "cpp",
        "cc": "cpp",
        "cxx": "cpp",
        "cu": "cuda",
        "cuh": "cuda",
    }.get(suffix, "unknown")
