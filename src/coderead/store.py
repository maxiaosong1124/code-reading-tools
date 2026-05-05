from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from coderead.models import FlowGraph, TraceEvent


@dataclass(frozen=True)
class TraceStore:
    session_dir: Path
    session_path: Path
    events_path: Path

    @classmethod
    def create(
        cls,
        root: str | Path,
        session_id: str,
        adapter: str,
        *,
        scenario: str | None = None,
        cwd: str | None = None,
        command: list[str] | None = None,
    ) -> TraceStore:
        root_path = Path(root)
        session_dir = root_path / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        session_path = session_dir / "session.json"
        events_path = session_dir / "events.jsonl"
        session = {
            "session_id": session_id,
            "adapter": adapter,
            "created_at": datetime.now(UTC).isoformat(),
            "scenario": scenario or "",
            "cwd": cwd or os.getcwd(),
            "command": command or [],
        }
        session_path.write_text(
            json.dumps(session, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        events_path.touch()
        return cls(session_dir=session_dir, session_path=session_path, events_path=events_path)

    def append_event(self, event: TraceEvent) -> None:
        with self.events_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True))
            file.write("\n")


def load_events_jsonl(path: str | Path) -> list[TraceEvent]:
    events = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(TraceEvent.from_dict(json.loads(line)))
    return events


def load_session_metadata(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_events_jsonl(events: Iterable[TraceEvent], path: str | Path) -> Path:
    output_path = Path(path)
    with output_path.open("w", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True))
            file.write("\n")
    return output_path


def dump_graph_json(graph: FlowGraph, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.write_text(
        json.dumps(graph.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path
