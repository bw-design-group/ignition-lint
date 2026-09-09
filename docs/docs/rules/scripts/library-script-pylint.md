---
title: LibraryScriptPylintRule
sidebar_label: LibraryScriptPylintRule
description: Runs pylint on Ignition project-library script modules (script-python/**/code.py).
---

# LibraryScriptPylintRule

Runs [pylint](https://pylint.readthedocs.io/) on every module of the Ignition **project script library** — the `code.py` files under `<project>/ignition/script-python/`. It is the library counterpart of [PerspectiveScriptPylintRule](./pylint-script.md) and is configured completely independently: its own `pylintrc`, its own `category_mapping`, its own `additional_builtins`.

**Domain:** `scripting`. Library files are opt-in — pass them explicitly, via a `--files` glob, or through the `ign-lint-scripting` pre-commit hook. A bare `ign-lint` run still only picks up `view.json`.

**Severity:** `error` for Fatal and Error pylint categories, `warning` for Warning, Convention and Refactor, remappable per category via `category_mapping`.

**Auto-fix:** No. Library modules are real Python files; use your editor or a formatter.

## Basic config

```json
{
  "LibraryScriptPylintRule": {
    "enabled": true
  }
}
```

The rule looks for `.config/.ignition-library-pylintrc` walking up from the working directory, then falls back to the copy bundled with ignition-lint. Run it on a package:

```bash
ign-lint --config rule_config.json --files "ignition/script-python/**/code.py"
```

## Common configurations

### Separate tuning from the Perspective rule

The whole point of two rules is two configurations. A typical layout keeps the Perspective rule permissive (embedded snippets) and the library rule strict (real modules):

```json
{
  "PerspectiveScriptPylintRule": {
    "enabled": true,
    "kwargs": {
      "pylintrc": ".config/.ignition-pylintrc"
    }
  },
  "LibraryScriptPylintRule": {
    "enabled": true,
    "kwargs": {
      "pylintrc": ".config/.ignition-library-pylintrc",
      "category_mapping": {
        "F": "error",
        "E": "error",
        "W": "error",
        "C": "warning",
        "R": "warning"
      }
    }
  }
}
```

### Declaring gateway globals

Names that exist at runtime but not in the file — gateway-scoped globals, names injected by a module — would otherwise report `E0602`. Declare them once:

```json
{
  "LibraryScriptPylintRule": {
    "enabled": true,
    "kwargs": {
      "additional_builtins": [
        "shared",
        "logger"
      ]
    }
  }
}
```

Top-level library packages do **not** need to be listed: when the module lives under a `script-python` folder, the rule discovers its sibling top-level packages (`General`, `Widgets`, …) and declares them automatically. The `system` module and the Jython builtins `unicode`/`long` come from the bundled rcfile.

## What it lints

One `code.py` at a time, directly on the real file, so line numbers in the output are the real line numbers. The sibling `resource.json` is read into the module node (scope, restricted, overridable) but is not linted.

## Examples

### Correct code

`tests/cases/scripting/clean/code.py` uses `system.tag.readBlocking`, `long` and `unicode` and passes cleanly under the bundled rcfile.

### Problematic code

`tests/cases/scripting/violations/code.py` produces, grouped by category:

```
  LibraryScriptPylintRule:

    Pylint - Error (E):
      • Line 19: Undefined variable 'undefined_helper' (undefined-variable) (E0602)

    Pylint - Warning (W):
      • Line 11: Unused import json (unused-import) (W0611)
      • Line 24: Unused variable 'scratch' (unused-variable) (W0612)

    Pylint - Convention (C):
      • Line 13: Constant name "badConstant" doesn't conform to ... (invalid-name) (C0103)
```

Because each file is exactly one module, lines are not prefixed with a script path; the file header above the block names the file.

## Pylintrc

Resolution order: the `pylintrc` kwarg (absolute, or relative to the working directory) → `.config/.ignition-library-pylintrc` walking up from the working directory → the bundled `.config/.ignition-library-pylintrc` inside the installed package → a minimal inline ruleset. The bundled file is derived from the Perspective one but pre-declares only `system`, `unicode` and `long` as builtins and never assumes view-scope names such as `self` or `event`.

## Common gotchas

- **`additional-builtins` on the command line replaces the rcfile value.** The rule merges the rcfile's list, the discovered packages and your `additional_builtins` before passing them, so nothing is lost — but if you supply your own rcfile, keep `system` in its `additional-builtins`.
- **Fixtures without a `script-python` ancestor** (like this repo's `tests/cases/scripting`) are recognised via the sibling `resource.json`; package discovery is skipped for them.
- **WebDev resources are not covered.** `doGet.py`-style files are a different resource kind and will get their own rule.

## See also

- [Full LibraryScriptPylintRule reference](../../reference/scripts/library-script-pylint.md)
- [LibraryNamePatternRule](../naming/library-name-pattern.md) — naming conventions for the same packages and modules
- [Configuration overview](../../getting-started/configuration.md#lint-domains) — how rules map to domains
