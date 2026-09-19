"""Diff entre deux configurations (spec §9.1 etape 5, §9.2 exemple de
resume avant confirmation) - toujours affiche avant application, jamais
un remplacement silencieux de la configuration active."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ChangeKind = Literal["added", "removed", "changed"]

_MISSING = object()


@dataclass(frozen=True)
class ConfigChange:
    path: str
    kind: ChangeKind
    old_value: Any = None
    new_value: Any = None

    def __str__(self) -> str:
        if self.kind == "added":
            return f"  + {self.path} : {self.new_value}"
        if self.kind == "removed":
            return f"  - {self.path} : {self.old_value}"
        return f"  ~ {self.path} : {self.old_value} -> {self.new_value}"


def diff_configs(old: dict[str, Any], new: dict[str, Any], _prefix: str = "") -> list[ConfigChange]:
    changes: list[ConfigChange] = []
    all_keys = sorted(set(old.keys()) | set(new.keys()))

    for key in all_keys:
        path = f"{_prefix}.{key}" if _prefix else key
        old_value = old.get(key, _MISSING)
        new_value = new.get(key, _MISSING)

        if old_value is _MISSING:
            changes.append(ConfigChange(path, "added", new_value=new_value))
        elif new_value is _MISSING:
            changes.append(ConfigChange(path, "removed", old_value=old_value))
        elif isinstance(old_value, dict) and isinstance(new_value, dict):
            changes.extend(diff_configs(old_value, new_value, path))
        elif old_value != new_value:
            changes.append(ConfigChange(path, "changed", old_value=old_value, new_value=new_value))

    return changes
