---
title: Architecture
sidebar_label: Architecture
description: How ignition-lint loads, models, and analyzes Ignition resources across lint domains
---

# Architecture

This page is the conceptual map of the framework. Read it before writing a custom rule — most rule bugs trace back to a misunderstanding of one of these components.

## Lint domains

ignition-lint lints more than one kind of Ignition resource. Each kind is a **domain**, declared by a `DomainSpec` (`common/domain.py`) and registered in `domains/`:

| Domain | Files | Loader | Node types | Rules |
| --- | --- | --- | --- | --- |
| `perspective` | `view.json` | flatten → `ViewModelBuilder` | components, bindings, scripts, properties | every Perspective rule |
| `scripting` | `script-python/**/code.py` | `ScriptModelBuilder` | `script_package`, `script_module` | `LibraryScriptPylintRule`, `LibraryNamePatternRule` |

A `DomainSpec` carries everything that varies per domain: `matches(path)` decides which files belong to it, `load(path)` turns a file into a `LoadedFile` (nodes, named model collections, and — for JSON domains — the flattened JSON and parsed document), and `default_globs` says what a bare run searches for. Every `LintingRule` declares its `domain` (default `PERSPECTIVE`); the CLI builds one `LintEngine` per domain that has files, configures it with the rules of that domain from the flat config file, and runs each file through `engine.process_file(path, spec)`. Features that only make sense for JSON (auto-fix, flattened statistics) are gated on what the loader returned, never on the domain's name.

### Adding a domain

Adding a domain is a pure addition — `cli.py` and `linter.py` do not change:

1. Add a `LintDomain` member (`common/domain.py`); its value is the domain's display key in CLI output.
2. Add node types to `NodeType` and node classes in `model/node_types.py` (never extend `ALL_SCRIPTS` — that set drives Perspective script rules), plus no-op `visit_<type>` methods on `NodeVisitor`.
3. Write a loader/builder producing a `LoadedFile`, and a `DomainSpec` in `domains/<name>.py`; import it in `domains/__init__.py`.
4. Write rules with `domain = LintDomain.<NAME>`; they are discovered like any other rule.
5. Add fixtures under `tests/cases/<domain>/`, a bind mount in `docker/docker-compose.yaml`, and a docs page.

`tests/integration/test_cli_scripting_domain.py::TestExtensibilityProof` registers a throwaway domain at runtime and drives the generic CLI path; it is the executable form of this checklist.

## Pipeline (Perspective)

A lint run on a view flows through four phases:

```
view.json → flatten → build model → run rules → report
```

| Phase | Module | Output |
| --- | --- | --- |
| Flatten | `common/flatten_json.py` | Path → value pairs |
| Build model | `model/builder.py` | Object tree of typed nodes |
| Run rules | `linter.py` + `rules/*` | Per-rule violations |
| Report | `cli.py` | Grouped, severity-aware output |

For the scripting domain the first two phases are replaced by `model/script_builder.py`, which reads a `code.py` and its sibling `resource.json` into a `ScriptModule` node plus one `ScriptPackage` node per enclosing folder under `script-python`.

## Phase 1 — Flattening

The flattener converts a hierarchical Perspective view into a flat dictionary keyed by dot-paths. Array indices are bracketed:

```json
{
  "root": {
    "children": [{
      "meta": {"name": "Button"},
      "props": {"text": "Click Me"}
    }]
  }
}
```

becomes

```json
{
  "root.children[0].meta.name": "Button",
  "root.children[0].props.text": "Click Me"
}
```

This representation is what every downstream phase reads. Some rules (`ExcessiveContextDataRule`, `UnusedCustomPropertiesRule`) skip the model and operate directly on flattened JSON for performance or coverage reasons.

## Phase 2 — Model building

`ViewModelBuilder` walks the flattened JSON and produces typed nodes. Every node has a `.path` (its location in the original JSON) and a `.node_type` (the enum below).

### Node types

```
src/ignition_lint/model/node_types.py
```

