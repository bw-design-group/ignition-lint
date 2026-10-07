# Naming test cases (view and folder names)

Exercises naming rules on the view itself and its parent folders rather than on
components inside the view. `tests/cases/views/` is the first bare `views` directory on
the path, so it plays the role of the Perspective views root
(`com.inductiveautomation.perspective/views/` in a real project export); everything
below it, including this `Naming/` folder, is the view tree. The folder is a single
capitalised word so it satisfies PascalCase and Title Case alike and never adds a
violation of its own.

View folders are plain directories with no resource files. The directory that
contains `view.json` is the view; its name is the view name.

| Path below `tests/cases/views/` | View name | Folders | PascalCase result |
| --- | --- | --- | --- |
| `Naming/PascalFolder/PascalView` | `PascalView` | `Naming`, `PascalFolder` | passes |
| `Naming/Title Case Folder/Title Case View` | `Title Case View` | `Naming`, `Title Case Folder` | fails on folder and view |
| `Naming/PascalFolder/Nested Sub Folder/DeepView` | `DeepView` | `Naming`, `PascalFolder`, `Nested Sub Folder` | fails on the sub folder only |

There is no `view.json` directly in this directory. Test cases are discovered at any
depth, so each view above has its own golden files under
`tests/debug/cases/Naming/...`, regenerated with, for example:

```bash
python scripts/generate_debug_files.py "Naming/Title Case Folder/Title Case View"
```
