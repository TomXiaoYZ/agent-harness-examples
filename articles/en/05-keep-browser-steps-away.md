# Keep browser steps away from your coding agent: three blocked rounds, then one clean pass

Short version: **I no longer hand Codex any step that opens a web page, logs in, takes a screenshot, uploads, or records the screen.** Those steps go either to Claude Code, which does acceptance and has a browser extension, or into a "human prerequisites" section that I complete myself before dispatch. Codex gets only the work it can finish on the local machine.

The rule came out of a video content pipeline. Here is what the per-round receipts from two episodes said.

## Episode one: five of six rounds stopped at the browser

On October 26 an episode needed assets generated in an online design tool, with a screen recording. Stage A went to Codex and ran six rounds. The first five came back `blocked`, each for a different reason:

1. The tool was not logged in. The card's preflight said stop and wait for me.
2. A "Try it free for 30 days" banner appeared. The card said to stop at any paid, upgrade, or trial prompt, so it stopped.
3. The account and settings pages returned a server error, so the plan and remaining credits could not be checked.
4. Recording needed the browser's debugging protocol. The permission check answered "not approved by the user" and forbade workarounds.
5. One generation ran, and the browser saved the first download to the default Downloads folder, which broke the "write only to this episode's directory" boundary. It stopped and asked.

Round six passed.

Every stop was correct behavior. Codex did not guess, did not route around the check, and did not click "start trial" for me. The defect was the card: it buried five prerequisites that **only a human could clear** inside an execution task, and each one cost a full round to discover.

## Episode two: the same error, three times

On October 29–30 the next episode needed a transcription test run on a web page, with screenshots. All three receipts gave the same blocker:

> The browser access host is unavailable

- Round 1 failed at preflight. None of the four tests ran.
- Round 2 did all the local work it could (audio prep, one transcription test, a scoring script, +166 lines of source), retried the browser once, and got the same line.
- Round 3 made its single browser check, failed, and stopped with no new source.

On October 31 the root cause was found: **a Codex thread started by my dispatch script cannot obtain the browser-plugin credentials that the desktop app issues.** The network toggle is irrelevant; round 1 had network access on and still failed. That card could never have succeeded on the Codex side. A fourth round would have ended the same way.

## After the split

The same day the episode was split in two:

- **Browser work**: open the page, screenshot, upload. Claude Code does this through its browser extension, after I connect the extension once.
- **Local production**: voice, subtitles, compositing, QA. This became a new Codex card whose authorization section turns off network and MCP, and whose acceptance checklist says "no browser access".

The local card came back `done` on round one: a 229.5-second video, +447 lines of source against a 700-line budget, 25 self-checks passed, and `human_action: none`.

Since then, the next two episodes produced 9 receipts and 3 were `blocked`: a citation that did not match its source, a read/write scope conflict, and a truncated voice line. None were about the browser.

## Where the rule lives

The written rule is one line in the dispatch skill's pre-dispatch checklist: **don't dispatch browser steps.** Opening pages, screenshots, uploads, and logged-in actions become acceptance steps or human prerequisites.

One line of prose gets forgotten, so three scripts back it up:

1. **The card checker (`check_card.py`) refuses any card without a `## Human prerequisites` section** (`## 人工前置条件` in my templates). The section lists login, browser or recording permissions, paid tiers, and download directories, and says whether I have handled each. "None" is allowed. Leaving the section out is not. It forces whoever writes the card to ask, before dispatch, whether any step needs a person.
2. **The same checker refuses a third round.** Once the card logs a third round, it errors out: split the card, or bring the evidence to me. Under this rule, episode two would never have reached round three.
3. **The dispatcher (`codex_thread.py`) disables plugins, apps, and MCP by default.** Turning them on takes an explicit flag, and even then the browser credentials are not there. That closes the "maybe just enable the plugin" detour.

To be clear about the limits: no script can tell **whether** a card contains a browser step. A person still makes that call. What the scripts guarantee is that the question gets asked, and that a wrong answer costs at most two rounds.

## What you can copy

Add this section to your task card template, and have your pre-dispatch check fail if the heading is missing:

```markdown
## Human prerequisites

Done and confirmed before dispatch (write "none" if nothing applies):
- Login:
- Browser / screen-recording permission:
- Paid tier, and what to do at a trial prompt:
- Download directory:
```

Then split work three ways:

1. **Only a human can do it**: login, 2FA, payment confirmation. It goes in prerequisites and gets done before dispatch.
2. **It needs a browser but not a human**: it becomes an acceptance step for the side that actually has a browser, not for the executor that lacks the credentials.
3. **Everything else is local**: dispatch it with network and plugins turned off, so the card's boundary and the real permissions match.

One test settles most cases: **"If this step gets stuck, will a retry fix it, or only I can?"** If only you can, it does not belong on the executor's card.

This is part 5 of a series on running Claude Code and Codex together on real repositories. If you have pointed an agent at a browser, I'd like to hear where it got stuck.

## About the numbers

- Source: per-round receipts (`status` and `blockers` fields) for two episodes in my dispatch evidence directory, plus collaboration reviews dated 2026-10-26 and 2026-10-31.
- Episode one: six stage-A receipts on 2026-10-26; rounds 1–5 `blocked`, round 6 `done`. The five reasons are paraphrased from the receipts.
- Episode two: three receipts on 2026-10-29 and 10-30, all `blocked` with an identical error. Round 1's dispatch parameters show `networkAccess: true`. The split-off local card finished on 2026-10-31 in one round; 229.5 s, +447 lines, and 25 checks are from that receipt.
- "9 receipts, 3 blocked": every receipt file for the two following episodes, as of 2026-11-17.
- The root cause is the 2026-10-31 diagnosis from the content pipeline session. I did not build a separate reproduction.
