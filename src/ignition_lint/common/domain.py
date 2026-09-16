"""
Lint domain primitives.

A *domain* is one kind of Ignition resource that ign-lint knows how to load and lint
(Perspective views, the project script library, ...). Everything domain-specific is
declared on a :class:`DomainSpec` so the engine and CLI stay generic: they classify a
file with ``spec.matches``, turn it into nodes with ``spec.load``, and gate JSON-only
features (auto-fix, flattened statistics) on what the loader actually returned.

This module is a leaf: it must not import from ``model``, ``rules`` or ``domains`` so
that all of them can import it.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class LintDomain(str, Enum):
	"""Kinds of Ignition resources ign-lint can lint."""
	PERSPECTIVE = "perspective"
	SCRIPTING = "scripting"

	def __str__(self) -> str:
		return self.value


@dataclass
class LoadedFile:
	"""
	Result of loading one resource file into the object model.

	Attributes:
		nodes: Every node the rules should visit (already de-duplicated).
		model: Named node collections, used for statistics, serialization and debug output.
		flattened_json: Path/value pairs for JSON-backed domains; ``{}`` otherwise.
		json_data: The parsed source document for JSON-backed domains; ``None`` otherwise.
			When set, fix mode and ``PathTranslator`` are available for the file.
		timings: Optional per-phase load timings in milliseconds (``file_read_ms``,
			``json_flatten_ms``, ``model_build_ms``) for the profiling report.
	"""
	nodes: List[Any]
	model: Dict[str, List[Any]] = field(default_factory=dict)
	flattened_json: Dict[str, Any] = field(default_factory=dict)
	json_data: Optional[Any] = None
	timings: Dict[str, float] = field(default_factory=dict)

	@property
	def supports_json_features(self) -> bool:
		"""True when the loader produced a JSON document (fix mode, flattened stats, ...)."""
		return self.json_data is not None


@dataclass(frozen=True)
class DomainSpec:
	"""
	Declares how one lint domain recognises and loads its files.

	Attributes:
		domain: The domain identifier.
		display_name: Human-readable name used in CLI output.
		matches: Predicate deciding whether a path belongs to this domain.
		load: Loader turning a path into a :class:`LoadedFile`.
		default_globs: Globs searched on a bare run with no explicit files. Empty for opt-in domains.
	"""
	domain: LintDomain
	display_name: str
	matches: Callable[[Path], bool]
	load: Callable[[Path], LoadedFile]
	default_globs: Tuple[str, ...] = ()
