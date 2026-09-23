import json
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from app.services.schemas import AnalysisResponse


class ConfigDiffRequest(BaseModel):
    service: str = Field(min_length=1, max_length=100)
    format: Literal["yaml", "json"] = "yaml"
    before: str = Field(max_length=250_000)
    after: str = Field(max_length=250_000)


class ConfigDiffResponse(BaseModel):
    changes: list[dict[str, Any]]
    analysis: AnalysisResponse


def parse_document(text: str, document_format: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text) if document_format == "json" else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError, RecursionError) as exc:
        raise ValueError("Configuration document is invalid.") from exc
    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict) or any(not isinstance(key, str) for key in parsed):
        raise ValueError("Configuration root must be an object with string keys.")
    return parsed


def _flatten(
    value: Any, prefix: str = "", depth: int = 0, ancestors: frozenset[int] = frozenset()
) -> dict[str, Any]:
    if depth > 20:
        raise ValueError("Configuration nesting exceeds the supported limit.")
    if isinstance(value, dict):
        identity = id(value)
        if identity in ancestors:
            raise ValueError("Recursive YAML aliases are not supported.")
        next_ancestors = ancestors | {identity}
        result: dict[str, Any] = {}
        for key, child in value.items():
            segment = key.replace("\\", "\\\\").replace(".", "\\.")
            path = f"{prefix}.{segment}" if prefix else segment
            result.update(_flatten(child, path, depth + 1, next_ancestors))
        return result
    return {prefix: value}


def diff_configurations(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    old = _flatten(before)
    new = _flatten(after)
    keys = sorted(
        key
        for key in old.keys() | new.keys()
        if old.get(key) != new.get(key) or (key in old) != (key in new)
    )
    if len(keys) > 500:
        raise ValueError("Configuration diff exceeds 500 changed values.")
    return [{"key": key, "before": old.get(key), "after": new.get(key)} for key in keys]


def stable_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value
