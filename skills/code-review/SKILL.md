# Code Review

## Protect Scope First

- Confirm the PR scope before reviewing implementation details.
- Ask for explanation or separation for any change outside the stated scope.
- Do not mix changes with different purposes in one PR.
- For large PRs, prefer asking for decomposition over trying to review everything.
- If the PR touches config, schema, deployment, or external dependencies, require clear notes in the PR description.

## Ask For Design Rationale

- Do not only ask “does it work”; ask “why is it designed this way?”
- Require trade-off reasoning, not just “cleaner” or “more readable.”
- If the reason changes but the conclusion stays the same, watch for defending.
- A technically correct point is not necessarily relevant to the current decision.
- When external sources or AI-generated arguments are used, ask which comparison they actually support.

## Clarify The Alternatives

- Do not let the discussion become a false binary.
- List all reasonable options explicitly.
- Ask the author to explain why option B is better than option C.
- A reason against option A is not automatically a reason for option B.
- End with a concrete change, not an abstract debate.

## Check Performance And Cost

- For batch logic, check traversal count, allocation, query count, and I/O.
- Higher-level APIs may be readable, but watch for hidden intermediate structures and costs.
- Language-specific behavior can affect performance; do not rely only on rough Big-O claims.
- When performance matters, direct and explicit code with fewer allocations is often better.
- Do not sacrifice clear cost control for cosmetic conciseness.

## Check Tests

- Tests should verify required behavior, not just lock in the current implementation.
- If a new test reveals a separate issue, confirm whether it belongs in this PR.
- Test names and comments should describe scenarios, not hide unexplained product or production issues.
- Tests do not replace risk notes in the PR description.
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
- When the author becomes defensive, bring the discussion back to the original issue.
- Do not follow the author into a different battlefield.
- If the reply does not answer the question, ask: “Which question is this answering?”
- Stay professional, but mark true blockers as `Must`.

## Detect Defending

- The reason keeps changing, but the conclusion does not.
- The reply answers an adjacent issue, not the original one.
- A correct technical point is used to support the wrong comparison.
- Words like “readable,” “cleaner,” or “personal preference” are used to avoid a concrete trade-off.
- The author does not acknowledge valid reviewer points.
- When asked about scope, the author talks about local implementation details instead.

## Escalate When Needed

- Single issues can be fixed locally.
- Repeated issue patterns should be treated as delivery problems.
- If the reviewer keeps supplying requirements, architecture, or validation criteria, ownership may not be with the author.
- Code review is collaboration, not a substitute for the author’s thinking.
- A mergeable PR must be understandable, verifiable, and maintainable by others.