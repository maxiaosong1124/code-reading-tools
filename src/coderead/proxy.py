from __future__ import annotations

import asyncio
import inspect
import os
import select
import sys
from dataclasses import dataclass
from collections.abc import Awaitable, Callable, Sequence


@dataclass(frozen=True)
class PipeObservation:
    inject_to_writer: list[bytes]
    forward_chunk: bytes


ObserverResult = (
    bytes
    | Sequence[bytes]
    | tuple[Sequence[bytes], bytes]
    | PipeObservation
    | Awaitable[bytes | Sequence[bytes] | tuple[Sequence[bytes], bytes] | PipeObservation | None]
    | None
)
ByteObserver = Callable[[bytes], ObserverResult]


async def run_proxy(
    real_adapter: Sequence[str],
    *,
    on_client_chunk: ByteObserver | None = None,
    on_adapter_chunk: ByteObserver | None = None,
    on_ready: Callable[[], None] | None = None,
) -> int:
    process = await asyncio.to_thread(
        _run_proxy_blocking,
        real_adapter,
        on_client_chunk,
        on_adapter_chunk,
        on_ready,
    )
    return process


def _run_proxy_blocking(
    real_adapter: Sequence[str],
    on_client_chunk: ByteObserver | None,
    on_adapter_chunk: ByteObserver | None,
    on_ready: Callable[[], None] | None,
) -> int:
    import subprocess

    process = subprocess.Popen(
        list(real_adapter),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
    )
    if process.stdin is None or process.stdout is None:
        raise RuntimeError("failed to create adapter pipes")

    if on_ready is not None:
        on_ready()
    _proxy_select_loop(
        client_reader=sys.stdin.buffer,
        adapter_writer=process.stdin,
        adapter_reader=process.stdout,
        client_writer=sys.stdout.buffer,
        on_client_chunk=on_client_chunk,
        on_adapter_chunk=on_adapter_chunk,
        process=process,
    )
    return process.wait()


def _proxy_select_loop(
    *,
    client_reader,
    adapter_writer,
    adapter_reader,
    client_writer,
    on_client_chunk: ByteObserver | None,
    on_adapter_chunk: ByteObserver | None,
    process,
) -> None:
    client_fd = client_reader.fileno()
    adapter_fd = adapter_reader.fileno()
    open_fds = {client_fd, adapter_fd}
    while open_fds and process.poll() is None:
        readable, _, _ = select.select(list(open_fds), [], [], 0.1)
        for fd in readable:
            chunk = os.read(fd, 8192)
            if not chunk:
                open_fds.discard(fd)
                continue
            if fd == client_fd:
                _process_blocking_chunk(chunk, adapter_writer, on_client_chunk)
            else:
                _process_adapter_chunk(
                    chunk,
                    client_writer=client_writer,
                    adapter_writer=adapter_writer,
                    observer=on_adapter_chunk,
                )


def _process_adapter_chunk(
    chunk: bytes,
    *,
    client_writer,
    adapter_writer,
    observer: ByteObserver | None,
) -> None:
    forward_chunk = chunk
    if observer is not None:
        observation = asyncio.run(_resolve_observer_result(observer(chunk), original_chunk=chunk))
        forward_chunk = observation.forward_chunk
        for injected in observation.inject_to_writer:
            _write_chunk_blocking(adapter_writer, injected)
    if forward_chunk:
        _write_chunk_blocking(client_writer, forward_chunk)


def _process_blocking_chunk(chunk: bytes, writer, observer: ByteObserver | None) -> None:
    forward_chunk = chunk
    if observer is not None:
        observation = asyncio.run(_resolve_observer_result(observer(chunk), original_chunk=chunk))
        forward_chunk = observation.forward_chunk
        for injected in observation.inject_to_writer:
            _write_chunk_blocking(writer, injected)
    if forward_chunk:
        _write_chunk_blocking(writer, forward_chunk)


def _pipe_blocking(reader, writer, observer: ByteObserver | None = None) -> None:
    while True:
        chunk = _read_available_blocking(reader)
        if not chunk:
            break
        forward_chunk = chunk
        if observer is not None:
            observation = asyncio.run(_resolve_observer_result(observer(chunk), original_chunk=chunk))
            forward_chunk = observation.forward_chunk
            for injected in observation.inject_to_writer:
                _write_chunk_blocking(writer, injected)
        if forward_chunk:
            _write_chunk_blocking(writer, forward_chunk)


async def _pipe(reader, writer, *, observer: ByteObserver | None = None) -> None:
    while True:
        chunk = await _read_available(reader)
        if not chunk:
            break
        forward_chunk = chunk
        if observer is not None:
            observation = await _resolve_observer_result(observer(chunk), original_chunk=chunk)
            forward_chunk = observation.forward_chunk
            for injected in observation.inject_to_writer:
                await _write_chunk(writer, injected)
        if forward_chunk:
            await _write_chunk(writer, forward_chunk)


async def _read_available(reader) -> bytes:
    read = getattr(reader, "read1", None) or reader.read
    return await asyncio.to_thread(read, 8192)


def _read_available_blocking(reader) -> bytes:
    fileno = getattr(reader, "fileno", None)
    if fileno is not None:
        try:
            return os.read(fileno(), 8192)
        except OSError:
            return b""
    read = getattr(reader, "read1", None) or reader.read
    return read(8192)


async def _resolve_observer_result(result: ObserverResult, *, original_chunk: bytes) -> PipeObservation:
    if inspect.isawaitable(result):
        result = await result
    if result is None:
        return PipeObservation(inject_to_writer=[], forward_chunk=original_chunk)
    if isinstance(result, PipeObservation):
        return result
    if isinstance(result, bytes):
        return PipeObservation(inject_to_writer=[result], forward_chunk=original_chunk)
    if _is_replacement_tuple(result):
        injected, forward = result
        return PipeObservation(inject_to_writer=list(injected), forward_chunk=forward)
    return PipeObservation(inject_to_writer=list(result), forward_chunk=original_chunk)


def _is_replacement_tuple(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[1], bytes)
    )


async def _write_chunk(writer, chunk: bytes) -> None:
        await asyncio.to_thread(writer.write, chunk)
        flush = getattr(writer, "flush", None)
        drain = getattr(writer, "drain", None)
        if drain is not None:
            await drain()
        elif flush is not None:
            await asyncio.to_thread(flush)


def _write_chunk_blocking(writer, chunk: bytes) -> None:
    writer.write(chunk)
    flush = getattr(writer, "flush", None)
    if flush is not None:
        flush()
