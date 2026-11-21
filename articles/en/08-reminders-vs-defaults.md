# I added a "your session is getting long" hook. Context still hit 689K tokens per call. Caps belong in defaults, not reminders

Short version: **if you want to cap an agent's context, telling it to wrap up is not enough. Change the host's defaults.** I installed a hook that warns when a Claude Code session gets long. On the first full day it was live, a single call still carried 689K tokens of context. Then I changed two lines of config. In the three days since, no single call has gone above 171K.

Some background. I use Claude Code to plan and review, and Codex to write the code. In part 6 I showed that the planning and reviewing side often burns several times more tokens than the side that writes the code. That isn't because it does more work. It's because every call re-reads the whole conversation.

## Attempt 1: a reminder

On November 15 I added `long_session_hint.py`, a `UserPromptSubmit` hook. When the main session's context reaches 200K tokens, it says so once, and again at every additional 100K: "hand the next result to a fresh session." It never blocks a prompt and exits quietly on any error.

November 16 was the first full day with the hook live. From my local logs:

- 4,688 calls, about 662M tokens in total;
- per-call context: p90 289K, max 689K;
- subagents were 56% of all usage, and 96% of that ran on Opus.

By design, any session past 200K that day got the reminder. Context kept growing anyway. The reasons aren't mysterious. When the model sees the reminder, it's in the middle of something, and "finish this step first" always sounds right. And the hook only watches the main session. Subagents never pass through it, so they grow on their own.

**A reminder changes what the model knows. It doesn't change what it does.**

## Where the tokens went

On November 17 I laid out eight days of usage. Three causes stood out:

1. **No compaction.** Sessions ran on a 1M window and only auto-compacted close to 1M. Over seven days, per-call context had a median of 136K and a p90 of 389K. The longest session had been open for 136 hours straight.
2. **Every subagent on Opus.** Subagents were about half of all usage. Almost all were fresh general-purpose subagents with no model set, so they defaulted to Opus. The heaviest session alone spawned 71 of them.
3. **High fixed overhead.** The first call of a session already carried about 67K tokens: system prompt, tool definitions, the skill list. A few plugins I never use were part of that.

## Attempt 2: change the defaults

Same day, three changes, all in `~/.claude/settings.json`, effective for new sessions only:

```json
{
  "env": {
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "200000",
    "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet"
  },
  "enabledPlugins": {
    "some-unused-plugin@marketplace": false
  }
}
```

- The main session auto-compacts at roughly 200K;
- subagents default to Sonnet (any subagent that names a model explicitly is unaffected);
- three unused plugins are off.

I kept the reminder hook. Its job now is to tell me a session is getting long, not to hope the model stops itself.

## Three days later

Early today (November 21) I re-ran the same script with the same dedup rule. First a sanity check: for November 10 to 16, daily call counts and totals matched the November 17 review table day for day. Then the days after the change:

| Day | Calls | Total tokens | Context p90 | Context max | Subagent share | Opus share within subagents |
|---|---|---|---|---|---|---|
| 11-16 (reminder only) | 4,688 | 662M | 289K | 689K | 56% | 96% |
| 11-18 | 3,998 | 530M | 161K | 171K | 9% | 13% |
| 11-20 | 1,875 | 197M | 155K | 170K | 29% | 8% |

The clearest change is the ceiling. After the change, the largest single-call context was 171K, and p90 sat around 160K. That's exactly what a compaction window should do. Opus inside subagents fell from over 90% to around 10%.

Two caveats:

- **Daily totals are not comparable.** Every day has different work; 11-20 was lighter mostly because there was less to do. I compare the shape of a single call, not totals, and I'm not claiming a dollar saving.
- **Fixed overhead barely moved.** Counting the first main-session call of each session: median about 79K before, about 69K after, roughly 12% down. The plugins I turned off were a small slice. That one is still open.

The formal re-check is on November 24, with a full week of data.

## What you can copy

1. **Measure before you change anything.** Dedupe by `message.id + requestId`, bucket by day, and record per-call context p50, p90 and max, plus the subagent share. Without a baseline you can't tell whether a change did anything.
2. **Put the cap in a default.** Compaction window and subagent model are host settings. Once set, they apply whether or not the model feels like wrapping up. Keep the reminder for humans.
3. **Watch subagents separately.** Hooks on the main session don't see them. Give them their own numbers and their own defaults.
4. **Compare shape, not volume.** Workload changes every day, so totals say little. Context p90, max and model mix describe what each call looks like, and those you can compare.
5. **Write down the cost and the way back.** Compaction loses detail. Subagents doing hard reviews may get worse; name Opus explicitly for those. To roll back, delete the two `env` lines.

The core of the counting script is a few lines:

```python
seen = set()
for line in open(transcript):
    rec = json.loads(line)
    msg = rec.get('message') or {}
    usage = msg.get('usage')
    if not usage or (msg.get('id'), rec.get('requestId')) in seen:
        continue
    seen.add((msg.get('id'), rec.get('requestId')))
    ctx = sum(usage.get(k) or 0 for k in
              ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'))
    # accumulate ctx and output_tokens by day, subagent or not, and model
```

This is part 8 of the series. Part 6 said guards belong on the command an agent can't route around. This one is the other side of the same idea: caps belong where the agent doesn't have to decide anything.

## About the numbers

- Hook thresholds (200K, then every 100K) and "warn, never block": from the docstring and constants of `long_session_hint.py`. It went live the morning of 2026-11-15, per the commit log.
- Seven-day median 136K, p90 389K, 136 hours, subagents about half, 71 subagents, ~67K first call, the three config changes and their trade-offs: from my 2026-11-17 Claude Code usage review.
- The table, and the 56% / 96% for 11-16: a read-only scan of my local Claude Code logs on 2026-11-21, deduped by `message.id + requestId`, bucketed by US Eastern time. "Total" is uncached input + cache writes + cache reads + output. Local logs, not a bill. Call counts and totals for 11-10 to 11-16 match the review table day for day.
- First-call 79K vs 69K: same day, using the first usage record of each main session; before = 50 sessions from 11-10 to 11-16, after = 38 sessions from 11-18 on. The window differs from the review's 67K, so I don't compare the two.
- Config read back from `~/.claude/settings.json` on 2026-11-21: the two `env` values are 200000 and sonnet.
- 11-19 shows only 336 calls in the logs, far fewer than the days around it. I haven't looked into why, so it's left out of the table.
