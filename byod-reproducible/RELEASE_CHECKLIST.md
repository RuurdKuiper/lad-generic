# Release checklist

Before publishing this folder as its own repository:

1. Choose and add the intended open-source license.
2. Create `RuurdKuiper/BYOD`, or replace that URL in `README.md` and the first
   code cell of `notebooks/train_diffusion.ipynb` with the final repository.
3. Smoke-test each available small-model preset with
   `--mode quick --max-updates 2`; the public notebook intentionally keeps the
   full 25,000-update schedule.
4. Run `pytest -q` in a clean environment.
5. Scan the new repository for secrets and absolute local paths before its
   first commit; do not copy this parent repository's Git history.
6. For anonymous review, replace identifiable repository, dataset, model, and
   Space ownership links with anonymous mirrors.
