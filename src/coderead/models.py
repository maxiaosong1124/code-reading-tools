from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _safe_id_part(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_").lower()


@dataclass(frozen=True)
class SourceLocation:
    function: str
    file: str
    line: int
    column: int = 0
    language: str = "unknown"

    def node_id(self) -> str:
        file_part = _safe_id_part(self.file.rsplit("/", 1)[-1])
        function_part = _safe_id_part(self.function or "unknown")
        return f"node_{file_part}_{function_part}_{self.line}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "function": self.function,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceLocation:
        return cls(
            function=data["function"],
            file=data["file"],
            line=int(data["line"]),
            column=int(data.get("column", 0)),
            language=data.get("language", "unknown"),
        )


@dataclass(frozen=True)
class StackFrame:
    function: str
    file: str
    line: int
    column: int = 0
    language: str = "unknown"

    @property
    def location(self) -> SourceLocation:
        return SourceLocation(
            function=self.function,
            file=self.file,
            line=self.line,
            column=self.column,
            language=self.language,
        )

    def to_dict(self) -> dict[str, Any]:
        return self.location.to_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StackFrame:
        return cls(
            function=data["function"],
            file=data["file"],
            line=int(data["line"]),
            column=int(data.get("column", 0)),
            language=data.get("language", "unknown"),
        )


@dataclass(frozen=True)
class TraceEvent:
    id: str
    session_id: str
    timestamp: str
    adapter: str
    event_type: str
    reason: str
    command_before_stop: str | None
    thread_id: int
    top_frame: StackFrame
    stack: list[StackFrame]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "adapter": self.adapter,
            "event_type": self.event_type,
            "reason": self.reason,
            "command_before_stop": self.command_before_stop,
            "thread_id": self.thread_id,
            "top_frame": self.top_frame.to_dict(),
            "stack": [frame.to_dict() for frame in self.stack],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceEvent:
        return cls(
            id=data["id"],
            session_id=data["session_id"],
            timestamp=data["timestamp"],
            adapter=data["adapter"],
            event_type=data["event_type"],
            reason=data.get("reason", ""),
            command_before_stop=data.get("command_before_stop"),
            thread_id=int(data["thread_id"]),
            top_frame=StackFrame.from_dict(data["top_frame"]),
            stack=[StackFrame.from_dict(frame) for frame in data.get("stack", [])],
            metadata=data.get("metadata", {}),
        )


@dataclass
class FlowNode:
    id: str
    function: str
    file: str
    line: int
    language: str
    end_line: int | None = None
    parent_id: str | None = None
    hit_count: int = 0
    kinds: set[str] = field(default_factory=lambda: {"function_location"})
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": sorted(self.kinds)[0] if len(self.kinds) == 1 else "mixed",
            "kinds": sorted(self.kinds),
            "function": self.function,
            "file": self.file,
            "line": self.line,
            "end_line": self.end_line,
            "parent_id": self.parent_id,
            "language": self.language,
            "hit_count": self.hit_count,
            "metadata": self.metadata,
        }


@dataclass
class FlowEdge:
    from_id: str
    to_id: str
    kind: str
    count: int = 0
    thread_id: int | None = None
    evidence_event_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_id,
            "to": self.to_id,
            "kind": self.kind,
            "count": self.count,
            "thread_id": self.thread_id,
            "evidence_event_ids": self.evidence_event_ids,
        }


@dataclass
class FlowGraph:
    nodes: dict[str, FlowNode] = field(default_factory=dict)
    edges: dict[tuple[str, str], FlowEdge] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges.values()],
        }
