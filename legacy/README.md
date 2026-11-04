# Historical experiments

These files preserve the original Colab experiments and LAD inference app.
For the BYOD paper implementation, use
[`byod-reproducible/`](../byod-reproducible/README.md).

- `llama_loratrained_instructiontuning.ipynb`: original training notebook.
- `llama_loratrained_instructiontuning_mdlm.py`: Colab-exported MDLM notebook.
  The identical copy formerly at the repository root was removed during cleanup.
- `training/llama_loratrained_instructiontuning_3b_512lora.py`: earlier Colab
  training export.
- [`inference/`](inference/README.md): historical LAD inference app.

The training `.py` exports contain notebook commands such as `!pip install`;
they are archival notebook sources and cannot be run directly as Python scripts.
