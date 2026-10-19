# BYOD arXiv preparation

This is a separate preprint copy of `iclr2027_submission/iclr2027_conference.tex`.
The anonymous ICLR manuscript is unchanged. The alternate manual-edits draft
contains older provisional benchmark results and was not used as the source.

## Build and upload

```bash
python3 prepare.py
```

This builds `paper.pdf`, refreshes `ABSTRACT.txt`, and creates
`dist/arxiv-source.zip`. Upload the ZIP as a TeX/LaTeX submission with `paper.tex`
as the main file and PDFLaTeX as the engine. It includes a regenerated
`paper.bbl`, the bibliography, styles/macros, and the 10 referenced figures.
The manuscript PDF, alternate drafts, internal notes, and build files are
excluded. The archive has only one top-level manuscript.

The adapted `byod_preprint.sty` retains the single-column layout, displays
authors, labels the header "Preprint", and removes review line numbers. Author
names, affiliations, and contact email follow the details supplied by the author.
There is no claim of ICLR acceptance. Numerical results are unchanged. Appendix floats were allowed to sit beside
their descriptions, unnecessary page breaks were removed, and trajectory panels
were enlarged, producing a 21-page preprint.

Public code wording now links `https://github.com/RuurdKuiper/BYOD`. The recipe
uses the confirmed 0.9/0.1 answer/padding loss; the training table now correctly
distinguishes padding multiple 8 for Llama and 16 for the other presets. See
`../byod-reproducible/REPRODUCIBILITY.md` for the historical configuration note.

## Submission metadata

Use `ABSTRACT.txt` and `submission_metadata.json` to populate the form. The
repository URL is the intended destination: **publish the prepared standalone
repository before submitting this code-availability statement to arXiv**.
The code's MIT license is separate from the distribution license you choose for
the paper. Leave journal reference and DOI empty until an actual publication.
Inspect arXiv's generated PDF before finalizing the submission.

## Category and endorsement

Recommended primary category: **cs.LG**, because the contribution is a model
training/conversion method. **cs.CL** is also relevant for language modeling.
The arXiv taxonomy says cs.AI excludes machine learning and NLP, which have their
own categories. Select the appropriate category in your draft and check whether
arXiv requests further endorsement. Do not choose cs.AI solely because it is
the category for which you currently have endorsement.

Official references checked for this preparation:

- https://arxiv.org/category_taxonomy
- https://info.arxiv.org/help/endorsement.html
- https://info.arxiv.org/help/submit_tex.html
- https://iclr.cc/Conferences/2027/AuthorGuidelines

ICLR permits arXiv posting during review; retain anonymity in the ICLR copy.

## Before submitting

- Publish the clean BYOD checkout following its `RELEASE_CHECKLIST.md`.
- Open the repository, Colab notebook, demos, and dataset links while logged out.
- The code pins `Ruurd/LAD-training-1m-256`; the manuscript also links its public
  `Dovelove/BYOD-training-1m-256` mirror. All five Parquet hashes match, and the
  public 100-question suite matches the bundled prompts in order. Evidence is in
  `../byod-reproducible/reference/public_artifacts.json`.
- Confirm the paper's distribution license with all authors and complete any
  requested category endorsement.
