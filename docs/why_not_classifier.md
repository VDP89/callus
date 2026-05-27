# Why callus does not use a classifier

A short, sourced explanation of why `callus` builds its own LLM-as-judge against a per-author corpus instead of wrapping GPTZero, Originality.ai, Humalingo, Copyleaks, Pangram, or any of the open-source detectors like Ghostbuster, Binoculars, or Fast-DetectGPT.

## The numerical evidence

Two drafts on the same topic, by the same author, scored against the same Humalingo run:

| Draft | callus judge | Humalingo |
| --- | --: | --: |
| Clean blog post, already passed a heuristic voice audit | 20 | 91% |
| LessWrong submission with documented AI tells | 33 | 92% |

The relevant delta — clean voice versus voice with tells — is thirteen points on the calibrated judge and one point on the classifier. The classifier cannot see the difference.

## Why classifiers cannot see the difference

The mechanism is documented. Liang et al., Stanford, 2023, *GPT detectors are biased against non-native English writers* ([arXiv:2304.02819](https://arxiv.org/abs/2304.02819), published in Cell *Patterns*) measured seven commercial detectors against TOEFL essays and against US 8th-grade essays.

The headline numbers:

- Average false positive on non-native English: **61.22%**
- At least one of the seven detectors flagged: **97.80%** of non-native essays
- Unanimous flag across all seven: **19.78%**
- Average false positive on native essays: **5.19%**

The gap is roughly twelve times. The mechanism is perplexity: detectors estimate the probability of the next token under a reference language model. Native English essayists and AI both tend to produce text with higher per-token surprise; non-native writers and AI both tend to produce text with lower per-token surprise, because the available vocabulary is smaller and the collocations are more common. The two clusters overlap structurally.

OpenAI's own classifier was shut down in July 2023 with a public note about "low rate of accuracy." Anthropic does not ship one. The maintainers of Binoculars (ICML 2024) state on the repository that it is "academic only" and "more proficient in English." Ghostbuster (NAACL 2024) does not claim multilingual support.

## What callus measures instead

The judge prompt asks for three axes, none of which is `P(LLM-generated)`:

- **voice_distance** — how far the draft is from the writer's natural voice, defined by the corpus the writer built from their own raw prompts.
- **tells_density** — count of AI tells from the library (aphorism, hinge phrase, triplet negation, em-dash, filler, negation of identity, defensive clarification) normalized per two hundred words.
- **structural_ai_patterns** — sentence-rhythm uniformity, reveal-punchline endings, generic essay scaffolding.

The aggregate is the mean of the three. Non-native English does not raise any of them on its own. Tells do.

## When the classifier framing is still useful

Two cases.

If you are evaluating an unfamiliar writer's text and you have no corpus from them, classifier-based estimates of `P(LLM-generated)` are the right tool. They will be noisy, especially across non-native writers, but they are calibrated for that question.

If you want a binary sanity rail against catastrophe — "did I just publish something that scans as obvious bot output" — running a draft through a commercial classifier and reading the *direction* of the score is informative. A draft of yours that scores 99% may be worth a second look. A draft that scores 85% on a non-native writer is the normal floor.

Do not iterate against the classifier's number. The number does not move predictably when you fix the actual stylistic problems a reader will notice.

## What this implies for `callus`

The skill ships with no corpus on purpose. A generic corpus would calibrate against a generic voice, which is exactly the failure mode of the classifiers. The first action a new user takes is `callus build-corpus --source <their own session logs>`. The first audit a new user runs is human review of the first sixteen entries, to confirm what is in the corpus is actually them.

## Sources

- [Liang et al., *GPT detectors are biased against non-native English writers* (arXiv:2304.02819)](https://arxiv.org/abs/2304.02819)
- [The Markup, *AI Detection Tools Falsely Accuse International Students of Cheating*, 2023-08-14](https://themarkup.org/machine-learning/2023/08/14/ai-detection-tools-falsely-accuse-international-students-of-cheating)
- [OpenAI announcement on the discontinuation of the AI Text Classifier, July 2023](https://openai.com/index/new-ai-classifier-for-indicating-ai-written-text/)
- [Binoculars (Hans et al., ICML 2024) — `github.com/ahans30/Binoculars`](https://github.com/ahans30/Binoculars)
- [Ghostbuster (Verma et al., NAACL 2024) — `github.com/vivek3141/ghostbuster`](https://github.com/vivek3141/ghostbuster)
- [Fast-DetectGPT (Bao et al., ICLR 2024) — `github.com/baoguangsheng/fast-detect-gpt`](https://github.com/baoguangsheng/fast-detect-gpt)
