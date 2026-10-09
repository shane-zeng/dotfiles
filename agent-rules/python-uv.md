# Python Tooling — uv

Use `uv` as the preferred tool for Python execution, environment management, and dependency management.

## General Rules

- Prefer `uv` over `pip`, `venv`, `virtualenv`, and other Python environment management tools.
- Prefer existing CLI tools over writing Python scripts when they can accomplish the task efficiently.
- Do not install Python packages globally or modify the system Python environment.
- Preserve the existing Python tooling and dependency management conventions of each project.

## Script Execution

- Use `uv run --no-project <script.py>` for temporary Python scripts.
- Use `uv run --no-project --with <package> <script.py>` when temporary dependencies are required.
- Use `uv run <script.py>` for scripts belonging to an existing uv project.
- Use `uvx <tool>` for standalone Python CLI tools.
- Prefer inline script dependencies (PEP 723) for reusable standalone scripts.

## Dependency Management

- Use `uv add <package>` to add dependencies to uv projects.
- Use `uv remove <package>` to remove dependencies from uv projects.
- Use `uv sync` to synchronize dependencies in uv projects.
- Do not use bare `pip install`.
- Do not modify `pyproject.toml`, `uv.lock`, or other dependency files for temporary tasks.
- Do not migrate existing projects to uv unless explicitly requested.

## Environment Safety

- Do not modify or delete existing virtual environments without authorization.
- Do not automatically install uv if it is unavailable.
- Do not silently fall back to pip or another package manager when uv fails.
- Report dependency resolution, installation, or environment errors instead of bypassing them.
- Avoid unnecessary package installations and network downloads.

## Verification

- Verify that required dependencies are available before executing scripts.
- Report failures accurately; do not claim successful execution without verification.
- Clean up temporary files created solely for the task without affecting unrelated files.
