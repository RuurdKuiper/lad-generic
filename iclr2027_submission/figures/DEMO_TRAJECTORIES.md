# BYOD-Gemma trajectory panels

The panels are generated from the final live-denoising state returned by the
public BYOD-Gemma-2-9B Space. Regenerate all five from the repository root with:

```bash
python scripts/capture_demo_trajectories.py
```

The script uses the default prompt and leaves every unspecified control at its
demo default. It writes these exact files:

| File | Steps | Tokens | Remasking | Coloring |
|---|---:|---:|---|---|
| `demo_gemma_random_64steps_64tokens_iteration.png` | 64 | 64 | Random | Prediction iteration |
| `demo_gemma_confidence_64steps_64tokens_iteration.png` | 64 | 64 | Confidence-guided | Prediction iteration |
| `demo_gemma_confidence_64steps_64tokens_probability.png` | 64 | 64 | Confidence-guided | Prediction probability |
| `demo_gemma_confidence_32steps_64tokens_probability.png` | 32 | 64 | Confidence-guided | Prediction probability |
| `demo_gemma_confidence_16steps_64tokens_probability.png` | 16 | 64 | Confidence-guided | Prediction probability |

The LaTeX source detects these files automatically. If a panel is absent, its
appendix position is rendered as an explicit placeholder.

All captures use a block length equal to the new-token canvas and disable early
stopping. Delayed EOS/EOT retention remains at its demo default.
