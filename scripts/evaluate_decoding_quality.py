#!/usr/bin/env python3
"""Resumable, matched-prompt 5 x 3 hosted decoding quality comparison.

Outputs are deliberately saved verbatim for subsequent manual review. This does
not call a judge model or execute generated code.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import time

from evaluate_ending_controls import PlainOutput

ROOT = Path(__file__).resolve().parents[1]
METHODS = [
    ('confidence', 'Confidence-guided', 'Conditional bigram', 'Diffusion probability'),
    ('conditional_diffusion', 'Bigram Viterbi', 'Conditional bigram', 'Diffusion probability'),
    ('pmi_diffusion', 'Bigram Viterbi', 'PMI bigram', 'Diffusion probability'),
    ('conditional_margin', 'Bigram Viterbi', 'Conditional bigram', 'Viterbi path margin'),
    ('pmi_margin', 'Bigram Viterbi', 'PMI bigram', 'Viterbi path margin'),
]
CODING = [
    ('sum_even', 'Write Python function sum_even(nums) returning the sum of even integers in nums. Handle an empty list.'),
    ('palindrome', 'Write Python function is_palindrome(text) ignoring case and non-alphanumeric characters. Return a boolean.'),
    ('fibonacci', 'Write Python function fibonacci(n) returning a list of the first n Fibonacci numbers, starting with 0, 1. For n <= 0 return [].'),
    ('deduplicate', 'Write Python function deduplicate(items) removing duplicates while preserving first occurrence order. Items are hashable.'),
    ('balanced', 'Write Python function balanced(s) checking balanced parentheses (), brackets [], and braces {}. Ignore other characters.'),
    ('binary_search', 'Write Python function binary_search(nums, target) for sorted nums, returning its index or -1 if absent.'),
    ('word_counts', 'Write Python function word_counts(text) returning a dictionary of word frequencies. Split on whitespace and ignore case.'),
    ('merge_sorted', 'Write Python function merge_sorted(a, b) merging two sorted integer lists into one sorted list. Do not call sorted() or .sort().'),
    ('flatten', 'Write Python function flatten(rows) flattening a list of lists by one level. Preserve order and handle empty lists.'),
    ('fizzbuzz', 'Write Python function fizzbuzz(n) returning strings for integers 1 through n: Fizz for multiples of 3, Buzz for 5, FizzBuzz for both, otherwise the number as a string.'),
]
CODE_SUFFIX = ' Return only concise Python code, without explanation or examples.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/bigram/quality_experiment')
    parser.add_argument('--space', default='Ruurd/byod-gemma-2-9b')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--profile', choices=['original', 'paper-coding'], default='original')
    args = parser.parse_args()
    from dotenv import load_dotenv
    from gradio_client import Client
    from huggingface_hub import HfApi
    load_dotenv(ROOT/'.env')
    token = os.getenv('HF_TOKEN')
    client = Client(args.space, token=token, verbose=False)
    api = client.view_api(print_info=False, return_format='dict')['named_endpoints']['/generate']
    parameter_names = {p['parameter_name'] for p in api['parameters']}
    shared_controls = 'bigram_weight' not in parameter_names
    required = {'bigram_remasking_confidence', 'pmi_min_count', 'bigram_eos_delay_penalty'}
    assert required <= {p['parameter_name'] for p in api['parameters']}
    prompts = [line.strip() for line in (ROOT/'src/diffusion_lm/generation_prompts.txt').read_text().splitlines()
               if line.strip() and not line.startswith('#')][:30]
    tasks = [dict(id=f'open_{i+1:02}', task='open', prompt=p) for i,p in enumerate(prompts)]
    tasks += [dict(id=f'code_{name}', task='code', prompt=p+CODE_SUFFIX) for name,p in CODING]
    paper = args.profile == 'paper-coding'
    if paper:
        tasks = [task for task in tasks if task['task'] == 'code']
    steps_list = [32, 64, 128] if paper else [128, 64, 32]
    total = len(tasks) * len(steps_list) * len(METHODS)
    args.output.mkdir(parents=True, exist_ok=True)
    shared = dict(system_prompt='You are a helpful assistant.', max_new_tokens=128,
        block_length=128, temperature=1., top_k=16, pause_per_step=0.,
        trajectory_color_mode='No coloring', revisable_tokens=False, ar_check_interval=4,
        early_stopping=False, bigram_top_k=16, bigram_weight=.5, pmi_min_count=1,
        pmi_clip=2., generation_seed=42, measure_decoding=True)
    if paper:
        shared.update(temperature=0., top_k=1)
    if shared_controls:
        shared.pop('bigram_top_k')
        shared.pop('bigram_weight')
    metadata = dict(space=args.space, revision=HfApi(token=token).repo_info(args.space, repo_type='space').sha,
        seed=42, shared_options=shared, steps=steps_list, methods=METHODS, tasks=tasks,
        total=total, early_stopping_reason='Fixed forward-pass budget for comparing step counts.',
        coding_delay=paper, open_delay=True, coding_delay_strength=1., open_delay_strength=1000.,
        note='Strength 1 disables ending prediction penalty. Baseline uses no bigram selector. Manual review; no external judge.')
    if paper:
        metadata.update(profile='paper-coding', paper_source='arxiv_submission/paper.tex:408-429',
            sampling='Raw-logit greedy argmax with full-vocabulary retention confidence.',
            ending_policy='Delay retention only, no bigram logit penalty.',
            scope='Same ten custom assignments, 128-token MBPP-style canvas; NFE ablation, not HumanEval/MBPP benchmark scores.',
            priority='Baseline and PMI/diffusion pairs at every NFE first; remaining three methods afterwards.',
            quota_policy='Use available allowance, defer rejected budgets, stop when no budget is available.',
            probe='One PMI/diffusion/32 result reused from credit_probe.json; baseline-only greedy fix does not affect this path.')
    if shared_controls:
        metadata['probe'] = 'No legacy credit probe is reused with the shared-control selector.'
        metadata.update(shared_top_k=True, fixed_bigram_weight=.5, viterbi_temperature_scaling=True,
            note=metadata['note'] + ' Shared controls: Viterbi effective transition weight is 0.5 * temperature. Temperature zero ignores transitions; top-k 1 has only argmax candidates.')
    metadata = json.loads(json.dumps(metadata))
    manifest = args.output/'manifest.json'
    if manifest.exists():
        assert json.loads(manifest.read_text()) == metadata, 'Experiment inputs/revision changed; choose a new output directory'
    else:
        manifest.write_text(json.dumps(metadata, indent=2)+'\n')
    result_file = args.output/'results.jsonl'
    if paper and not shared_controls and not result_file.exists() and (args.output/'credit_probe.json').exists():
        probe = json.loads((args.output/'credit_probe.json').read_text())
        if probe['success']:
            options = dict(shared, question=tasks[0]['prompt'], num_steps=32,
                remasking_strategy='Bigram Viterbi', bigram_scoring_method='PMI bigram',
                bigram_remasking_confidence='Diffusion probability', delay_eos_eot=True,
                bigram_eos_delay_penalty=1.)
            assert options == probe['options']
            row = dict(key='code_sum_even/32/pmi_diffusion', **tasks[0], steps=32,
                method='pmi_diffusion', options=options, text=probe['text'], status=probe['status'],
                metrics=json.loads(probe['status'].split('Decoding metrics: ',1)[1]),
                wall_seconds=probe['wall_seconds'], source_revision=probe['revision'],
                output_sha256=hashlib.sha256(probe['text'].encode()).hexdigest())
            result_file.write_text(json.dumps(row)+'\n')
    completed = {r['key'] for line in result_file.read_text().splitlines() if (r:=json.loads(line))} if result_file.exists() else set()
    # Interleave tasks and configurations so interruption does not selectively
    # complete one configuration; coding first gives an early useful smoke test.
    cases = [(task, steps, method) for task in tasks[30:]+tasks[:30] for steps in [128,64,32] for method in METHODS]
    if paper:
        all_cases = [(task, steps, method) for steps in steps_list for task in tasks for method in METHODS]
        primary = {'confidence', 'pmi_diffusion'}
        cases = [c for c in all_cases if c[2][0] in primary] + [c for c in all_cases if c[2][0] not in primary]
    count = 0
    initial_completed = len(completed)
    not_before = {32: 0., 64: 0., 128: 0.}
    while len(completed) < len(cases):
        ready = [case for case in cases
                 if f"{case[0]['id']}/{case[1]}/{case[2][0]}" not in completed
                 and time.monotonic() >= not_before[case[1]]]
        if not ready:
            if paper:
                print(json.dumps(dict(event='quota_blocked', completed=len(completed), total=total)), flush=True)
                break
            wait = min(not_before[c[1]] for c in cases
                       if f"{c[0]['id']}/{c[1]}/{c[2][0]}" not in completed)-time.monotonic()
            print(json.dumps(dict(event='quota_wait', seconds=round(max(0,wait)), completed=len(completed))), flush=True)
            time.sleep(min(45., max(1.,wait)))
            continue
        task,steps,(method,strategy,scoring,confidence) = ready[0]
        key = f"{task['id']}/{steps}/{method}"
        if key in completed: continue
        options = dict(shared, question=task['prompt'], num_steps=steps,
            remasking_strategy=strategy, bigram_scoring_method=scoring,
            bigram_remasking_confidence=confidence, delay_eos_eot=paper or task['task']=='open',
            bigram_eos_delay_penalty=1000. if task['task']=='open' else 1.)
        for attempt in range(3):
            started = time.monotonic()
            try:
                status, html = client.submit(**options, api_name='/generate').result(timeout=600)
                plain = PlainOutput(); plain.feed(html)
                metrics = json.loads(status.split('Decoding metrics: ',1)[1]) if 'Decoding metrics: ' in status else None
                row = dict(key=key, **task, steps=steps, method=method, options=options,
                    text=plain.text, status=status, metrics=metrics, wall_seconds=time.monotonic()-started,
                    output_sha256=hashlib.sha256(plain.text.encode()).hexdigest())
                with result_file.open('a') as f:
                    f.write(json.dumps(row, ensure_ascii=False)+'\n'); f.flush(); os.fsync(f.fileno())
                print(json.dumps(dict(done=len(completed)+1,total=total,key=key,seconds=round(row['wall_seconds'],2),text=row['text'])), flush=True)
                completed.add(key)
                break
            except Exception as exc:
                error = dict(key=key, attempt=attempt+1, error=str(exc), wall_seconds=time.monotonic()-started)
                with (args.output/'errors.jsonl').open('a') as f: f.write(json.dumps(error)+'\n')
                print(json.dumps(error), flush=True)
                if 'quota' in str(exc).lower():
                    retry = re.search(r'Try again in (\d+):(\d+):(\d+)', str(exc))
                    if not retry: raise
                    hours,minutes,seconds = map(int,retry.groups())
                    retry_at = time.monotonic()+hours*3600+minutes*60+seconds+5
                    for step_count in not_before:
                        if step_count >= steps:
                            not_before[step_count] = max(not_before[step_count],retry_at)
                    break
                if attempt==2: raise
                time.sleep(5)
        count = len(completed) - initial_completed
        if args.limit and count>=args.limit: break
    (args.output/'run_state.json').write_text(json.dumps(dict(completed=len(completed), total=total,
        complete=len(completed)==total, quota_blocked=len(completed)<total and not args.limit), indent=2)+'\n')
    print(json.dumps(dict(completed=len(completed),total=total)), flush=True)


if __name__ == '__main__':
    main()
