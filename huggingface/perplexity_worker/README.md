---
title: Private perplexity experiment
emoji: 📊
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 5.49.1
python_version: "3.12"
app_file: app.py
startup_duration_timeout: 1h
---

Temporary private worker measuring standalone-answer token-pooled perplexity
with the frozen Microsoft Phi-4 reference model, NF4 quantization and BF16 compute.
Answers are returned to the caller with their summed NLL and scored token counts.

Set the Space variable `REFERENCE_REVISION` to the exact reference-model commit
before starting the worker. The saved experiments used
`2db69c1c3e91a05d2c64a3185acfbaf36f744e25`. Keep the Space private; its dependencies
are listed in `requirements.txt`. Run generation and scoring separately with
`scripts/evaluate_quick_perplexity.py`; saved manifests record the reference
revision and quantization. No prompt is included in the reference context, and
the first token of each answer is unscored.
