# Decoding quality experiment — final report on 557 reviewed outputs

**Finalized at the user's request using the 557 available generations, all manually reviewed. The 43 ungenerated calls are skipped; the waiting runner has been stopped. The original 600-run matrix is incomplete, so comparisons across all settings use the same 23 fully covered prose questions.**

Generation ran on [Ruurd's Gemma Space](https://huggingface.co/spaces/Ruurd/byod-gemma-2-9b); the local script submitted requests and saved outputs. Space revision: `c8003db3f4da4569d0915199751c1b7e0f1147d2`. No model training or deployment changes were made.

## Judgment on the available evidence

- **PMI with diffusion-probability remasking at 128 steps is the strongest prose setting on the 23 fully matched questions.** Mean manual grammar/fluency score: 2.39/3, with 11/23 clean answers. Confidence-guided baseline: 1.91/3 and 4/23 clean. Conditional bigram with diffusion probabilities: 2.09/3 and 10/23 clean.
- **128 steps helps much more consistently than 32 or 64.** The shorter schedules often leave word fragments, missing verbs, repeated lists, or number/conjunction loops.
- **Viterbi path-margin remasking does not improve the aggregate results here.** At 128 steps, both margin variants trail their corresponding diffusion-probability variants; conditional margin is particularly poor at 32 steps. This is an observation at these settings, not a claim about every possible parameter choice.
- **Coding remains poor, with no persuasive general gain from Viterbi.** With algorithm adherence, the best 128-step settings each solve only 2/10 assignments. PMI diffusion at 64 steps solves 2/10 versus the baseline's 1/10, a one-task difference in a small set.

These are exploratory judgments from one prompt set and one seed. They support a practical preference for **PMI + diffusion probability, 128 steps for prose**, not a reliable coding upgrade or a final result for all 30 prose questions.

## Coverage and settings

All 10 coding assignments are complete under every configuration (150 runs). All 30 prose questions have 32-step results; 28 have all 64-step results; the first 23 have every setting at every step count. A further two 128-step answers for question 24 are saved but excluded from the balanced comparison. The fair prose table below uses exactly the same first 23 questions for all 15 configurations.

Skipped calls: 33 at 128 steps and 10 at 64 steps. Exact keys: [missing_runs.json](missing_runs.json).

Common settings: 128 new tokens, block length 128, steps 128/64/32, seed 42, temperature 1, sampling top-k 16, bigram candidates 16, bigram weight 0.5, PMI minimum count 1, PMI clipping bound 2. System prompt: “You are a helpful assistant.” Retained tokens are frozen, revision is off, and early stopping is disabled to use the complete requested step budget.

For prose, EOS/EOT retention delay is on and bigram ending-delay strength is 1000. For code both are off (neutral strength 1). The baseline has no bigram selector, so the bigram ending prediction penalty is not applied there. Temperature and sampling top-k affect the sampled baseline; Viterbi selection is deterministic. These are the requested practical configurations, not an experiment isolating the bigram term from sampling and ending policy.

The 30 prose prompts are the original first 30 questions in `src/diffusion_lm/generation_prompts.txt`, ending with the traveler story. Coding prompts request short Python functions: even sum, palindrome normalization, Fibonacci, order-preserving deduplication, bracket matching, binary search, word counts, sorted merge, flattening, and FizzBuzz. The exact prompts/options are in [manifest.json](manifest.json) and every result record.

## Coding — complete matrix

Counts are solutions judged correct by reading, including named-algorithm adherence. No generated code was executed. Markdown fencing alone does not fail an otherwise correct function.

| Method | 32 steps | 64 steps | 128 steps |
| --- | --- | --- | --- |
| Confidence-guided; no Viterbi | 1/10 | 1/10 | 2/10 |
| Conditional + diffusion probability | 1/10 | 1/10 | 2/10 |
| PMI + diffusion probability | 1/10 | 2/10 | 2/10 |
| Conditional + path margin | 1/10 | 1/10 | 2/10 |
| PMI + path margin | 1/10 | 1/10 | 1/10 |

One additional PMI/diffusion/128 answer gives correct index-or-minus-one results using linear `in`/`list.index` instead of binary search. Counting only return behavior gives **3/10** for that configuration, which was the earlier progress-update number; requiring the named algorithm gives **2/10**. Both are recorded transparently. The conditional-margin/128 setting does produce a proper binary-search loop, but loses flattening relative to the baseline, so its overall total ties.

Every configuration solves even sum. The main extra successes are flattening and that one binary-search loop. Typical failures include `isalnum()` used as a palindrome test, out-of-range Fibonacci indexing, set-based deduplication losing order, missing Counter imports, malformed brackets/indentation, and unfinished comprehensions. Many bad answers end well before 128 tokens, so the cap alone does not explain the coding failures. Import-only defects receive partial credit in the separate 0–3 scores but do not count as fully correct here.

## Prose — balanced 23-question comparison

Cells show **mean manual score / 3** followed by the number of clean answers. Scale: 3 = no material grammar/fluency defect; 2 = localized defects; 1 = multiple conspicuous errors or severe repetition; 0 = mostly incoherent or degenerate output. Full criteria: [REVIEW_PROTOCOL.md](REVIEW_PROTOCOL.md).

| Method | 32 steps | 64 steps | 128 steps |
| --- | --- | --- | --- |
| Confidence-guided; no Viterbi | 0.91 (0/23 clean) | 1.09 (0/23 clean) | 1.91 (4/23 clean) |
| Conditional + diffusion probability | 1.17 (1/23 clean) | 1.52 (2/23 clean) | 2.09 (10/23 clean) |
| PMI + diffusion probability | 1.09 (0/23 clean) | 1.57 (3/23 clean) | 2.39 (11/23 clean) |
| Conditional + path margin | 0.61 (0/23 clean) | 1.22 (1/23 clean) | 1.78 (4/23 clean) |
| PMI + path margin | 1.26 (1/23 clean) | 1.39 (1/23 clean) | 2.00 (5/23 clean) |

Grammatically complete output is not necessarily factually correct. For example, some battery explanations use well-formed sentences to describe the wrong mechanism. Obvious content issues are noted opportunistically, but factual accuracy was not systematically scored. Severe repetition is included as a fluency defect even where individual clauses remain grammatical. Final cutoff at the token cap is recorded separately from internal grammar defects.

Visible completion counts on the same 23 questions:

| Method | 32 steps | 64 steps | 128 steps |
| --- | --- | --- | --- |
| Confidence-guided; no Viterbi | 16/23 | 19/23 | 20/23 |
| Conditional + diffusion probability | 19/23 | 20/23 | 21/23 |
| PMI + diffusion probability | 19/23 | 21/23 | 23/23 |
| Conditional + path margin | 12/23 | 13/23 | 18/23 |
| PMI + path margin | 17/23 | 19/23 | 21/23 |

Completion is a manual visible-text judgment, not a forced-EOS metric. A sentence may end grammatically at token 128 without terminal punctuation; a cap-reaching answer is not automatically marked incomplete. Conversely, unfinished code, trailing fragments, and open quotations can be incomplete before the cap.

## Concrete observations

- Amsterdam at 128 steps: PMI/diffusion and conditional/diffusion produce clean paragraphs. Conditional margin loops “United States” and also gives an incorrect location. Shorter runs frequently duplicate nouns or whole sentences.
- Leaves: no configuration earns a fully clean score. Errors include truncated pigment names, missing verbs after relative pronouns, and recursive “amount of chlorophyll” text.
- Exercise/waste questions: several settings collapse into empty numbering or repeated conjunction/list-item loops. The conditional/diffusion/128 exercise answer is clean, while many alternatives are not.
- Frozen tokens were not revised, and all recorded calls ran the exact requested number of denoising steps. Viterbi profiles report exactly that many selector calls.

## Timing — descriptive only

| Method | Available 128-step runs | Median request seconds | Mean selector ms/step |
| --- | --- | --- | --- |
| Confidence-guided; no Viterbi | 34 | 8.69 | N/A |
| Conditional + diffusion probability | 34 | 10.41 | 11.57 |
| PMI + diffusion probability | 33 | 10.37 | 11.73 |
| Conditional + path margin | 33 | 12.20 | 25.91 |
| PMI + path margin | 33 | 12.26 | 26.02 |

Request time includes hosted allocation/network/queue/rendering effects. Selector time is measured separately with GPU synchronization and includes decoder work, not extra neural-model forwards. Profiling itself adds synchronization overhead. Available counts differ because the quota prevented some 128-step configurations; do not treat the wall-clock numbers as a controlled latency benchmark. Margin mode adds decoder work without a corresponding aggregate quality gain in this test.

## Saved evidence and reproduction

- [All available answers, labeled by configuration](answers_labeled.md)
- [Raw outputs, exact options, status, timings](results.jsonl)
- [Per-answer manual scores and reasons](manual_scores.csv)
- [Manual judgments keyed by prompt and exact output hash](manual_reviews.json)
- [Balanced prose aggregate](balanced_prose_summary.json)
- [All available aggregates with sample counts](summary.json)

Answers were read in sheets with shuffled configuration labels; exact duplicates within a prompt share a recorded judgment. This is an implementer's review in the same session as running the experiment, **not an independent blinded human study**. No external judge model, grammar checker, or execution-based grading was used. Only one baseline seed was tested, and 10 coding tasks are too few to establish a robust one-task advantage.

The experiment is closed at 557 outputs; no further calls are scheduled. For an explicitly requested future extension, the runner is resumable and skips every saved key:

```sh
.venv/bin/python scripts/evaluate_decoding_quality.py
.venv/bin/python scripts/render_decoding_quality_review.py artifacts/bigram/quality_experiment --pending
.venv/bin/python scripts/summarize_decoding_quality.py artifacts/bigram/quality_experiment
```

The runner was stopped after the user chose to base the assessment on the existing results. The original matrix is retained as provenance; its 43 missing keys are intentionally skipped. Any future extension would require generation and manual review of those outputs before reporting a full 30-question comparison.
