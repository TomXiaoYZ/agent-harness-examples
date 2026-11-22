# My review subagents said "waiting for the notification" and handed back. 11 of 21 did it, and the parent sat idle 12 minutes

Short version: **when a subagent puts its wait in the background and ends its turn with "waiting for the notification," the parent sees that as a finished task.** On November 21 I dispatched 23 UI cards in a data platform repo, one after another. For 21 of them I can line up the subagent's transcript with the receipt timestamp. In 11 of those, the review subagent handed back before Codex had written its receipt. The parent got a message that said "still waiting," and then it stopped too. The longest stall was 12 minutes, until I typed "how's it going?" The fix was one commit: the wait now runs in the foreground in 170-second slices and returns a special exit code when it isn't done yet, so the caller just runs it again.

Some background. Claude Code splits work into cards and reviews it; Codex writes the code. For each card, the parent session starts a background review subagent. The subagent opens a Codex terminal, waits for the receipt, reruns tests and browser checks against a checklist, and writes a verdict. The parent only reads the verdict and decides whether to merge.

## What happened

It was a fast morning: 23 cards dispatched between 10:52 and 14:13 UTC. The trouble was in the "wait for the receipt" step.

The review brief at the time said: "Run wait in the background with Bash, wait for the completion notification, don't poll." The subagents did exactly that. They put the wait in the background, printed something like "Dispatch done, waiting for Codex's round 1 receipt, will continue reviewing when the background notification arrives," and ended their turn.

From the subagent's side that's fine. When the background task finishes, it gets woken up and carries on. But from the parent's side, **a subagent that ends its turn has handed back.** The parent gets a "task completed" notification, and what's inside is a half-finished report.

Two concrete cases:

- **UX-3a**: the subagent handed back at 11:36:53 saying it was waiting for the receipt. A second later the parent replied "round 1 is still running, no result yet" and stopped. The receipt landed at 11:41:35. The parent only moved again because I sent it an unrelated instruction at 11:40.
- **UX-10a**: the subagent handed back at 13:59:05, and the notification summary said it was "waiting on its own background task." This time the parent didn't even reply. It just stopped. The receipt was written at 14:08:54, and the parent didn't move. At 14:11:13 I asked "how's it going?" Only then did it check the evidence folder and find the receipt had been there for a while. From the early hand-back to my question: 12 minutes.

Early the next morning, in a different session, I wrote: "I keep seeing the parent agent sitting idle. Either it never dispatched a subagent, or the subagent already finished."

## Why it happened

Reading through the transcripts, there were three layers.

**Layer one: the brief told the subagent to go to the background.** When I wrote it I was thinking "no polling, save tokens." I didn't think about what a subagent ending its turn means to the parent.

**Layer two: the foreground can't wait forever either.** Why not have the subagent wait two hours in the foreground? Because Claude Code moves any foreground command that runs past 180 seconds into the background, whatever timeout you set. So a two-hour foreground wait was never an option, and the subagent would end up at "background wait, end turn" anyway.

**Layer three: notifications can arrive early.** A different child exposed this one. On November 21 a child agent that doesn't report its status to my terminal orchestration tool was announced as "turn finished" right after it launched. The parent trusted the note, went to read the result, saw the child was still busy, and stopped, with nothing left to wake it. I had fixed a bug in the same family on November 19 (a child messaging the parent mid-task made the wait return early). This was the same problem coming in through a different door.

Stack the three together and the result is always the same: **the parent thinks someone will wake it, and nobody does.**

## The fix: one commit

The November 22 fix (6 files, +96 / −23) did four things:

1. **The wait now runs in the foreground in slices.** Each call waits at most 170 seconds, so it returns before the 180-second cutoff. If the round isn't done, it exits with code 4, meaning "Codex is still working, run the same command again." No receipt file is written until the round ends, so a half result can't be mistaken for a full one.
2. **Other messages no longer cut the wait short.** When the parent's terminal receives a message from another child, the underlying wait returns early. Now it just keeps waiting until the slice is used up.
3. **"Turn finished" needs evidence.** The dispatch script records the child's turn counter before sending the task. It only notifies the parent once the counter has moved and the status is no longer "working." For a child that never reports status, it tells the parent after 10 minutes, honestly: "can't tell, don't sit waiting for it, go look yourself."
4. **One line in the global rules.** Before the parent ends its turn "waiting for a result," it has to confirm something will wake it. If a subagent hands back "still waiting" instead of a result, the parent checks the evidence folder right away: if it's done, carry on; if not, send the subagent back to wait in the foreground until the end.

