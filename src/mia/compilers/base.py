from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any


class UnsupportedIntentError(ValueError):
    """Raised when a backend cannot preserve canonical intent semantics."""


@dataclass(frozen=True)
class CompilationResult:
    backend: str
    artifact: str | tuple[str, ...]
    registry_hash: str
    intent_hash: str
    audit_hash: str
    capabilities: dict[str, bool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def shell_command(self) -> str:
        if not isinstance(self.artifact, tuple):
            raise TypeError("this compilation is not a command")
        return shlex.join(self.artifact)
