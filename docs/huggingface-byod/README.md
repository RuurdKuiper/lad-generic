# Hugging Face BYOD announcement

Published under the Ruurd account as an author post at
<https://huggingface.co/papers/2610.41574#6ae88d732c4b59d1b5205872>.
The post now contains the full `article.md`, with its first heading changed to
level two. The original arXiv abstract remains unchanged above the post.

- `article.md`: short blog article, with the Colab workflow, all seven Ruurd generation demos, and three paper visuals.
- `paper-post.md`: the previous, shorter author comment, retained as an alternative.
- `preview.html`: local preview of the published article and shorter alternative using bundled PNG figures.
- `figures/`: publication figures suitable for upload to the Hugging Face editor.

Both Markdown files use verified public arXiv image URLs and can be pasted without uploading assets. If the editor does not display an external SVG, upload the corresponding bundled PNG and replace that image URL.

## Publish

For the blog, sign in as Ruurd at <https://huggingface.co/new-blog>, select the Ruurd namespace, use the first heading as the title, and paste the rest of `article.md` into the body.

The example supplied in the request is an author comment under a paper, rather than a standalone blog. `article.md` is now published in that format under Ruurd. Edit the existing comment for future updates rather than posting it again. No separate blog article has been published.

The arXiv citation is present on the four Ruurd BYOD Spaces, four Ruurd BYOD models, and the Ruurd/LAD-training-1m-256 and Ruurd/BYOD-tokenized-256 datasets. All ten artifacts are linked on the paper page. The citation was removed from the four Dovelove Space READMEs to preserve anonymous review presentation; old Git revisions still contain it. Local model and Space publishing templates omit the citation for anonymous releases and the Dovelove namespace. The citation used is:

```markdown
Paper: [BYOD: Build Your Own DLM — Efficient Autoregressive-to-Diffusion Language Model Conversion](https://arxiv.org/abs/2610.41574)
```

The article was published using Hugging Face's official paper comment API, including three embedded paper figures, the direct Colab link, and all seven Ruurd generation demos. No connected Hugging Face article-publishing plugin was found.

Ruurd's authorship is now verified. The main paper-page buttons link to the GitHub repository and the Colab notebook. The separate Daily Papers media gallery has not been changed; the three figures are embedded in the article below the abstract. Verification confirmed the abstract and title are unchanged, the published article matches the source, and all three figures are rendered as image elements. See `artifacts/byod_paper_page/article-update.json` for the publication record.

## Sources and figure provenance

- Published v1: <https://arxiv.org/html/2610.41574v1>.
- Training workflow: public <https://github.com/RuurdKuiper/BYOD> README and notebook.
- Colab: <https://colab.research.google.com/github/RuurdKuiper/BYOD/blob/main/notebooks/train_diffusion.ipynb>.
- Figure 1: `benchmark_radar_panels.png`, copied from the repository’s paper figure export. Its corresponding PDF is byte-identical to `arxiv_submission/figures/benchmark_radar_panels.pdf`.
- Figure 3: `open_generation_budget.png`, same provenance and PDF identity check.
- Figure 7(a): `demo_gemma_confidence_64steps_64tokens_probability.png`, copied directly from `arxiv_submission/figures/`.
- Publishing instructions: <https://huggingface.co/docs/hub/blog-articles>.

Claims preserve the paper’s matched-harness comparison and acknowledge the open-generation quality gap. The article distinguishes paper-mode GPU requirements from quick-mode experiments, and identifies newer demo decoding options as outside the paper’s evaluated settings. No claim of faster wall-clock inference or free-Colab reproduction is made.
