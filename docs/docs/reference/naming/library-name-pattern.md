---
title: LibraryNamePatternRule (full reference)
sidebar_label: LibraryNamePatternRule
description: Full technical reference for LibraryNamePatternRule.
toc_max_heading_level: 4
---

# LibraryNamePatternRule — full reference

:::tip[Looking for the short version?]
See the [user guide](../../rules/naming/library-name-pattern.md).
:::

## Purpose
Validates the names of project-library packages (`NodeType.SCRIPT_PACKAGE`) and modules (`NodeType.SCRIPT_MODULE`) against a naming convention. Implemented as a thin subclass of `NamePatternRule` in `rules/naming/library_name_pattern.py`; every option documented in the [NamePatternRule reference](./name-pattern.md#configuration) applies.

## Domain
`LintDomain.SCRIPTING`. Registered under its own name, so it is configured and enabled independently of `NamePatternRule`.

## Differences from NamePatternRule
| Aspect | NamePatternRule | LibraryNamePatternRule |
| --- | --- | --- |
| Default `target_node_types` | `{component}` | `{script_package, script_module}` |
| Default `convention` | `None` (falls back to PascalCase without suggestions) | `"snake_case"` (with suggestions) |
| Name extractors | component/property/method/handler | adds `script_package` and `script_module` → `node.name` |
| `supports_fix` | `True` (component renames) | `False` |
| Dedup | none needed | `_reported_package_paths` — each package path reported once per rule instance (one CLI run) |

`target_node_types` is auto-derived from `node_type_specific_rules` keys when given, as in the parent; `preprocess_config` converts `"script_package"`/`"script_module"` strings to `NodeType` members.

## Node paths
Package and module `path` values are dotted (`General.Util`, `General.Util.Config`), computed from the folders after the innermost `script-python` ancestor. Violation lines therefore read `<dotted.path>: Name '<name>' doesn't follow <convention> for <node_type> (suggestion: '<X>')`.

Without a `script-python` ancestor the loader emits no package nodes and names the module after its parent folder, so the working directory never leaks into the names being validated.

## Edge cases
- The same package under two modules in one run: one violation.
- Perspective nodes handed to the rule are ignored (they are not in `target_node_types`).
- Must construct with no arguments (registry contract).

## See also
- [User guide](../../rules/naming/library-name-pattern.md)
- [NamePatternRule reference](./name-pattern.md)
