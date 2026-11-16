# Check against the long-form reviewer responses

Counts include spaces, newlines, Markdown and URLs. Each short file is below 5,000 Unicode characters and 5,000 UTF-16 code units. The three long-form files are unchanged.

## mNeh

Retained: the LAD objective/family distinction and separate-protocol Table 5; ranks 128/512/1024/2048, Llama parent, A100 batch/memory choices, rank cost and diminishing per-unit returns; exploratory module/MLP/rate tests; expanded question counts and scoring corrections; all ten literature links; Table 3/Appendix D uncertainty reporting; Gemma/LLaDA scores, paired interval, selection/multiple-comparison caveats, model-size/history differences and the low-cost conversion argument. Both questions are answered, with cross-references replacing repetition.

Qualification: the long-form W2 says the result is not significant after accounting for multiple testing, while Q2 says the interval is unadjusted. The short file consistently states that it is unadjusted and makes no superiority claim; it does not imply an adjusted significance test was performed.

Tone: acknowledges the concern while defending the objective and cross-family contribution; keeps the reporting-convention argument and willingness to report uncertainty.

## dPsL

Retained: all three weakness replies and three question replies; LAD attribution, missing matched controls and Appendix B context; rank settings, hardware, validation-only evidence and exploratory-test limits; coverage and outcome counts; MATH/Gemma/Qwen corrections; all ten reporting-convention links and the note about counts elsewhere; paired scores/interval and selection caveats; MMLU-Pro budget rationale and the reported lack of cut-short answers; math/code task scores; conversion times, LLaDA pretraining hours and hardware/prior-training caveats; perplexity gap; untested merged-model fine-tuning; unequal output limits; diagnostic-only right-context copying and missing practical infilling/latency evaluation.

Condensed: repeated details in questions now refer to the corresponding weakness replies. The awkward description of model families as hyperparameters is expressed as prioritizing cross-family tests over a full sweep.

Tone: keeps the practical contribution, the reporting-convention defense, and candid limits; does not add an inference-speed, superiority or optimal-rank claim.

## fC22

The latest rewrite uses full sentences and explicit score comparisons. It retains the six weakness replies and three question replies, with brief reviewer excerpts. Repeated Response labels were removed to leave room for prose.

Retained: expanded coverage and outcome counts; MATH rescoring and regenerated Gemma/Qwen results; Wilson and paired bootstrap methods; both mean comparisons and intervals; multiple-comparison and selection caveats; model-size/history caveats; corrected intermediate scores and counts; the argument that uncertainty reporting is uncommon; instruction-tuned parents and examples of benchmark-training exposure; the 19% mixture share, prompt filtering, task-format confound and matched AR control; indicative retention after 400,000 example presentations; LAD attribution and the cross-family, mask-only contribution; the missing matched LAD control; all four ranks, adapter cost, validation-loss trade-off and exploratory settings; same-position reconstruction and missing alignment/weight ablations; untested merged-model training; open-generation budgets and metrics, the corrected perplexity claim and missing reduced-NFE task evaluation; mathematics/code comparisons, conversion costs and pretraining/hardware caveats; missing latency measurements and the limits of merging; the sequence-length mismatch and difficulty/truncation confounds.

Condensed or omitted supporting detail: full literature URLs and citation locations; seven of the ten paper names in the uncertainty-reporting example list; the Qwen base/Instruct numerical example; the detailed Dream/Tülu/FLAN source chain and RL/SFT distinction; A100 memory/batch-size figures; the arithmetic example for rank increments; names and task lists from the reduced-NFE literature comparison; dynamic-padding details; and repeated statistics in the question replies. These remain in the long form. The short version preserves the main arguments but is not information-complete.

Tone check: the reply remains appreciative, defends useful conversion across four families, keeps the reporting-convention argument, and treats retention as indicative. It acknowledges missing controls, imperfect generation, unmeasured latency and unresolved length effects without claiming optimal settings, model superiority or inference acceleration. The readability rewrite does not introduce new experiments or results.
