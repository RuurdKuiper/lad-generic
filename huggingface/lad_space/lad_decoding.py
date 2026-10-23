"""PMI Viterbi selection for LAD's full-sequence correction loop."""
from pathlib import Path
import sys

import torch

# The publication bundle includes the shared n-gram decoding modules.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from diffusion_lm.bigram import BigramViterbiSelector


def select_lad_answer(logits, input_ids, answer_start, scorer, *, top_k=16,
                      temperature=2.0, weight=0.5, min_count=1, pmi_clip=2.0,
                      repetition_penalty_strength=0.0, repetition_excluded_token_ids=(),
                      trigram_scorer=None, trigram_weight=0.5, trigram_min_count=2,
                      trigram_clip=2.0, randomized_viterbi=False,
                      independent_temperature=False):
    """Replace every answer position, including visible, previously retained IDs.

    LAD was trained to correct unmasked tokens. No answer row becomes a frozen
    singleton merely because it was not re-noised. The prompt supplies fixed left
    context and is returned unchanged. Confidence uses the selected token's raw
    full-vocabulary diffusion probability, after the caller's EOS bias.
    """
    if logits.ndim != 2 or logits.shape[0] != len(input_ids):
        raise ValueError("Expected logits [sequence length, vocabulary]")
    if not 0 <= answer_start < len(input_ids):
        raise ValueError("The prompt must leave at least one answer position")
    if logits.shape[-1] != scorer.vocab_size:
        raise ValueError("LAD output vocabulary does not match the bigram checkpoint")
    selector = BigramViterbiSelector(
        scorer, weight, scoring_method="pmi", min_count=min_count, pmi_clip=pmi_clip,
        remasking_confidence="diffusion",
        trigram_scorer=trigram_scorer, trigram_weight=trigram_weight,
        trigram_min_count=trigram_min_count, trigram_clip=trigram_clip,
        randomized_viterbi=randomized_viterbi,
        independent_temperature=independent_temperature,
    )
    current = torch.as_tensor(input_ids[answer_start:], dtype=torch.long, device=logits.device)
    selected, confidence = selector.select_block(
        logits[answer_start:], current, torch.ones_like(current, dtype=torch.bool),
        top_k=top_k, temperature=temperature,
        left_id=input_ids[answer_start - 1] if answer_start else None,
        repetition_penalty_strength=repetition_penalty_strength,
        repetition_excluded_token_ids=repetition_excluded_token_ids,
    )
    # Keep the legacy full-sequence confidence shape. Prompt entries are unused.
    full_confidence = torch.cat((confidence.new_zeros(answer_start), confidence))
    return list(input_ids[:answer_start]) + selected.tolist(), full_confidence
