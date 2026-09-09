---
title: Architecture
sidebar_label: Architecture
description: How ignition-lint parses, models, and analyzes Perspective views
---

# Architecture

This page is the conceptual map of the framework. Read it before writing a custom rule — most rule bugs trace back to a misunderstanding of one of these components.

## Pipeline

A lint run flows through four phases:

```
view.json → flatten → build model → run rules → report
```

| Phase | Module | Output |
| --- | --- | --- |
| Flatten | `common/flatten_json.py` | Path → value pairs |
| Build model | `model/builder.py` | Object tree of typed nodes |
| Run rules | `linter.py` + `rules/*` | Per-rule violations |
| Report | `cli.py` | Grouped, severity-aware output |

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
| `VIEW` | `View` | the view itself — name and folder path derived from the view.json location, not its contents |

Convenience sets:

- `ALL_BINDINGS` — every binding type
- `ALL_SCRIPTS` — every script type

Each node class adds type-specific attributes: `Component.name`, `ExpressionBinding.expression`, `TagBinding.tag_path` / `mode` / `references`, `ScriptNode.script` and `get_formatted_script()`, etc.

The `View` node is the one node not built from the flattened JSON. `ViewModelBuilder.build_model` accepts the optional `source_file_path` of the view.json and derives the view name (the directory containing `view.json`) and its folder path (every directory between the views root and the view directory) from it — see `common/view_path.py`. The views root is the `views` directory under `com.inductiveautomation.perspective`, falling back to the first bare `views` segment. With no root in the path the view is still named after its directory, but no folders are reported. It is built last so it can also summarize the view: `root_container_type` (the root component's type), `default_size` (the view's `props.defaultSize`, when declared) and `node_counts` / `total_nodes` over every other modeled node. Callers that build a model without a path get an empty `view` collection.

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

`LintEngine` (`linter.py`) orchestrates the whole pipeline:

1. Loads the configured rules from `rule_config.json`
2. Flattens the view
3. Builds the model
4. For each rule, filters nodes by target types and calls visit methods
5. Calls `post_process()` and `finalize()` hooks
6. Collects violations and returns a structured report

For batch runs (multiple files), the engine processes one file at a time but allows rules with `batch_mode=True` (currently only `PylintScriptRule`) to accumulate state across files and report once at the end.

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

See `src/ignition_lint/common/fix_operations.py` for the full schema and `name_pattern.py` / `lint_script.py` for working examples.

## Where rules live

```
src/ignition_lint/rules/
├── common.py          # base classes (LintingRule, BindingRule, ScriptRule, FixableMixin)
├── registry.py        # auto-discovery
├── naming/            # NamePatternRule
├── structure/         # BadComponentReferenceRule, ComponentReferenceValidationRule
├── performance/       # PollingIntervalRule
├── properties/        # UnusedCustomPropertiesRule, ExcessiveContextDataRule
├── scripts/           # PylintScriptRule
└── _examples/         # reference rules — excluded from auto-discovery
```

Any `.py` file under `rules/` (excluding `_examples/`, `__init__.py`, `registry.py`, `common.py`) is auto-discovered. Subdirectories are recursed.

## See also

- [Creating rules](./creating-rules.md) — practical guide
- [API reference](./api-reference.md) — registry and base-class details
- [Testing rules](./testing-rules.md) — `BaseRuleTest`, golden files
- [Troubleshooting](./troubleshooting.md) — common rule-development issues
