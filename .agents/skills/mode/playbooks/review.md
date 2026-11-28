### Review

**Judge one PR at its head. Find what breaks, for whom, and when. Taste is not a finding.**

Review triage (`../references/review-triage.md`) is the other direction: it handles comments a PR received. This playbook writes them.

1. **Pin the head and read in order.** Record the head SHA and judge only that content. Read the whole diff first, then the callers, the tests, and anything the diff reaches indirectly, then the repository's AGENTS.md, CLAUDE.md, and ADRs. A claim in the PR body is something to check, not evidence.
2. **Apply the lenses that fit the diff.** Read the leaf skill for each principle you apply, at `../../<name>/SKILL.md` from this file.
   - Behavior change and edge cases: **principle-fix-root-causes** (is a guard covering a state that should not exist?), **principle-boundary-discipline**, **principle-model-the-domain**.
   - Size and shape: **principle-laziness-protocol**, **principle-subtract-before-you-add**, **principle-minimize-reader-load**. A change bigger than its goal, or a new layer with one caller, is a finding.
   - Tests: **principle-test-behavior-not-implementation**, **principle-prove-it-works**. Check that the QA the PR claims actually exercises the changed behavior.
   - Types and reruns: **principle-type-system-discipline**, **principle-make-operations-idempotent**.
   - Risky surfaces (migrations, permissions, public APIs, CI workflows, shared config): run the **blast-radius** skill and follow the breakage past the diff.
   - Leftovers: debug output, dead code, commented-out code, stray files.
3. **Hold the repository rules as must.**
   - A plaintext secret, credential, or a committed `*.local.*` file.
   - A dependency added with a version range instead of an exact pin. A release younger than the seven-day cooldown is a should.
   - Injection, missing access control, or an unsafe default.
   - A hand-written implementation of something a standard library already does is a should.
4. **Verify as deep as the environment allows.** Reading is the default. With a checkout of the head, run the change the way a user would, as the Shipping playbook's verifier does: the **e2e** skill for UI, the command itself for a CLI, the tests for a library. Report `PASS` or `FAIL` with what you ran. Without a checkout, say the review was read-only.
5. **Write each finding with a severity and a consequence.** Start with `must`, `should`, or `nit`. Say what breaks, for whom, and when, and anchor it to `path:line`. `must` means it breaks behavior, data, or security for someone. Do not pad. "No findings" is a valid review.
6. **End with one verdict line.** Order the findings by weight, then close with either "safe to merge" or "fix first" and the must items. The review is the reply, so skip restating the goal and naming principles.

How to post (inline notes, `gh pr review`, or a bot command) and when to approve belong to the caller. Never push, edit code, request changes, or merge from this playbook.
