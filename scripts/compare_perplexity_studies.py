#!/usr/bin/env python3
"""Compare completed Gemma and LLaDA runs with matching prompts and settings."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/bigram'


def main():
    sources = {'Gemma':BASE/'perplexity_128', 'LLaDA':BASE/'perplexity_llada_128'}
    manifests = {name:json.loads((p/'manifest.json').read_text()) for name,p in sources.items()}
    summaries = {name:json.loads((p/'summary.json').read_text()) for name,p in sources.items()}
    for field in ['prompts','steps','shared','methods','total']:
        assert manifests['Gemma'][field] == manifests['LLaDA'][field], field
    references = set()
    for name,p in sources.items():
        assert summaries[name]['generated'] == summaries[name]['scored'] == manifests[name]['total'] == 100
        scores = [json.loads(line) for line in (p/'scores.jsonl').read_text().splitlines()]
        references.update(json.dumps(row['reference'], sort_keys=True) for row in scores)
    assert len(references) == 1, 'Reference model configuration differs'
    out = BASE/'perplexity_models'; out.mkdir(exist_ok=True)
    groups = {name:{(g['steps'],g['method']):g for g in summary['groups']} for name,summary in summaries.items()}
    steps = manifests['Gemma']['steps']
    rows = []
    for n in steps:
        row = {'steps':n}
        for name in sources:
            a,b = groups[name][n,'confidence'],groups[name][n,'pmi_diffusion']
            row[name] = dict(baseline_ppl=a['perplexity'],pmi_ppl=b['perplexity'],
                ratio=b['perplexity']/a['perplexity'],reduction_percent=100*(1-b['perplexity']/a['perplexity']),
                ratio_ci95=b['paired_ppl_ratio_ci95'],wins=b['per_answer_ppl_wins'],
                baseline_distinct_1=a['mean_distinct_1'],pmi_distinct_1=b['mean_distinct_1'],
                baseline_unique_tokens=a['mean_unique_tokens'],pmi_unique_tokens=b['mean_unique_tokens'],
                baseline_mean_words=a['mean_words'],pmi_mean_words=b['mean_words'])
        rows.append(row)
    data = dict(rows=rows,manifests=manifests,reference=json.loads(next(iter(references))))
    (out/'comparison.json').write_text(json.dumps(data,indent=2)+'\n')
    report = ['# PMI Viterbi across Gemma and LLaDA', '',
        'Both models completed the same 10 prompts, 128-native-token limit, one block, seed 1234, '
        'and NFE budgets 8, 16, 32, 64, 128: 100 outputs per model. Phi-4 NF4/BF16 '
        'scores standalone answers identically for both models.', '',
        'Confidence-guided baseline: temperature 0.7, top-k 3. PMI Viterbi: temperature 2, '
        'top-k/candidates 16, weight 0.5, minimum count 1, clipping ±2, diffusion confidence. '
        'EOS/EOT retention delay is on for both; ending prediction delay is 10 for PMI '
        'and disabled for the baseline. Early stopping is off.', '',
        'The bigram scorers use the same 980,000 training responses, separately tokenized '
        'for each model. The core sampler and Viterbi source are identical. This tests '
        'transfer of the Gemma-preferred settings bundle, not optimal LLaDA settings '
        'or the isolated effect of Viterbi.', '',
        '## Phi-4 token-pooled perplexity', '',
        'Lower is better. Reduction is relative to the confidence baseline within each model.', '',
        '| NFE | Gemma baseline | Gemma PMI | Reduction | LLaDA baseline | LLaDA PMI | Reduction |',
        '|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        g,l = row['Gemma'],row['LLaDA']
        report.append(f"| {row['steps']} | {g['baseline_ppl']:.2f} | {g['pmi_ppl']:.2f} | {g['reduction_percent']:.0f}% | "
                      f"{l['baseline_ppl']:.2f} | {l['pmi_ppl']:.2f} | {l['reduction_percent']:.0f}% |")
    report += ['', '## Consistency across questions', '',
        'Per-question wins mean lower reference PPL, not a manual quality judgment. '
        'Intervals are paired prompt bootstrap 95% intervals for PMI/baseline pooled PPL; '
        'values below 1 favor PMI. One generation seed; 10 questions.', '',
        '| NFE | Gemma wins | Gemma ratio interval | LLaDA wins | LLaDA ratio interval |', '|---:|---:|---:|---:|---:|']
    for row in rows:
        g,l = row['Gemma'],row['LLaDA']; gl,gh=g['ratio_ci95']; ll,lh=l['ratio_ci95']
        report.append(f"| {row['steps']} | {g['wins']}/10 | {gl:.3f}–{gh:.3f} | {l['wins']}/10 | {ll:.3f}–{lh:.3f} |")
    report += ['', '## Repetition and length checks', '',
        'Distinct-1 is unique token types / total tokens in each complete answer, averaged '
        'across questions using each model’s native tokenizer. Higher ratios mean less '
        'token repetition. Compare method changes within a model; '
        'absolute values across tokenizers are not directly equivalent. The shared '
        '128-token cap also permits different word counts.', '',
        '| NFE | Gemma Distinct-1 baseline → PMI | LLaDA Distinct-1 baseline → PMI | LLaDA mean words baseline → PMI |',
        '|---:|---:|---:|---:|']
    for row in rows:
        g,l = row['Gemma'],row['LLaDA']
        report.append(f"| {row['steps']} | {g['baseline_distinct_1']:.3f} → {g['pmi_distinct_1']:.3f} | "
            f"{l['baseline_distinct_1']:.3f} → {l['pmi_distinct_1']:.3f} | {l['baseline_mean_words']:.1f} → {l['pmi_mean_words']:.1f} |")
    report += ['', 'Mean number of unique token types in each full answer:', '',
        '| NFE | Gemma baseline → PMI | LLaDA baseline → PMI |', '|---:|---:|---:|']
    for row in rows:
        g,l = row['Gemma'],row['LLaDA']
        report.append(f"| {row['steps']} | {g['baseline_unique_tokens']:.1f} → {g['pmi_unique_tokens']:.1f} | "
            f"{l['baseline_unique_tokens']:.1f} → {l['pmi_unique_tokens']:.1f} |")
    report += ['', 'Predictable repetition can receive excellent perplexity. Read the '
        'examples and repetition/length checks alongside the scores. These are '
        'small exploratory comparisons, not factuality or reasoning benchmarks.', '',
        '## Full reports and representative answers', '',
        '- [Gemma report](../perplexity_128/REPORT.md)',
        '- [LLaDA report](../perplexity_llada_128/REPORT.md)', '',
        '![Perplexity and PMI/baseline ratios](comparison.png)', '']
    notes = out/'INTERPRETATION.md'
    if notes.exists(): report += [notes.read_text()]
    (out/'REPORT.md').write_text('\n'.join(report)+'\n')
    os.environ.setdefault('MPLCONFIGDIR','/tmp/byod-perplexity-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for name,color in [('Gemma','#2563eb'),('LLaDA','#ea580c')]:
        for method,label,style in [('confidence','baseline','--'),('pmi_diffusion','PMI','-')]:
            axes[0].plot(steps,[groups[name][n,method]['perplexity'] for n in steps],
                         marker='o',linestyle=style,color=color,label=f'{name} {label}')
        axes[1].plot(steps,[r[name]['ratio'] for r in rows],marker='o',color=color,label=name)
        axes[1].fill_between(steps,[r[name]['ratio_ci95'][0] for r in rows],
                             [r[name]['ratio_ci95'][1] for r in rows],alpha=.15,color=color)
    axes[0].set(ylabel='Phi-4 token-pooled perplexity',yscale='log')
    axes[1].set(ylabel='PMI / baseline perplexity',yscale='log')
    axes[1].axhline(1,color='gray',linestyle=':')
    for ax in axes:
        ax.set_xscale('log',base=2);ax.set_xticks(steps,labels=steps)
        ax.set_xlabel('NFE');ax.grid(alpha=.2);ax.legend()
    fig.suptitle('10 shared prompts · 128 native tokens · one seed')
    fig.tight_layout();fig.savefig(out/'comparison.png',dpi=180);plt.close(fig)
    print(out/'REPORT.md')


if __name__ == '__main__':
    main()
