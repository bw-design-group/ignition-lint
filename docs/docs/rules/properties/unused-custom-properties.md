---
title: UnusedCustomPropertiesRule
sidebar_label: UnusedCustomPropertiesRule
description: Flags custom properties and view parameters that are defined but never referenced.
---

# UnusedCustomPropertiesRule

Flags custom properties and view parameters that are defined in a view but never read, bound, or written to. These dangling definitions accumulate as views evolve — bindings get rewritten, parameters get renamed, components get removed — and they leave behind dead configuration that adds noise to the designer, bloats serialized views, and confuses future maintainers.

**Severity:** `error` by default — unused properties are technical debt that the rule asks you to clean up. Downgrade to `"warning"` while bringing a legacy view into compliance.

**Auto-fix:** Yes, for **custom properties only**. The rule emits a safe fix that deletes the unused definition — the value entry in the owning `custom` object plus any matching `propConfig` entries. **View parameters are never auto-deleted**, not even under `--fix-unsafe`: they are the view's public interface, and the callers that pass them (parent views, page config, navigation actions) are invisible to the linter. See [What `--fix` does](#what---fix-does).

## Basic config

Enable the rule with defaults — unused props become errors:

```json
{
  "UnusedCustomPropertiesRule": {
    "enabled": true
  }
}
```

That's it. Every `custom.*`, `params.*`, and `<component>.custom.*` definition in the view is checked, and anything that isn't bound or referenced gets flagged. Values of any shape count as definitions — scalars, arrays, objects, and empty objects/arrays (`"key_1": {}`) alike; for an object property the top-level key is the definition, and it is credited as used whenever any of its nested children is bound or referenced.

## Common configurations

### Downgrade to warning while cleaning up legacy views

Useful when you're adopting the rule on a codebase that already has lots of orphaned definitions — surface them in CI logs without breaking the build:

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

### Strict mode on a freshly-cleaned codebase

Once a view is clean, lock it down so new unused props never sneak in:

```json
{
  "UnusedCustomPropertiesRule": {
    "enabled": true,
    "kwargs": {
      "severity": "error"
    }
  }
}
```

## Examples

### Correct code

A view-level custom property that is referenced from an expression binding passes. `usedProp` is read inside the binding text, so the rule marks it as used:

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

A property that has its own binding is also considered used — even if nothing else references it. From `tests/cases/PreferredStyle/view.json`:

```json
{
  "custom": {
    "customViewParam": "value"
  },
  "params": {
    "viewParam": "value"
  },
  "propConfig": {
    "custom.customViewParam": { "persistent": true },
    "params.viewParam": { "paramDirection": "input", "persistent": true }
  }
}
```

### Problematic code

A view with `custom` and `params` entries that are never bound and never referenced:

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

Output:

```
UnusedCustomPropertiesRule (error):
  • custom.unusedViewProp: custom property 'unusedViewProp' is defined but never referenced
  • params.unusedViewParam: view parameter 'unusedViewParam' is defined but never referenced
```

## What counts as "used"

A property is treated as used when **any** of the following hold:

- The property has a binding of **any** type — including types the object model doesn't represent as nodes (query, expr-struct, http, tag-history). A property being populated by a binding is "used" by definition; binding owners are credited from the flattened JSON keys so no binding shape is missed.
- The whole `params`/`custom` object is forwarded to a consumer — e.g. an embedded view's `props.params` bound with `{view.params}` (expression) or a property binding on the path `view.params`. Any member may be read by the next view, so every property in that scope is credited. Bare `self.view.params` in scripts already behaved this way.
- It appears in an expression binding, e.g. `{view.custom.X}`, `{view.params.X}`, `{this.custom.X}`, `{self.view.custom.X}`, or `{self.view.params.X}`.
- It appears in a property binding's target/source path.
- It appears in a tag binding's `tagPath` string.
- It appears in a script (event handler, message handler, custom method, transform), e.g. `self.view.custom.X`, `self.view.params.X`, `self.custom.X`, or `self.params.X`.
- A component custom is read through **any** component-yielding expression in a script — navigation calls (`self.getSibling('Btn').custom.data`), variables holding a component (`comp.custom.data`), or quoted subscripts (`self.custom['data']`, names with spaces included). A dynamic subscript (`self.custom[key]`) conservatively credits every component custom property, since any member could be read.

A fallback string-scan over every value in the flattened JSON catches references in fields the model builder doesn't surface as dedicated nodes — so most real-world reference patterns get picked up automatically.

## What `--fix` does

For flagged **custom properties** (view-level and component-level) the rule generates a removal fix consisting of `DELETE` operations:

- the property's value entry in the owning `custom` object (absent for non-persistent properties, which live only in `propConfig`), and
- the property's `propConfig` entry, plus `propConfig` entries for any nested children of an object property (e.g. `custom.network.nat1` alongside `custom.network`).

These fixes are always **safe** (applied with plain `--fix`): custom properties are internal to the view — nothing outside the view can reference them, so deleting an unused one cannot break another resource.

This rule never emits unsafe fixes. A violation gets **no fix at all** — not even under `--fix-unsafe` — when removal cannot be verified from the analyzed file alone:

- **View parameters.** Params are the view's public interface — a parent view, page configuration, or navigation action may pass the parameter even though nothing inside the view reads it, and none of those callers are visible to the linter. Auto-deleting one could silently break the project, so the violation reports and a human decides.
- **Properties with an `onChange` property-change script.** Removing the property deletes the script and whatever side effects it carried.
- **Flagged properties whose `propConfig` entry still contains a `binding`.** A bound property should always be credited as used, so this state means detection hit a blind spot — deleting it would destroy a working binding.
- **Definitions the rule cannot locate unambiguously in the JSON.**

Deletions only ever target `custom` and `propConfig` containers on the view or on a real component (one with `meta.name`). Normal component properties under `props.*` — including subtrees that happen to contain a literal `"custom"` key — are never touched.

Note: removal deletes individual keys only. If the last property in a `custom`/`params`/`propConfig` object is removed, the now-empty `{}` container is left in place (harmless to Ignition; the Designer drops it on next save).

## Caveats

- **Output parameters** are evaluated by the same rules as everything else. An output param (`paramDirection: "output"`) with no binding and no inbound references is flagged because it cannot deliver data back to a parent view.
- **`propConfig` entries** are not new definitions — they are binding-owner markers. So `propConfig.params.breakerStatus.binding` marks `view.params.breakerStatus` as used.
- **Wildcard component references**: `{this.custom.foo}` and `self.custom.foo` can't be resolved to a specific component, so they mark **every** `*.custom.foo` definition as used. This means views that share a property name across many components may under-report unused properties (but never produce false positives for legitimate usages).
- **Persistent vs non-persistent**: the rule does not differentiate. Both are scanned the same way and both are eligible to be flagged.
- **Private properties**: names starting with `_` (and the reserved `_JavaDate`) are skipped during property discovery.

## See also

- [Full UnusedCustomPropertiesRule reference](../../reference/properties/unused-custom-properties.md) — every detection phase, every regex, every edge case
- [Configuration overview](../../getting-started/configuration.md) — the `rule_config.json` schema
