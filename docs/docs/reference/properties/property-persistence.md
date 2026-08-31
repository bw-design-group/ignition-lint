---
title: PropertyPersistenceRule (full reference)
sidebar_label: PropertyPersistenceRule
description: Full technical reference for PropertyPersistenceRule — every option, detection semantics, exemption tokens, and auto-fix behavior.
toc_max_heading_level: 4
---

# PropertyPersistenceRule — full reference

:::tip[Looking for the short version?]

See the [user guide](../../rules/properties/property-persistence.md). This page is the complete technical reference — every constructor argument, exact detection semantics, exemption token grammar, and auto-fix behavior.

:::

## Purpose

In Perspective, every property configured under `propConfig` carries a `persistent` flag; **absent means `true`** (the Ignition default). For a bound property, `persistent: true` makes the designer save the last binding result into `view.json` on every save. Dynamic bindings therefore rewrite the file constantly, producing git-diff churn with zero runtime value: at runtime the binding recomputes the value regardless of what was saved.

This rule enforces a project-wide persistence convention for bound properties. It exists to *teach* as much as to enforce — the violation messages explain the churn mechanism and the null-handling discipline that non-persistent bindings require.

## Severity

Configurable via `severity`; `error` by default. `"warning"` is recommended during adoption.

## Opt-in behavior

The rule is registered and instantiated like every rule, but it is **inert unless `expected_persistent` is configured**. `create_from_config({})` produces a rule that never flags anything. This makes the check strictly opt-in even though all registered rules run by default.

## What it checks

The rule scans the **flattened JSON** directly (not the object model, which only carries propConfig metadata for view-level properties). For every propConfig entry — view-level (`propConfig.<key>`) and component-level (`<component>.propConfig.<key>`) — that:

1. is a `custom.*` entry (the scope is hard-coded, matching [PropertyAccessRule](./property-access.md) — persistence on component `props.*` and view `params.*` is Designer-managed territory),
2. **contains a binding**, and
3. is not exempt by binding type,

it compares the entry's *effective persistence* (`persistent` value if declared, otherwise `true`) against `expected_persistent`.

Unbound properties are never checked — persistence on an unbound property is how its value is stored at all.

### `expected_persistent: false`

Flags entries that are effectively persistent. Auto-fixable.

### `expected_persistent: true`

Two checks, no auto-fix:

- a bound entry with `persistent: false` is flagged, and
- a persistent bound entry with **no stored value** (no matching `custom.<name>` entry) is flagged — the point of persistence is that the key exists before the first binding evaluation, which requires a stored default. (This is the `require_default_value` semantic from issue #84, implied by expected persistence rather than configured separately.)

## Why the tag-binding exemption exists

A non-persistent bound property's key does not exist until its binding first evaluates. Expression, property, and query bindings always evaluate (even to `null`), so the key eventually appears. **Tag bindings do not**: if the tag isn't found — a common situation with indirect tag bindings whose path is built from other properties — the binding never evaluates and the key never exists. Views written against such a property can misbehave in ways that are hard to trace back to a persistence flag. Tag bindings are therefore exempt by default; projects that guarantee tag existence can opt them in.

## Configuration

### `expected_persistent`

**Type:** `bool | null` &nbsp;·&nbsp; **Default:** `null` (rule inert)

The expected `persistent` value for bound properties. Must be a JSON boolean; any other non-null value raises `ValueError` at configuration time.

---

### `exempt_binding_types`

**Type:** `list[str]` &nbsp;·&nbsp; **Default:** `["tag"]`

Binding types skipped by the check. **Setting this replaces the default entirely** — pass `[]` to check every binding type. Unknown tokens raise `ValueError` at configuration time.

| Token | Exempts |
| --- | --- |
| `expr` | Expression bindings |
| `expr-struct` | Expression structure bindings |
| `property` | Property bindings |
| `query` | Query bindings |
| `tag` | All tag bindings, regardless of mode |
| `tag.direct` | Direct tag bindings only |
| `tag.indirect` | Indirect tag bindings only |
| `tag.expression` | Expression-mode tag bindings only |

Binding type is read from the entry's `binding.type`; tag mode from `binding.config.mode`.

---

### `severity`

**Type:** `"error" | "warning"` &nbsp;·&nbsp; **Default:** `"error"`

## Auto-fix

Generated only for `expected_persistent: false` violations, and always marked **safe**. Each fix contains:

1. `SET_VALUE` — `persistent: false` on the propConfig entry (added if the flag was absent).
2. `DELETE_KEY` — the stored designer value (e.g. the `custom.<name>` entry), **only if present**. PropConfig-only properties get just the flag change. Deleting the stored value is correct by construction: the property is bound, so the runtime value comes from the binding, and the stored value is by definition the stale designer result.

Skipped edge cases:

- Entries whose propConfig key contains an array index (e.g. `custom.list[0]`) keep their stored value — deleting list elements would shift sibling indices.
- Component owners whose JSON path cannot be resolved get no fix (the violation still reports).

No fix is generated for `expected_persistent: true` violations: the linter cannot invent a meaningful default value.

## Violation message formats

Messages are kept deliberately terse — a legacy view can produce dozens of these — with the reasoning living on this page instead:

```
<path>: bound property is persistent; set persistent=false to stop storing designer results in view.json

<path>: bound property is not persistent; this project expects persistent=true

<path>: persistent bound property has no stored default value
```

`<path>` is the owner-qualified propConfig key: `custom.myProp` at view level, `root.root.children[0].Label.custom.myProp` at component level.

## See also

- [PropertyAccessRule reference](./property-access.md) — the companion `access`-mode rule
- [UnusedCustomPropertiesRule reference](./unused-custom-properties.md) — detects and removes ghost/stale property definitions left behind after bindings are deleted
