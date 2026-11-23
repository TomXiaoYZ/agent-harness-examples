# I capped my agent rules at 10 KB. In under three days 16 bytes were left, and cleanup found 4 rules contradicting each other

Short version: **"to add a rule, delete one first" written in a comment does nothing.** On November 20 I added a test to my agents' global rules file: it must stay under 10,000 bytes. It was 9,111 bytes at the time, and the comment said "to add a rule, delete one first." In under three days, 4 commits each added a little and none deleted anything. The file reached 9,984 bytes, 16 bytes under the cap, and the test stayed green the whole time. On the evening of November 22 I cleaned it up: down to 7,186 bytes, with the cap tightened to 8,000. The cleanup also found 4 places where rules contradicted each other, and one of them was added by my own fix the day before.

Some background. This rules file is the "global conventions" file that every Claude Code and Codex session loads in full at the start. I mentioned it in part 9, when I fixed my always-red CI: the upstream template capped it at 4,000 bytes, I raised the cap to 10 KB, and I admitted the file hadn't been slimmed down, the ceiling just sat a little above where it was. This is what happened to that ceiling.

## What happened

After the cap went in, 4 commits touched the file:

| Time (US Eastern) | Change | Size | Left |
|---|---|---|---|
| 11-20 22:25 | Add a new subagent type | 9,120 | 880 |
| 11-21 03:26 | Frontend changes must go through a review skill | 9,407 | 593 |
| 11-22 00:28 | Parent session must not wait idle (the fix from part 10) | 9,850 | 150 |
| 11-22 21:18 | Add another agent; all agents share project memory | 9,984 | 16 |

Each one made sense on its own. Each was the takeaway from a real problem that day. But across the 4 commits the file gained 5 lines and lost 3, and the 3 removed lines were old sentences being rewritten, not space being freed up. Not once did anyone actually delete before adding.

The real problem only showed up during the cleanup on the night of November 22. I asked an agent to review the whole rule set for conflicts, duplication, and stale descriptions. It came back with:

- **4 conflicts.** The clearest: the global rules said, roughly, "work that should be visible in the terminal goes through the dispatch script, don't substitute a built-in subagent." Step 4 of the dispatch skill said "open a new subagent for each card's review." The first sentence came from my part 10 fix. I was thinking about "don't let the parent sit idle" and never checked what the skill said. The other three: one place said "after delivering, move on to the next item on your own," another said "only start other sessions when I explicitly ask"; the default model didn't say who it applied to; and the list of dispatch targets named an agent that had no template.
- **3 docs that didn't match reality.** The README said the budget was 4,000 bytes, but the test said 10,000. It said there were 17 default skills, and the list had 24. It said a scheduled check was "installed," and it wasn't.
- **13 "(name, date)" annotations.** Every rule carried who decided it and when, some with a short postmortem story. None of that helps an agent act, and every session read it anyway.

## Why it happened

Three layers.

**Layer one: the test checks the ceiling, not the trend.** It asserted "≤ 10,000." 9,984 is green. Nothing checked the "delete first" comment.

**Layer two: new rules get tacked onto the closest existing bullet.** All 4 commits appended a sentence to an existing item. The line count barely moved; the lines just got longer. That's the easiest way to write it and the hardest to notice: the diff shows one changed line.

**Layer three: the same thing lived in two places.** Card size limits, round counts, and environment cleanup were written once in the global rules and again in the dispatch skill. Change one and the other goes stale. When you add a rule, you only look at the file you're editing. That's where the conflicts came from: nobody wrote anything wrong. Each place was right on its own and wrong next to the other.

## The fix: one commit

The cleanup commit at 21:35 on November 22 did four things:

1. **Rewrote the file into 5 sections** (roles and communication; projects, sessions, and dispatch; facts and workspace; quality; boundaries that must stay). 9,984 bytes went to 7,186, or 4,962 characters to 3,566.
2. **Tightened the cap from 10,000 to 8,000 bytes.** The comment now says "to add a rule, delete an old one first."
3. **Wrote one resolution for each of the 4 conflicts.** For the subagent one: built-in subagents are only for Claude Code task sessions that exist to isolate context; everything else goes through the dispatch script. For moving on: the next authorized step toward the same goal is fine; opening a new session or dispatching a new card needs my request or the repo's continuation mode.
4. **Kept each detail in one place.** Card, round, and cleanup details live only in the dispatch skill; the global rules just say "see that skill." All 13 name-and-date annotations are gone, since git history already has them. The 3 stale descriptions now match reality.

