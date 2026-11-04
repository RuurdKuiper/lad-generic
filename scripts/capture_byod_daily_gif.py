#!/usr/bin/env python3
"""Capture every streamed frame from a seeded BYOD-Gemma demo invocation."""
import argparse
import json
import os
import time
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from gradio_client import Client
from huggingface_hub import HfApi


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=303)
    parser.add_argument('--output', type=Path, default=Path('/tmp/byod-gif-captures'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / f'seed-{args.seed}.json'
    if path.exists():
        raise FileExistsError(f'Preserving existing capture: {path}; use another output directory.')
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    api = HfApi(token=os.getenv('HF_TOKEN'))
    space = 'Ruurd/byod-gemma-2-9b'
    revision = api.repo_info(space, repo_type='space').sha
    client = Client(space, token=api.token, verbose=False)
    parameters = client.view_api(return_format='dict', print_info=False)['named_endpoints']['/generate']['parameters']
    defaults = {p['parameter_name']: p.get('parameter_default') for p in parameters}
    settings = dict(defaults)
    settings.update(question='What do you know about Diffusion Language Models?',
                    max_new_tokens=128, num_steps=64, block_length=128,
                    trajectory_color_mode='Prediction probability', generation_seed=args.seed)
    start = time.monotonic()
    job = client.submit(api_name='/generate', **settings)
    status, html = job.result(timeout=180)
    frames = job.outputs()
    soup = BeautifulSoup(html, 'html.parser')
    answer = soup.find('textarea').get_text()
    visible = sum('token position' in span.get('title', '') and 'masked at' not in span.get('title', '')
                  for span in soup.find_all('span'))
    result = dict(seed=args.seed, space=space, space_revision=revision, settings=settings, interface_defaults=defaults,
                  answer=answer, visible_tokens=visible, frames=frames, status=status, html=html,
                  wall_seconds=time.monotonic() - start)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(f'Saved {len(frames)} actual frames and {visible} text tokens to {path}\n{answer}')


if __name__ == '__main__':
    main()
