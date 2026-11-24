# Codex Global Instructions

- Resolve the installed entry symlink to find this repository's source
  directory. Use `$CODEX_HOME/AGENTS.md` when `CODEX_HOME` is set; otherwise
  use `~/.codex/AGENTS.md`. For example:

  ```zsh
  instructions_entry="${CODEX_HOME:-$HOME/.codex}/AGENTS.md"
  instructions_repo="$(dirname "$(readlink "$instructions_entry")")"
  ```

- At the start of each task, read
  `"$instructions_repo/global-AGENTS.md"` and follow it as the shared personal
  guidance.
- Before drafting or creating a commit message, read
  `"$instructions_repo/global-git-commit-instructions.md"` and follow its
  format and Codex attribution rules.
- Commit formatting guidance does not authorize creating a commit. Create one
  only when explicitly requested.

## Codex Subagent Delegation

- Delegate proactively when independent workstreams can produce separately verifiable results and parallel execution is likely to save enough time to justify coordination and verification. Also delegate when isolating read-heavy work would materially reduce the main agent's context load.
- Keep quick, single-scope, sequential, or tightly coupled work in the main agent.
- Start with no more than three concurrent subagents. Give each one a bounded task, relevant context, clear read/write boundaries, and a concise expected deliverable.
- Prefer parallel read-only exploration and review. Delegate implementation only when ownership can be divided by file or module; do not assign multiple agents to edit the same files.
- Ask agents for evidence such as file paths, symbols, line numbers, and the repositories, branches, versions, or time windows examined. Require confirmed facts, inferences, and unresolved questions to be distinguished. Keep raw search output and logs in the subagent context unless needed.
- The primary agent remains responsible for planning, conflict resolution, integration, and final verification. Check delegated findings before relying on them. For cross-service investigations, split evidence collection by service or source, then reconcile the execution path and remaining uncertainty in the primary agent.
- Spawn agents only when parallelism or context isolation offers a real benefit; each agent adds model and tool usage.

### Model and Reasoning Selection

- Choose whether to delegate separately from model and reasoning effort. A large search scope can be split into bounded fact-gathering tasks, while causal conclusions, compatibility decisions, and risk assessment may need a stronger model.
- Use the installed `code_mapper` and `docs_researcher` presets with `gpt-6-luna` and `high` effort for bounded code tracing and version-matched official documentation research. Keep simple lookups in the primary agent.
- Use Sol with `medium` effort for routine implementation, and the installed `reviewer` preset with Sol and `high` effort for focused PR review. Do not rely on inheriting the primary model to provide this review baseline.
- Use Sol with `high` effort for cross-service reasoning or framework compatibility analysis. Consider an available Astra model with `high` effort for security-sensitive changes, retry and data-consistency semantics, or root-cause investigations with competing explanations. These are starting points to validate, not guarantees of quality.
- Custom agent files pin their configured model and reasoning effort; explicit spawn values do not override those fields. When a task needs a different configuration, use an available built-in agent such as `default` or `explorer` with explicit model and effort values. Include the relevant custom role's read-only boundary, evidence requirements, and expected report in that assignment. Bounded evidence collection may still use the Luna presets.
- Select models and effort levels supported by the current client and tools. If the preferred configuration is unavailable, use a supported alternative and report any material limitation; do not claim a model change that was not applied.
- Start with the task's baseline effort. Reserve `xhigh` or higher supported effort for especially demanding reasoning, conflicting evidence, or gaps found during verification; do not copy the primary agent's maximum effort into every subtask.
- Evaluate representative tasks with the same inputs and change only the model or effort at a time. Compare missed issues, false positives, elapsed time, token usage when available, and follow-up work needed by the primary agent before changing the defaults.