## Where the rules live

- **The budget test on the rules file**: `≤ 8,000` bytes, run in CI on every PR. Next to it, another test guards the "boundaries that must stay" and fails if one goes missing (covered in part 9).
- **The global rules only route.** Procedures live in their skills; the global file only says when to use which skill. Each number appears once.

## Still open

- **74 minutes after the cleanup, it grew 338 bytes.** The cleanup merged at 21:35. Commits at 22:43 and 22:49 added 287 and 51 bytes. It's 7,524 now, 476 under the new cap. At the earlier rate (873 bytes in under three days), I estimate it hits the cap again in about two days. A cap stops "over." It doesn't stop "full."
- **Conflicts are still found by hand.** Bytes can be tested. Two rules that say opposite things can't, at least not by anything I have. This time I found them because I asked for a review. There's nothing that tells me when the next one appears.

## What you can take from this

1. **Give every always-loaded rules file a byte budget test, and set it below the current size.** Set it a little above and you've handed out room to grow. It will get used.
2. **Look at headroom per commit, not just the latest.** This reads git history only and prints size, delta, and headroom after each commit that touched the file. Run it with `sh`. On my repo it prints exactly the 4 rows in the table above, plus the 3 after the cleanup.

```sh
#!/bin/sh
# usage: budget_log.sh <rules-file> <byte-budget> [range]; size, delta, and headroom after each commit that touched the file
file=$1; budget=$2; range=${3:-HEAD}
git log --reverse --format='%h %ad' --date=format:'%m-%d %H:%M' "$range" -- "$file" |
while read -r sha day time; do
  size=$(git cat-file -p "$sha:$file" 2>/dev/null | wc -c | tr -d ' ')
  [ -n "$prev" ] && delta=$((size - prev)) || delta=0
  printf '%s %s %s %6d B  %+5d  left %5d\n' "$day" "$time" "$sha" "$size" "$delta" $((budget - size))
  prev=$size
done
```

3. **When you add a rule, search for its opposite first.** Take the key nouns in the new rule ("subagent," "continue," "session") and search the rules file and every skill for them. Look for a sentence that says the reverse. Searching "subagent" would have shown me step 4 of the skill.
4. **Write each thing once and link to it everywhere else.** A detail written twice will eventually be stale in one of those places.

This is part 11 of the series. Earlier parts kept saying "put the rule where the agent can't route around it." This one is about the cost: every rule the agent can't route around is one every session has to read, and the more of them there are, the more likely two of them disagree. Rules need a budget too, and it should be tighter than what you have now.

## About the numbers

- The 10,000-byte cap, 9,111 bytes, and the comment: the test file and rules file in the 2026-11-20 fix commit (read with `git cat-file`, counted in bytes).
- Times, sizes, and headroom for the 4 commits (9,120 / 9,407 / 9,850 / 9,984, 16 left): the script above, run read-only on that repo on 2026-11-23; times in US Eastern. "5 lines added, 3 removed" is the `git log --numstat` total for the rules file across those 4 commits.
- 4 conflicts, 3 stale descriptions, 13 annotations: from the review the agent handed back in the 2026-11-22 cleanup session, checked item by item against the cleanup commit's diff and the pre-cleanup file. The 13 counts parenthetical "(name, date)" notes in the pre-cleanup file.
- 9,984 → 7,186 bytes, 4,962 → 3,566 characters, cap 10,000 → 8,000, 5 sections: the files before and after the cleanup commit (`wc -c`, `wc -m`) and the test file diff.
- 74 minutes, +287, +51, 7,524, 476 left: file sizes after the two commits (22:43, 22:49) following the cleanup (21:35), read with the same script.
- "Hits the cap again in about two days": extrapolated from 873 bytes in under three days. It's an estimate.
- The budget test passes now: a local run of that test file on that repo's main on 2026-11-23, 2 tests passed.
