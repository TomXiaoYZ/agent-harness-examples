# Claude Code plans, Codex builds: what 152 task cards taught me about governing two coding agents

I maintain several personal repositories: a data platform, a quant research repo with hard "never touch live trading" lines, a few e-commerce tools, and a content pipeline. Since late October I have split the work between two agents:

- **Claude Code defines and accepts.** It decides what to build, writes the task, and checks the result.
- **Codex implements.** It writes code and runs tests inside the spec it is given.

Between 2026-10-28 and 2026-11-14 this setup dispatched 152 task cards across 7 repositories. Four things moved it from "sometimes works" to "runs every day". Each one came out of a specific failure.

## 1. The handoff is a file in the repo, not a chat

Early on I told Codex what to do in conversation. Context scattered, and when it finished I could not say whether it had drifted.

Now the only handoff is a Markdown card at `docs/tasks/<date>-<topic>/README.md`, committed to the task branch. Codex reads that card, and I review against the same commit. Every card has these sections:

- Goal and user path
- Acceptance criteria (runnable commands or clickable pages)
- Boundaries
- An **authorization** section (network, writable dirs, model, effort)
- Tests that must fail first
- A rounds log

Two of these sections earned their place.

**Authorization is the only source of dispatch parameters.** The dispatcher reads permissions from the card and rejects command-line flags that would widen them. To widen scope, you write a new card. That way every escalation leaves a trace.

**I write the required tests first, and Codex must see them fail before implementing.** Behavior that no test covers is behavior Codex should not build.

## 2. Cards have a size cap and at most two rounds

One early card grew to 700 lines across 4 files. Codex followed it, but I could not review it properly. A handoff card failed twice for environmental reasons:

- **Round 1:** the worktree sat under the repo's `.codex/` directory, which the sandbox treats as read-only.
- **Round 2:** `git add` was refused, because a linked worktree's `.git/` metadata is also read-only to the sandbox.

Both times Codex stopped, reported `blocked` honestly, and touched nothing in the main checkout. The problem was the card and the environment, not the executor.

So I added two hard limits:

1. **Cards stay under 12 KB and contain no pasted source.** A card references paths and symbols, and Codex reads the worktree itself. A preflight script checks size, pasted code, missing sections, leftover placeholders, and line budgets over 300 without a stated reason.
2. **Two rounds maximum.** If round 2 is still returned, the card gets split or escalated to a human with evidence. No round 3.

Across the 152 cards:

- 116 finished in one round (76%).
- 29 took two rounds.
- 7 took three or four:
  - 1 predates the two-round rule.
  - 2 needed a browser or audio and video.
  - 4 broke the rule after it existed.

Those 4 cards show that "max two rounds" is ultimately enforced by a person. The summary script flags them, but it cannot stop someone from dispatching a third round.

The browser cases produced another rule: **threads started by my dispatcher cannot use the browser plugin's credentials.** So opening pages, taking screenshots and logging in stay on the Claude side, as acceptance steps.

## 3. The manager costs 41x the engineer, by token volume

This was the number I least expected. On the 141 cards where both sides could be measured:

- Claude Code's median token volume (input plus cache) was 25.5M.
- Codex's was 0.8M.
- The median ratio was 41x, and the worst single card was 363x.

Most of the Claude Code side is cache reads, which are much cheaper per token than fresh input, so 41x is a volume ratio, not a bill ratio. The direction is still clear: the expensive side is the one that plans and reviews and keeps growing its context.

The reason is that every request resends the whole conversation. I started with one long session per project, and one transcript reached 32 MB. Late in that session, each turn re-read the history of every card before it.

The fix was **one card, one task session**:

- The project session only plans and writes cards.
- Dispatch, monitoring and acceptance happen in a fresh session that returns a verdict of 30 lines or fewer.
- The verdict is written into the card's rounds log, so the project session can be cleared without losing state.
- Acceptance runs in two stages: first write a checklist from the card alone, then read the diff against it. That keeps the reviewer from being anchored by the executor's own summary.

The ratio is still high, and I am still working on it. The summary script now flags any card where the Claude Code side exceeds Codex by more than 5x.

## 4. The gate has bugs too

I added a turn-end hook on the Codex side that audits the diff for budget overruns, files outside the card's list, and defensive code the card does not justify. If the audit fails, it sends Codex back within the same turn, at most twice.

The hook then became a source of blocks itself. It mistook test function names for file paths, and it enforced a "tests ≤ 1.5x source" budget that no card had written down. Codex reported each case accurately in its receipt instead of deleting reasonable code to get past the audit.

The lesson: **a gate is code and has bugs.** In every review I now pull out "blocked by audit misfire" separately and fix the audit before blaming the executor.

## Take-aways

The templates, preflight script and two-stage verdict format are in a sanitized example repo: https://github.com/TomXiaoYZ/agent-harness-examples

1. Put the handoff in the repo and commit it to the branch.
2. Cap card size, allow at most two rounds, then split or escalate.
3. Measure cost per accepted change, not total usage. The expensive side is often the manager.

---

**Methodology.**
- **Scope:** local delegation evidence and Codex state DB, covering cards changed 2026-10-28 to 2026-11-14 (152 cards, 7 repos).
- **Rounds:** the number of executor receipts per card.
- **Claude Code tokens:** input plus cache, summed over all Claude Code transcripts in that repo during the task window. This may include unrelated work, so it skews high.
- **Codex tokens:** the thread's `tokens_used`.
