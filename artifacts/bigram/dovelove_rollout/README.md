# Dovelove BYOD rollout

All four Spaces are deployed and verified with PMI Viterbi and model-specific full-corpus scorers.

The interface hides the ending-delay control (fixed default 10), checkpoint path, seed and decoding measurements. The reproducibility accordion and the quoted Viterbi/weight explanations are removed. API evaluation overrides remain available. Existing repository-link preferences and visitor counters are preserved.

Live checks confirmed the hidden defaults and completed baseline and Viterbi inference on each Space (8 successful calls). Local checks: 126 passed; 2 CUDA-only checks skipped.

| Space | Revision |
|---|---|
| [Dovelove/byod-llama-3.1-8b](https://huggingface.co/spaces/Dovelove/byod-llama-3.1-8b) | `82b1a9eeaf574264ef0747711b779c395942b3b1` |
| [Dovelove/byod-ministral-8b](https://huggingface.co/spaces/Dovelove/byod-ministral-8b) | `0dbf9aa8fc15699d25e7141369fd28aba2de8edf` |
| [Dovelove/byod-qwen2.5-7b](https://huggingface.co/spaces/Dovelove/byod-qwen2.5-7b) | `a4fa1b03d230eaa8f5cb5623f81c145dd18583c4` |
| [Dovelove/byod-gemma-2-9b](https://huggingface.co/spaces/Dovelove/byod-gemma-2-9b) | `7ad959e3b8102fffa77a11c8ffe65fa74a101963` |
