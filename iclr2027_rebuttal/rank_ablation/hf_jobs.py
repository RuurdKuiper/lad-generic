"""Stage the rank study and submit jobs within the author's $42 total cap."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = "Ruurd/iclr2027-rank-ablation"
IMAGE = "pytorch/pytorch@sha256:a7103283ea7113e10ae5d014bd2342acebda0bc53164b2f7b1dd6eb7a766bdb6"
CAP = 42.0
GPU_SECONDS = 14 * 3600
CPU_SECONDS = 3600
RATES = {"cpu-upgrade": .0005, "rtx-pro-6000": .045833}
LEDGER = HERE / "budget_ledger.json"


def rank1024_timeout(state):
    """Respect the additional $17 allowance and the original total ceiling."""
    accounted = sum(job.get("cost_upper_usd", job["reserved_usd"]) for job in state["jobs"])
    prior_1024 = sum(job.get("cost_upper_usd", job["reserved_usd"]) for job in state["jobs"]
                     if job["role"] == "training-1024")
    available = min(17.0 - prior_1024 - 2.0, CAP - accounted - 2.0)
    seconds = min(5 * 3600, max(0, math.floor(available / RATES["rtx-pro-6000"]) - 1) * 60)
    if seconds < 4 * 3600:
        raise RuntimeError("Remaining allowance does not safely fit the measured rank-1024 training time")
    return seconds


def validate_controlled_recipe():
    """The new control may change only rank, alpha and its own output path."""
    import yaml

    baseline = json.loads((HERE / "controlled_recipe.json").read_text())
    for name, expected in baseline["scientific_code_sha256"].items():
        path = ROOT / "src" / Path(name).relative_to("code")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Scientific source differs from the other three ranks: {name}")
    config = yaml.safe_load((HERE / "configs/rank_1024.yaml").read_text())
    assert config["lora_r"] == config["lora_alpha"] == 1024
    excluded = {"lora_r", "lora_alpha", "output_dir"}
    for rank in (128, 512, 2048):
        other = yaml.safe_load((HERE / f"configs/rank_{rank}.yaml").read_text())
        if {k: v for k, v in config.items() if k not in excluded} != {k: v for k, v in other.items() if k not in excluded}:
            raise RuntimeError(f"Rank-1024 recipe differs from rank {rank}")
    for name, expected in baseline["unchanged_benchmark_files"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Benchmarked manuscript/report changed during rank-study setup: {name}")


def save(value):
    LEDGER.write_text(json.dumps(value, indent=2) + "\n")


def stage(api):
    bundle = HERE / "bundle"
    bundle.mkdir(exist_ok=True)
    if (HERE / "controlled_recipe.json").is_file():
        validate_controlled_recipe()
    for name in ("run_training.py", "build_runtime.py", "batch_worker.py", "single_rank_worker.py", "requirements.txt", "controlled_recipe.json"):
        source = HERE / name
        if source.exists():
            shutil.copy2(source, bundle / name)
    shutil.copytree(HERE / "configs", bundle / "configs", dirs_exist_ok=True)
    shutil.copytree(ROOT / "src/diffusion_lm", bundle / "code/diffusion_lm", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    for path in bundle.rglob(".DS_Store"):
        path.unlink()
    files = {path.relative_to(bundle).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in bundle.rglob("*") if path.is_file() and path.name != "source_manifest.json"}
    (bundle / "source_manifest.json").write_text(json.dumps(files, indent=2) + "\n")
    api.create_repo(REPO, repo_type="dataset", private=True, exist_ok=True)
    if not api.dataset_info(REPO).private:
        raise RuntimeError("Refusing public artifact repository")
    commit = api.upload_folder(repo_id=REPO, repo_type="dataset", folder_path=bundle, path_in_repo="input",
                               commit_message="Stage immutable $42 Llama rank study sources and configs",
                               delete_patterns=["input/**/.DS_Store"])
    state = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"cap_usd": CAP, "jobs": []}
    state.update(repo=REPO, input_revision=commit.oid, image=IMAGE)
    save(state)
    print(json.dumps({"repo": REPO, "revision": commit.oid, "source_files": len(files)}))


def launch(api, phase):
    from huggingface_hub import get_token
    from huggingface_hub.utils import get_session

    state = json.loads(LEDGER.read_text())
    if state.get("pending_launch"):
        raise RuntimeError("A launch has an unresolved receipt; reconcile it before spending more")
    role = "build" if phase == "build" else ("training-1024" if phase == "rank1024" else "training")
    flavor, seconds = ("cpu-upgrade", CPU_SECONDS) if phase == "build" else ("rtx-pro-6000", GPU_SECONDS)
    previous = [job for job in state["jobs"] if job["role"] == role]
    if previous:
        if len(previous) >= 3 or any(
            api.inspect_job(job_id=job["job_id"], namespace="Ruurd").status.stage not in {"ERROR", "FAILED"}
            for job in previous
        ):
            raise RuntimeError("This role was already submitted; inspect it before retrying")
        for record in previous:
            if phase != "build" and "cost_upper_usd" not in record:
                observed = datetime.now(timezone.utc)
                duration = (observed - datetime.fromisoformat(record["created_at"])).total_seconds()
                record["cost_upper_usd"] = (math.ceil(duration / 60) + 1) * RATES[flavor]
                record["confirmed_stopped_at"] = observed.isoformat()
                record["status"] = "ERROR"
        save(state)
    existing = [job for job in api.list_jobs(namespace="Ruurd")
                if (job.environment or {}).get("RANK_REPO") == REPO
                and (job.environment or {}).get("RANK_ROLE") == role]
    known = {job["job_id"] for job in previous}
    if any(job.id not in known or job.status.stage not in {"ERROR", "FAILED"} for job in existing):
        raise RuntimeError("A matching job already exists; reconcile its receipt before launching")
    response = get_session().get("https://huggingface.co/api/jobs/hardware", headers=api._build_hf_headers(), timeout=30)
    response.raise_for_status()
    hardware = next(item for item in response.json() if item["name"] == flavor)
    if hardware["unitLabel"] != "minute" or float(hardware["unitCostUSD"]) > RATES[flavor]:
        raise RuntimeError("Hardware rate changed; refusing launch")
    accounted = sum(job.get("cost_upper_usd", job["reserved_usd"]) for job in state["jobs"])
    contingency = 2.0 if phase == "rank1024" else 3.0
    if phase == "rank1024":
        validate_controlled_recipe()
        seconds = rank1024_timeout(state)
    elif phase == "train":
        seconds = min(seconds, max(0, math.floor((CAP - 3.0 - accounted) / RATES[flavor]) - 1) * 60)
        if seconds < 12 * 3600:
            raise RuntimeError("Remaining budget no longer supports the planned complete study")
    reserved = (math.ceil(seconds / 60) + 1) * RATES[flavor]
    # GPU bootstrap/starting contingency is reserved in addition to its timeout.
    if accounted + reserved + contingency > CAP:
        raise RuntimeError("Job and startup reserve would exceed the $42 cap")
    runtime_revision = api.dataset_info(REPO).sha
    if phase != "build":
        if not api.file_exists(REPO, "runtime/manifest.json", repo_type="dataset", revision=runtime_revision):
            raise RuntimeError("Compiled FP8 runtime is not ready")
        if not (HERE / "batch_worker.py").is_file():
            raise RuntimeError("Budget forecast worker is not prepared")
    bootstrap = """import hashlib,json,os,subprocess,sys,time