## Where the rules live

- **The dispatch script's wait subcommand**: the default slice is 170 seconds, a named constant with a comment about the 180-second limit. While Codex is still working it exits 4 and writes no receipt.
- **The review brief**: step 2 of phase two now says "run wait in the foreground; on exit code 4, run it again unchanged; don't background it, don't replace it with a sleep loop, don't end your turn 'waiting for the notification'," along with the reason: once a subagent hands back, the parent only has half a report.
- **Tests**: three new ones. One checks that a message from someone else doesn't end the wait, one checks that a still-working round exits 4 and writes no receipt, and one asserts the default slice is under 180 seconds. All 9 tests in that file pass, and CI on the fix commit is green.

## Still open

- **The fix is less than a day old.** I don't have post-fix dispatch data yet, so I can't say the stalls are gone. After the next batch of cards I'll count early hand-backs the same way.
- **The brief is text, not a hook.** Slicing the wait removes the reason to background it, but if a subagent does it anyway, nothing stops it. The parent's "check before you stop" rule is the backstop.

## What you can take from this

1. **Know what "ending a turn" means one level up.** A subagent's "background wait, wait for notification" looks to the parent like a finished task. Anything you need to wait for, wait for before handing back, not after.
2. **If your tool backgrounds long commands, slice the wait.** Here's a generic version: wait for a receipt file, return 4 when the slice runs out, and the caller runs it again on 4. I tried both cases locally: with no file it returned 4 after 6 seconds; with the file showing up at 3 seconds it returned 0 right away.

```sh
#!/bin/sh
# usage: slice_wait.sh <receipt-file> [seconds]; 0 when the receipt appears, 4 when the slice runs out (run again)
receipt=$1; slice=${2:-170}
end=$(( $(date +%s) + slice ))
while [ "$(date +%s)" -lt "$end" ]; do
  [ -s "$receipt" ] && { echo "done: $receipt"; exit 0; }
  sleep 5
done
echo "still working: run the same command again"; exit 4
```

3. **Count early hand-backs.** For each card, compare two times: when the subagent first handed back, and the receipt file's modification time. If the first is earlier, it handed back early. For me it was 11 of 21 that day. At that rate, a human watching won't keep up.
4. **Base "done" notifications on state changes, not on time.** Record the turn count before sending the task, and only call the turn over once it has moved. If a child can't report status, say so plainly.

This is part 10 of the series. Earlier parts were about putting rules where the agent can't route around them. This one is the other side: the wait has to go somewhere it can't be skipped too. A wait that happens after the hand-back is a wait nobody is doing.

## About the numbers

- 23 cards, dispatched 10:52–14:13: the 23 UI card folders in that repo's evidence directory for 2026-11-21; times are the first timestamp in each review subagent's transcript (UTC).
- 21 matched, 11 early: I read each review subagent's transcript from that day, took the card name from its wait command, and compared it against the modification time of the last receipt file in the evidence folder. If the parent got its first hand-back or completion notice from that subagent before the receipt time, it counts as early. 2 more cards are excluded because the card name in the command was quoted and didn't parse.
- UX-3a's 11:36:53, 11:36:54, 11:41:35, and 11:40, and UX-10a's 13:59:05, 14:08:54, and 14:11:13: timestamps from the parent session transcript and receipt file modification times (UTC). "12 minutes" is 13:59:05 to 14:11:13.
- The brief line "run wait in the background with Bash, wait for the completion notification, don't poll": the line removed from the brief in the fix commit (arguments omitted).
- 180 and 170 seconds: the wait slice constant and its comment in the fix commit.
- The child announced as finished at launch (11-21) and mid-task messages ending the wait early (fixed 11-19): from a code comment in the fix commit and the message of the 11-19 commit, respectively.
- 6 files, +96 / −23, 3 new tests, 10 minutes: from the diff of the 2026-11-22 fix commit.
- 9 tests passing and green CI: a local run of that test file on 2026-11-22 and the CI result for that commit.
- My own words: from my message in the fix session on 2026-11-22.
