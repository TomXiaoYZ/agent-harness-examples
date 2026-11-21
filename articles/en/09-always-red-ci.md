# My CI was red for 6 days and 19 PRs got merged anyway. The same 45 tests failed every time, so red became the background color

Short version: **a CI that is always red is the same as no CI.** The repository that holds my agent workflow went red on its very first CI run and stayed red for 6 days and 24 runs. 19 PRs were merged in that window. Every run had the same 45 failures, and 40 of them had nothing to do with code: the repo had lost its executable bits and two symlinks when it was imported. The fix was one commit. Since then, 15 of 16 runs have passed.

Some background. This repo holds my hooks, dispatch scripts, skills, and global rules. Every Claude Code and Codex session loads its rules from here, so when it breaks, every project feels it. The guards, status board, and reminder hook from earlier parts of this series all live in it.

## What happened

On November 14 the repo ran CI on GitHub for the first time. The workflow, called Verify, runs pytest and two check scripts on every PR.

- First run: 45 failed, 91 passed.
- Last red run, November 20: 45 failed, 127 passed.

Over six days, 36 new tests were added, and all of them passed. The failure count never moved. There were 24 runs across 20 branches, every one a failure, and 19 PRs merged, including the audit false-positive fix from part 2 and the long-session reminder from part 8.

40 lines in the failure log were the same error: `PermissionError: [Errno 13] Permission denied`. The tests execute the scripts directly, and the scripts weren't executable.

## Why nobody fixed it for six days

It wasn't that nobody saw it. An audit doc I wrote on the evening of November 15 had the cause, and marked it "can start right away":

- every script with a `#!` line was stored in git as `100644`, not executable;
- two files that should have been symlinks had been flattened into regular files whose only content was a relative path, so running them gave `Exec format error`;
- in a scratch copy, adding the executable bits took the failures from 45 to 20, restoring the two links took it to 7, and 2 of those came from the scratch copy having no commit history. 5 were real;
- those 5 were assertions inherited from an upstream template. They checked for clauses and files from someone else's environment, which were never going to exist in mine.

After that doc, CI went red 19 more times and 15 more PRs were merged before anyone fixed it.

My read: **when the red is identical every time, it stops being a signal.** Every PR was red, so red said nothing, and nobody at merge time compared 45 against 46. If a new test had broken, it would have drowned in the old red.

One more thing. It's a private repo on a free plan, which means no branch protection. "Don't merge unless checks pass" can't be enforced by the platform. I called the branch protection API today and got a 403. Whether a red PR gets merged is entirely up to whoever merges it.

## The fix: one commit

The November 20 fix did three things:

1. **Restored the executable bits.** Git records 34 files changing from `100644` to `100755`.
2. **Turned the two fake links back into real symlinks** (mode `120000` in git).
3. **Replaced the inherited assertions with my own current constraints** instead of just deleting them:
   - the global rules file must keep all six "boundaries that must stay" (for example: never push to main on your own, credentials live only in the system keychain);
   - every local link in the README must resolve;
   - the global rules file stays under 10 KB.

Of the 16 runs since, 15 passed and 1 was auto-cancelled because a newer push landed on the same branch. The latest run: 190 passed, 0 failed.

## Where the rules live

- **The Verify workflow** runs pytest, a skill bundle check, and a repo context check on every PR. The tests execute scripts directly, so if the executable bits get lost again, CI goes red immediately. And because CI is green now, red means something new broke.
- **`tests/test_agent_context.py`** fails if any of the six boundaries goes missing. Those are what I'm most afraid of losing in a "let's trim the rules" pass.
- **`tests/test_readme_contract.py`** fails if a local README link stops resolving.

## Two things still open

- **Merging is still gated by people.** The platform can't require checks, and I haven't added a "stop if checks failed" step to my merge command yet. What changed is that CI is green, so red finally carries information.
- **The 10 KB cap was raised to fit.** The upstream cap was 4,000 bytes. My rules file was 7,314 bytes on November 15 and is 9,407 today. The fix set the cap to 10 KB with a comment that says "to add a rule, delete one first." The file hasn't been slimmed down. The ceiling just sits a little above where it is now.

## What you can take from this

1. **After importing or migrating a repo, check file modes first.** This reads git objects only and doesn't touch your working tree. On the commit before my fix it reports exactly 34 missing executable bits and 2 flattened links. On today's main it prints nothing.

```sh
ref=${1:-HEAD}
git ls-tree -r "$ref" | while read -r mode type sha path; do
  [ "$mode" = 100644 ] || continue
  head=$(git cat-file -p "$sha" | head -c 64)
  case "$head" in
    '#!'*) echo "not executable: $path" ;;
    ../*) [ "$(git cat-file -p "$sha" | wc -l)" -eq 0 ] && echo "flattened symlink?: $path" ;;
  esac
done
```

2. **If CI is red on its first run, make it green before doing anything else.** An always-red CI isn't a CI with a problem. It's no CI. The test is simple: if several runs in a row fail with exactly the same count, nobody is reading it.
3. **Replace inherited assertions with your own constraints. Don't just delete them.** Deleting turns CI green, but then it guards nothing. Ask what you'd hate most to lose, write that as the new assertion, and put the reason in a comment.
4. **If the platform can't require checks, put the check in your merge step.** I haven't done this one yet. It's on the list.

This is part 9 of the series. Earlier parts kept saying "put the rule where the agent can't route around it." This one is the flip side. The check was in a place nobody could skip, but it was always red, so everyone learned to ignore it.

## About the numbers

- 24 failures, 20 branches, 16 runs after the fix (15 passed, 1 cancelled): read on 2026-11-21 with `gh run list` across all 40 runs of the Verify workflow. First run 2026-11-14, fix run 2026-11-20 (UTC).
- 19 merged PRs: `gh pr list --state merged` the same day, counting merges before the fix commit. The 15 PRs and 19 failures after the audit doc use the same lists and the doc's commit time (2026-11-15 21:21 US Eastern).
- 45 failed / 91 passed, 45 failed / 127 passed, 40 PermissionError lines, 190 passed: read from the logs of the first run, the last red run, and the latest run.
- The 45 → 20 → 7 → 5 breakdown: from the 2026-11-15 repo audit doc, done as an experiment in a scratch copy.
- 34 mode changes, 2 links, and the new assertions: from the 2026-11-20 fix commit itself. Its message says "32", but git records 34 mode changes.
- 7,314 and 9,407 bytes: the first from the audit doc, the second from `wc -c` on current main on 2026-11-21.
- Branch protection 403: the GitHub branch protection API response on 2026-11-21.
- The check script: run on 2026-11-21 against the pre-fix commit and current main, with the results described above.
