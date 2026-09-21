# Release checklist

Before publishing this folder as its own repository:

1. Choose and add the intended open-source license.
2. Create `RuurdKuiper/BYOD`, or replace that URL in `README.md` and the first
   code cell of `notebooks/train_diffusion.ipynb` with the final repository.
3. Run the Colab once in `quick` mode for each base-model family whose license
   you have accepted.
4. Run `pytest -q` in a clean environment.
5. Scan the new repository for secrets and absolute local paths before its
   first commit; do not copy this parent repository's Git history.
6. For anonymous review, replace identifiable repository, dataset, model, and
   Space ownership links with anonymous mirrors.

