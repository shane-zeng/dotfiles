# Code Review

## Protect Scope First

- Confirm the PR scope before reviewing implementation details.
- Ask for explanation or separation for any change outside the stated scope.
- Do not mix changes with different purposes in one PR.
- For large PRs, prefer asking for decomposition over trying to review everything.
- If the PR touches config, schema, deployment, test infrastructure, or external dependencies, require clear notes in the PR description.
- A valid problem does not automatically justify expanding the current PR to solve it.

## Ask For Design Rationale

- Do not only ask “does it work”; ask “why is it designed this way?”
- Require trade-off reasoning, not just “cleaner”, “more readable”, or “best practice”.
- A technically correct point is not necessarily relevant to the current decision.
- When external sources or AI-generated arguments are used, ask which concrete project decision they support.
- Distinguish between solving the actual failure mode and adding a broader preventive mechanism.

## Clarify The Alternatives

- Do not let the discussion become a false binary.
- List reasonable alternatives when the decision materially affects architecture or maintenance cost.
- A reason against option A is not automatically a reason for option B.
- Prefer the smallest mechanism that adequately addresses the demonstrated risk.
- Do not introduce permanent infrastructure complexity for a rare failure without sufficient justification.

## Check Performance And Cost

- For batch logic, check traversal count, allocation, query count, and I/O.
- Higher-level APIs may be readable, but watch for hidden intermediate structures and costs.
- Language-specific behavior can affect performance; do not rely only on rough Big-O claims.
- When performance matters, direct and explicit code with fewer allocations is often better.
- Consider long-term maintenance cost, not only implementation cost.

## Check Tests

- Tests should verify required behavior, not just lock in the current implementation.
- If a new test reveals a separate issue, confirm whether it belongs in this PR.
- Tests do not need to reproduce every runtime environment detail.
- Distinguish application behavior tests from environment/configuration verification.
- If changing global test infrastructure, require evidence that the protected failure mode justifies the permanent complexity.
- Clarify which behaviors are intentional, temporary debt, or meant to be fixed.

## Check Comments

- Comments should explain non-obvious business rules or technical constraints.
- Do not accept “legacy does this” or “it was already like this” as the only rationale.
- If comments work harder than the code, question whether the design is too complex.
- If comments mention risks, constraints, or exceptional cases, the PR description should mention them too.
- Do not let comments disguise unresolved design problems.

## Communicate Clearly

- State the fact first, then the requested action.
- Prefer concrete requested changes over vague open-ended questions.
- A clear blocking decision is not the same as refusing discussion.
- Do not over-explain by default; provide enough reasoning for the author to understand the issue.
- Do not feel required to provide a complete replacement design when rejecting an approach.
- Stay professional, but mark true blockers as `Must`.

## Detect Defending

- The reason keeps changing, but the conclusion does not.
- The reply answers an adjacent issue, not the original one.
- A correct technical point is used to support the wrong comparison.
- Generic terms such as “readable”, “cleaner”, “best practice”, or “personal preference” replace concrete trade-offs.
- The author does not acknowledge valid reviewer points.
- When asked about scope, the author talks about local implementation details instead.

## Escalate When Needed

- Single issues can usually be resolved locally.
- Repeated issue patterns should be treated as delivery or collaboration problems.
- If the reviewer keeps supplying requirements, architecture, or validation criteria, ownership may not be with the author.
- Code review is collaboration, not a substitute for the author’s thinking.
- If the discussion becomes primarily about whether the review itself is fair, respectful, or authoritative, separate that from the technical decision.
- A mergeable PR must be understandable, verifiable, and maintainable by others.
