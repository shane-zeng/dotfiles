# Python Tooling

Prefer uv for Python environment and dependency management.

## Rules

- Use `uv run` to execute Python scripts.
- Use `uv run --no-project` for temporary scripts outside Python projects.
- Use `uv run --with <package>` for temporary dependencies.
- Use `uvx` for standalone Python CLI tools.
- Use `uv add` and `uv remove` for dependency changes in uv projects.
- Avoid bare `pip install` and modifications to system Python.
- Do not migrate existing Python projects without explicit approval.
- Preserve existing project dependency management conventions.
- Do not modify project dependency files for temporary scripts.
- If uv is unavailable, report the issue rather than silently falling back.
