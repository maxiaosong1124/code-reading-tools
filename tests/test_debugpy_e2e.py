from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

from coderead.dap import DapMessageBuffer, encode_message
from coderead.store import load_events_jsonl


class DapClient:
    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self.process = process
        self.buffer = DapMessageBuffer()
        self.seq = 1

    def request(self, command: str, arguments: dict | None = None) -> int:
        seq = self.seq
        self.seq += 1
        message = {
            "seq": seq,
            "type": "request",
            "command": command,
            "arguments": arguments or {},
        }
        assert self.process.stdin is not None
        self.process.stdin.write(encode_message(message))
        self.process.stdin.flush()
        return seq

    def read_message(self, timeout: float = 30.0) -> dict:
        assert self.process.stdout is not None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                stderr = _read_stderr(self.process)
                raise RuntimeError(f"DAP process exited with {self.process.returncode}: {stderr}")
            ready, _, _ = select.select([self.process.stdout], [], [], max(0.0, min(0.1, deadline - time.monotonic())))
            if not ready:
                continue
            header = self.process.stdout.readline()
            if not header:
                continue
            if not header.lower().startswith(b"content-length:"):
                continue
            length = int(header.split(b":", 1)[1].strip())
            separator = self.process.stdout.readline()
            assert separator == b"\r\n"
            body = self.process.stdout.read(length)
            return json.loads(body.decode("utf-8"))
        raise TimeoutError(f"timed out waiting for DAP message; stderr={_read_stderr(self.process)}")

    def wait_for_response(self, request_seq: int, timeout: float = 30.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = self.read_message(timeout=max(0.1, deadline - time.monotonic()))
            if message.get("type") == "response" and message.get("request_seq") == request_seq:
                return message
        raise TimeoutError(f"timed out waiting for response {request_seq}")

    def wait_for_event(self, event: str, timeout: float = 30.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = self.read_message(timeout=max(0.1, deadline - time.monotonic()))
            if message.get("type") == "event" and message.get("event") == event:
                return message
        raise TimeoutError(f"timed out waiting for event {event}")


def test_proxy_captures_stopped_stack_trace_end_to_end(tmp_path):
    adapter = Path(__file__).parent / "fixtures" / "echo_adapter.py"
    trace_root = tmp_path / "traces"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "coderead.cli",
            "proxy",
            "--out-dir",
            str(trace_root),
            "--real-adapter",
            sys.executable,
            str(adapter),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    client = DapClient(process)
    _wait_for_trace_session(trace_root)

    try:
        initialize = client.request("initialize", {"adapterID": "fake"})
        assert client.wait_for_response(initialize)["success"] is True

        next_request = client.request("next", {"threadId": 1})
        stopped = client.wait_for_event("stopped")
        assert stopped["body"]["reason"] in {"breakpoint", "step"}

        events_path = _wait_for_events_path(trace_root)
        events = load_events_jsonl(events_path)

        assert events
        assert events[0].command_before_stop == "next"
        assert events[0].top_frame.file == "/repo/app.py"
        assert events[0].top_frame.function == "main"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def test_debugpy_adapter_direct_sanity():
    process = subprocess.Popen(
        [sys.executable, "-m", "debugpy.adapter"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    client = DapClient(process)

    try:
        initialize = client.request(
            "initialize",
            {
                "adapterID": "debugpy",
                "clientID": "coderead-test",
                "clientName": "coderead-test",
                "linesStartAt1": True,
                "columnsStartAt1": True,
                "pathFormat": "path",
            },
        )
        assert client.wait_for_response(initialize)["success"] is True
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def _wait_for_events_path(trace_root: Path, timeout: float = 30.0) -> Path:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        candidates = list(trace_root.glob("*/events.jsonl"))
        for candidate in candidates:
            if candidate.read_text(encoding="utf-8").strip():
                return candidate
        time.sleep(0.05)
    raise TimeoutError("timed out waiting for trace events")


def _wait_for_trace_session(trace_root: Path, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if list(trace_root.glob("*/session.json")):
            return
        time.sleep(0.05)
    raise TimeoutError("timed out waiting for proxy trace session")


def _read_stderr(process: subprocess.Popen[bytes]) -> str:
    if process.stderr is None:
        return ""
    ready, _, _ = select.select([process.stderr], [], [], 0)
    if not ready:
        return ""
    return os.read(process.stderr.fileno(), 65536).decode("utf-8", errors="replace")
