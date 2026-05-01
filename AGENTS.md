# Developer Profile & CLI Context
I am a Backend Engineer using a macOS environment with Zsh. My terminal is highly customized with specific modern Rust-based CLI tools.

## Core Tooling & Aliases
When suggesting terminal commands, **ALWAYS** use these aliases defined in my `.zshrc`:
- Use `ls` or `ll` (points to `eza`) for listing files.
- Use `cat` (points to `bat`) for reading file content.
- Use `find` (points to `fd`) for searching files.
- Use `grep` (points to `rg`) for searching text.
- Use `lg` for Git operations (prefers `lazygit` interface).
- Use `z` (points to `zoxide`) for directory navigation.

## Command Generation Rules
1. **No Redundancy**: Do not suggest `ls -la` if `ll` is available.
2. **Modern Tooling**: Prefer `fd` over `find` and `rg` over `grep` for performance.
3. **Safety First**: If a command involves `ssh-add`, remind me that I have a custom function `set-ssh-key <key_name>` to handle multi-account setups.
4. **Path Awareness**: Be aware that my workspace is primarily located under `/Volumes/workspace/`.

## Path & Workspace Context
- **Primary Workspace**: `/Volumes/workspace/`
- **Session Exports**: All session summaries or documented discussions should be suggested to be saved in `/Volumes/workspace/copilot/docs/sessions/`.
- **System Specs**: My technical specifications and requirements are located in `/Volumes/workspace/copilot/spec/`.

## Output Behavior
- **Automatic Path Suggestions**: When I ask to "save this session" or "document this", always provide the full CLI command using `cat` or `tee` to redirect the output to the `/Volumes/workspace/copilot/docs/sessions/` directory.
- **Spec Awareness**: When I ask to "refer to specs" or "check requirements", remind me to provide context from the `/Volumes/workspace/copilot/spec/` folder if you don't have it in your current context.
- **Naming Convention**: Use `YYYY-MM-DD-topic.md` for session files unless otherwise specified.

---

## Code Quality & Maintainability Rules

### Core Principles
- Follow SOLID, but **do not apply blindly**. Prefer pragmatism over purity.
- Avoid duplication (DRY), but **do not abstract prematurely**.
- Keep code simple (KISS).
- Avoid over-engineering (YAGNI).
- Complex or non-obvious logic must include PHPDoc or inline comments.

---

### Anti Over-Engineering Rules (Critical)

To prevent unnecessary abstraction, follow these concrete thresholds:

#### Function Extraction Rules
Only extract a function if **ANY** of the following is true:

- Logic is **≥ 10 lines**
- Logic is reused **≥ 2 times**
- Logic has a **clear domain meaning** (not just mechanical steps)
- Logic contains **branching complexity** (if/else, loops, edge cases)
- Function name improves readability more than inline code

Otherwise:
- Keep logic inline
- DO NOT create trivial wrapper functions

❌ Bad:

    function formatName($name) {
        return trim($name);
    }

✅ Good:

    $name = trim($name);

---

#### Abstraction (Service / Class) Rules
Only introduce a new class/service if:

- It encapsulates a **business concept**, not just code grouping
- It will be reused across **multiple contexts**
- It reduces cognitive load in the caller
- It isolates **side effects or external dependencies**

Avoid:
- Single-use service classes
- “Manager”, “Helper”, “Util” with no clear domain meaning

---

#### DRY vs Readability Tradeoff
- Prefer **duplication over wrong abstraction**
- Only DRY when duplication is:
  - stable (unlikely to diverge)
  - clearly identical in intent

Rule:
> If merging code introduces condition flags (`$type`, `$mode`), reconsider abstraction.

---

#### SOLID Application Boundary
Apply SOLID when:

- Code is part of a **shared module / library**
- Logic is **expected to evolve**
- There are **multiple implementations**

Do NOT force SOLID when:

- Logic is simple and stable
- Only one implementation exists
- It increases indirection without real benefit

---

#### Comments & Documentation
Add comments when:

- Business rules are not obvious
- There are hidden constraints or edge cases
- Logic involves domain-specific decisions

Do NOT comment:
- trivial assignments
- self-explanatory code

---

#### Code Review Heuristics (Quick Checks)

Before introducing abstraction, ask:

1. Will this be reused?
2. Does this reduce or increase cognitive load?
3. Would inline code be clearer?
4. Am I designing for a future that may not happen?

If unsure → **do not abstract**

---

### Philosophy

> Prefer explicit, slightly duplicated, readable code over clever abstraction.

> The goal is maintainability, not architectural purity.

---

---

### Language & Communication Rules

- Responses must be in **Traditional Chinese**, except for:
  - Translation tasks
  - Technical terms (e.g., programming languages, frameworks, CLI commands, error messages)

- Technical terms may remain in English, but explanations must be in Chinese for clarity and precision.
