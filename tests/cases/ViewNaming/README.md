# ViewNaming test cases

Exercises naming rules on the view itself and its parent folders rather than on
components inside the view. The `views/` directory plays the role of the
Perspective views root (`com.inductiveautomation.perspective/views/` in a real
project export); everything below it is the view tree.

View folders are plain directories with no resource files. The directory that
contains `view.json` is the view; its name is the view name.

| Path below `views/` | View name | Folders | PascalCase result |
| --- | --- | --- | --- |
| `PascalFolder/PascalView` | `PascalView` | `PascalFolder` | passes |
| `Title Case Folder/Title Case View` | `Title Case View` | `Title Case Folder` | fails on folder and view |
| `PascalFolder/Nested Sub Folder/DeepView` | `DeepView` | `PascalFolder`, `Nested Sub Folder` | fails on the sub folder only |

There is no `view.json` directly in this directory. Test cases are discovered at any
depth, so each view above has its own golden files under
`tests/debug/cases/ViewNaming/views/...`, regenerated with, for example:

```bash
python scripts/generate_debug_files.py "ViewNaming/views/Title Case Folder/Title Case View"
```
