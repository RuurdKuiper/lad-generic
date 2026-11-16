# Qwen AR GSM8K / HumanEval investigation

Status: the targeted A100 probe isolated the eager-versus-SDPA backend as the trigger for the tested failures. A corrected SDPA evaluation is now running separately; do not use the original campaign's new Qwen AR answers as final results. The initial CPU inspection below predates this GPU probe.

## Verified backend correction

Probe job [6af15e38e6320c66fad7e2b4](https://huggingface.co/jobs/Ruurd/6af15e38e6320c66fad7e2b4) completed on A100, Torch 2.8.0+cu128 / Transformers 4.57.6 / PEFT 0.20.0. Kept the same pinned model, BF16, greedy decoding, output limits and repetition penalty 1.05 while changing the attention backend.

- Eager exactly reproduces the original campaign's saved bad texts for GSM8K indices 127/128 and HumanEval 95/98 (4/4).
- SDPA corrects all four of those answers (4/4). This is a selected diagnostic set, not an unbiased accuracy estimate.
- On historical GSM8K indices 0/1, SDPA exactly reproduces both historical texts. On HumanEval 0/1 it retains both correct scores, with exact historical text for index 0.
- A separate SDPA/penalty-1.0 variant was diagnostic only. The fix retains 1.05; do not conflate the attention change with a changed repetition penalty.

This establishes a useful operational fix for this model/runtime; it does not establish the underlying kernel-level numerical mechanism or prove all eager implementations fail. `worker.py` now selects SDPA for Qwen AR, explicitly pinned in the corrected model specification. Other native AR loaders retain their previous backend.

The immutable original campaign is not patched in place. A separate [correction cohort](CORRECTIONS.md) invalidates all newly generated non-HumanEval Qwen AR outcomes from the eager cohort for final reporting, regardless of whether each was correct, and replaces them under SDPA. Historical outputs require a new AR replay gate. HumanEval remains deferred at the author's request: its confirmed fix is implemented, but its affected scores are still provisional pending a future corrected rerun.

The corrected worker has subsequently passed its complete 16-question historical AR replay gate: **16/16 correctness matches, 13/16 exact text matches**. Its first eight new corrected answers have been saved. This supports reuse of the selected historical Qwen cohort under the corrected protocol; it does not imply bitwise reproduction for every historical answer.

Snapshot: private dataset revision `bc90f69561df2ea566fb1efbc6afae517d5eefeb`; individual prompts/outputs are retained in ignored `qwen_diagnostic/sample_inspection.json`. Inspection script: `inspect_qwen_samples.py`. Generated code was parsed, not executed locally.

| Task | Historical correct / evaluated | Newly generated correct / evaluated | Combined |
| --- | --- | --- | --- |
| GSM8K | 115 / 125 (92.00%) | 23 / 86 (26.74%) | 138 / 211 (65.40%) |
| HumanEval | 83 / 95 (87.37%) | 27 / 69 (39.13%) | 110 / 164 (67.07%) |

These are different questions in the historical and added subsets, not a matched replay comparison. HumanEval's historical denominator is 95 available reusable predictions, not 125. The observed drop alone cannot distinguish a harder subset from a changed runtime/protocol.

## Individual outputs and scoring

- GSM8K index 127 changes the question's 50 friends and 20 more into 55 and 2 more. Index 128 changes intermediate products and then sums different values. These are errors in generated reasoning, not merely answer extraction.
- All 86 added GSM8K outputs contain a `####` answer. Independent rescoring agrees with all stored correctness flags. No incorrect score concealed an exact correct extracted final answer.
- HumanEval/95 assigns `upper_case = set`, then calls `.add`, rather than creating a set instance. HumanEval/96 uses `num**0` in the primality check. HumanEval/98 refers to an undefined singular variable instead of the defined plural name.
- 10 of the 69 added HumanEval outputs contain syntax errors after applying the same code extractor used for evaluation. Other failures include valid Python with incorrect algorithms or undefined variables. Syntax validity alone is not a correctness test.
- Neither task has an output near the 1,024-token output limit (lengths measured by retokenizing saved decoded text; exact generated token counts were not stored). Truncation does not explain these examples.

## Protocol checks

- Current Qwen AR is the native `Qwen/Qwen2.5-7B-Instruct` model, pinned to `a09a35458c702b33eeacc393d103063234e8bc28`, BF16, greedy decoding, cache enabled, 1,024 output tokens.
- All 414 frozen GSM8K/HumanEval prompts produce identical chat-template token IDs with the original saved Qwen tokenizer and the current pinned base tokenizer. This rules out a tokenizer/template mismatch for these inputs.
- Historical AR evaluation used the diffusion session with the adapter disabled and original normalization weights restored. The current worker loads the native AR model directly. The original Qwen initial and trained normalization-state files contain identical tensors; this does not itself establish equality to every tensor in the current base revision.
- A concrete implementation difference exists: the current native AR loader explicitly selects eager attention; the historical loader did not explicitly select it. Historical package versions, base commit and attention backend were not fully recorded. Eager versus SDPA is a candidate to test, not a confirmed cause.
- Current base generation configuration contains repetition penalty 1.05. The explicit generation call does not override it. Historical AR calls also did not override it; the historical effective value was not logged. There is no evidence yet that this setting changed.
- The campaign's historical replay gate currently applies to diffusion models only. Consequently, Qwen AR has no same-question replay establishing historical runtime agreement. Passing the Qwen diffusion gate would not establish AR agreement.

## Required next diagnostic before using the score as final

At a controlled GPU opportunity, rerun a small fixed selection of both old and added questions, preserving full generated text and effective generation configuration. First reproduce the current native eager setup. Then change only the attention backend to SDPA on the same questions. If needed, compare the historical adapter-disabled loading path and inspect base norm tensors. Do not infer a fix simply because a configuration scores higher: verify the intended causal AR protocol and compare matched outputs. Keep the current raw predictions and label replacements explicitly; do not silently overwrite them or alter settings in the running immutable campaign.

Add an AR replay/protocol diagnostic to the next reviewed campaign revision, retaining actual replay text rather than only match booleans. If a runtime defect is confirmed, invalidate and rerun all affected new Qwen AR questions under the corrected documented protocol, retaining historical results only where compatible. Additional GPU diagnostics must be accounted for within the campaign budget.
