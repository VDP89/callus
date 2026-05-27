# Setting up callus for your own voice

The whole architecture only works if the corpus is yours. A generic corpus calibrates against a generic voice, which is exactly the failure mode of classifier-based detectors. Five steps.

## 1. Build the corpus

If you use Claude Code, your raw prompts are sitting in `.jsonl` files under `~/.claude/projects/<your-project>/`. The `build-corpus` command extracts them and applies thirteen calibrated filters to drop pasted outputs, command dumps, Codex reviews, dashboard copy, emoji-heavy reviewer text, and short operational commands.

```bash
callus build-corpus \
  --source ~/.claude/projects/your-project \
  --out callus/voice_corpus.jsonl \
  --opsec "secrets/" "private/"
```

The `--opsec` flag drops any prompt that contains the given path substrings. Use it for anything you do not want sitting in a plain JSONL on disk — credentials, financial paths, personal data.

If you are not on Claude Code, you need to assemble the corpus yourself. The format is one JSON object per line:

```json
{"text": "the raw prompt or paragraph", "ts": "2026-05-27T12:00:00", "words": 142}
```

You can mix sources — chat exports from other tools, draft fragments, comments you wrote on forums. The only rule is "raw, by you, not output that an assistant produced and you copy-pasted."

## 2. Sample-review what ended up in the corpus

The filters are good but not perfect. They were calibrated against a human-labeled sample with target pass rate 80%. Before you treat the corpus as ground truth for your voice, look at a sixteen-row sample:

```bash
shuf -n 16 callus/voice_corpus.jsonl | python -c "
import json, sys
for i, line in enumerate(sys.stdin, 1):
    row = json.loads(line)
    print(f'[{i:2d}] {row[\"words\"]}w: {row[\"text\"][:200]}...')
    print()
"
```

For each entry, ask: is this me writing, or is this content I pasted that survived the filters? If more than three of sixteen are not actually you, extend the filters in `callus/build_corpus.py` (the `F1` through `F13` functions are documented) and rebuild.

## 3. Write a voice profile

Copy `cookbook/profile_template.md` to `voice-profile.md` (in your current working directory, or wherever you want callus to find it) and edit the rules to match how you actually write. The example file in `cookbook/` describes the format. Things to include:

- Your name and roles.
- Channels you write for, with idiom and audience for each.
- Phrases you never use (vocabulary you have personally rejected).
- Closing patterns you do use and want preserved.
- Per-channel hashtag sets and link-funnel destinations if you operate on social.

The profile is not consumed by the LLM directly; the judge reads a compressed version. But editing yours forces you to write down the rules you carry in your head, which is itself useful.

## 4. Validate with an eval set

Optional but recommended for serious use. Build twenty samples in four groups of five:

- Five drafts of yours you know are clean voice.
- Five drafts of yours you know have AI tells (output of an LLM you have not yet edited).
- Five synthetic drafts you ask an LLM to write in English on topics in your domain.
- Five synthetic drafts you ask an LLM to write in Spanish on topics in your domain.

Score all twenty. Look at the medians by group. If your clean drafts cluster well below the synthetic ones (a gap of at least fifteen points is reasonable), the calibration is working. If the gap is small, your voice profile or your corpus is too generic.

## 5. Use it

Score:

```bash
callus score draft.md
```

Rewrite toward your voice:

```bash
callus rewrite draft.md --target 25 --out draft.v2.md
```

If you wire the optional hook (see README), every session you close adds new candidate prompts to a pending review file, which you approve manually with `callus approve <pending.md>`. The corpus grows over time. So does the calibration.
