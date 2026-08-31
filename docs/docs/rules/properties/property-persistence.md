---
title: PropertyPersistenceRule
sidebar_label: PropertyPersistenceRule
description: Validates the persistent flag on bound properties — persistent bindings store designer results in view.json and churn your git history.
---

# PropertyPersistenceRule

Every property configured in `propConfig` carries a `persistent` flag, and Ignition defaults it to `true`. For a **bound** property that saved value is often stale or incorrect: the designer saves the last binding result into `view.json` on every save, so a dynamic binding (a timestamp, a query result, a tag value), or a transformation reliant on other bindings rewrites the file constantly. This results in pure git-diff churn with no runtime benefit, since at runtime the binding recomputes the value anyway.

This rule lets a project enforce a persistence convention for bound properties. It is **opt-in and inert by default**: without `expected_persistent` in your config it checks nothing.

**Severity:** configurable, `error` by default. Start with `"warning"` while adopting.

**Auto-fix:** Yes, for `expected_persistent: false` — `--fix` sets `persistent: false` on the propConfig entry and deletes the stale stored value from `custom.<name>`. No fix for `expected_persistent: true` (the linter can't invent a default value).

## The trade-off you're opting into

Making bound properties non-persistent is best practice, but it demands discipline:

- **The key doesn't exist until the binding first evaluates.** Anything reading the property must chain off the binding and handle nulls, rather than assume a value is present at view startup. Done right, downstream bindings naturally wait for the first evaluation; done carelessly, you get null-reference errors or brief render glitches.
- **Tag bindings may never create the key.** A tag binding — especially an indirect one — whose tag isn't found will never resolve the initial evaluation. In a designer, the property key never appears at all and the user assumes the binding does not exist. For this reason, tag bindings are **exempt by default**.

## Basic config

```json
{
  "PropertyPersistenceRule": {
    "enabled": true,
    "kwargs": {
      "expected_persistent": false,
      "severity": "warning"
    }
  }
}
```

This flags every bound `custom.*` property (view-level and component-level) that is persistent — explicitly or by Ignition's absent-means-true default — except tag-bound properties.

## Less common configurations

### Check tag bindings too

The default `exempt_binding_types: ["tag"]` skips all tag bindings. If your project guarantees its tags exist, override the exemption list (it replaces the default entirely):

```json
{
  "PropertyPersistenceRule": {
    "enabled": true,
    "kwargs": {
      "expected_persistent": false,
      "exempt_binding_types": []
    }
  }
}
```

You can also exempt by tag mode — `"tag.indirect"` exempts only indirect tag bindings while still checking direct ones — or exempt other binding types entirely (`"query"`, `"expr"`, `"expr-struct"`, `"property"`).

### Enforce persistence instead

Some projects prefer stored defaults so every key exists before the first binding evaluation:

```json
{
  "PropertyPersistenceRule": {
    "enabled": true,
    "kwargs": {
      "expected_persistent": true
    }
  }
}
```

This flags bound properties with `persistent: false`, and also flags persistent bound properties that have **no stored default value** — persistence without a value defeats its own purpose.

## Example

### Problematic view.json

```json
{
  "custom": {
    "lineData": "2026-08-31 06:24:59"
  },
  "propConfig": {
    "custom.lineData": {
      "binding": {
        "config": { "expression": "now()" },
        "type": "expr"
      },
      "persistent": true
    }
  }
}
```

Every designer save rewrites `custom.lineData` with whatever the binding last produced. The linter emits:

```
PropertyPersistenceRule (warning):
  • custom.lineData: bound property is persistent; set persistent=false to stop storing designer results in view.json
```

### After `--fix`

```json
{
  "custom": {},
  "propConfig": {
    "custom.lineData": {
      "binding": {
        "config": { "expression": "now()" },
        "type": "expr"
      },
      "persistent": false
    }
  }
}
```

## See also

- [Full PropertyPersistenceRule reference](../../reference/properties/property-persistence.md) — every option and violation format
- [PropertyAccessRule](./property-access.md) — the companion opt-in rule for `access` modes
- [UnusedCustomPropertiesRule](./unused-custom-properties.md) — detects and removes ghost/stale property definitions (propConfig entries with no binding, no value, and no references)
