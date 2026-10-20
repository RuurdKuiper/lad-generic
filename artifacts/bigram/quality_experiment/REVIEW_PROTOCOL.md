# Manual decoding comparison

600 planned responses: 10 short Python assignments and the first 30 shared open-ended prompts, each under five decoders and 128/64/32 denoising steps. One seed (42), one 128-token block, no early stopping. Full inputs and exact Space revision are in manifest.json. Generated answers are in results.jsonl. No model deployment or training changes are part of this experiment.

The requested baseline samples at temperature 1 and top-k 16. Viterbi is deterministic and uses its own 16 candidates; temperature/sampling top-k do not change its selection. Thus this compares the requested practical configurations, not an isolated bigram-scoring ablation. Ending retention delay is on for prose and off for code; the fading bigram ending penalty is 1000 for prose and disabled (strength 1) for code. The baseline has no bigram prediction penalty.

## Review criteria

Review every response by reading it. Exact duplicates for the same prompt may share a judgment, with this recorded explicitly. Do not call an external judge model. Do not use a grammar checker or code execution pass rate as a substitute for reading.

Coding correctness (0–3): 3 = valid Python meeting the requested contract, including stated edge cases; 2 = mostly useful with a minor defect; 1 = substantial syntax/logic error but recognizable approach; 0 = unusable or irrelevant. Markdown fences alone do not make code incorrect. Flag incomplete code separately, including truncation at the 128-token cap.

Prose grammar (0–3): 3 = grammatical with no material errors; 2 = isolated grammar/syntax problem; 1 = multiple conspicuous errors or broken sentence structure; 0 = mostly incoherent. Do not penalize factual mistakes as grammar. Assess the visible sentences and flag a final cutoff separately; malformed or repetitive wording within the answer still counts. A fragment that constitutes the entire answer cannot pass solely because it is short.

Excuse an unfinished final sentence as a budget cutoff only when the status shows all 128 visible tokens. Earlier unfinished endings remain output errors.

Record completion/truncation and a short specific reason alongside every score. Compare mean scores, fully correct/grammatical proportions, and completion rates by method and step count. Treat these as exploratory judgments from one small prompt set and one baseline seed, not statistical proof. More steps can change the whole trajectory, so performance need not be monotonic.

Coding sensitivity check: also report strict_full_score excluding any behaviorally correct answer that substitutes a different named algorithm. One binary_search answer uses linear membership/index lookup; it meets index-or-minus-one behavior but is not a binary-search implementation. Record both counts transparently rather than silently changing an earlier score.
