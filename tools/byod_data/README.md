# Local BYOD dataset maintenance

These tools maintain the published datasets and are intentionally excluded from
the standalone BYOD repository. Run them from the main research checkout after
installing `byod-reproducible` and setting `HF_TOKEN` in its `.env` (or the shell).

```bash
python tools/byod_data/build_training_dataset.py --help
python tools/byod_data/publish_tokenized_data.py --help
```

`prepare.py` retains the offline tokenization pipeline. Published profiles are
consumed directly by the reproducible training package. The local release
exporter remains `python byod-reproducible/prepare_release.py`.
