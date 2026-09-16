---
title: Debug output
sidebar_label: Debug output
description: Generate flattened JSON, model dumps, and golden files for debugging
---

# Debug output

When a rule isn't behaving the way you expect, or when you're developing a new rule, the framework can dump everything it built from a view: the flattened path-value JSON, the constructed object model, per-rule statistics, and golden reference files for regression testing.

## Generating debug files

```bash
# Generate debug files for every test case
python scripts/generate_debug_files.py

# Generate for a specific test case
python scripts/generate_debug_files.py PascalCase LineDashboard

# List test cases and their debug status
python scripts/generate_debug_files.py --list

# Remove all debug directories
python scripts/generate_debug_files.py --clean
```

Each test case directory under `tests/cases/views/` gets a `debug/` subdirectory containing:

| File | Purpose |
| --- | --- |
| `flattened.json` | Path → value pairs from the JSON flattener |
| `model.json` | Serialized object model — every node, type, and metadata |
| `stats.json` | Statistics + which rules apply to which node types |
| `README.md` | Per-case explanation generated alongside the artifacts |

## When to use each file

### `flattened.json`
Use when: you're debugging a path issue (e.g., a rule expected `props.text` but the actual path is `props.config.text`). The flattened JSON shows exactly what the rule's path-based detection sees.

### `model.json`
Use when: you're debugging visitor logic. The model is what `visit_*` methods receive. Inspecting it tells you which node type, name, and properties your method will get.

### `stats.json`
Use when: you're auditing rule coverage or wondering why a rule didn't fire. Stats include node-type counts, which rules visited which node types, and how many violations each produced.

## Per-rule debug output

Some rules write their own debug artifacts:

### `PerspectiveScriptPylintRule`

Saves the combined script (the temp file pylint actually analyzes) to `tests/debug/` (when running from `tests/`) or `.ignition-lint/debug/` (otherwise). The file is saved automatically whenever pylint reports any issues, with the filename derived from a timestamp + PID. Set `debug=true` in the rule config to also save when there are no issues.

See [PerspectiveScriptPylintRule](../rules/scripts/pylint-script.md) for the full debug-file format.

## Golden file testing

The framework includes regression tests that compare generated debug files against committed reference files. This catches accidental changes to model-building logic.

```bash
# Regenerate all golden files
python scripts/generate_debug_files.py

# Run golden file tests (from tests/)
cd tests
python -m unittest unit.test_golden_files -v
```

The tests validate:

- JSON flattening consistency
- Model building reproducibility
- Node creation and serialization
- Statistics generation accuracy

### Developer workflow

When you change something that affects model building:

1. Update the test case (`tests/cases/views/<Name>/view.json`) or the model code
2. Regenerate the debug files: `python scripts/generate_debug_files.py <CaseName>`
3. Review the diff — does it match what you expected?
4. Run golden file tests to confirm no regressions in other cases: `python -m unittest unit.test_golden_files -v`

## Debug-output flag

`--debug-output <dir>` writes per-file debug artifacts during a normal lint run:

```bash
ign-lint --config rule_config.json --files "**/view.json" --debug-output ./analysis
```

For each file linted, ignition-lint writes one folder that mirrors the file's location relative to the working directory, holding the same three artifacts as the golden files:

```
analysis/
├── .ignition-lint-debug                  # marker: this directory is managed by ign-lint
├── views/Dashboard/
│   ├── flattened.json
│   ├── model.json
│   └── stats.json
├── views/Login/
│   └── ...
└── ignition/script-python/general/config/ # scripting domain: no flattened.json
    ├── model.json
    └── stats.json
```

Because every Perspective view is literally named `view.json`, keying on the folder is what keeps a thousand views from overwriting each other.

**Cleanup.** At the start of every run ign-lint removes the folders the previous run wrote, so stale folders for deleted views do not accumulate. The `.ignition-lint-debug` marker doubles as the manifest: it lists every folder ign-lint wrote, and only those listed folders are ever deleted. ign-lint only creates the marker in a directory it created itself or found empty; if you point `--debug-output` at a directory that already holds other files, ign-lint writes into it, prints a warning, and never cleans it. Folders written in the last five seconds are kept for the next run so parallel pre-commit batches sharing one directory do not erase each other; if you use `--debug-output` from a hook, prefer `require_serial: true` so one process owns the directory.

## Debug-nodes flag

`--debug-nodes <type>` prints every node of the given type(s) the framework discovered:

```bash
ign-lint --files path/to/view.json --debug-nodes component
ign-lint --files path/to/view.json --debug-nodes expression_binding property
```

Available types: `component`, `property`, `expression_binding`, `property_binding`, `tag_binding`, `event_handler`, `message_handler`, `custom_method`, `transform`.

## Stats-only flag

`--stats-only` builds the model but doesn't run rules — useful when you just want a count:

```bash
ign-lint --files "**/view.json" --stats-only --verbose
```

Output:

```
Stats for views/Dashboard/view.json:
  Components: 47
  Bindings (expression): 12
  Bindings (property): 3
  Bindings (tag): 8
  Scripts (event handler): 6
  Scripts (custom method): 2
  Total nodes: 78
```

## Analyze-rules flag

`--analyze-rules` reports which rules ran, which node types they targeted, and how many violations each produced:

```bash
ign-lint --config rule_config.json --files "**/view.json" --analyze-rules
```

Useful when:

- Onboarding a new rule and confirming it's actually executing
- Debugging unexpected behavior — does the rule see the nodes it expects?
- Auditing CI cost — which rules dominate runtime?

## See also

- [Command line](./cli.md) — every debug-related flag
- [Architecture](../developing/architecture.md) — what the model looks like
- [Testing rules](../developing/testing-rules.md) — how golden files are wired into the test suite
- [Troubleshooting](../developing/troubleshooting.md) — diagnosing common rule problems