| Enum value | Class | Description |
| --- | --- | --- |
| `COMPONENT` | `Component` | UI components — buttons, labels, containers |
| `PROPERTY` | `Property` | Component or view-level properties |
| `EXPRESSION_BINDING` | `ExpressionBinding` | `expr` bindings |
| `EXPRESSION_STRUCT_BINDING` | `ExpressionStructBinding` | Multi-expression struct bindings |
| `PROPERTY_BINDING` | `PropertyBinding` | property-to-property bindings |
| `TAG_BINDING` | `TagBinding` | tag bindings (direct, expression, indirect modes) |
| `QUERY_BINDING` | `QueryBinding` | named-query bindings |
| `MESSAGE_HANDLER` | `MessageHandlerScript` | message handlers |
| `CUSTOM_METHOD` | `CustomMethodScript` | component custom methods |
| `TRANSFORM` | `TransformScript` | script transforms inside bindings |
| `EVENT_HANDLER` | `EventHandlerScript` | event handler scripts |
| `PROPERTY_CHANGE_SCRIPT` | `PropertyChangeScript` | `onChange` scripts on custom/params properties |
| `VIEW` | `View` | the view itself — name and folder path derived from the view.json location, not its contents (Perspective domain) |
| `SCRIPT_MODULE` | `ScriptModule` | project-library module (`code.py`) — scripting domain |
| `SCRIPT_PACKAGE` | `ScriptPackage` | project-library package folder — scripting domain |

Convenience sets:

- `ALL_BINDINGS` — every binding type
- `ALL_SCRIPTS` — every Perspective embedded-script type (scripting-domain nodes are deliberately excluded)

Each node class adds type-specific attributes: `Component.name`, `ExpressionBinding.expression`, `TagBinding.tag_path` / `mode` / `references`, `ScriptNode.script` and `get_formatted_script()`, etc.

The `View` node is the one node not built from the flattened JSON. `ViewModelBuilder.build_model` accepts the optional `source_file_path` of the view.json and derives the view name (the directory containing `view.json`) and its folder path (every directory between the views root and the view directory) from it — see `common/view_path.py`. The views root is the `views` directory under `com.inductiveautomation.perspective`, falling back to the first bare `views` segment. With no root in the path the view is still named after its directory, but no folders are reported. It is built last so it can also summarize the view: `root_container_type` (the root component's type), `default_size` (the view's `props.defaultSize`, when declared) and `node_counts` / `total_nodes` over every other modeled node. Callers that build a model without a path get an empty `view` collection. The Perspective domain loader (`domains/perspective.py`, used by `process_file`) passes the file path through, and `collect_nodes` iterates `NODE_COLLECTIONS` (which starts with `view`), so the node reaches rules on the CLI path exactly as it does via `process(flattened_json, source_file_path=...)`.

## Phase 3 — Rule execution (visitor pattern)

The framework uses the visitor pattern to dispatch each node to the right rule method without coupling node classes to rule classes.

```
src/ignition_lint/rules/common.py
```

### How it works

1. **Rule declares interest.** Each rule's `__init__` calls `super().__init__(target_node_types)` with the node types it cares about.
2. **LintEngine filters nodes.** Before calling visit methods, the engine filters the model to only nodes matching `target_node_types`.
3. **Double dispatch.** For each filtered node, the engine calls `node.accept(rule)`. The node knows its own type and routes to the right `visit_*` method on the rule.

```python
# What you write in a rule
def visit_component(self, node: ViewNode):
    if some_condition:
        self.add_violation(f"{node.path}: explanation")

# What the framework does
for node in model.filter(rule.target_node_types):
    node.accept(rule)  # → rule.visit_component(node)
```

### Visit methods

Every rule inherits a complete set of empty `visit_*` methods from `NodeVisitor`. Override only what you need:

```python
class NodeVisitor:
    def visit_component(self, node): pass
    def visit_property(self, node): pass
    def visit_expression_binding(self, node): pass
    def visit_property_binding(self, node): pass
    def visit_tag_binding(self, node): pass
    def visit_message_handler(self, node): pass
    def visit_custom_method(self, node): pass
    def visit_transform(self, node): pass
    def visit_event_handler(self, node): pass
    def visit_script_module(self, node): pass   # scripting domain
    def visit_script_package(self, node): pass  # scripting domain
    def visit_generic(self, node): pass  # fallback
```

### Lifecycle hooks

Rules can override these in addition to visit methods:

