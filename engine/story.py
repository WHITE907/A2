"""Data models for dialogue trees, factions, and contextual party banter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class DialogueOption:
    id: str
    text: str
    next_node_id: str = ""
    conditions: dict[str, Any] = field(default_factory=dict)
    actions: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DialogueOption":
        return cls(
            id=str(payload.get("id", "")),
            text=str(payload.get("text", "")),
            next_node_id=str(payload.get("next_node_id", "")),
            conditions=dict(payload.get("conditions") or {}),
            actions=tuple(dict(action) for action in payload.get("actions", [])),
        )


@dataclass(frozen=True)
class DialogueNode:
    id: str
    text: str
    options: tuple[DialogueOption, ...] = ()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DialogueNode":
        return cls(
            id=str(payload.get("id", "")),
            text=str(payload.get("text", "")),
            options=tuple(DialogueOption.from_dict(option) for option in payload.get("options", [])),
        )


@dataclass(frozen=True)
class DialogueTree:
    id: str
    speaker_id: str
    start_node_id: str
    nodes: dict[str, DialogueNode]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DialogueTree":
        nodes = {
            node.id: node
            for node in (DialogueNode.from_dict(value) for value in payload.get("nodes", []))
        }
        return cls(
            id=str(payload.get("id", "")),
            speaker_id=str(payload.get("speaker_id", "")),
            start_node_id=str(payload.get("start_node_id", "start")),
            nodes=nodes,
        )


@dataclass(frozen=True)
class FactionDefinition:
    id: str
    name: str
    description: str = ""
    rivals: tuple[str, ...] = ()
    shop_discount_per_point: float = 0.0
    max_discount: float = 0.0

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FactionDefinition":
        return cls(
            id=str(payload.get("id", "")),
            name=str(payload.get("name", "")),
            description=str(payload.get("description", "")),
            rivals=tuple(str(value) for value in payload.get("rivals", [])),
            shop_discount_per_point=float(payload.get("shop_discount_per_point", 0.0)),
            max_discount=float(payload.get("max_discount", 0.0)),
        )


@dataclass(frozen=True)
class BanterDefinition:
    id: str
    trigger: str
    lines: tuple[str, ...]
    conditions: dict[str, Any] = field(default_factory=dict)
    once: bool = False

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BanterDefinition":
        return cls(
            id=str(payload.get("id", "")),
            trigger=str(payload.get("trigger", "")),
            lines=tuple(str(value) for value in payload.get("lines", [])),
            conditions=dict(payload.get("conditions") or {}),
            once=bool(payload.get("once", False)),
        )
