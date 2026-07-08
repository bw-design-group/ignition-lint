---
title: UnusedCustomPropertiesRule (full reference)
sidebar_label: UnusedCustomPropertiesRule
description: Full technical reference for UnusedCustomPropertiesRule — detection algorithm, regex patterns, edge cases.
toc_max_heading_level: 4
---

# UnusedCustomPropertiesRule — full reference

:::tip[Looking for the short version?]

See the [user guide](../../rules/properties/unused-custom-properties.md). This page is the complete technical reference — every detection phase, every regex pattern, every edge case the rule handles. Read it when you're debugging a false positive, integrating with custom code, or extending the rule.

:::

## Purpose
Detects custom properties and view parameters that are defined in a Perspective view but never referenced or populated anywhere in that view. Surfacing these dangling definitions keeps views lean and prevents dead configuration from accumulating over time.

## Severity
`error` by default — unused properties accumulate as technical debt; surfacing them as errors forces cleanup. Configurable via the `severity` option.

## What it checks
The rule discovers three categories of property definitions:

- View-level custom properties (`custom.*`)
- View parameters (`params.*`, both input and output directions)
- Component-level custom properties (`<component>.custom.*`)

A property is considered **used** when any of the following hold:

- The property has a binding of any type (expression, property, tag, query) — verified in `_mark_binding_owner_as_used`. A property being populated by a binding is "used" by definition.
- It appears in an expression binding under one of these patterns:
  - `{view.custom.X}`
  - `{view.params.X}`
  - `{this.custom.X}`
  - `{self.view.custom.X}`
  - `{self.view.params.X}`
- It appears in a property binding's target/source path string.
- It appears in a tag binding's `tagPath` string.
- It appears in any script (event handler, message handler, custom method, transform) under one of:
  - `self.view.custom.X`
  - `self.view.params.X`
  - `self.custom.X`
  - `self.params.X`
- It is matched by a generic fallback string-scan over every value in the flattened JSON, so references inside non-modeled string fields are still picked up.

## Why it matters
Perspective views grow organically over time. As bindings are rewritten, parameters renamed, or components removed, the underlying property definitions are often left behind in `custom`, `params`, and `propConfig`. Each orphaned definition adds visual noise in the designer, increases serialization size, and creates ambiguity for future developers ("is this still wired up somewhere?"). Detecting them early keeps views focused on the data actually flowing through the application, makes refactoring safer, and helps reviewers quickly understand a view's true surface area.

## Configuration

The rule accepts a single option that controls how violations surface.

### Severity

#### `severity`
**Type:** `"warning" | "error"` &nbsp;·&nbsp; **Default:** `"error"`

Severity level emitted for unused-property violations. Pass `"warning"` to keep the rule informational while cleaning up legacy views; pass `"error"` (default) to force resolution. The value is forwarded to `LintingRule.__init__` and used by `add_violation` when reporting unused properties.

### Configuration example

```json
{
  "UnusedCustomPropertiesRule": {
    "enabled": true,
    "kwargs": {
      "severity": "warning"
    }
  }
}
```

## How property usage is detected
The rule executes in distinct phases against the model produced by the lint engine:

1. **Visit phase** — `visit_property` walks every property node and collects every definition into `defined_properties`. Three path shapes are recognized: top-level `custom.<name>`, top-level `params.<name>`, and any nested `<component>.custom.<name>` (excluding `propConfig.*` paths).
2. **Reference phase** — Visitors over expression bindings, property bindings, tag bindings, event handlers, message handlers, custom methods, and transforms run regex scans for references:
   - Expression-form regexes (`{view.custom.X}`, `{view.params.X}`, `{this.custom.X}`, `{self.view.custom.X}`, `{self.view.params.X}`) live in `_check_expression_for_references`.
   - Script-form regexes (`self.view.custom.X`, `self.view.params.X`, `self.custom.X`, `self.params.X`) live in `_check_script_for_references`.
3. **Binding-owner phase** — Whenever a binding is visited, `_mark_binding_owner_as_used` strips the `propConfig.` prefix and any `.binding` / `.persistent` / `.paramDirection` suffix from the owning path, then marks that property as used. So a binding declared at `propConfig.params.breakerStatus.binding` marks `view.params.breakerStatus` as used even if nothing references it.
4. **Wildcard fallback** — `{this.custom.X}`, `self.custom.X`, and `self.params.X` references mark a wildcard `*.custom.X` / `*.params.X` because the rule cannot disambiguate which specific component instance the reference targets. During finalization, any defined `<component>.custom.X` matching a `*.custom.X` wildcard is treated as used.
5. **Flattened JSON sweep** — `_search_flattened_json_for_references` runs after the standard visitors and scans every string value in the flattened JSON for the literal patterns derived from each defined property (including `self.view.custom.X`, `self.view.params.X`, and bracketed short-form `{X}`). This catches references in fields that the model builder does not surface as dedicated nodes.
6. **Finalize** — Any property still in `defined_properties` but not in `used_properties` (and not covered by a wildcard match) is reported as a violation.

## Examples

### Correct code

The view defines `customViewParam` and `viewParam`. Both have entries in `propConfig`, which the rule treats as binding-owner references that mark the properties as used. From `tests/cases/PreferredStyle/view.json`:

```json
{
  "custom": {
    "customViewParam": "value"
  },
  "params": {
    "viewParam": "value"
  },
  "propConfig": {
    "custom.customViewParam": {
      "persistent": true
    },
    "params.viewParam": {
      "paramDirection": "input",
      "persistent": true
    }
  }
}
```