| Hook | When called | Use it for |
| --- | --- | --- |
| `before_visit()` | Before any nodes are visited | Reset state, prepare caches |
| `visit_*()` | Once per matching node | Per-node logic |
| `post_process()` | After all nodes visited | Cross-node analysis, batch processing |
| `finalize()` | After post_process | Cleanup, summary output |

### Severity and violation reporting

`add_violation(message, severity=None)` is the canonical way to report. It appends to `self.errors` or `self.warnings` based on severity:

```python
self.add_violation(f"{node.path}: violation message")
self.add_violation(f"{node.path}: also a violation", severity="warning")
```

Don't append directly to `self.errors` in new rules — `add_violation` handles severity routing centrally.

## Specialized base classes

| Class | Targets | Adds |
| --- | --- | --- |
| `LintingRule` | Anything (`target_node_types` set in `__init__`) | Base visitor, severity routing |
| `BindingRule` | `ALL_BINDINGS` by default | Convenient default for binding-only rules |
| `ScriptRule` | `ALL_SCRIPTS` by default | Auto-collects scripts into `self.collected_scripts`, calls `process_scripts()` for batch analysis |
| `FixableMixin` | Mix in alongside any rule base | Adds `add_fix()` / `get_fixes()`; framework integrates fixes when `--fix` is requested |

Use the most specific base class. A rule that only ever looks at scripts should subclass `ScriptRule`, not `LintingRule`.

## Lint engine

`LintEngine` (`linter.py`) is domain-agnostic and orchestrates rule execution for one file at a time:

1. `process_file(path, spec)` asks the domain spec to load the file into a `LoadedFile`
2. Fix context (original JSON + `PathTranslator`) is set up only when the loader returned a JSON document
3. For each rule, filters nodes by target types and calls visit methods
4. Calls `post_process()` and, after all files, `finalize()` hooks
5. Collects violations and returns `LintResults`

`process(flattened_json, ...)` remains as the Perspective-only entry point used by `BaseRuleTest`, the golden-file tests and `scripts/generate_debug_files.py`. The CLI keeps one engine per domain and merges their `finalize_batch_rules()` results; rules with `batch_mode=True` (currently only `PerspectiveScriptPylintRule`) accumulate state across files and report once at the end.

## Auto-fix

Rules that inherit `FixableMixin` can produce `Fix` objects describing JSON edits. When `--fix` is enabled (or via the framework API), the engine applies safe fixes automatically and reports unsafe ones for human review.

A `Fix` includes:

| Field | Purpose |
| --- | --- |
| `rule_name` | Which rule produced it |
| `violation_message` | The violation it addresses |
| `description` | Human-readable explanation |
| `operations` | List of `FixOperation` (JSON path edits) |
| `is_safe` | Whether automated application is safe |
| `safety_notes` | If unsafe, why |

See `src/ignition_lint/common/fix_operations.py` for the full schema and `name_pattern.py` / `lint_script.py` for working examples. Fixes are only possible in JSON-backed domains; the engine never establishes fix context for a `LoadedFile` without `json_data`.

## Where rules live

```
src/ignition_lint/rules/
├── common.py          # base classes (LintingRule, BindingRule, ScriptRule, FixableMixin)
├── registry.py        # auto-discovery
├── naming/            # NamePatternRule, LibraryNamePatternRule (scripting)
├── structure/         # BadComponentReferenceRule, ComponentReferenceValidationRule
├── performance/       # PollingIntervalRule
├── properties/        # UnusedCustomPropertiesRule, ExcessiveContextDataRule, PropertyPersistenceRule, PropertyAccessRule
├── scripts/           # PerspectiveScriptPylintRule, LibraryScriptPylintRule (scripting), pylint_support.py (shared, not a rule)
└── _examples/         # reference rules — excluded from auto-discovery
```

Any `.py` file under `rules/` (excluding `_examples/`, `__init__.py`, `registry.py`, `common.py`) is auto-discovered. Subdirectories are recursed.

## See also

- [Creating rules](./creating-rules.md) — practical guide
- [API reference](./api-reference.md) — registry and base-class details
- [Testing rules](./testing-rules.md) — `BaseRuleTest`, golden files
- [Troubleshooting](./troubleshooting.md) — common rule-development issues
