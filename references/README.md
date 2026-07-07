# External reference material

Third-party / reverse-engineered references used to sanity-check ignition-lint's
model against real Ignition behavior. **None of this is an official spec.**

## `perspective-view-schema.unofficial.json`

An **unofficial** JSON Schema (draft-07) for Perspective `view.json`, authored by
Paul Griffith (Inductive Automation) and shared on the IA forum. It is
reverse-engineered from the design-time GSON serializers.

**Status: unofficial, unvalidated, no guarantees.** Per IA staff (Kevin Herron),
`view.json` "is a serialization format that is effectively private because it's an
implementation detail... serialized and deserialized with custom GSON serializers.
There is no validation." So there is no authoritative schema to defer to — treat
this file as a set of *hypotheses to confirm against a live Designer*, not truth.

- Source thread: https://forum.inductiveautomation.com/t/json-schema-for-view-json/114184
- Path-reference grammar (authoritative docs): https://www.docs.inductiveautomation.com/docs/8.1/ignition-modules/perspective/working-with-perspective-components/bindings-in-perspective/binding-property-path-reference

### Gap analysis vs. ignition-lint's current model (as of 2026-07-07)

Where the schema describes structure ignition-lint does **not** currently model.
Each should be verified in a real Designer before acting on it.

| Schema element | Modeled today? | Impact if real |
| --- | --- | --- |
| `scripts.extensionFunctions[]` | **No** — no node type, builder never reads it | Extension-function script bodies are invisible to `PylintScriptRule` and both component-reference rules — they are silently un-linted. Likely the biggest real gap. |
| Binding `type: "http"` | **No** — builder handles only `expr`/`expression`, `expr-struct`, `property`, `tag`, `query` | HTTP bindings are not modeled at all. |
| Binding `type` tag-history | **No** | Tag-history bindings are not modeled. |
| `access` levels `PUBLIC`/`PROTECTED`/`SYSTEM` | **Partial** — builder only tests `== 'PRIVATE'` | Non-private/non-public access levels are collapsed into "not private". |
| Message handler `sessionScope`/`pageScope`/`viewScope`; action `scope` (`G`/`C`) | **No** — scope is inferred from JSON location instead | Explicit scope flags could make the reference / unused-custom-property scope inference authoritative instead of positional. |
| `permissions` / `securityLevels` | **No** | Not lint-relevant today; noted for completeness. |
| Binding `enabled` / `previewEnabled` / `overlayOptOut`; action `enabled` / `preventDefault` / `stopPropagation` | **No** | Metadata, not currently lint-relevant. |

Note the schema's binding-path grammar is intentionally open (`config` is a bare
`object`), so it does **not** enumerate the reference forms (`/root/...`, `./`,
`../`, `.../`) — those come from the docs above, not from this schema. See
ignition-lint issue #114 for the reference-grammar work.
