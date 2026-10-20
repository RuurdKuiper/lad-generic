#!/usr/bin/env python3
"""Resumable hosted diffusion comparison of two practical decoding setups.

Uses the existing app sampler, not the paper's official LLaDA sampler. Reference
perplexity is exp(sum(answer NLL) / sum(scored answer tokens)), never mean PPL.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

from evaluate_ending_controls import PlainOutput

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/bigram/perplexity_quick'
SPACE = 'Ruurd/byod-gemma-2-9b'
WORKER = 'Ruurd/byod-perplexity-eval'


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def append(path, row):
    with path.open('a') as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def generate(client, api, limit, questions=30, max_new_tokens=64, steps_list=None):
    if (OUT/'experiment_decision.json').exists():
        raise RuntimeError('This experiment was closed; use a new output directory.')
    steps_list = steps_list or [8,16,32,64]
    prompts = [p.strip() for p in (ROOT/'src/diffusion_lm/generation_prompts.txt').read_text().splitlines()
               if p.strip() and not p.startswith('#')][:questions]
    assert len(prompts) == questions
    assert questions > 0 and max_new_tokens > 0 and all(0 < s <= max_new_tokens for s in steps_list)
    shared = dict(system_prompt='You are a helpful assistant.', max_new_tokens=max_new_tokens,
        block_length=max_new_tokens, pause_per_step=0., trajectory_color_mode='No coloring',
        revisable_tokens=False, ar_check_interval=4, delay_eos_eot=True,
        early_stopping=False, bigram_scoring_method='PMI bigram', pmi_min_count=1,
        pmi_clip=2., generation_seed=1234, measure_decoding=True,
        bigram_remasking_confidence='Diffusion probability')
    methods = dict(confidence=dict(remasking_strategy='Confidence-guided', temperature=.7,
                                  top_k=3, bigram_eos_delay_penalty=1.),
                   pmi_diffusion=dict(remasking_strategy='Bigram Viterbi', temperature=2.,
                                      top_k=16, bigram_eos_delay_penalty=10.))
    manifest = dict(space=SPACE, revision=api.repo_info(SPACE, repo_type='space').sha,
        prompts=prompts, steps=steps_list, shared=shared, methods=methods, total=questions*len(steps_list)*2,
        caveat='Practical app-settings comparison, not isolated Viterbi ablation or exact paper replication.')
    path = OUT/'manifest.json'
    if path.exists():
        assert json.loads(path.read_text()) == manifest, 'Space or experiment settings changed'
    else:
        path.write_text(json.dumps(manifest, indent=2)+'\n')
    results = OUT/'results.jsonl'
    done = {r['key'] for r in read_rows(results)}
    count = 0
    # Complete every NFE/method pair for each prompt before moving to the next.
    for i, prompt in enumerate(prompts):
        for steps in manifest['steps']:
            for method, options in methods.items():
                key = f'open_{i+1:02}/{steps}/{method}'
                if key in done:
                    continue
                kwargs = dict(shared, **options, question=prompt, num_steps=steps)
                for attempt in range(2):
                    started = time.monotonic()
                    try:
                        status, html = client.submit(**kwargs, api_name='/generate').result(timeout=600)
                        assert f'Denoising step {steps}/{steps}' in status, status
                        plain = PlainOutput(); plain.feed(html)
                        if not plain.text.strip():
                            raise RuntimeError('Empty output; refusing to score a failed generation')
                        metrics = json.loads(status.split('Decoding metrics: ',1)[1]) if 'Decoding metrics: ' in status else None
                        if metrics is not None:
                            assert metrics['selector_calls'] == steps, metrics
                        append(results, dict(key=key, prompt=prompt, prompt_id=i+1, steps=steps,
                            method=method, options=kwargs, text=plain.text, status=status,
                            metrics=metrics, wall_seconds=time.monotonic()-started,
                            output_sha256=hashlib.sha256(plain.text.encode()).hexdigest()))
                        done.add(key); count += 1
                        print(json.dumps(dict(done=len(done), total=manifest['total'], key=key,
                            seconds=round(time.monotonic()-started,2), text=plain.text)), flush=True)
                        break
                    except Exception as exc:
                        append(OUT/'errors.jsonl', dict(key=key, attempt=attempt+1, error=str(exc)))
                        if 'quota' in str(exc).lower() or attempt == 1:
                            raise
                        time.sleep(3)
                if limit and count >= limit:
                    return


def score(client, limit):
    rows = read_rows(OUT/'results.jsonl')
    done = {r['key'] for r in read_rows(OUT/'scores.jsonl')}
    pending = [dict(key=r['key'], text=r['text']) for r in rows if r['key'] not in done]
    if limit:
        pending = pending[:limit]
    if not pending:
        return
    result = client.predict(pending, api_name='/score')
    assert {r['key'] for r in result['results']} == {r['key'] for r in pending}
    metadata = {k:v for k,v in result.items() if k != 'results'}
    for row in result['results']:
        append(OUT/'scores.jsonl', dict(**row, reference=metadata))
    print(json.dumps(dict(scored=len(pending), reference=metadata)), flush=True)


def diversity():
    from huggingface_hub import HfApi, hf_hub_download
    from transformers import AutoTokenizer
    from diffusion_lm.metrics import distinct_n
    manifest = json.loads((OUT/'manifest.json').read_text())
    is_llada = 'llada' in manifest['space'].lower()
    if is_llada:
        config = json.loads(Path(hf_hub_download(manifest['space'], 'space_model.json',
            repo_type='space', revision=manifest['revision'])).read_text())
        model, revision = config['model_repo_id'], config['model_revision']
    else:
        model = 'google/gemma-2-9b-it'
        revision = HfApi().model_info(model).sha
    tokenizer = AutoTokenizer.from_pretrained(model, revision=revision, token=os.getenv('HF_TOKEN'),
                                             trust_remote_code=is_llada,
                                             cache_dir=ROOT/'artifacts/tokenizer_cache')
    rows = {}
    for row in read_rows(OUT/'results.jsonl'):
        special_ids = set(tokenizer.all_special_ids)
        ids = [i for i in tokenizer.encode(row['text'], add_special_tokens=False) if i not in special_ids]
        rows[row['key']] = dict(tokens=len(ids), unique_tokens=len(set(ids)), **{
            f'distinct_{n}':distinct_n(row['text'],tokenizer,n) for n in [1,2,3]})
    result = dict(tokenizer=model, revision=revision, results=rows)
    (OUT/'diversity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(diversity_scored=len(rows),tokenizer=model)))


def summarize():
    import numpy as np
    manifest = json.loads((OUT/'manifest.json').read_text()) if (OUT/'manifest.json').exists() else {}
    steps_list = manifest.get('steps', [8,16,32,64])
    total = manifest.get('total',240)
    canvas = manifest.get('shared',{}).get('max_new_tokens',64)
    question_count = len(manifest.get('prompts',list(range(30))))
    model_label = 'LLaDA-8B-Instruct' if 'llada' in manifest.get('space','').lower() else 'Gemma'
    rows = read_rows(OUT/'results.jsonl')
    scores = {r['key']:r for r in read_rows(OUT/'scores.jsonl')}
    diversity_path = OUT/'diversity.json'
    diversity_rows = json.loads(diversity_path.read_text())['results'] if diversity_path.exists() else {}
    groups = []
    for steps in steps_list:
        paired_ids = set.intersection(*[set(r['prompt_id'] for r in rows if r['steps']==steps
            and r['method']==m and r['key'] in scores) for m in ['confidence','pmi_diffusion']])
        grouped = {}
        for method in ['confidence','pmi_diffusion']:
            selected = sorted([r for r in rows if r['steps']==steps and r['method']==method
                               and r['prompt_id'] in paired_ids], key=lambda r:r['prompt_id'])
            valid = [scores[r['key']] for r in selected]
            if not valid:
                continue
            assert all(s['tokens'] > 0 and s['nll'] is not None for s in valid)
            nll = np.array([s['nll'] for s in valid]); tokens = np.array([s['tokens'] for s in valid])
            grouped[method] = (nll,tokens)
            groups.append(dict(steps=steps, method=method, prompts=len(valid),
                perplexity=math.exp(nll.sum()/tokens.sum()), reference_tokens=int(tokens.sum()),
                median_answer_perplexity=float(np.median(np.exp(nll/tokens))),
                mean_words=float(np.mean([len(r['text'].split()) for r in selected]))))
            if all(r['key'] in diversity_rows for r in selected):
                groups[-1]['mean_generated_tokens'] = float(np.mean([diversity_rows[r['key']]['tokens'] for r in selected]))
                groups[-1]['mean_distinct_1'] = float(np.mean([diversity_rows[r['key']]['distinct_1'] for r in selected]))
                groups[-1]['mean_unique_tokens'] = float(np.mean([diversity_rows[r['key']]['unique_tokens'] for r in selected]))
        if len(grouped)==2:
            rng = np.random.default_rng(1234)
            indices = rng.integers(0,len(paired_ids),size=(10000,len(paired_ids)))
            logs = {}
            for method,(nll,tokens) in grouped.items():
                logs[method] = nll[indices].sum(axis=1)/tokens[indices].sum(axis=1)
            ratio = np.exp(logs['pmi_diffusion']-logs['confidence'])
            groups[-1]['paired_ppl_ratio_ci95'] = np.quantile(ratio,[.025,.975]).tolist()
            baseline_nll,baseline_tokens = grouped['confidence']
            pmi_nll,pmi_tokens = grouped['pmi_diffusion']
            groups[-1]['per_answer_ppl_wins'] = int(np.sum(pmi_nll/pmi_tokens < baseline_nll/baseline_tokens))
    output = dict(generated=len(rows), scored=len(scores), planned=total, groups=groups,
        interpretation='Lower reference perplexity means more predictable text, not necessarily more factual or useful answers.')
    (OUT/'summary.json').write_text(json.dumps(output, indent=2)+'\n')
    report = [f'# Quick {model_label} perplexity comparison', '',
        f"Saved generations: {len(rows)}/{total}; scored: {len(scores)}/{total}.", '',
        f'{question_count} standard questions; one seed (1234); {canvas}-token canvas; one block; '
        'delayed EOS/EOT retention; early stopping disabled. All generation and '
        'reference scoring runs on Hugging Face ZeroGPU.', '',
        'Baseline: existing app confidence-guided sampler, temperature 0.7, top-k 3. '
        'Viterbi: PMI, diffusion confidence, temperature 2, top-k 16, fixed weight '
        '0.5, minimum count 1, clipping ±2, ending-delay strength 10. This compares '
        'the practical setups, including their different sampling/ending settings; '
        'it does not isolate the effect of Viterbi or exactly replicate the paper.', '',
        'Reference: microsoft/phi-4, NF4 with double quantization and BF16 compute. '
        'Standalone answers scored without question conditioning. Perplexity is '
        'exp(total negative log likelihood / total scored reference tokens). '
        'Only matched prompts are compared at each NFE.', '',
        '| NFE | Paired prompts | Confidence PPL | PMI PPL | PMI / confidence | Paired 95% bootstrap interval |',
        '|---:|---:|---:|---:|---:|---:|']
    if (OUT/'experiment_decision.json').exists():
        report[4:4] = ['Generation stopped at the user’s request. All completed question sets are retained below.', '']
    for steps in steps_list:
        by_method = {g['method']:g for g in groups if g['steps']==steps}
        if len(by_method)!=2:
            continue
        base = by_method['confidence']; pmi = by_method['pmi_diffusion']
        low,high = pmi['paired_ppl_ratio_ci95']
        report.append(f"| {steps} | {base['prompts']} | {base['perplexity']:.2f} | "
            f"{pmi['perplexity']:.2f} | {pmi['perplexity']/base['perplexity']:.3f} | {low:.3f}–{high:.3f} |")
    report += ['', 'Bootstrap: 10,000 paired prompt resamples, seed 1234. '
        'The interval captures prompt variability for these outputs; it does not '
        'capture variation across generation seeds.', '',
        'Lower perplexity means more predictable text under Phi-4. Repetition and '
        'shorter or generic answers can also lower perplexity; it is not a '
        'correctness or factuality score. See saved answers for qualitative review.', '',
        '| NFE | Confidence mean words | PMI mean words |', '|---:|---:|---:|']
    for steps in steps_list:
        paired = [g for g in groups if g['steps']==steps]
        if len(paired)==2:
            report.append(f"| {steps} | {paired[0]['mean_words']:.1f} | {paired[1]['mean_words']:.1f} |")
    report += ['', 'Median per-answer perplexity and paired win counts supplement the '
        'token-pooled metric above. They help show whether the result is concentrated '
        'in a few failed answers. A win means lower per-answer PPL, not a manual quality judgment.', '',
        '| NFE | Confidence median PPL | PMI median PPL | PMI PPL wins |', '|---:|---:|---:|---:|']
    for steps in steps_list:
        paired = [g for g in groups if g['steps']==steps]
        if len(paired)==2:
            report.append(f"| {steps} | {paired[0]['median_answer_perplexity']:.2f} | "
                f"{paired[1]['median_answer_perplexity']:.2f} | {paired[1]['per_answer_ppl_wins']}/{paired[1]['prompts']} |")
    if diversity_rows:
        report += ['', f'Distinct-1 ({model_label} tokenizer) is the number of unique token types '
            'divided by the total number of tokens in the complete generated answer, '
            'excluding special tokens and the prompt. Each answer is measured separately; '
            'the table averages those ratios and unique-token counts across questions. '
            'Higher ratios indicate less token repetition. This is not a grammaticality score.', '',
            '| NFE | Confidence Distinct-1 | PMI Distinct-1 | Confidence mean unique tokens | PMI mean unique tokens |',
            '|---:|---:|---:|---:|---:|']
        for steps in steps_list:
            paired = [g for g in groups if g['steps']==steps]
            if len(paired)==2 and all('mean_distinct_1' in g for g in paired):
                report.append(f"| {steps} | {paired[0]['mean_distinct_1']:.3f} | {paired[1]['mean_distinct_1']:.3f} | "
                    f"{paired[0]['mean_unique_tokens']:.1f} | {paired[1]['mean_unique_tokens']:.1f} |")
    if (OUT/'QUALITATIVE_NOTES.md').exists():
        report += ['', (OUT/'QUALITATIVE_NOTES.md').read_text().replace('# ', '## ', 1)]
    if (OUT/'REPRESENTATIVE_EXAMPLES.md').exists():
        report += ['', (OUT/'REPRESENTATIVE_EXAMPLES.md').read_text()]
    (OUT/'REPORT.md').write_text('\n'.join(report)+'\n')
    answers = []
    for row in rows:
        answers += [f"## Question {row['prompt_id']} · NFE {row['steps']} · {row['method']}",
                    '', row['prompt'], '', row['text'], '']
    (OUT/'answers.md').write_text('\n'.join(answers))
    if groups:
        os.environ.setdefault('MPLCONFIGDIR', '/tmp/byod-perplexity-matplotlib')
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib import pyplot as plt
        fig, ax = plt.subplots(figsize=(6.4,4))
        for method,label in [('confidence','Confidence-guided'),('pmi_diffusion','PMI Viterbi')]:
            points = [g for g in groups if g['method']==method]
            ax.plot([p['steps'] for p in points], [p['perplexity'] for p in points], marker='o',label=label)
        paired_count = min(g['prompts'] for g in groups)
        ax.set(xlabel='NFE', ylabel='Phi-4 token-pooled perplexity',
               title=f'{model_label} · {paired_count} paired questions · {canvas}-token limit')
        ax.set_xticks(steps_list); ax.grid(alpha=.2); ax.legend()
        fig.tight_layout(); fig.savefig(OUT/'perplexity.png', dpi=180); plt.close(fig)
    print(json.dumps(output,indent=2))


def main():
    global OUT, SPACE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['generate','score','summarize','diversity'])
    parser.add_argument('--limit', type=int)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--space', default=SPACE)
    parser.add_argument('--questions', type=int, default=30)
    parser.add_argument('--max-new-tokens', type=int, default=64)
    parser.add_argument('--steps', type=int, nargs='+', default=[8,16,32,64])
    args = parser.parse_args()
    OUT = args.output
    SPACE = args.space
    OUT.mkdir(parents=True, exist_ok=True)
    if args.action == 'summarize':
        summarize(); return
    from dotenv import load_dotenv
    from gradio_client import Client
    from huggingface_hub import HfApi
    load_dotenv(ROOT/'.env')
    if args.action == 'diversity':
        diversity(); return
    client = Client(SPACE if args.action=='generate' else WORKER, token=os.getenv('HF_TOKEN'), verbose=False)
    if args.action == 'generate':
        generate(client, HfApi(), args.limit, args.questions, args.max_new_tokens, args.steps)
    else:
        score(client, args.limit)


if __name__ == '__main__':
    main()
