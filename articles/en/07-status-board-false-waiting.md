# My agent status board said 40 cards were waiting to be merged. 34 of them had no worktree left

The short version: **every row on a multi-agent status board has to trace back to a structured field or a piece of outside evidence, and when the field is empty the code has to go look, not quietly treat "unknown" as "no".** My board script has been wrong four times in four weeks. Each time looked different. Each time it was this. The fourth one is still open, and the numbers below are from a run I did this morning.

Setup: Claude Code writes task cards and reviews the results, Codex does the implementation. Every dispatched card leaves an evidence folder: a start record, an event stream, and Codex's receipt. A read-only script scans those folders and prints a table saying who each card is waiting on: Codex, the reviewer, or me. That table is how I find out who is waiting on whom.

## Miss 1: it saw none of the cards

On October 26 I ran a review. Since the previous one, the project sessions had dispatched 13 tasks on their own. The script's output listed zero of them.

Each session had written its evidence files slightly differently. Some had no start record, some used a different name for the event stream. The script knew one layout and treated everything else as absent.

The fix was to discover tasks by their event-stream files and to pin the evidence layout in the dispatch instructions. The lesson is plain: an empty board does not mean nothing is running.

## Miss 2: a merged card shown as "blocked"

On October 31 the board showed a card in an e-commerce tooling repo as blocked, apparently waiting for a second round.

In reality that card had been accepted and merged two days earlier. The "blocked" in the receipt came from a temp-directory problem inside the sandbox. The reviewer had run the full test suite outside the sandbox, and 2099 tests passed.

The script could not see that, for two reasons:

1. the review verdict was free text, with nothing to parse;
2. the task worktree had been removed after the merge, and the script looked for the card under the worktree path.

That day I rewrote how the board derives status, borrowing a rule from an open-source multi-agent research prototype: **a card has exactly one stage, decided by what it is waiting for; read structured fields only, match in order, stop at the first hit, and never infer from free text.** Receipts must carry `status` and `human_action`. Verdicts must carry `verdict` and `final`. A card that cannot be found gets its own label, "cannot derive", instead of being filed under "waiting for review".

## Miss 3: accepted a week ago, still "waiting for your answer"

On November 13 I noticed a card that had been accepted a week earlier and still showed as waiting for my answer.

The cause was match order. The receipt's `human_action` held a question, the script matched that first, and stopped. But the task session had already answered the question and written an accept verdict after it.

The fix: a verdict on the latest round outranks the receipt's `human_action`. Two days later I added one more: only a verdict on the latest round decides who is waiting, so an already-answered round-1 "blocked" cannot hold up round 2.

"First match wins" is a fine rule, but it puts all the correctness into the ordering. **Order the checks by which evidence is newer, not by which condition sounds more serious.**

## Miss 4: 40 cards "waiting to be merged", still there today

In a November 15 audit the board had about 265 rows. 39 of them said "accepted: waiting for commit/PR/merge and worktree return", and 32 of those were in one repository, a data platform. I spot-checked one. Its task branch had been merged long before.

This morning, November 19, I ran the script again without changing it:

- 313 task rows in total;
- 40 rows say "accepted, waiting to be merged", 34 of them in that same repo;
- for those 34 cards, not a single worktree directory exists on disk;
- 9 still have a task branch, and it is already merged into the integration branch; the other 25 have no branch left, and of the 7 I sampled, 6 have a matching merge commit on the integration branch;
- the number of cards that actually need a decision from me is 8.

So at least 34 rows in the "waiting for merge and worktree return" column do not match reality: every worktree is gone, and for 15 of them I can show the merge directly. Those rows were burying the 8 that needed me.

The cause is one line:

```python
returned = bool(worktree) and not os.path.isdir(worktree)
```

It reads: the start record has a worktree path, and that directory no longer exists, so the worktree has been returned. But 33 of these 34 cards have no worktree path in their start record at all. The empty field makes the whole expression false, and the script concludes "not returned yet".

**An empty field was read as "no".** It is the same mistake as miss 2. With evidence missing, the script picked an answer when it should have said "unknown" or looked somewhere else.

