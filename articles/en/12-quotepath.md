# git turned my Chinese file names into octal. The backfill script said "0 remaining" and had skipped 34 docs

Short version: **when a script says "0 remaining," that only covers what it could see.** Early on November 17, I had an agent backfill metadata into docs across 9 of my personal repos. In every repo the backfill script reported "0 still non-compliant." A second check that lists files a different way found 34 non-compliant docs in 4 of those repos, and every one had Chinese characters in its file name. By default git escapes non-ASCII paths as octal and wraps them in double quotes. The script filtered on names ending in `.md`, so those files just vanished, with no error. The same bug made my pre-commit docs check blind to Chinese file names. The fix was one commit: 3 files, +13 / −2.

Some background. All my repos follow one standard for `docs/`: every doc starts with a metadata block (type, author, date, sources, and so on). Two scripts go with it. A checker, which with `--changed` only looks at docs touched on the current branch; my agents' global rules say to run it whenever they edit docs. And a backfill script that adds the metadata to old docs in bulk. Both ask git for the file list.

## What happened

The order that night (US Eastern):

- 02:10: the checker and the standard were merged.
- 02:27: the backfill script ran in all 9 repos. Each printed "filled N docs, 0 still non-compliant." 1,019 docs in total, each body diffed against the original and unchanged.
- In the same pass, the agent ran the checker in full mode on each repo. Four didn't add up: 1, 23, 9, and 1 docs "missing metadata," 34 in total. Every file name it listed contained Chinese.
- Ten seconds later the agent called it: git quotes Chinese file names by default, the backfill script skipped them, and the checker's `--changed` mode had the same bug.
- 02:28: the fix was merged. After a rerun those 34 docs were filled, and full checks showed 0 non-compliant in all 9 repos.

Under 2 minutes from seeing 34 to merging the fix. I got lucky: the two modes list files differently, so their numbers disagreed, and that's the only reason anyone noticed.

## Why it happened

git has a setting called `core.quotepath`, on by default. With it on, any path containing non-ASCII bytes comes out of `git ls-files`, `git diff --name-only`, and `git status --porcelain` looking like this:

```text
docs/plain.md
"docs/\344\270\255\346\226\207\346\226\207\346\241\243.md"
```

The second line is a doc named with four Chinese characters. Each byte becomes a backslash plus three octal digits, and the whole line is wrapped in double quotes.

Three layers stacked up:

**Layer one: the filter saw a different file.** The backfill script ran `git ls-files docs` and kept lines where `f.endswith(".md")`. The escaped line ends in a quote, so it was dropped. The checker's `--changed` mode did the same thing on top of `git diff --name-only`. No error, no warning. The line might as well not exist.

**Layer two: "remaining" was counted inside the script's own view.** "0 still non-compliant" was true for the files the script had listed. The mistake was the reader (the agent included) taking it to mean "0 in this repo."

**Layer three: the gate had a hole and stayed green.** `--changed` is the check agents run before committing docs. A branch that added a Chinese-named doc with no metadata would get a clean 0, because the file was never listed. The checker was only live for 18 minutes before the fix, so this didn't actually let anything through. But without that full-mode cross-check, the hole would have stayed open, and green, indefinitely.

Why didn't full mode get bitten? It doesn't ask git. It walks the filesystem with Python's `rglob("*.md")`. Two ways of listing files produced two different counts, and that's what exposed it.

## The fix: one commit

1. **One extra argument in each script's git wrapper**: `["git", "-C", repo, "-c", "core.quotepath=off", *args]`. Every git call goes through that wrapper, so one change covers all of them.
2. **One new test**: create a git repo in a temp dir, commit a compliant doc as the baseline, then add `docs/kb/` plus a Chinese-named `.md` containing only a heading and no metadata, and assert that `--changed` returns 1. Before the fix it returned 0.

All 9 tests in that file pass after the fix.

