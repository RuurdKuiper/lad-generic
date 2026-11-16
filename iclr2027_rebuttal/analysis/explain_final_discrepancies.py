"""Static, offline diagnostics for final HumanEval and MATH discrepancies.

Parses generated Python as syntax only; never executes generated programs.
"""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

from tokenizers import Tokenizer

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent / "evaluation"
sys.path.insert(0, str(HERE.parents[1] / "src"))
from diffusion_lm.benchmarks import _extract_python_code


def program(prediction, metadata):
    entry = metadata['entry_point']
    code = _extract_python_code(prediction, entry)
    if re.search(rf"(?m)^\s*(?:async\s+)?def\s+{re.escape(entry)}\s*\(", code):
        return code
    first = next((line for line in code.splitlines() if line.strip()), '')
    if first and not first[:1].isspace():
        code = '\n'.join('    '+line if line else line for line in code.splitlines())
    return metadata['prompt'].rstrip('\n')+'\n'+code.lstrip('\n')


def main():
    final_path = EVAL/'generation_diagnostic/nov15_gemma/assembled_results.jsonl'
    final = [json.loads(line) for line in final_path.open() if line.strip()]
    original = [json.loads(line) for line in (EVAL/'generation_diagnostic/nov15/main_results.jsonl').open() if line.strip()]
    examples = {r['fingerprint']: r for r in map(json.loads, (EVAL/'campaign_bundle/examples.jsonl').open())}
    family_paths = {'gemma': 'gemma_d', 'qwen': 'qwen_d', 'ministral': 'ministral_d', 'llama': 'llama_25k'}
    tokenizers = {family: Tokenizer.from_file(str(EVAL/'original_checkpoints'/key/'tokenizer.json'))
                  for family, key in family_paths.items()}
    result = {'python_version': sys.version,
              'analysis_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'final_results_sha256': hashlib.sha256(final_path.read_bytes()).hexdigest(),
              'human_groups': {}, 'math_by_level': {}, 'math_standardized': {}, 'code_syntax_totals': {}}
    packets = []
    keys = list(dict.fromkeys(r['model_key'] for r in final))
    for key in keys:
        family = key.split('_')[0]
        tokenizer = tokenizers.get(family)
        rows = [r for r in final if r['model_key'] == key and r['task'] == 'humaneval']
        oldids = {r['fingerprint'] for r in original if r['model_key'] == key and r['task'] == 'humaneval' and r['source'] == 'legacy_rescored'}
        groups = {}
        for name, selected in [('historical_ids', [r for r in rows if r['fingerprint'] in oldids]),
                               ('added_ids', [r for r in rows if r['fingerprint'] not in oldids])]:
            counts = Counter(n=len(selected), correct=sum(r['correct'] for r in selected))
            lengths = []; canonical_lengths = []; prompt_lengths = []; errors = Counter()
            for row in selected:
                ex = examples[row['fingerprint']]
                code = program(row['prediction'], ex['metadata'])
                cap = row['settings']['max_new_tokens']
                n_tokens = len(tokenizer.encode(row['prediction'], add_special_tokens=False).ids) if tokenizer else None
                near = n_tokens is not None and n_tokens >= cap-8
                if tokenizer:
                    lengths.append(n_tokens)
                    canonical = len(tokenizer.encode(ex['metadata']['prompt']+ex['target'], add_special_tokens=False).ids)
                    canonical_lengths.append(canonical)
                    prompt_lengths.append(len(tokenizer.encode(ex['metadata']['prompt'], add_special_tokens=False).ids))
                    counts['canonical_full_function_over_cap'] += canonical > cap
                    counts['canonical_body_only_over_cap'] += len(tokenizer.encode(ex['target'], add_special_tokens=False).ids) > cap
                counts['near_cap'] += near
                counts['fail_near_cap'] += near and not row['correct']
                error = None
                try:
                    tree = ast.parse(code)
                    functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == ex['metadata']['entry_point']]
                    counts['missing_entry'] += not functions
                    counts['docstring_only_function'] += bool(functions) and all(isinstance(n, (ast.Expr, ast.Pass)) for n in functions[0].body)
                except SyntaxError as exc:
                    error = exc.msg
                    errors[error] += 1
                    counts['syntax_invalid'] += 1
                    counts['syntax_invalid_near_cap'] += near
                    counts['unterminated_triple_quote'] += 'unterminated triple-quoted' in error
                if key == 'gemma_d' and name == 'added_ids' and not row['correct']:
                    packets.append({'index': row['sample_index'], 'correct': row['correct'], 'near_cap': near,
                                    'tokens': n_tokens, 'syntax_error': error, 'example': ex, 'prediction': row['prediction']})
            groups[name] = dict(counts, tokenizer_available=tokenizer is not None,
                                mean_output_tokens=sum(lengths)/len(lengths) if lengths else None,
                                mean_specification_tokens=sum(prompt_lengths)/len(prompt_lengths) if prompt_lengths else None,
                                mean_canonical_full_function_tokens=sum(canonical_lengths)/len(canonical_lengths) if canonical_lengths else None,
                                syntax_errors=dict(errors))
        result['human_groups'][key] = groups
        result['code_syntax_totals'][key] = {}
        for task in ['humaneval', 'mbpp']:
            code_rows = [r for r in final if r['model_key'] == key and r['task'] == task]
            invalid = 0
            invalid_311 = 0
            for row in code_rows:
                ex = examples[row['fingerprint']]
                code = program(row['prediction'], ex['metadata']) if task == 'humaneval' else _extract_python_code(row['prediction'])
                try:
                    ast.parse(code)
                except SyntaxError:
                    invalid += 1
                try:
                    ast.parse(code, feature_version=(3, 11))
                except SyntaxError:
                    invalid_311 += 1
            result['code_syntax_totals'][key][task] = {'n': len(code_rows), 'syntax_invalid': invalid,
                                                     'syntax_invalid_python311_grammar': invalid_311}
        # Compare MATH levels within the same adopted generation cohort.
        mathrows = [r for r in final if r['model_key'] == key and r['task'] == 'math']
        oldmath = {r['fingerprint'] for r in original if r['model_key'] == key and r['task'] == 'math' and r['source'] == 'legacy_rescored'}
        level_groups = {}
        for name, ids in [('historical_ids', oldmath), ('added_ids', {r['fingerprint'] for r in mathrows}-oldmath)]:
            level_groups[name] = {str(level): {'n': sum(r['fingerprint'] in ids and examples[r['fingerprint']]['metadata']['level'] == level for r in mathrows),
                                               'correct': sum(r['fingerprint'] in ids and examples[r['fingerprint']]['metadata']['level'] == level and r['correct'] for r in mathrows)} for level in range(1, 6)}
        result['math_by_level'][key] = level_groups
        old_levels, new_levels = level_groups['historical_ids'], level_groups['added_ids']
        expected = sum(new_levels[str(level)]['n']*old_levels[str(level)]['correct']/old_levels[str(level)]['n'] for level in range(1, 6))
        result['math_standardized'][key] = {'added_correct_expected_if_historical_level_rates_held': expected,
                                            'added_n': sum(v['n'] for v in new_levels.values()),
                                            'added_correct_observed': sum(v['correct'] for v in new_levels.values()),
                                            'note': 'Descriptive reweighting using noisy historical level rates, not a causal or predictive guarantee.'}
    (HERE/'final_discrepancy_explanations.json').write_text(json.dumps(result, indent=2)+'\n')
    folder=EVAL/'llada_manual_check';folder.mkdir(exist_ok=True)
    (folder/'fresh_gemma_humaneval_failure_packet.json').write_text(json.dumps(packets, ensure_ascii=False, indent=2)+'\n')
    for key, groups in result['human_groups'].items():
        print(key, json.dumps(groups))
    print('MATH standardization', json.dumps(result['math_standardized']))
    print('GEMMA FAILURE EXAMPLES')
    chosen=[]
    for condition in [lambda p: p['syntax_error'] and 'unterminated triple' in p['syntax_error'],
                      lambda p: p['syntax_error'] is None,
                      lambda p: p['syntax_error'] and 'unterminated triple' not in p['syntax_error']]:
        chosen.extend([p for p in packets if condition(p)][:2])
    for packet in chosen:
        print('INDEX',packet['index'],'TOKENS',packet['tokens'],'ERROR',packet['syntax_error'])
        print('SPEC',packet['example']['metadata']['prompt'])
        print('OUTPUT',packet['prediction'])
        print('REFERENCE',packet['example']['target'])


if __name__ == '__main__':
    main()
