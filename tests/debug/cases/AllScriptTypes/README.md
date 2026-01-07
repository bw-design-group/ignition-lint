# Debug Golden Output Files for AllScriptTypes
Regenerate these files whenever the view.json is updated or when model builder logic changes.
These files help developers diagnose issues with the model building and rule application processes.

This directory contains debug information generated from `tests/cases/AllScriptTypes/view.json`:

## Files

- **`flattened.json`**: The flattened path-value representation of the original JSON
- **`model.json`**: The serialized object model with all nodes organized by type
- **`stats.json`**: Comprehensive statistics including node counts and rule coverage

## Generation

These files were generated using:
```bash
python scripts/generate_debug_files.py AllScriptTypes
```

## Usage

These files help developers understand:
1. How the JSON flattening process works
2. What nodes the model builder creates
3. Which rules apply to which nodes
4. Statistics about the view structure

