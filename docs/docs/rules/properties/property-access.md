---
title: PropertyAccessRule
sidebar_label: PropertyAccessRule
description: Validates the access mode of user-configured custom properties — gateway-side staging data should be PRIVATE, not shipped to every client.
---

# PropertyAccessRule

Perspective properties have three access modes, declared per property in `propConfig` (absent means `PUBLIC`):

| Mode | Client behavior |
| --- | --- |
| `PUBLIC` | Default. The value is synchronized to the client DOM; browser JavaScript can read **and write** it. |
| `PROTECTED` | The client can read the value, but the back-end ignores client-side writes. |
| `PRIVATE` | Hidden. The value is never sent to the client. |

Custom properties are frequently gateway-side staging: a view aggregates a large dataset once on `custom.data`, and ten bindings fan out from it into the components that actually render. The client never reads the staging value — but if it's `PUBLIC` (the default), the whole dataset is serialized over the websocket to every session anyway. Marking it `PRIVATE` cuts that traffic and improves responsiveness.

This rule lets a project enforce an access convention for **user-configured custom properties only** — view-level `custom.*` and component-level `<component>.custom.*`. It deliberately never evaluates:

- **component `props.*`** — components render from their props; marking a table's `props.data` PRIVATE would stop the table from rendering.
- **`params.*`** — view parameters are the view's public interface.

The rule is **opt-in and inert by default**: without `expected_access` in your config it checks nothing.

**Severity:** configurable, `error` by default. Start with `"warning"` while adopting.

**Auto-fix:** Yes. `--fix` sets (or, for `expected_access: "PUBLIC"`, removes) the `access` declaration. The fix is hard-scoped to `custom.*` propConfig entries — by construction it cannot touch `props.*`, `params.*`, or any other part of the view.

## Basic config

```json
{
  "PropertyAccessRule": {
    "enabled": true,
    "kwargs": {
      "expected_access": "PRIVATE",
      "severity": "warning"
    }
  }
}
```

Every custom property whose effective access differs — including props with no `access` declaration at all, which are `PUBLIC` by default — is flagged.

## Less common configurations

### Exempt intentionally client-visible props

If specific custom props are legitimately read by the client, exempt them rather than lowering the standard. Each entry matches the bare property name at any level, a prop key at any level, or a fully-qualified path — with `*`/`?` wildcards supported in every form:

```json
{
  "PropertyAccessRule": {
    "enabled": true,
    "kwargs": {
      "expected_access": "PRIVATE",
      "exempt_props": [
        "theme",
        "client*",
        "root.root.children[0].Chart.custom.legendConfig"
      ]
    }
  }
}
```

`"theme"` exempts `custom.theme` on the view and on every component; `"client*"` exempts every prop whose name starts with `client`; the full path pins one specific component prop. Patterns are anchored (`"data"` does not exempt `dataSet`), and brackets are literal, so indexed paths match exactly as written.

### Standardize on the default

Projects that prefer no access overrides can enforce `PUBLIC`; the fix then *removes* `access` declarations (and deletes access-only propConfig entries entirely):

```json
{
  "PropertyAccessRule": {
    "enabled": true,
    "kwargs": {
      "expected_access": "PUBLIC"
    }
  }
}
```

With `expected_access: "PUBLIC"`, undeclared props already comply — only explicit `PROTECTED`/`PRIVATE` declarations are flagged.

## Example

### Problematic view.json

```json
{
  "custom": {
    "kpiData": [ "… large aggregated dataset …" ]
  },
  "propConfig": {
    "custom.kpiData": {
      "binding": { "config": { "queryPath": "KPI/Hourly" }, "type": "query" },
      "persistent": false
    }
  }
}
```

`custom.kpiData` only feeds other bindings on the gateway, but with no `access` declaration it is `PUBLIC` and the full dataset ships to every client session. The linter emits:

```
PropertyAccessRule (warning):
  • custom.kpiData: custom property access mode is PUBLIC, expected PRIVATE
```

`--fix` adds `"access": "PRIVATE"` to the entry (creating the propConfig entry if the prop had none).

## See also

- [Full PropertyAccessRule reference](../../reference/properties/property-access.md) — every option, fix behavior, and scoping guarantees
- [PropertyPersistenceRule](./property-persistence.md) — the companion opt-in rule for the `persistent` flag on bound properties
- [ExcessiveContextDataRule](./excessive-context-data.md) — when the staged dataset is large enough that it shouldn't be in the view at all
- [UnusedCustomPropertiesRule](./unused-custom-properties.md) — detects and removes ghost/stale property definitions (propConfig entries with no binding, no value, and no references)
