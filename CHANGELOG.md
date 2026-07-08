# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- `UnusedCustomPropertiesRule` no longer flags properties bound by binding types without dedicated model nodes (query, expr-struct, http, tag-history). Binding-owner crediting previously ran only from the modeled binding visitors (expression, property, tag), so a property populated by e.g. a query binding was reported as "never referenced" — and would have been deleted by the new auto-fix. Owners are now credited by scanning flattened-JSON keys, covering every binding shape at both view and component level. As a backstop, the fixer withholds any fix whose `propConfig` entry still contains a `binding` key.
- `UnusedCustomPropertiesRule` now detects (and `--fix` deletes) object-valued custom properties, including empty ones. Previously an empty dict/array custom property (`"custom": {"key_1": {}}`) vanished during JSON flattening and was invisible to the whole pipeline, and a populated object custom only surfaced as its nested children — so the top-level property was never flagged or removed, at both view and component level. Flattening now preserves empty containers as `{}`/`[]` leaves, and the rule registers the top-level property from its nested leaves. When an object property's child is referenced or bound, the parent is still credited as used.
- `UnusedCustomPropertiesRule` no longer flags component custom properties that are read through expressions its `self.*` patterns could not see: navigation calls (`self.getSibling('Btn').custom.data`), variables holding a component (`comp.custom.data`), quoted subscripts (`self.custom['data']`, including non-identifier names like `custom['my prop']`), and dynamic subscripts (`self.custom[key]`, which conservatively credits every component custom). Each of these was a false positive that the new auto-fix would have turned into deletion of a live property.
- `UnusedCustomPropertiesRule` no longer flags view parameters that are forwarded wholesale to an embedded view. A binding of `{view.params}` (expression) or a property binding on the path `view.params` passes the entire params object to the next view, so every parameter in that scope is now credited as used — matching the existing whole-object handling of bare `self.view.params` in scripts. Same for `{view.custom}` / `view.custom`.

### Added
- `UnusedCustomPropertiesRule` now supports auto-fix: `--fix` deletes unused custom properties (the value entry plus every matching `propConfig` entry, including nested-children entries of object properties), for both view-level and component-level definitions. The rule emits only safe fixes — view parameters are never auto-deleted, not even under `--fix-unsafe`, because the callers that pass them (parent views, page config, navigation actions) are outside the analyzed file and removal cannot be verified; the same no-fix policy applies to properties carrying an `onChange` property-change script. Backed by a new `DELETE_KEY` fix operation in the fix framework (`FixOperation`/`FixEngine`/`PathTranslator.delete_value`), which deletes dict keys only and refuses list elements to avoid index-shift hazards.

## [0.6.2] - 2026-07-07

