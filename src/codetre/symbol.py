"""Data models for codetre symbols."""

from dataclasses import dataclass, field


@dataclass
class Symbol:
    name: str
    kind: str
    line_start: int
    line_end: int
    calls: list[str] = field(default_factory=list)
    children: list["Symbol"] = field(default_factory=list)


@dataclass
class FileResult:
    file: str
    symbols: list[Symbol]
