"""
Domain registry: which kinds of Ignition resources ign-lint can lint.

Importing this package registers the built-in domains. Adding a domain is a pure
addition: write a ``DomainSpec`` in a new module here, import it below, and give it
node types and rules. Neither ``cli.py`` nor ``linter.py`` needs to change.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..common.domain import DomainSpec, LintDomain, LoadedFile
from .perspective import PERSPECTIVE_SPEC
from .scripting import SCRIPTING_SPEC


class DomainRegistry:
	"""Ordered registry of :class:`DomainSpec` objects keyed by :class:`LintDomain`."""

	def __init__(self):
		self._specs: Dict[LintDomain, DomainSpec] = {}

	def register_domain(self, spec: DomainSpec) -> DomainSpec:
		"""Register (or replace) the spec for ``spec.domain``."""
		self._specs[spec.domain] = spec
		return spec

	def unregister_domain(self, domain: LintDomain) -> None:
		"""Remove a domain; used by tests that register throwaway specs."""
		self._specs.pop(domain, None)

	def get_spec(self, domain: LintDomain) -> DomainSpec:
		"""Return the spec for ``domain``; raises KeyError when unknown."""
		return self._specs[domain]

	def all_specs(self) -> List[DomainSpec]:
		"""All registered specs in registration order."""
		return list(self._specs.values())

	def classify_file(self, path: Path) -> Optional[DomainSpec]:
		"""First registered spec whose ``matches`` accepts ``path``, else None."""
		for spec in self._specs.values():
			if spec.matches(path):
				return spec
		return None

	def default_globs(self) -> Tuple[str, ...]:
		"""Union of every spec's default globs, in registration order, without duplicates."""
		globs: List[str] = []
		for spec in self._specs.values():
			for pattern in spec.default_globs:
				if pattern not in globs:
					globs.append(pattern)
		return tuple(globs)


_global_registry = DomainRegistry()
_global_registry.register_domain(PERSPECTIVE_SPEC)
_global_registry.register_domain(SCRIPTING_SPEC)


def get_domain_registry() -> DomainRegistry:
	"""Return the global domain registry."""
	return _global_registry


def register_domain(spec: DomainSpec) -> DomainSpec:
	"""Register a domain with the global registry."""
	return _global_registry.register_domain(spec)


def get_spec(domain: LintDomain) -> DomainSpec:
	"""Spec for ``domain`` from the global registry."""
	return _global_registry.get_spec(domain)


def all_specs() -> List[DomainSpec]:
	"""All specs in the global registry."""
	return _global_registry.all_specs()


def classify_file(path: Path) -> Optional[DomainSpec]:
	"""Classify ``path`` against the global registry."""
	return _global_registry.classify_file(path)


def default_globs() -> Tuple[str, ...]:
	"""Default globs across every registered domain."""
	return _global_registry.default_globs()


__all__ = [
	"DomainRegistry",
	"DomainSpec",
	"LintDomain",
	"LoadedFile",
	"PERSPECTIVE_SPEC",
	"SCRIPTING_SPEC",
	"get_domain_registry",
	"register_domain",
	"get_spec",
	"all_specs",
	"classify_file",
	"default_globs",
]
