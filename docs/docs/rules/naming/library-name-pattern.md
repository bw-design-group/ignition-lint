---
title: LibraryNamePatternRule
sidebar_label: LibraryNamePatternRule
description: Enforces naming conventions on project-library packages and script modules.
---

# LibraryNamePatternRule

Applies [NamePatternRule](./name-pattern.md)'s conventions to the Ignition **project script library**: the package folders under `script-python` and the module folders that hold a `code.py`. Same options, same violation messages, keyed by two node types:

| Node type | What is named | Example |
| --- | --- | --- |
| `script_package` | A folder that contains other packages or modules | `General` in `General/Config/code.py` |
| `script_module` | The folder holding `code.py` — the name you import | `Config` in `General/Config/code.py` |

**Domain:** `scripting`. Configure it in `rule_config.json` like any other rule; it only runs on library files.

**Severity:** `warning` by default; configurable globally or per node type.

**Auto-fix:** No — renaming folders on disk is out of scope.

## Basic config

```json
{
  "LibraryNamePatternRule": {
    "enabled": true
  }
}
```

Defaults to **snake_case** for both packages and modules. This matches the IA Exchange style guide (module and library script names all lowercase) and the Google Python style guide (`lower_with_under`), so a single-word lowercase name satisfies both. Pick a different convention with `convention` or per-type overrides.

### Migrating legacy PascalCase packages

Many existing projects carry PascalCase library folders (`General`, `Widgets`, …) from before a convention was enforced. Renaming a package changes every `import` and dotted call in the project, so treat it as a migration rather than a quick fix:

1. Start with `"severity": "warning"` so the rule reports without blocking commits.
2. Exempt packages you are not ready to rename with `skip_names` (names, not paths).
3. Rename one package at a time in the Designer, then remove it from `skip_names`.

```json
{
  "LibraryNamePatternRule": {
    "enabled": true,
    "kwargs": {
      "convention": "snake_case",
      "severity": "warning",
      "skip_names": [
        "General",
        "Widgets"
      ]
    }
  }
}
```

## Common configurations

### Different conventions per node type

```json
{
  "LibraryNamePatternRule": {
    "enabled": true,
    "kwargs": {
      "node_type_specific_rules": {
        "script_package": {
          "convention": "snake_case",
          "min_length": 2,
          "severity": "error"
        },
        "script_module": {
          "convention": "PascalCase",
          "min_length": 2,
          "severity": "warning"
        }
      }
    }
  }
}
```

### Only check modules

```json
{
  "LibraryNamePatternRule": {
    "enabled": true,
    "kwargs": {
      "convention": "snake_case",
      "target_node_types": [
        "script_module"
      ]
    }
  }
}
```

## Examples

`tests/cases/scripting/badModule_name/code.py`:

```
  LibraryNamePatternRule:
    • badModule_name: Name 'badModule_name' doesn't follow snake_case for script_module (suggestion: 'badmodule_name')
```

A package is surfaced by every module beneath it, so the rule reports each package **once per run**, under the first file that revealed it. Module names are reported per file.

## What gets skipped

- Package nodes are only produced when the file lives under a `script-python` folder. Fixtures checked out on their own (like `tests/cases/scripting`) yield module names only.
- Everything `NamePatternRule` skips (`skip_names`, abbreviations, …) applies unchanged.

## See also

- [Full LibraryNamePatternRule reference](../../reference/naming/library-name-pattern.md)
- [NamePatternRule](./name-pattern.md) — the Perspective counterpart and the full option list
- [LibraryScriptPylintRule](../scripts/library-script-pylint.md)
