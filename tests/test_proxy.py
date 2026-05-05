import io
import asyncio

from coderead.proxy import _pipe


def test_pipe_writes_observer_injected_bytes_before_original_chunk():
    reader = io.BytesIO(b"original")
    writer = io.BytesIO()

    def observer(chunk: bytes) -> list[bytes]:
        assert chunk == b"original"
        return [b"injected-"]

    asyncio.run(_pipe(reader, writer, observer=observer))

    assert writer.getvalue() == b"injected-original"
