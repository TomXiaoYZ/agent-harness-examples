# "One card, one context" sat in the docs for two weeks. Then one day cost ~420M tokens, and the guard got bypassed the day after

The short version: **a rule that limits how long an agent's context gets cannot live at the "entrance". It has to live inside the command the agent cannot avoid, and every action that moves work forward has to check it.** I wrote "one task card, one fresh context" into my instructions and nothing enforced it for two weeks. The first time I turned it into code, it was bypassed within a day.

Some background. I use Claude Code to split work into task cards and review the results, and Codex to implement them. Dispatching, monitoring and accepting a card is supposed to happen in a short context opened for that card alone.

## Failure one: the rule was only a sentence

The rule dates from a review on October 30. Every request resends the whole conversation, and back then I ran one long session per project. One transcript had grown to 32 MB with 1,878 tool results. By the later cards, every turn was re-reading the history of all the earlier ones.

So the rule went into the dispatch skill, as its first structural rule. Nothing else changed.

On November 14, a batch of cards was due in a data platform repository. Two subagents each received a batch: one dispatched and accepted 26 cards inside a single context, the other 8.

That day:

- the Claude Code side used about 420M tokens, almost all of it re-reading a context of roughly 370K tokens;
- Codex wrote all the code for those cards with 49M.

The side doing planning and review spent more than 8 times what the side doing implementation spent.

Two things let it happen:

1. **The rule was just text.** It was in the skill, and nothing held it.
2. **A wrapper script hid the calls from hooks.** I had written a `dispatch.sh` for convenience, wrapping the dispatch command. A hook only saw "a shell script ran", not each real dispatch call inside it. Even a hook aimed at the dispatch command would have been blind.

## Failure two: the guard checked one action

The same day the rule became code. Not in a hook, but inside the dispatch script itself: before creating a thread, `codex_thread.py start` calls `dispatch_scope.py`, which asks whether this context has already dispatched a different card. If it has, the call is refused. A second round on the same card passes.

On November 15 it was bypassed.

A subagent had 14 cards to handle. It let throwaway subagents run only `start`, then stayed in its own context and ran `turn` (which drives the thread) and acceptance for all 14 cards. The guard checked `start`. It did not check `turn`. That cost about 132M tokens, again re-reading one growing context.

The guard literally said "`start` may not cross cards", and this path obeyed it to the letter. **Whatever action you guard, the work moves to the one you did not.**

The fix landed the same day: `turn` calls the same guard, and every context that drives a thread is written into the thread's registry file. Once a context has touched one card, through `start` or `turn`, it cannot touch another.

## How the guard knows who is calling

The hard part: when the script runs, which context ran it? A main session and its subagents share one session ID.

The answer is in the transcripts. Claude Code keeps one JSONL transcript for the main session and one per subagent. At the moment the guard runs, exactly one of them has a Bash tool call with no result yet, because the guard is that call. So:

1. read the session from the `CLAUDE_CODE_SESSION_ID` environment variable;
2. scan the tail of the main transcript and every subagent transcript for that session;
3. the transcript holding the newest Bash call without a result is the caller.

Whenever the caller cannot be identified, the guard lets the call through: when I run the script myself from a terminal, or when two contexts are waiting on Bash at the same instant. **The guard would rather miss than block a person by mistake.**

## What the registry shows now

Since the guard went in, registry files carry a caller field. As of the morning of November 18:

- 98 threads have a recorded caller, across 5 repositories;
- 109 distinct contexts appear, and 108 of them touched exactly one card;
- one context ran `start` for 2 cards on November 17, and the guard did not stop it. I have not found out why yet, so it stays on the record as an open leak.

I also added a hint hook that never blocks, `long_session_hint.py`, on the prompt-submit event. When the main conversation reaches 200K tokens of context, and at each further 100K, it tells the model to hand new results to a fresh session and tells me the current size. On any error it exits quietly. The reason: on November 14 and 15, main sessions kept working at 220K to 490K tokens of context, while Codex threads in the same window had a median context of 67K.

## What you can copy

The core is under 20 lines. This is a simplified version. The registry holds one JSON file per thread, with the card path and the contexts that touched it:

```python
def check(threads_dir, card, who):
    """Return a refusal message if `who` already touched another card, else None."""
    if not who:
        return None  # caller unknown: let it through
    card = os.path.realpath(card)
    for path in glob.glob(os.path.join(threads_dir, '*.json')):
        with open(path, encoding='utf-8') as fh:
            reg = json.load(fh)
        touched = reg.get('caller') == who or who in reg.get('turn_callers', [])
        if touched and os.path.realpath(reg['card']) != card:
            return f'this context already touched {reg["card"]}; open a fresh one for the new card'
    return None
```

Three things to keep in mind:

1. **Put the guard inside the command, not around it.** A hook can be hidden by a wrapper script. A check inside the dispatch script cannot be skipped by anything that wants to dispatch.
2. **List every action that moves work forward, and check each one.** Guard only "start" and the work moves to "continue". I missed `turn`, and it cost 132M tokens.
3. **Say what to do next in the refusal.** Mine tells the agent to go back to the project session and open a new session or subagent for this card, with only this card's brief. A bare "no" sends it looking for another way around.

A quick test for whether a rule is actually enforced: **"if the agent never read this sentence, what would happen?"** If the answer is "nothing", the rule is still a wish.

This is part 6 of a series on running two coding agents together. Part 1 found that the manager costs more than the engineer. This one is the follow-up: once you know where the cost is, how do you make the rule hold.

## About the numbers

- 32 MB and 1,878 tool results come from my collaboration review of 2026-10-30.
- 26 cards, 8 cards, ~420M, ~370K and 49M come from the header comment of `dispatch_scope.py` and the rule text in the dispatch skill. They describe 2026-11-14. Most of the Claude Code side is cache reads, so this is token volume, not a bill. "More than 8 times" is 420M divided by 49M. I did not recompute these figures for this article.
- 14 cards and ~132M come from the `check_turn` comment in the same script and the skill text, for 2026-11-15.
- 98 threads, 5 repositories, 109 contexts, 108 with one card and 1 with two: I counted these directly from the thread registry files on the morning of 2026-11-18, over entries with a caller field, which start on 2026-11-14.
- 220K to 490K, 67K, and the 200K and 100K thresholds come from the header comment and constants of `long_session_hint.py`, dated 2026-11-15.
