---
title: Command line
sidebar_label: Command line
description: Full CLI reference for ignition-lint
---

# Command line

Complete reference for the `ign-lint` CLI. The CLI is the primary interface — every other integration (pre-commit, GitHub Actions, custom scripts) wraps it.

## Synopsis

```bash
ign-lint [FILE ...] [--files <pattern>] [options]
```

## Selecting which files to lint

There are **two distinct ways** to tell ignition-lint which files to check. Pick one — they
are different input modes, not meant to be combined.

### 1. Explicit file list (positional arguments)

Pass concrete file paths directly. They are used verbatim — no globbing, no `view.json` name
filtering. This is what pre-commit's `pass_filenames` appends, and what you want when you
already know the exact files.

```bash
# Single file
ign-lint path/to/view.json

# Several explicit files
ign-lint views/Home/view.json views/Login/view.json views/Admin/view.json
```

### 2. Glob mode (`--files`)

`--files` takes a **single value**: one glob (or a comma-separated list of globs). The pattern
is expanded by ignition-lint's own globber — not the shell — and results are filtered to
`view.json`. Use this for standalone audits and CI full-repository scans.

```bash
# One glob (quote it so the shell doesn't expand it!)
ign-lint --files "**/view.json"

# Multiple globs — comma-separated in ONE value
ign-lint --files "views/**/view.json,components/**/view.json"
```

:::warning `--files` is not repeatable
`--files` holds a single value, so repeating the flag does **not** accumulate — the last one
wins. Write `--files "a/**/view.json,b/**/view.json"`, not
`--files "a/**/view.json" --files "b/**/view.json"`. Likewise, passing multiple
space-separated paths after `--files` (e.g. `--files A.json B.json`) is **deprecated**: the
first path binds to `--files` and the rest to the positional list. ignition-lint still lints
them all and prints a deprecation warning, but you should pass an explicit list as positional
arguments (mode 1) instead.
:::

## Common invocations

```bash
# With config
ign-lint --config rule_config.json --files "**/view.json"

# Verbose, with timing
ign-lint --config rule_config.json --files "**/view.json" --verbose
```

## Options

### Files and configuration

| Flag | Description |
| --- | --- |
| `--files <pattern>` | A **single** glob, or a comma-separated list of globs, expanded by ignition-lint's globber and filtered to `view.json` (default: `**/view.json`). **Not repeatable** — a second `--files` overrides the first. For an explicit set of files, pass them as positional arguments instead. See [Selecting which files to lint](#selecting-which-files-to-lint). |
| `--config <path>` | Path to a `rule_config.json`. If omitted, every registered rule runs with defaults. |

### Whitelist

Whitelisting lets you exclude specific files from linting — useful for legacy code. By default ignition-lint does NOT use a whitelist.

| Flag | Description |
| --- | --- |
| `--whitelist <path>` | Path to a whitelist file (typically `.whitelist.txt`) |
| `--no-whitelist` | Disable whitelist (overrides `--whitelist`) |
| `--generate-whitelist <pattern>...` | Generate a whitelist file from glob patterns |
| `--whitelist-output <path>` | Output file for `--generate-whitelist` (default: `.whitelist.txt`) |
| `--append` | Append to existing whitelist (use with `--generate-whitelist`) |
| `--dry-run` | Preview without writing (use with `--generate-whitelist`) |

See [Whitelist guide](./whitelist.md) for details.

### Auto-fix

Rules that support it can rewrite the view to resolve violations (e.g. [NamePatternRule](../rules/naming/name-pattern.md) renames components, [UnusedCustomPropertiesRule](../rules/properties/unused-custom-properties.md) deletes unused property definitions, [PropertyPersistenceRule](../rules/properties/property-persistence.md) and [PropertyAccessRule](../rules/properties/property-access.md) normalize `propConfig` metadata on custom properties). Pick **one** mode:

| Flag | Description |
| --- | --- |
| `--fix` | Apply **safe** fixes — isolated edits with no ripple effects |
| `--fix-unsafe` | Apply **all** fixes, including unsafe ones that rewrite references (binding/script mentions of a renamed component). Enables fix mode on its own — do not also pass `--fix` |
| `--fix-dry-run` | **Preview** what would be fixed without modifying any file |
| `--fix-rules <names>` | Comma-separated list of rules whose fixes to apply (default: all fixable rules) |

The three modes are mutually exclusive choices: `--fix` for safe-only, `--fix-unsafe` to include reference rewrites, `--fix-dry-run` to preview. After fixes are applied, the rules are re-evaluated once on the fixed view so the reported results reflect the post-fix state, not the violations that were just fixed.

