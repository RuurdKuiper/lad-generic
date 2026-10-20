# BYOD Viterbi rollout

All three public Spaces are deployed and verified. Each scorer was trained on all 980,000 training responses with the corresponding tokenizer.

Defaults: PMI scoring, diffusion-probability retention confidence, temperature 2, shared top-k/candidate count 16, weight 0.5, minimum count 1, clipping ±2, ending-delay strength 10. EOS/EOT retention delay and early stopping default on. New-token limit, denoising steps, and block length default to 64.

Live checks verified the interface defaults and completed 16-NFE generations with both PMI Viterbi and confidence-guided decoding on each model. The Viterbi metrics confirmed active token changes. Local validation: 126 tests passed, 2 CUDA-only tests skipped.

| Space | Deployment revision |
|---|---|
| [Ruurd/byod-ministral-8b](https://huggingface.co/spaces/Ruurd/byod-ministral-8b) | `a0b71814ab4f21dfb76963ab19f700e8818d7fac` |
| [Ruurd/byod-llama-3.1-8b](https://huggingface.co/spaces/Ruurd/byod-llama-3.1-8b) | `c8fd1efb8ef980a182f93f9f53f7c26c31b4eefd` |
| [Ruurd/byod-qwen2.5-7b](https://huggingface.co/spaces/Ruurd/byod-qwen2.5-7b) | `42f4809f51abcead37fe96eaa38d4b4b137e8119` |

Deployment: `deployment.json`. Native-tokenizer scorer checks: `scorer_validation.json`. Live defaults, outputs and decoding metrics: `hosted_verification.json`.
