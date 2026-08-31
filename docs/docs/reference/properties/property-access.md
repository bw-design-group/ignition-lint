---
title: PropertyAccessRule (full reference)
sidebar_label: PropertyAccessRule
description: Full technical reference for PropertyAccessRule — every option, detection semantics, and the auto-fix scoping guarantees.
toc_max_heading_level: 4
---

# PropertyAccessRule — full reference

:::tip[Looking for the short version?]

See the [user guide](../../rules/properties/property-access.md). This page is the complete technical reference — every constructor argument, exact detection semantics, and the fix's scoping guarantees.

:::

## Purpose

Perspective property access modes control what the client can see and do (declared per property in `propConfig`; **absent means `PUBLIC`**):

- **PUBLIC** — unrestricted. The value is synchronized to the client DOM; browser JavaScript can read and write it.
- **PROTECTED** — read only. The client can read the value; the back-end ignores client-side write requests.
- **PRIVATE** — hidden. The value is never sent to the client.

Custom properties commonly act as gateway-side staging — one aggregated dataset on `custom.data` feeding many downstream bindings. Left `PUBLIC` (the default), that dataset is serialized over the websocket to every client session even though nothing on the client reads it. This rule lets a project enforce an access convention so staging data is declared `PRIVATE` (or whatever the project standardizes on).

## Severity

Configurable via `severity`; `error` by default. `"warning"` is recommended during adoption.

## Opt-in behavior

The rule is **inert unless `expected_access` is configured**. `create_from_config({})` produces a rule that never flags anything, making the check strictly opt-in even though all registered rules run by default.

## Scope: custom properties only, by construction

The rule evaluates **user-configured custom properties only** — the union of:

- every top-level property in a `custom` object (view-level `custom.*` and component-level `<component>.custom.*`), and
- every propConfig entry whose key starts with `custom.` (so propConfig-only transient props are covered too).

It never evaluates:

- **component `props.*`** — components render from their props. Declaring e.g. a table's `props.data` PRIVATE would stop the data from reaching the client and the table would not render. This scope exclusion is hard-coded, not configurable.
- **`params.*`** — view parameters are the view's public interface.
- Structures that merely resemble a custom scope: `custom` objects are only recognized on the view root or on real components (identified by `meta.name`), so a component literally named `custom` is never misread.

Evaluation is at **top-level property granularity**: the effective access of `custom.network` comes from the propConfig entry `custom.network`; a nested entry like `custom.network.nat1` does not satisfy (or receive) the check for `network`.

## Configuration

### `expected_access`

**Type:** `str | null` &nbsp;·&nbsp; **Default:** `null` (rule inert)

One of `PUBLIC`, `PROTECTED`, `PRIVATE` (case-insensitive; normalized to uppercase). Anything else raises `ValueError` at configuration time.

A property's *effective* access is its declared `access` value, or `PUBLIC` when undeclared. Consequences:

- `expected_access: "PRIVATE"` (or `"PROTECTED"`) flags undeclared props too — they are effectively PUBLIC.
- `expected_access: "PUBLIC"` flags only explicit non-PUBLIC declarations; undeclared props already comply.

---

### `exempt_props`

**Type:** `list[str]` &nbsp;·&nbsp; **Default:** `[]`

Properties to skip. Each entry is tried against three forms of every candidate property, and matches if any form matches:

- the bare property **name** — `"data"` exempts the view's `custom.data` and every component's `custom.data`;
- the **prop key** at any level — `"custom.data"` (equivalent to the bare name for custom props);
- the **fully-qualified path** — `"root.root.children[0].Chart.custom.data"` exempts exactly that property.

Wildcards are supported in every form: `*` matches any run of characters (including dots) and `?` matches exactly one character — `"kpi*"` exempts every property whose name starts with `kpi`. Everything else is literal and patterns are fully anchored: `"data"` does not exempt `dataSet`, and brackets are **not** character classes, so indexed paths like `children[0]` match exactly as written.

Use this for props intentionally read by client-side code rather than relaxing `expected_access` project-wide.

---

### `severity`

**Type:** `"error" | "warning"` &nbsp;·&nbsp; **Default:** `"error"`

## Auto-fix

All fixes are marked **safe**: because the rule's scope is custom-only by construction, the client-breaking failure mode (hiding component `props.*`) cannot occur.

For `expected_access: "PRIVATE"` or `"PROTECTED"`:

- entry exists → `SET_VALUE` its `access` key;
- entry missing but the owner has a `propConfig` dict → `SET_VALUE` a new entry `{"access": "<expected>"}`;
- owner has no `propConfig` dict at all → the first fix for that owner creates the dict with the entry; subsequent fixes for the same owner add entries (fixes apply in generation order, so the dict exists by the time they run).

For `expected_access: "PUBLIC"`:

- `DELETE_KEY` the `access` declaration (PUBLIC is the implicit default — cleaner than writing it out);
- if the entry declared *only* `access`, the whole now-empty entry is deleted instead.

### Scoping guarantees (defense in depth)

Two independent layers keep the fix from ever touching anything but `custom.*` propConfig entries:

1. The fix generator only receives already-filtered violations (custom scope, not exempt) and never re-derives targets.
2. A final guard inspects every generated operation path: it must land on a `propConfig` key starting with `custom.` (or, for propConfig-dict creation, introduce only `custom.*` keys). Any operation failing the guard drops the **entire fix** rather than emitting it — the violation still reports for manual action.

The test suite (`tests/unit/properties/test_property_access.py`, `TestAccessFixScoping`) additionally asserts, over a kitchen-sink view, that the exact post-fix JSON diff contains nothing outside `custom.*` propConfig entries — including a bound `props.data` table analogue, `params.*` at both levels, `props.params.*` keys, and a component named `custom`.

## Violation message format

```
<path>: custom property access mode is <ACTUAL>, expected <EXPECTED>
```

`<path>` is the owner-qualified prop key: `custom.kpiData` at view level, `root.root.children[0].Chart.custom.theme` at component level.

## Companion cleanup: ghost properties

A "ghost" custom property — a propConfig entry (often just `{"access": "PRIVATE", "persistent": false}`) whose binding was deleted, with no stored value and no remaining references — sits in the file silently forever. That case is detected and auto-fixed by [UnusedCustomPropertiesRule](./unused-custom-properties.md), which performs full reference analysis before declaring a definition dead. Run both rules together for complete propConfig hygiene.

## See also

- [PropertyPersistenceRule reference](./property-persistence.md) — the companion `persistent`-flag rule
- [ExcessiveContextDataRule reference](./excessive-context-data.md) — for when staged data shouldn't live in the view at all