The fix for this one is written up in my November 15 improvement list and has not been merged. I am leaving that on the record here.

The same run also shows 16 rows of "running, no receipt", aged from 25 to 549 hours. The script flags anything past 6 hours, but a flag is all it does, and nobody has gone to close them. Whether the board is accurate and whether anyone acts on it are two separate problems.

## What you can copy

Here is a simplified version of the stage derivation, plus the fix for miss 4. The second function is the proposed fix and is not merged in my own script yet.

```python
def stage(n_runs, receipt, verdict, returned):
    """receipt: fields of the latest receipt; verdict: (round, outcome, is_final). One stage per card."""
    current = verdict if verdict and verdict[0] >= n_runs else None
    if current and current[1] == 'accept':
        return 'accepted and returned' if returned else 'waiting for merge'
    if current and current[1] == 'blocked':
        return 'waiting for a human answer'
    if current and current[1] == 'return':
        return 'waiting for a human to split' if current[2] else 'waiting for next round'
    if receipt is None:
        return 'running'
    if receipt.get('human_action') not in (None, 'none'):
        return 'waiting for a human answer'
    return 'waiting for review'


def is_returned(worktree_field, repo, task):
    # Field has a value: check whether the directory is still there.
    if worktree_field:
        return not os.path.isdir(worktree_field)
    # Field is empty: that is not a "no". Fall back to outside evidence.
    if os.path.isdir(os.path.join(repo, '.worktrees', task)):
        return False
    merged = subprocess.run(['git', '-C', repo, 'branch', '--merged', 'HEAD'],
                            capture_output=True, text=True).stdout
    return f'task/{task}' in merged.split()
```

Four things to watch when you build your own:

1. **Write down which field each stage reads.** Receipts and verdicts get fixed fields, and free text is for humans. When the script cannot read a field, it says "cannot derive" and lists the card separately.
2. **Order the matches by how fresh the evidence is.** The latest round's verdict goes first, an old receipt's question goes after it. Each time the order bites you, put that card's name in a comment next to the check, so the next person who reorders it sees why.
3. **Give empty values their own path.** For every boolean, ask what the expression evaluates to when the field is empty, and whether that result is right. Two of my four misses were this.
4. **Show only the rows that need action by default.** Of today's 313 rows, 238 are some flavor of "ended". They deserve one count, not 238 lines.

A quick way to test whether a board can be trusted: pick one column and reconcile it. Take each row in that column to the system it describes and check. I did that for "waiting for merge" today, and at least 34 of 40 rows did not hold up. With a mismatch rate like that, the column should not drive decisions until it is fixed.

This is part 7 of a series. Part 2 covered how a hook can wrongly blame the implementing agent. This is the other end: the table built for the human can be wrong about the human's queue, too.

## About the numbers

- 13 tasks missed: from my October 26, 2026 collaboration review.
- The blocked card that was already merged, the 2099 passing tests, and the two causes: from the October 31, 2026 review.
- "Accepted a week ago, still waiting for an answer" and the two ordering fixes: from comments in the board script's `derive_stage` function (dated November 13 and 15, 2026) and the matching commits.
- About 265 rows, 39 rows, 32 rows: from a November 15, 2026 audit, one run at 21:12 that day.
- 313 rows, 40, 34, 8 cards, 16 rows, 25 to 549 hours, 238 ended rows (151 + 63 + 24): from my own read-only run of the same script on the morning of November 19, 2026. No token counts were collected.
- 0 of 34 worktree directories present, 33 start records with an empty worktree field, 9 task branches merged into the integration branch, 25 branches deleted, 6 of 7 sampled with a merge commit: checked the same day with read-only git commands. "15 with a direct proof of merge" is 9 + 6. The sample is not exhaustive, so for the other 19 I only confirmed the worktree is gone. For the one sampled card without a merge commit I found only a test commit and drew no conclusion.
- The one-line snippet is verbatim from the current script. The fix is not merged, and `is_returned` as shown is a proposal that I have not run in my own environment.