A property that is referenced from an expression binding is also valid — here `usedProp` and `usedComponentProp` both appear in the binding text:

```json
{
  "custom": {
    "usedProp": "value"
  },
  "root": {
    "children": [
      {
        "meta": { "name": "TestLabel" },
        "type": "ia.display.label",
        "custom": {
          "usedComponentProp": "value"
        },
        "props": {
          "text": {
            "binding": {
              "type": "expression",
              "config": {
                "expression": "{view.custom.usedProp} + {this.custom.usedComponentProp}"
              }
            }
          }
        }
      }
    ]
  }
}
```

### Problematic code

A view with a `custom` property and a `params` entry that are never referenced or bound:

```json
{
  "custom": {
    "unusedViewProp": "value"
  },
  "params": {
    "unusedViewParam": "default value"
  },
  "root": {
    "children": [],
    "meta": { "name": "root" }
  }
}
```

A component-level custom property that is never used:

```json
{
  "root": {
    "children": [
      {
        "meta": { "name": "TestButton" },
        "type": "ia.input.button",
        "custom": {
          "unusedComponentProp": "value"
        }
      }
    ],
    "meta": { "name": "root" }
  }
}
```

An output parameter that has no binding and no inbound references (still flagged because it provides no data to a parent view):

```json
{
  "params": {
    "outputWithoutBinding": null
  },
  "propConfig": {
    "params.outputWithoutBinding": {
      "paramDirection": "output",
      "persistent": true
    }
  },
  "root": { "children": [], "meta": { "name": "root" } }
}
```

**Violation message format:**

```
<definition_location>: <prop_type> '<name>' is defined but never referenced
```

Where `<prop_type>` is `view parameter` for entries under `params.*` and `custom property` for entries under `custom.*`. `<name>` is the final segment of the property path, and `<definition_location>` is the original flattened JSON path where the property was discovered.

## Special handling

### Output parameters
Output parameters (`paramDirection: "output"`) are evaluated by the same logic as every other property: they only count as "used" when they have a binding **or** are referenced elsewhere. An output parameter with no binding and no references is flagged because it cannot deliver data back to a parent view, so it is effectively dead.

### Persistent vs non-persistent
The rule does not differentiate by the `persistent` flag. Both persistent and non-persistent properties are scanned identically, and both are eligible to be reported as unused.

### `propConfig` paths
When walking the flattened JSON, paths under `propConfig.*` are not treated as new property definitions — they are treated as binding-owner references. The rule strips the leading `propConfig.` prefix when determining the property whose binding is being declared. So `propConfig.params.breakerStatus.binding` marks `view.params.breakerStatus` as used.

### Wildcard component references
A reference such as `{this.custom.foo}` or `self.custom.foo` cannot be resolved to a specific component, so it is recorded as `*.custom.foo`. During finalization, every defined `<component>.custom.foo` whose name matches the wildcard is considered used. The same wildcard handling applies to `self.params.foo`.

## Auto-fix support
This rule provides auto-fixes for flagged **custom properties only** (view-level and component-level). The fix deletes the definition via `DELETE_KEY` operations — the value entry in the owning `custom` object (when present; non-persistent properties have none) and every `propConfig` entry belonging to the property, including nested-children entries of an object property (`custom.network.nat1` alongside `custom.network`). Every fix this rule emits is **safe**: custom properties are internal to the view, so removal cannot break anything outside it.

The rule never emits unsafe fixes. No fix is generated — regardless of `--fix-unsafe` — for:

- **View parameters.** They are the view's public interface; parent views, page configuration, or navigation actions may pass them, and none of those callers are visible when linting a single file. Removal cannot be verified, so it is never automated.
- **Properties with an `onChange` property-change script**, since removal deletes the script and its side effects.
- **Flagged properties whose `propConfig` entry still contains a `binding` key** (defense in depth). Binding owners are credited as used from the flattened JSON keys (covering every binding type, including query/expr-struct/http/tag-history which have no model nodes), so a flagged-but-bound property indicates a detection blind spot — the violation reports, but nothing is deleted.
- **Definitions that cannot be resolved unambiguously.** Component custom properties are located by resolving the (index-stripped) definition path back to the component's real JSON path via the `PathTranslator`; anything unresolvable must be removed manually.

Deletion paths are only ever constructed inside `custom` and `propConfig` containers, so ordinary `props.*` values can never be removed by this rule's fixes. Empty `custom`/`propConfig` containers left behind after the last key is deleted are kept in place.

## Edge cases & exemptions
- The reserved key `_JavaDate` and any property name beginning with `_` are skipped during property discovery — handled by `LintingRule._is_private_property` in the base class.
- Paths under `propConfig.*` are never registered as property definitions; they only contribute binding-owner usage markers.
- A wildcard reference (`{this.custom.foo}`, `self.custom.foo`) marks **every** `*.custom.foo` as used, since the rule cannot pin down which component instance was meant. This may under-report unused properties in views that share property names across many components, but it never produces false positives for legitimate usages.
- The flattened-JSON sweep only inspects string values; numeric, boolean, and null fields are skipped (a property reference in those would not be syntactically valid anyway).
- Rule state (`defined_properties`, `used_properties`, `flattened_json`) is reset on every file via `process_nodes`, so processing many views back-to-back does not leak references between files.

## See also
- [UnusedCustomPropertiesRule user guide](../../rules/properties/unused-custom-properties.md) — the short version
- [Configuration overview](../../getting-started/configuration.md)
- [Creating Rules](../../developing/creating-rules.md)