Why not just run `git config --global core.quotepath off`? Because global config lives on my machine only. CI, a fresh container, Codex's sandbox all get the default. As it turns out I hadn't set it locally either (I checked: no such key in my global config). Put the flag in the script and it behaves the same wherever it runs.

## Where the rules live

- **The git wrapper in both scripts**: path output is never escaped.
- **The test `test_changed_handles_non_ascii_names`**: if someone removes the flag, CI goes red.

## Still open

- **Another script in the same repo has the same bug.** Before writing this, I went through every script in that repo that calls `ls-files`, `--name-only`, or `--porcelain`. Two still don't pass the flag. One only checks whether `status --porcelain` output is empty, so it's unaffected. The other is the snapshot step that runs when a task worktree is handed back: it takes untracked files from `status --porcelain`, tars them up, then force-removes the worktree. I reproduced it in a scratch repo: an untracked file with a Chinese name is judged "doesn't exist," left out of the tarball, and then deleted along with the worktree. I don't know whether that has ever actually lost a file. It isn't fixed yet.
- **I turned off quoting instead of switching to `-z`.** `-z` separates entries with NUL and handles spaces, newlines, and quotes too. It's the more thorough fix. This time I only fixed the case that had already bitten.

## What you can take from this

1. **If a script parses paths from git output, turn off quoting in the wrapper.** Pass `-c core.quotepath=off` on every call, or use `-z`. Don't rely on whatever global config the environment has.
2. **Put a non-ASCII file name in your test fixtures.** One test is enough. What it guards against is someone deleting the flag.
3. **Count what you'd lose.** This compares how many `.md` files git lists with default settings versus with quoting off. The difference is what a suffix filter would silently drop. Run it with `sh`. I ran it on `docs/` in those 9 repos today: 4 of them have a difference, 57 files in total.

```sh
#!/bin/sh
# usage: quoted_count.sh [path]; compare .md counts git lists with default settings vs quoting off; the difference is what a suffix filter drops
p=${1:-.}
a=$(git ls-files -- "$p" | grep -c '\.md$')
b=$(git -c core.quotepath=off ls-files -- "$p" | grep -c '\.md$')
echo "default $a  quotepath=off $b  lost $((b - a))"
```

4. **Check "0 remaining" by a different route.** Have whatever counts "remaining" list files differently from whatever did the work: one through git, one through the filesystem, say. It's done when the numbers agree.

This is part 12 of the series. Most earlier parts were about whether an agent can route around a rule. This one is about a rule that can't see: the check itself was correct, it just never got shown one kind of file. Before you trust a green check, make sure it saw everything.

## About the numbers

- 9 repos, 1,019 docs filled, "0 still non-compliant" in each: output of the first bulk run in the 2026-11-17 backfill session (07:27:12 UTC, 02:27 US Eastern), summing each repo's "filled" count.
- 34 docs in 4 repos (1 / 23 / 9 / 1), all with Chinese names: the full-mode "non-compliant" counts from the same output, plus the list of non-compliant files the agent printed right after.
- "Ten seconds later": the agent's message at 07:27:22 UTC. "Under 2 minutes": 07:27:12 to the fix commit at 07:28:51 UTC (02:28:51 US Eastern).
- 34 filled after the fix, 0 non-compliant in all 9 repos, 9 tests passing: the rerun output in the same session after the fix commit.
- 3 files, +13 / −2, and the test's contents: the fix commit's diff.
- 18 minutes: from the commit that merged the checker (02:10:35 US Eastern) to the fix commit (02:28:51).
- The escaping example, and untracked Chinese-named files judged as missing: reproduced locally in a scratch repo on 2026-11-24.
- 2 scripts without the flag: a read-only search of `scripts/` on that repo's current main on 2026-11-24.
- 57 files: the script above, run read-only on the current `docs/` of the 9 repos on 2026-11-24, differences summed. It's higher than 34 because 34 only counted docs missing metadata at the time; 57 is every Chinese-named `.md` today.
- Global config not set: `git config --global --get core.quotepath` printed nothing on my machine on 2026-11-24.
