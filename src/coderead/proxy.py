from __future__ import annotations

import asyncio
import inspect
import sys
from collections.abc import Awaitable, Callable, Sequence


ObserverResult = bytes | Sequence[bytes] | Awaitable[bytes | Sequence[bytes] | None] | None
ByteObserver = Callable[[bytes], ObserverResult]


async def run_proxy(
    real_adapter: Sequence[str],
    *,
    on_client_chunk: ByteObserver | None = None,
    on_adapter_chunk: ByteObserver | None = None,
) -> int:
    process = await asyncio.create_subprocess_exec(
        *real_adapter,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=sys.stderr,
    )
    if process.stdin is None or process.stdout is None:
        raise RuntimeError("failed to create adapter pipes")

    client_to_adapter = asyncio.create_task(
        _pipe(sys.stdin.buffer, process.stdin, observer=on_client_chunk)
    )
    adapter_to_client = asyncio.create_task(
        _pipe(process.stdout, sys.stdout.buffer, observer=on_adapter_chunk)
    )
    await asyncio.wait(
        {client_to_adapter, adapter_to_client},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in (client_to_adapter, adapter_to_client):
        if not task.done():
            task.cancel()
    return await process.wait()


async def _pipe(reader, writer, *, observer: ByteObserver | None = None) -> None:
    while True:
        chunk = await asyncio.to_thread(reader.read, 8192)
        if not chunk:
            break
        if observer is not None:
            injected_chunks = await _resolve_observer_chunks(observer(chunk))
            for injected in injected_chunks:
                await _write_chunk(writer, injected)
        await _write_chunk(writer, chunk)


async def _resolve_observer_chunks(result: ObserverResult) -> list[bytes]:
    if inspect.isawaitable(result):
        result = await result
    if result is None:
        return []
    if isinstance(result, bytes):
        return [result]
    return list(result)


async def _write_chunk(writer, chunk: bytes) -> None:
        await asyncio.to_thread(writer.write, chunk)
        flush = getattr(writer, "flush", None)
        drain = getattr(writer, "drain", None)
        if drain is not None:
            await drain()
        elif flush is not None:
            await asyncio.to_thread(flush)
