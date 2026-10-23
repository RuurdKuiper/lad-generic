# Expanded BYOD bigram/trigram rollout

All eight BYOD Spaces now use expanded, tokenizer-specific scorers. The smaller-corpus rollout is retained as historical evidence in `../byod_simple_rollout/`.

## Training corpus

Count training ran locally on CPU using cached source files; smoke generation ran on the hosted Hugging Face Spaces.

Each model uses all 980,000 original response documents plus exactly 800,000,000 added tokens, measured with its own tokenizer: 720M FineWeb-Edu, 40M Python-Edu and 40M FineMath. Source revisions are pinned; raw-source texts are deduplicated within each source and counts never cross document boundaries. Original responses keep their original EOS/truncation policy. The last added document can be truncated to meet the exact budget.

All bigram counts are retained. Trigrams retain count >=2, including count two; compact prefix totals include singleton contributions. PMI uses successor-token marginals. Trigram backoff is 50, minimum count two, clip +/-2 and relative weight 0.5.

| Model | Original tokens | Total tokens | Retained trigrams | BG MiB | TG MiB |
|---|---:|---:|---:|---:|---:|
| gemma | 73,467,371 | 873,467,371 | 61,224,918 | 524.7 | 838.5 |
| llama | 71,088,258 | 871,088,258 | 67,229,715 | 502.5 | 910.4 |
| qwen | 72,705,486 | 872,705,486 | 64,834,514 | 481.7 | 877.7 |
| ministral | 73,214,218 | 873,214,218 | 64,568,580 | 462.2 | 872.4 |

Exact source files, counts, tokenizer fingerprints and checkpoint hashes are in `../byod_expanded_ngrams/<model>/complete.json`. Corpus additions use the same pinned sources and 90/5/5 mix as the expanded LLaDA scorer; each tokenizer reaches its own token budget, so final document cutoffs differ.

## Deployment

Each account owns its own scorer repositories. Spaces pin immutable asset revisions, avoiding the Space per-file size limit. Config updates and removal of superseded small expanded files occur atomically. Legacy `bigram.pt` remains. Asset hashes were checked after upload. `huggingface/byod_ngram_assets.json` preserves pins for future ordinary republishes.

Model weights, backend, identity, links, hardware, secrets and generation settings were preserved. The interface remains Confidence-guided / BG + TG Viterbi (Gumbel), temperature 0.7, top-k 16, bigram weight 1, ending-delay strength 10, with APD, early stopping and EOS retention available.

| Space | Live revision | Asset revision |
|---|---|---|
| [Ruurd/byod-gemma-2-9b](https://huggingface.co/spaces/Ruurd/byod-gemma-2-9b) | `7874a818b36345ece4f92ee709ac7bc701eecb94` | `625b95fa1e62e0a2ef588290b22717329029e140` |
| [Dovelove/byod-gemma-2-9b](https://huggingface.co/spaces/Dovelove/byod-gemma-2-9b) | `1e9f8ca749a1ed4f7aadba8ec88d7fa74d3254b4` | `b4b9fd91ea8d619ae8ff7885c43be547cee4f671` |
| [Ruurd/byod-llama-3.1-8b](https://huggingface.co/spaces/Ruurd/byod-llama-3.1-8b) | `4d5a22c6482b3e90f1e343fe700830c776395b1c` | `6063da3df9412f0becd6ed553c0025c42ee3c00c` |
| [Dovelove/byod-llama-3.1-8b](https://huggingface.co/spaces/Dovelove/byod-llama-3.1-8b) | `e3bff44190a76599423362d6e0f5122a0d594d40` | `f1c078f191f5dc0993d95e67d47049c6049b7f76` |
| [Ruurd/byod-ministral-8b](https://huggingface.co/spaces/Ruurd/byod-ministral-8b) | `ecbdae84af42161f686472f42978d1002e080342` | `14b72d85ad9f1a3a74943940825cdcfdb949086c` |
| [Dovelove/byod-ministral-8b](https://huggingface.co/spaces/Dovelove/byod-ministral-8b) | `f53b664e54c7b3b3e7454946d72ad42888b2f8ef` | `2b7712df6e6c6840a14e71acfc0bc0a1adbe1879` |
| [Ruurd/byod-qwen2.5-7b](https://huggingface.co/spaces/Ruurd/byod-qwen2.5-7b) | `65b932bfa607d5718f1fb8c25b11d2dacca1e277` | `f7be5ddf9d04208cd648e754aa897ad295096df4` |
| [Dovelove/byod-qwen2.5-7b](https://huggingface.co/spaces/Dovelove/byod-qwen2.5-7b) | `1678cf910234c98c8dee70de3997d977273d972f` | `6b96a74bb01b25f3edd06da83c25048c7314cc6f` |

## Verification

- 88 local checks passed; 6 CUDA-only tests skipped (83 decoding/interface tests, one source-counting test and four publisher tests).
- All four expanded pairs have matching tokenizer/vocabulary/token-count metadata, verified integer count totals and finite clipped correction queries.
- All eight Spaces are RUNNING at their new commit, with preserved configuration and the same two-method interface.
- Both methods were exercised on every Space: 16 short smoke generations, 16 output positions and two denoising steps each. Every call used exactly two denoising forward passes and left no unresolved masks.

These are deployment/correctness checks, not a generation-quality study or matched speed benchmark. `hosted_verification.json` records texts and timings; cold downloads happen at startup, outside timed GPU inference. `deployment.json` records before/after configuration, asset hashes and rollback revisions.
