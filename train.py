#!/usr/bin/env python
import argparse
from pathlib import Path
from dotenv import load_dotenv
import yaml
from diffusion_lm.training import run_training

load_dotenv(Path(__file__).resolve().parent / ".env")


def main():
    """Parse the YAML configuration and launch one training run."""
    p = argparse.ArgumentParser(); p.add_argument("--config", required=True)
    args = p.parse_args()
    with open(args.config) as f: config = yaml.safe_load(f)
    run_training(config)


if __name__ == "__main__":
    main()
