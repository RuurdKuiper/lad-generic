# BYOD-Gemma illustrative denoising GIF

This is a selected example from multiple generation attempts, **not a
representative performance evaluation**. The model output is unedited.
The selected run used the ordinary system prompt, seed 303, BG + TG Viterbi
(Gumbel), temperature 0.3, top-k 16, a 128-token canvas, and a 64-step budget.
It produced 73 visible tokens in 37 steps, with early stopping enabled.

Only four files are retained:

- `byod-gemma-denoising.gif`: the published illustration.
- `capture.json`: exact request settings, Space revision, final answer, and all
  original streamed HTML frames for this run.
- `provenance.json`: selection disclosure, rendering settings, and checksums.
- This README.

Rejected attempts, obsolete batch settings, duplicate renders, and redundant
PNG/text exports were removed. The earlier system-guided example is historical
material inside the [research archive](../../archives/README.md). Playback is
slowed for readability and does not represent inference latency.

Recreate the animation from its saved frames, without invoking the model:

```sh
pip install -e '.[media]'
python scripts/render_byod_daily_gif.py artifacts/byod_daily_gif/capture.json \
  --output /tmp/byod-gemma-denoising.gif
```

Optional `--sidecars` exports the final PNG, answer text, and render metadata.
New captures default to `/tmp/byod-gif-captures`, away from the selected example.
