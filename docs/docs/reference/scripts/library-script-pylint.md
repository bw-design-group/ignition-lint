---
title: LibraryScriptPylintRule (full reference)
sidebar_label: LibraryScriptPylintRule
description: Full technical reference for LibraryScriptPylintRule — options, rcfile resolution, builtin discovery and output.
toc_max_heading_level: 4
---

# LibraryScriptPylintRule — full reference

:::tip[Looking for the short version?]
See the [user guide](../../rules/scripts/library-script-pylint.md).
:::

## Purpose
Runs pylint on Ignition project-library modules (`ignition/script-python/**/code.py`) loaded by the `scripting` domain. Each file is a complete Python module, so pylint runs on the real file and lines map 1:1.

## Domain
`LintDomain.SCRIPTING`. Configured like any other rule in the flat config file; the CLI routes it to the scripting engine by its declared domain. It only ever sees `ScriptModule` nodes (`NodeType.SCRIPT_MODULE`) produced by `model/script_builder.py`.

## Severity
Per pylint category through `category_mapping`, exactly like [PerspectiveScriptPylintRule](./pylint-script.md#severity). Default: `F`/`E` → `error`, `W`/`C`/`R` → `warning`.

## How it works
1. **Collect.** `visit_script_module` gathers the module node(s) of the current file.
2. **Resolve builtins.** `--additional-builtins` is assembled from three sources, de-duplicated in order: the `additional-builtins` option read from the resolved rcfile (a command-line value would otherwise *replace* it), the top-level package folders beside this module's package when a `script-python` ancestor exists, and the `additional_builtins` kwarg.
3. **Run pylint** in-process (`pylint_support.run_pylint`) with `--rcfile`, `--output-format=text`, `--score=no`, `--jobs=1`. Modules built in memory (no `file_path` on disk) are written to a temporary file first.
4. **Parse** `path:line:col: CODE: message` lines into `PylintViolation(category, code, message, path=<dotted module path>, line)`.
5. **Report.** One empty placeholder violation per message keeps the counts right; `format_violations_grouped()` renders the category-grouped text.

## Configuration

#### `severity`
**Type:** `str` · **Default:** `"error"` — fallback for categories missing from `category_mapping`.

#### `pylintrc`
**Type:** `str | None` · **Default:** `None` — see [Pylintrc resolution order](#pylintrc-resolution-order).

#### `category_mapping`
**Type:** `dict[str, str]` · **Default:** `{'F': 'error', 'E': 'error', 'W': 'warning', 'C': 'warning', 'R': 'warning'}`.

#### `additional_builtins`
**Type:** `list[str]` · **Default:** `[]` — extra names pylint treats as defined. Merged with the rcfile's list and the discovered packages.

#### `debug`
**Type:** `bool` · **Default:** `False` — prints the resolved rcfile, the category mapping and the final builtin list. There is no `debug_dir`: nothing is generated that would need saving.

The rule must be constructible with no arguments (registry contract).

## Pylintrc resolution order
`pylint_support.resolve_pylintrc(explicit, ".ignition-library-pylintrc")`:

1. Explicit `pylintrc` (absolute, or relative to `os.getcwd()`); a missing file prints a warning and continues.
2. `<dir>/.config/.ignition-library-pylintrc` for every ancestor of the working directory, closest wins.
3. `<package>/.config/.ignition-library-pylintrc` bundled with ignition-lint.
4. Inline fallback `--disable=all --enable=unused-import,undefined-variable,syntax-error,invalid-name`.

### The bundled rcfile
Derived from the Perspective rcfile with these differences: `additional-builtins=system,unicode,long` (no view-scope or project-specific names), `ignored-modules=com.inductiveautomation,java,javax,org`, `jobs=1`, and the WebDev `do*.py` ignore list removed. Everything else (Python 2.7 compatibility disables, naming regexes, complexity limits) is identical.

## Output format
```
    Pylint - Error (E):
      • Line <N>: <message> (<symbol>) (<CODE>)
```
Categories render in `F, E, W, C, R` order; empty categories are omitted. With a single module per file no path prefix is printed. If several modules are processed in one pass (programmatic use) each line is prefixed with the module's dotted path.

## Edge cases
- **No `script-python` ancestor** (fixtures, ad-hoc files): the module name is the parent folder, no packages are discovered, no package builtins are added.
- **`resource.json` missing or invalid:** the node's `resource` is `{}`; linting proceeds.
- **Auto-fix:** not supported. `allow_fix` in the config prints the standard "no effect" note.

## See also
- [User guide](../../rules/scripts/library-script-pylint.md)
- [PerspectiveScriptPylintRule reference](./pylint-script.md)
- [Architecture → Lint domains](../../developing/architecture.md#lint-domains)
