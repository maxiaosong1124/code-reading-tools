import io
import asyncio
import select
import subprocess
import sys
import json

from coderead.dap import encode_message
from coderead.proxy import _pipe


def test_pipe_writes_observer_injected_bytes_before_original_chunk():
    reader = io.BytesIO(b"original")
    writer = io.BytesIO()

    def observer(chunk: bytes) -> list[bytes]:
        assert chunk == b"original"
        return [b"injected-"]

    asyncio.run(_pipe(reader, writer, observer=observer))

    assert writer.getvalue() == b"injected-original"


def test_pipe_can_replace_original_chunk_with_observer_forward_bytes():
    reader = io.BytesIO(b"original")
    writer = io.BytesIO()

    def observer(chunk: bytes) -> tuple[list[bytes], bytes]:
        assert chunk == b"original"
        return [b"injected-"], b"replacement"

    asyncio.run(_pipe(reader, writer, observer=observer))

    assert writer.getvalue() == b"injected-replacement"


def test_proxy_cli_forwards_debugpy_initialize(tmp_path):
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "coderead.cli",
            "proxy",
            "--out-dir",
            str(tmp_path),
            "--real-adapter",
            sys.executable,
            "-m",
            "debugpy.adapter",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert process.stdin is not None
        assert process.stdout is not None
        __import__("time").sleep(1.0)
        process.stdin.write(
            encode_message(
                {
                    "seq": 1,
                    "type": "request",
                    "command": "initialize",
                    "arguments": {"adapterID": "debugpy"},
                }
            )
        )
        process.stdin.flush()
        ready, _, _ = select.select([process.stdout], [], [], 30)
        assert ready
        deadline = __import__("time").monotonic() + 30
        while True:
            assert __import__("time").monotonic() < deadline
            ready, _, _ = select.select([process.stdout], [], [], 0.1)
            if not ready:
                continue
            header = process.stdout.readline()
            assert header.lower().startswith(b"content-length:")
            length = int(header.split(b":", 1)[1].strip())
            assert process.stdout.readline() == b"\r\n"
            body = process.stdout.read(length)
            message = json.loads(body.decode("utf-8"))
            if message["type"] == "response":
                assert message["command"] == "initialize"
                break
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_proxy_cli_forwards_client_request_to_adapter(tmp_path):
    adapter = __import__("pathlib").Path(__file__).parent / "fixtures" / "echo_adapter.py"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "coderead.cli",
            "proxy",
            "--out-dir",
            str(tmp_path),
            "--real-adapter",
            sys.executable,
            str(adapter),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(
            encode_message(
                {
                    "seq": 1,
                    "type": "request",
                    "command": "initialize",
                    "arguments": {"adapterID": "fake"},
                }
            )
        )
        process.stdin.flush()
        ready, _, _ = select.select([process.stdout], [], [], 5)
        assert ready
        header = process.stdout.readline()
        assert header.lower().startswith(b"content-length:")
        length = int(header.split(b":", 1)[1].strip())
        assert process.stdout.readline() == b"\r\n"
        body = process.stdout.read(length)
        message = json.loads(body.decode("utf-8"))
        assert message["type"] == "response"
        assert message["command"] == "initialize"
    finally:
        process.terminate()
        process.wait(timeout=5)