### Fixed
- The component-rename auto-fixer no longer silently breaks bindings it cannot see (#114). Its reference detection previously required two or more leading dots, so a component referenced only via single-dot `./Child` or absolute `/root/Container/Component` paths was misclassified as safe to rename — plain `--fix` renamed it and left every such binding dangling (hit in production: 9 broken bindings across 5 views). Detection and rewriting now share one reference-grammar parser with the validation rules, covering `./`, `../`, `.../`, and `/root/...` forms in expressions, property-binding paths, and expression-struct values.
- Rename reference rewriting no longer corrupts unrelated text (#115). Rewrites previously used a whole-value `str.replace()` of the bare component name, which mangled overlapping sibling names (renaming `data label` rewrote part of `{../data label 2...}`, leaving a dangling reference), mutated display literals (`'pump status: '` became `'PumpStatus: '`), and edited comments and `sendMessage()` payloads inside scripts. Operations now replace the full reference text only — scripts are tokenized so real `getSibling`/`getChild` calls are distinguished from the same text in comments or unrelated string literals — and fix-conflict detection is operation-aware, so two components referenced in one expression both rename cleanly.
- The rename fixer no longer creates duplicate sibling names (#116). A suggestion that collides with an existing sibling (e.g. `My Button` → `MyButton` beside an existing `MyButton`), or with another pending rename converging on the same name, is skipped and the violation message says why (`suggestion 'MyButton' already in use by a sibling; rename manually`). Previously plain `--fix` produced two identically-named siblings — invalid in the Designer and ambiguous for references.
- `ComponentReferenceValidationRule` now validates absolute `/root/...` references in expressions, property bindings, and expression-struct bindings (#114). Previously these were silently skipped, so a broken absolute reference was never reported.
- `ComponentReferenceValidationRule` no longer false-positives on view-scoped navigation chains. On a view property/param `onChange` or view event script, `self` is the view, so `self.getChild("root")` validly resolves to the root container — the rule previously flagged `Component 'root' not found as child` on every such chain, and mis-attributed genuinely broken chains to the first link instead of the actually missing one. Scope is inferred from the flattened-JSON location (top-level `propConfig.*`/`events.*` keys), the same inference `UnusedCustomPropertiesRule` uses; view-scoped `getSibling`/`self.parent` chains are skipped rather than guessed at.
- Defense in depth for renames: a component name found in a context the fixer cannot safely rewrite (an untokenizable script, a `runScript()` expression payload, or a navigation-call pattern in a non-script value) now blocks fix generation entirely instead of being renamed around — under both `--fix` and `--fix-unsafe`.

### Added
- `common/reference_parser.py` — single shared owner of Ignition's component-reference grammar (relative/absolute binding paths, brace-wrapped expression references, tokenize-based script navigation calls), consumed by both the validation rules and the rename fixer so the two can no longer drift apart.
- `tests/cases/ExtensionFunctions` — real Designer export of an Alarm Status Table with populated `filterAlarm`/`filterShelvedAlarm` extension functions, capturing the baseline for modeling them as first-class script nodes (#117).
- `references/perspective-view-schema.unofficial.json` — Paul Griffith's unofficial Perspective view.json schema with provenance notes and a gap analysis against the current object model.

### Changed
- Renamed the Docusaurus documentation source directory from `documentation/` to `docs/`, updating the docs deploy workflow, `docusaurus.config.ts`, and `CLAUDE.md` references accordingly. [dc216c9]
- Added an explicit `.poetry/` entry to the root `.gitignore` to keep Poetry's project-local runtime state (auto-installed plugins, per-machine config) out of version control. [c3cc77d]

### Removed
- Removed the legacy flat-file `docs/` folder (PRD notes, standalone rule/tutorial guides, whitelist and troubleshooting docs) superseded by the Docusaurus documentation site. [2ef6a30]
- Removed the orphaned `images/test-failure.png` asset that was no longer referenced. [ab94b9b]

## [0.6.1] - 2026-06-22

### Changed
- The two complementary component-reference rules — `BadComponentReferenceRule` ("you are doing a bad practice": brittle traversal) and `ComponentReferenceValidationRule` ("something is broken": reference does not resolve) — now inspect the **same expanded set of nodes** so neither has a blind spot the other silently covers. A new shared `COMPONENT_REFERENCE_NODES` constant defines that set: expression bindings, **expression-struct bindings**, **property bindings**, and all script types (message handler, custom method, transform, event handler, and **`onChange` property-change**). Previously `BadComponentReferenceRule` only visited scripts and plain expression bindings (it ignored property bindings and expression-struct bindings entirely), `ComponentReferenceValidationRule` skipped expression-struct bindings, and neither rule actually scanned `onChange` property-change scripts even though they were nominally in scope. [94def42][2bcc0d1][e2d470e]

### Fixed
- `BadComponentReferenceRule` now flags brittle relative traversal (`./Foo`, `../Bar`) in **property binding** paths and **expression-struct** bindings, not just in scripts and plain expression bindings. A broken/brittle reference written as a property binding path previously sailed through this rule completely. [94def42]
- `ComponentReferenceValidationRule` now validates **single-dot** relative references (`./Child` — the current-container "drill into a child" idiom) in both expressions and property bindings. Previously the rule required two or more leading dots, so a broken `./MissingChild` reference (common in pipe/coordinate-container bindings) resolved to nothing and was never reported. The rule also now validates references inside **expression-struct** bindings. [2bcc0d1]
- Both reference rules now actually scan `onChange` property-change scripts. The shared node set already targeted them, but neither rule implemented the visitor, so a brittle or broken `getSibling`/`getChild`/relative reference inside an `onChange` script was silently skipped. [e2d470e]

## [0.6.0] - 2026-06-05

### Fixed
- `--files` no longer silently drops the first file when two or more paths are passed (e.g. `--files A B C`, exactly how pre-commit invoked the bundled hook). `--files` is a single-value option, so argparse bound the first path to it and the rest to the variadic positional `filenames`; `collect_files` then treated the two sources as mutually exclusive (`if filenames: ... elif files: ...`) and discarded the path bound to `--files`. The two sources are now merged and de-duplicated, so every supplied file is linted.
- `UnusedCustomPropertiesRule` no longer reports a false positive on a view-level custom property or parameter that is read via the bare `self.custom.X` / `self.params.X` idiom from a **view-scoped** script. Scope is now inferred from the flattened-JSON location: scripts on the view's own custom properties/params (top-level `propConfig.*`) or the view's event handlers (top-level `events.*`) run with `self` == the view, so a bare `self.custom.X` there is credited to `view.custom.X`. Component-scoped scripts (anything under `root.*`) keep the strict behavior — a bare `self.custom.X` refers to that component's own custom and does not credit a view-level property of the same name.

### Changed
- The space-separated multi-file form after `--files` (e.g. `--files A B C`) is deprecated. It is still linted, but ignition-lint now prints a deprecation warning pointing at the supported invocations: an explicit list as positional arguments, or a single comma-separated/glob value for `--files`.
- The bundled pre-commit hook (`.pre-commit-hooks.yaml`) no longer appends `--files`; it relies on `pass_filenames` to pass staged files as positional arguments. The pre-commit, whitelist, and CLI docs are updated to document the two distinct file-selection modes (explicit positional list vs single `--files` glob) and to stop recommending the deprecated `--files`-last pattern.

## [0.5.3] - 2026-06-04

### Added
- Property-change (`onChange`) scripts defined under `propConfig.<property>.onChange.script` (view-level and component-level) are now modeled as first-class `PropertyChangeScript` nodes. Previously they were not built into any script node, so script-oriented rules such as `PylintScriptRule` silently skipped their bodies; those scripts are now linted and counted in model statistics. New `NodeType.PROPERTY_CHANGE_SCRIPT` and `property_change_scripts` model collection. (#99)

### Fixed
- `--fix-unsafe` now enables fix mode on its own instead of being a silent no-op unless `--fix` was also passed. The three fix flags are now mutually exclusive choices: `--fix` (safe fixes only), `--fix-unsafe` (also rewrite references), and `--fix-dry-run` (preview). Help text for `--fix-unsafe` no longer says "use with --fix". (#93)
- When fixes are applied, ignition-lint now re-evaluates the rules once on the fixed view and reports those post-fix results, instead of printing (and counting in the exit status) the pre-fix violations it just resolved. The re-evaluation collects no fixes and never re-applies, so there is no multi-pass fix loop; `--fix-dry-run` mutates nothing and still reports the pre-fix state. (#94)
- `UnusedCustomPropertiesRule` no longer reports a false positive on a parent object/container custom property (e.g. `custom.network`) when only its nested children (`custom.network.nat1`/`nat2`) are bound or referenced. A property is now credited as used when any descendant path is bound or referenced. Reference detection is also made location-independent — references in scripts that are not modeled as their own nodes (e.g. property-change `onChange` scripts) are now detected the same as in transforms/event handlers — while preserving the component-vs-view namespace distinction (a bare `self.custom.X` does not credit a view-level property; only a nested `self.custom.X.child` does). [063379e]
- Documentation site now publishes a working `llms.txt` / `llms-full.txt` index for LLM consumption. Links in `llms.txt` were previously root-rooted (e.g. `/getting-started/installation.md`) and 404'd under the `/ignition-lint/` GitHub Pages base path; they are now emitted as fully-qualified URLs via the plugin's `relativePaths: false` option. The search page is also excluded from the index. [33d2524]

## [0.5.2] - 2026-06-02

### Fixed
- `ViewModelBuilder` now collects view-level custom and param properties that are defined only via a `propConfig` binding (e.g. non-persistent bound props, or persistent props whose parent object in the custom tree is empty). Previously these properties were silently invisible to property-scoped rules; `NamePatternRule` and `UnusedCustomPropertiesRule` now see them. [ef24bf6][05b558c]

## [0.5.1] - 2026-05-12

### Added
- Docusaurus 3 documentation site under `documentation/`, published to GitHub Pages at https://bw-design-group.github.io/ignition-lint on push to `main`. Covers tutorial, per-rule user guides, full per-rule technical references with per-option breakdowns, usage (CLI, pre-commit, GitHub Actions, whitelist, debug output), developer guide (architecture, creating rules, API reference, testing, troubleshooting), and a changelog mirror auto-copied from this file. [094f971]
- `.github/workflows/deploy-docs.yml` — builds the docs site and deploys to GitHub Pages on push to `main` (path-filtered to `documentation/**` and `CHANGELOG.md`) or via `workflow_dispatch`. [094f971]

### Changed
- README rewritten as a 53-line landing page that hands off to the published docs (was a 1170-line monolithic doc that duplicated content now living in the docs site). [094f971]

## [0.5.0] - 2026-05-10

### Added
- Auto-fix for trailing whitespace (C0303) in PylintScriptRule via `--fix` flag [d775d45]
- PylintScriptRule now uses FixableMixin so the existing fix infrastructure discovers it automatically [d775d45]
- Unit tests covering the registry contract: every registered rule must instantiate from `{}`, registration is idempotent, metadata is computed lazily [9342e8d]
- `--verbose` now prints a per-rule breakdown showing each rule's source (config path or "defaults") plus disabled / errored rules [9342e8d]

### Changed
- **Opinionated by default**: every registered rule now runs unless explicitly disabled. Previously the user's config acted as an allowlist (only listed rules ran); now the config is an override layer — rules absent from the config run with default kwargs, and `enabled: false` is the way to opt out. Configs that already list every rule (including the bundled `rule_config.json`) behave identically. Configs that listed only a subset of rules will start producing additional violations from the rules they previously omitted. [9342e8d]
- Registry no longer instantiates rules at registration time. Validation is now static-only (`issubclass(LintingRule)`, has `error_message`, has `create_from_config`); the empty-config smoke test moved to the test suite. [9342e8d]
- Registering the same rule class under the same name is now a silent no-op. The misleading `"Skipped invalid rule … is already registered"` warnings at startup are gone. [9342e8d]
- Rule metadata (`error_message`, source file, etc.) is computed lazily on first `get_rule_metadata()` call instead of at registration time. [9342e8d]
- `RULES_MAP` is now a live read-only Mapping view backed by the registry, so test code that explicitly imports a private rule module (e.g. `rules/_examples/…`) sees that rule via the same lookup API. [9342e8d]
- `rules/examples/` renamed to `rules/_examples/`. The `_` prefix excludes the directory from auto-discovery — example rules stay available for documentation and tests but are no longer registered or run by default. Test code that needs them imports the module directly. [9342e8d]
- Gitignore jython cache directories [67e8ede]
- Each pre-commit batch invocation now reports its own honest totals; removed the terminal-summary override that aggregated escalating totals across batches (the `_AGGREGATED_SUMMARY.txt` file is still written when batch files exist) [dacf480]

### Fixed
- Stale `_AGGREGATED_SUMMARY.txt` from a previous run no longer pollutes a later passing run's reported totals; cleanup now removes stale summary files (≥5s old) and the aggregator no longer reads existing summaries on non-batch paths [dacf480]
- Empty-but-valid config (`{}`) no longer aborts with "No valid configuration found"; it now means "run every rule with defaults". [9342e8d]

## [0.4.1] - 2026-02-20

### Changed
- Rename PyPI package from `ignition-lint` to `ign-lint` (CLI command is now `ign-lint`) [fef2808]
- Switch PyPI publishing to OIDC trusted publisher (no API tokens needed) [47ce126]
- Split publish workflow into build and publish jobs with GitHub environment approval gates [47ce126]
- Trigger publish workflow from tag push; derive package version from git tag [d284d2d]
- Gate Test PyPI publishing on RC tags and Prod PyPI on stable tags [d284d2d]
- Use `pipx install poetry` for GitHub runner compatibility [7c71154]

## [0.4.0] - 2026-02-15

### Added
- Auto-fix framework with `--fix`, `--fix-unsafe`, `--fix-dry-run`, and `--fix-rules` CLI flags [fd17cbf]
- NamePatternRule generates auto-fix suggestions to rename components to match naming conventions [fd17cbf]
- Safety tiers: safe fixes (unreferenced renames) vs unsafe fixes (reference updates, `this.meta.name` bindings) [fd17cbf]
- FixableMixin for rules to opt into providing auto-fixes [fd17cbf]

### Fixed
- Preserve Ignition unicode escapes (`\u0027`, `\u003c`, etc.) when writing view.json files after fixes [3dc40cb]

## [0.3.6] - 2026-02-15

### Added
- Whitelist feature for managing technical debt by ignoring specific views [dbe1363]
- CLI helper functions to generate whitelist from glob patterns [dbe1363]
- ComponentReferenceValidationRule to validate that component references resolve to actual components [057d0f2]
- BadComponentReference test case with property, expression, and script getChild references [eb08041]
- Mixed tabs/spaces detection with clear error messages [369173a]
- Tests for script indentation with comments [e85b26f]
- Implement feature for custom formatting output by rule and configured pylint category mapping[c7c1402]
- Support for BadComponentReferenceRule severity to be defined by user in rule config [ce39662]

### Changed
- Optimize script error messages in non-batch mode of pylint rule [11a7683]
- ComponentReferenceValidationRule added to default rule_config.json [c63f540]
- Disabled duplicate-code check in pylint config for test files [88b68f5]
- Enforce yapf style file usage in all CLAUDE.md commands [7b5be3a]

### Fixed
- Handle custom property references (.custom.) in ComponentReferenceValidationRule [dd10a0f]
- Skip comment lines when checking script indentation [b2788e7]

## [0.3.5] - 2026-02-13

### Added
- Automatic aggregation of batch results with cleanup for pre-commit workflows [e59d6d1]

### Fixed
- Resolve race conditions and file conflicts when running in parallel execution (e.g., pre-commit hooks) [82f6f21] [bbbda21]
- Add script indentation validation and smart auto-correction for view.json files [3e116b1]
- Improve debug file management with automatic cleanup and source file tracking [3e116b1]

## [0.3.4] - 2026-02-12

### Fixed
- Handle view.params with bindings in UnusedCustomPropertiesRule [536319b]

## [0.3.3] - 2026-02-07

### Fixed
- Upgrade Python to 3.13.1 and remove pre-commit version constraint [71ba2a5]

## [0.3.2] - 2026-02-06

### Added
- Comprehensive tests for mixed naming patterns (PascalCase/SCREAMING_SNAKE_CASE) [b19a336]

### Changed
- Simplify NamePatternRule pattern configuration from 'custom_pattern' to 'pattern' [27dc03f]

### Fixed
- Add common Ignition event handlers to default pylintrc exemptions [16d8c30]

## [0.3.1] - 2026-02-05

### Added
- A suggestion_convention parameter in NamePatternRule to support a default naming convention suggestion when using custom regex pattern [40641c1]

## [0.3.0] - 2026-02-03

### Added
- Prep package to be available on PyPI - install with `pip install ignition-lint` [02ad134]
- Python 3.13 support [02ad134]
- PyPI metadata: keywords and classifiers for better package discoverability [02ad134]
- Automated release preparation workflow triggered by RC tags [41d9491]
- PyPI publishing workflow for automated package publishing [2430eb1]
- Comprehensive release process documentation in RELEASING.md [d189aa1]
- CLI `--version` flag to display package version [69310f9]
- v0.3.0 implementation documentation [2ccb2b6]

### Changed
- Moved `pre-commit` from runtime dependencies to dev dependencies (cleaner installation) [02ad134]
- Updated Python version constraint to `>=3.10,<3.14` (was `>=3.10,<3.13`) [02ad134]
- Optimized CI pipeline to run only on PRs with smart Python version matrix [bde11a4]
- Renamed ci.yml to ci-pipeline.yml for clarity [bde11a4]
- Updated CLAUDE.md with release process section [5d990bc]
- Moved bundled pylintrc from root to `src/ignition_lint/.config/.pylintrc` [69310f9]
- Updated author order to reflect primary contributor [9e16825]

### Fixed
- NamePatternRule now correctly expects snake_case for custom methods (was incorrectly expecting camelCase) [56669ad]
- Bundled pylintrc now properly included in wheel package for pip installations [69310f9]

### Removed
- `ignition-api-stubs` dependency (not used at runtime, was blocking Python 3.13 support) [02ad134]
- Redundant unittest.yml and integration-test.yml workflows that are covered by the ci-pipeline.yaml [bde11a4]
- Temporary v0.3.0 implementation guide (archived implementation notes kept) [436451d]

## [0.2.10] - 2026-01-29

### Added
- NamePatternRule now skips props.aspectRatio properties to prevent false positives on coordinate containers [eabbb41]

## [0.2.9] - 2026-01-27

### Added
- UnusedCustomPropertiesRule now detects self.params references in script transforms [5cf928d]
- Test coverage expanded for UnusedCustomPropertiesRule with 8 new test cases covering script transforms, tag bindings, message handlers, custom methods, property bindings, and expression patterns [5599aad]

### Fixed
- UnusedCustomPropertiesRule now correctly recognizes view parameters used as self.params in script transforms, preventing false positives [5cf928d]
- Pattern matching in script reference detection now properly handles escaped regex patterns for .params. and .custom. patterns [5cf928d]

## [0.2.8] - 2026-01-26

### Added
- BadComponentReferenceRule added to default rule_config.json to detect brittle component traversal patterns (.getSibling, .getParent, .getChild)
- NamePatternRule now validates message_handler nodes (kebab-case convention)
- NamePatternRule now validates custom_method nodes (snake_case convention)

### Changed
- NamePatternRule no longer validates event_handler nodes as event handler names (onActionPerformed, onClick, etc.) are framework-defined by Ignition components
- rule_config.json updated with comprehensive naming conventions for all user-controllable node types:
  - component: PascalCase (min 3 chars)
  - property: camelCase (min 2 chars)
  - message_handler: kebab-case (min 2 chars)
  - custom_method: snake_case (min 2 chars)
- Add docker/.gitignore and remove tracked files matching ignore patterns [9ce499a]

## [0.2.7] - 2026-01-15

### Security
- Updated Python requirement from >=3.9 to >=3.10 (Python 3.9 reached EOL October 2025)
- Updated filelock from 3.18.0 to 3.20.3 to fix CVE-2025-68146 (TOCTOU race condition vulnerabilities)
- Updated virtualenv from 20.31.2 to 20.36.1 to fix CVE-2026-22702 (TOCTOU vulnerabilities in directory creation)
- Added explicit `permissions: contents: read` to all GitHub Actions workflows following principle of least privilege

### Changed
- NamePatternRule now skips position properties (x, y coordinates) to prevent false positives on coordinate container properties [5e1b209]
- NamePatternRule now skips SVG path properties (d property in props.elements) to prevent false positives on SVG shape components [70b6329]

### Fixed
- UnusedCustomPropertiesRule now properly resets state between files to prevent false positives [30a440b]
- Resolved Pylance type errors in unit test base classes and test files [64afcf9]

## [0.2.6] - 2026-01-09

### Added
- Performance profiling with `--timing-output` and `--results-output` flags [b66e88b]
- Batch processing mode for PylintScriptRule to process all files together [95b81fa]
- ExcessiveContextDataRule to detect large arrays and excessive nesting in custom properties [9d76661]
- Four detection methods for excessive context data: array size, sibling properties, nesting depth, total data points [41e3c95]
- Detailed warnings and errors in results report output [3da2a29]
- Timestamp to timing reports for tracking report generation time [cc3eb3b]
- Auto-save debug files when PylintScriptRule finds errors [0ce3555]
- Configurable debug directory for PylintScriptRule via `debug_dir` parameter [43fa11f]
- File path header display at top of output before violations [ee1cb1f]

### Changed
- Disabled batch mode by default for clearer per-file output [28ac26e]
- `--warnings-only` flag replaced with `--ignore-warnings` for clearer intent [e81c1c1]
- Removed confusing "additional" wording from batch results output [20a8956]
- File path now shown once at top instead of repeated in each violation header [ee1cb1f]

### Fixed
- Pre-commit compatibility and configuration simplification [942cc7f]
- CSS property detection now includes all style containers [8c2d21f]
- Deprecated stage names in pre-commit configuration [cdc1bc0]
- Duplicate model building in LintEngine [7f0c84b]
- Duplicate violation output in non-batch mode [52295bb]
- Duplicate warning statements in output [d667c78]
- Report styling improvements [f83ea8a]
- Strip array indices from script function names for valid Python [33271a6]
- Warn when specified pylintrc file is not found [c1b904f]
- Always show pylintrc resolution in debug mode [5936f59]
- Create parent directories for timing and results output files [bf1a9bd]
- Suppress pylint module name errors for temporary files with timestamps [cf7ba13]
- Rule name spacing in output [8ac97c1]

### Performance
- Optimized `_is_property_persistent` with propConfig caching (30s → <1s for large files) [a618dda]
- PylintScriptRule quick optimization wins [dbb00e5]

### Documentation
- Added ExcessiveContextDataRule documentation [5ffa23d]
- Corrected pre-commit workflow documentation (incremental checks vs full scans) [795d9a1]

## [0.2.5] - 2026-01-09

### Added
- Pre-push hooks for comprehensive validation (full pylint + full test suite)
- yapf format check to pre-commit stage
- Clear section comments distinguishing pre-commit vs pre-push hook stages
- Changelog skills for automated changelog management
- .lfsconfig to skip LFS downloads during pre-commit installation

### Changed
- Reorganized pre-commit hooks into fast pre-commit stage (5-10s) and comprehensive pre-push stage (1-2min)
- Pre-commit pylint now only runs on changed files for faster feedback
- Migrated deprecated stage names (`commit` → `pre-commit`, `push` → `pre-push`)
- Updated PR template with breaking change section and type of change checklist
- Bundle .config/ directory with package for default pylintrc access
- Pylintrc resolution order now: rule_config.json → repo .config → package .config → pylint defaults
- Use Pythonic any() approach for CSS property detection

### Fixed
- Pre-commit installation failing due to LFS 404 errors
- CSS property detection now includes all style containers (.textStyle., .elementStyle., .instanceStyle.)
- CSS properties (kebab-case) no longer incorrectly flagged as naming violations
- Deprecated stage name warnings in pre-commit configuration

### Removed
- Redundant .ignition-lint-precommit.json file
- --pylintrc CLI argument (all configuration now via rule_config.json)
- Unnecessary target_node_types from rule_config.json (auto-derived)

## [0.2.4] - 2024-12-XX

### Added
- Configurable pylintrc parameter for PylintScriptRule
- Improved output capture for pylint script linting
- Makefile for convenience commands
- Support for CSS properties in style and elementStyle properties

### Fixed
- Model builder now properly handles arrays
- Event handler domain and event type extraction
- Transform script key now correctly uses "code"
- CSS property detection includes all style containers
- Pre-commit compatibility and configuration simplification
- View script linting issues

### Changed
- Debug files regenerated with corrected event handler extraction
- Rule coverage target types now sorted alphabetically

### Removed
- .DS_Store files from repository

## [0.2.3] - 2024-XX-XX

### Changed
- Reworked name rule to not require node_types list in arguments
- Updated pre-commit configuration

## [0.2.2] - 2024-XX-XX

### Fixed
- Severity levels on name patterns for different node types

## [0.2.1] - 2024-XX-XX

### Initial tracked release

[Unreleased]: https://github.com/bw-design-group/ignition-lint/compare/v0.6.2...HEAD
[0.6.2]: https://github.com/bw-design-group/ignition-lint/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/bw-design-group/ignition-lint/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/bw-design-group/ignition-lint/compare/v0.5.3...v0.6.0
[0.5.3]: https://github.com/bw-design-group/ignition-lint/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/bw-design-group/ignition-lint/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/bw-design-group/ignition-lint/compare/v0.5.0-rc1...v0.5.1
[0.4.1]: https://github.com/bw-design-group/ignition-lint/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/bw-design-group/ignition-lint/compare/v0.3.6...v0.4.0
[0.3.6]: https://github.com/bw-design-group/ignition-lint/compare/v0.3.5...v0.3.6
[0.3.5]: https://github.com/bw-design-group/ignition-lint/compare/v0.3.4...v0.3.5
[0.3.4]: https://github.com/bw-design-group/ignition-lint/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/bw-design-group/ignition-lint/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/bw-design-group/ignition-lint/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/bw-design-group/ignition-lint/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/bw-design-group/ignition-lint/compare/v0.2.10...v0.3.0
[0.2.10]: https://github.com/bw-design-group/ignition-lint/compare/v0.2.9...v0.2.10
[0.2.9]: https://github.com/bw-design-group/ignition-lint/compare/v0.2.8...v0.2.9
[0.2.8]: https://github.com/bw-design-group/ignition-lint/compare/v0.2.7...v0.2.8
[0.2.7]: https://github.com/bw-design-group/ignition-lint/compare/v0.2.6...v0.2.7
[0.2.6]: https://github.com/bw-design-group/ignition-lint/compare/v0.2.5...v0.2.6
[0.2.5]: https://github.com/bw-design-group/ignition-lint/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/bw-design-group/ignition-lint/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/bw-design-group/ignition-lint/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/bw-design-group/ignition-lint/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/bw-design-group/ignition-lint/releases/tag/v0.2.1
