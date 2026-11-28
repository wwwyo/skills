### Opening a PR

Invoked at the end of every other playbook.

Work from a git worktree off trunk, and keep unrelated work out of it. Rebase into small, landable commits. Run **no-comments** over the diff before commit.

Title: `type(scope): subject`, naming a real symbol when one carries the change. Body: a one-minute briefing under 40 lines with these `##` headings in order, dropping empty ones: `## Why`, `## What changed`, `## Scope`, `## Tradeoffs` (only rejected alternatives a reviewer would otherwise ask about), `## Blast Radius`, `## Verification`.

Stack follow-ups with [gh-stack](../../gh-stack/SKILL.md). Open PRs ready, through the run's PR tool with `draft: false`. Without one, use `gh pr create` without `--draft`, or `origin pr create --status open` when Origin's CLI resolves the repository. Once the PR is open, run the **Babysit** playbook on it in `drive` mode, unless the user named another mode or said not to babysit. Under Autopilot-full or Autopilot-stack the PR's owner already babysits it per that playbook, so opening the PR starts no second babysit.