os.environ['RANK_BOOT_MONOTONIC']=str(time.monotonic())
from pathlib import Path
from huggingface_hub import snapshot_download
os.umask(0o077)
snapshot=Path(snapshot_download(os.environ['RANK_REPO'],repo_type='dataset',revision=os.environ['INPUT_REVISION'],allow_patterns=['input/**'],local_dir='/tmp/rank-input'))
bundle=snapshot/'input'
for name,expected in json.loads((bundle/'source_manifest.json').read_text()).items():
 if hashlib.sha256((bundle/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Source hash mismatch: '+name)
os.chdir(bundle)
os.environ['PYTHONPATH']=str(bundle/'code')
if os.environ['RANK_ROLE']=='build':
 os.execv(sys.executable,[sys.executable,str(bundle/'build_runtime.py')])
runtime=Path(snapshot_download(os.environ['RANK_REPO'],repo_type='dataset',revision=os.environ['RUNTIME_REVISION'],allow_patterns=['runtime/**'],local_dir='/tmp/rank-runtime'))/'runtime'
manifest=json.loads((runtime/'manifest.json').read_text());wheel=runtime/manifest['wheel']
if hashlib.sha256(wheel.read_bytes()).hexdigest()!=manifest['sha256']:raise RuntimeError('FP8 wheel hash mismatch')
subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','-r',str(bundle/'requirements.txt')],check=True)
subprocess.run([sys.executable,'-m','pip','install','--no-deps',str(wheel)],check=True)
entry='single_rank_worker.py' if os.environ['RANK_ROLE']=='training-1024' else 'batch_worker.py'
os.execv(sys.executable,[sys.executable,str(bundle/entry)])
"""
    env = {"RANK_REPO": REPO, "RANK_ROLE": role, "RANK_IMAGE": IMAGE,
           "INPUT_REVISION": state["input_revision"], "RUNTIME_REVISION": runtime_revision,
           "BOOTSTRAP": bootstrap, "HF_HOME": "/tmp/rank-hf", "TOKENIZERS_PARALLELISM": "false",
           "RANK_GPU_SECONDS": str(seconds), "RANK_CAP_USD": str(CAP)}
    state["pending_launch"] = {"role": role, "reserved_usd": reserved}
    save(state)
    job = api.run_job(image=IMAGE, command=["bash", "-lc", "python -m pip install --quiet huggingface-hub==0.36.2 && exec python -c \"$BOOTSTRAP\""],
                      flavor=flavor, timeout=seconds, namespace="Ruurd", env=env, secrets={"HF_TOKEN": get_token()})
    record = {"role": role, "job_id": job.id, "url": job.url, "flavor": flavor,
              "input_revision": state["input_revision"], "runtime_revision": runtime_revision,
              "timeout_seconds": seconds, "reserved_usd": reserved, "created_at": job.created_at.isoformat()}
    state["jobs"].append(record)
    state["planning_envelope_usd"] = accounted + reserved + contingency
    state["startup_contingency_usd"] = contingency
    state.pop("pending_launch", None)
    save(state)
    print(json.dumps(record, indent=2))


def main():
    from dotenv import load_dotenv
    from huggingface_hub import HfApi

    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stage", "build", "train", "rank1024"))
    args = parser.parse_args()
    api = HfApi()
    if api.whoami()["name"] != "Ruurd":
        raise RuntimeError("Wrong Hugging Face account")
    stage(api) if args.action == "stage" else launch(api, args.action)


if __name__ == "__main__":
    main()
