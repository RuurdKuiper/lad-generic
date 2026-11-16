"""Build FP8 bindings on inexpensive CPU hardware, without renting a GPU."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import site
import time


def main():
    from huggingface_hub import HfApi

    started = time.monotonic()
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                    "ninja", "packaging", "wheel", "pybind11", "transformer-engine[core-cu12]==2.13.0"], check=True)
    import torch

    if not torch.__version__.startswith("2.8.0") or torch.version.cuda != "12.8":
        raise RuntimeError("The compiled wheel must target the pinned Torch 2.8 / CUDA 12.8 image")
    os.environ.update(MAX_JOBS="4", NVTE_FRAMEWORK="pytorch", NVTE_CUDA_ARCHS="120", TORCH_CUDA_ARCH_LIST="12.0")
    # PyTorch's pip CUDA libraries ship cuDNN headers outside CUDA_HOME.
    # Expose them to the extension compiler in this otherwise identical image.
    includes = [str(path.parent) for root in site.getsitepackages()
                for path in Path(root).glob("nvidia/cudnn/include/cudnn.h")]
    if not includes:
        raise RuntimeError("cuDNN development headers were not found in the pinned image")
    os.environ["CPATH"] = os.pathsep.join(includes + [os.environ.get("CPATH", "")])
    libraries = [str(Path(path).parent / "lib") for path in includes]
    os.environ["LIBRARY_PATH"] = os.pathsep.join(libraries + [os.environ.get("LIBRARY_PATH", "")])
    wheels = Path("/tmp/rank-wheels")
    wheels.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps",
                    "transformer-engine-torch==2.13.0", "--wheel-dir", str(wheels)], check=True)
    wheel = next(wheels.glob("transformer_engine_torch*.whl"))
    manifest = {
        "wheel": wheel.name, "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "torch": torch.__version__, "cuda": torch.version.cuda,
        "python": sys.version, "build_seconds": time.monotonic() - started,
        "architecture": "SM120", "image": os.environ["RANK_IMAGE"],
    }
    (wheels / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], check=True, text=True, capture_output=True).stdout
    (wheels / "build-requirements.txt").write_text(freeze)
    api = HfApi()
    if not api.dataset_info(os.environ["RANK_REPO"]).private:
        raise RuntimeError("Runtime artifacts must remain private")
    commit = api.upload_folder(repo_id=os.environ["RANK_REPO"], repo_type="dataset", folder_path=wheels,
                               path_in_repo="runtime", commit_message="Build pinned CUDA-12.8 FP8 wheel on CPU")
    print(json.dumps({"status": "runtime_ready", "revision": commit.oid, **manifest}), flush=True)


if __name__ == "__main__":
    main()