```bash
# Apply safe fixes
ign-lint --config rule_config.json --files "**/view.json" --fix

# Apply safe + unsafe fixes (rewrites references too)
ign-lint --config rule_config.json --files "**/view.json" --fix-unsafe

# Preview without writing
ign-lint --config rule_config.json --files "**/view.json" --fix-dry-run

# Only apply fixes from specific rules
ign-lint --config rule_config.json --files "**/view.json" --fix --fix-rules NamePatternRule
```

See [NamePatternRule → What `--fix` does](../rules/naming/name-pattern.md#what---fix-does) and [UnusedCustomPropertiesRule → What `--fix` does](../rules/properties/unused-custom-properties.md#what---fix-does) for how safe vs. unsafe fixes are classified.

### Output and severity

| Flag | Description |
| --- | --- |
| `--verbose` | Print per-file timing, ignored-file lists, rule coverage |
| `--ignore-warnings` | Exit zero even if warnings are present (errors still fail) |
| `--warnings-only` | Run rules but only report warnings (suppress errors) |
| `--timing-output <path>` | Write per-file timing to a file |
| `--results-output <path>` | Write a structured results report to a file |

### Analysis and debugging

| Flag | Description |
| --- | --- |
| `--stats-only` | Skip rule execution; print model statistics only |
| `--debug-nodes <type>...` | Print all nodes of the given type(s) — `component`, `expression_binding`, `property`, etc. |
| `--analyze-rules` | Print which rules visited which node types and how many violations each produced |
| `--debug-output <dir>` | Write debug artifacts (flattened JSON, model dump) to the directory |

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | No errors (warnings may still be present) |
| 1 | One or more error-severity violations |
| 2 | Configuration or file-loading failure |

`--ignore-warnings` doesn't change exit codes — warnings already exit 0 by default. `--warnings-only` suppresses errors entirely so the run always exits 0.

## Reading the output

A typical violation report:

```
Found 2 errors in views/dashboard/view.json:
  PollingIntervalRule (error):
    • root.Container.props.text.binding: 'now(5000)'

  NamePatternRule (warning):
    • root.Container.children[0].my_button: Name 'my_button' doesn't follow PascalCase for component (suggestion: 'MyButton')

Summary:
  Total issues: 2
```

Each violation includes the JSON path inside the view, the rule name, the severity, and the message. For pylint-detected issues the format is grouped by category — see [PylintScriptRule](../rules/scripts/pylint-script.md).

## Patterns and globbing

`--files` patterns are matched by ignition-lint's internal globber, not the shell. **Quote your patterns** to prevent shell expansion:

```bash
# Right
ign-lint --files "**/view.json"

# Wrong (shell expands first; long arg lists may exceed ARG_MAX)
ign-lint --files **/view.json
```

For very large repositories (hundreds of view files), use the CLI's globbing rather than shelling out `find ... -exec`. Some pre-commit configurations pass every matched file as an arg, which can exceed system `ARG_MAX` limits — the CLI's internal globbing avoids this.

## Stats-only mode

`--stats-only` builds the model but skips rule execution. Useful for:

- Auditing what's in a view (component count, binding count, script count)
- Sanity-checking a view loads correctly
- Profiling model-build performance separately from rule execution

```bash
ign-lint --files "**/view.json" --stats-only --verbose
```

## Rule analysis mode

`--analyze-rules` reports which rules ran, what node types they visited, and how many violations each produced. Useful when:

- Onboarding a new rule and you want to confirm it's actually executing
- Debugging unexpected behavior — does the rule see the nodes it expects?
- Auditing CI cost — which rules dominate runtime?

```bash
ign-lint --config rule_config.json --files "**/view.json" --analyze-rules
```

## Debug-nodes mode

`--debug-nodes` dumps every node of the given type(s) the framework discovered:

```bash
ign-lint --files path/to/view.json --debug-nodes component expression_binding
```

Useful when developing a rule — see exactly what your visit method will receive.

## Combining modes

Modes compose. A representative debugging session:

```bash
ign-lint \
  --config rule_config.json \
  --files "views/Dashboard/view.json" \
  --verbose \
  --debug-output ./analysis \
  --analyze-rules
```

## See also

- [Configuration](../getting-started/configuration.md) — full `rule_config.json` schema
- [Pre-commit](./pre-commit.md) — wrap the CLI in a git hook
- [GitHub Actions](./github-actions.md) — wrap it in CI
- [Whitelist](./whitelist.md) — exempt files
- [Debug output](./debug-output.md) — generate model dumps and golden files
