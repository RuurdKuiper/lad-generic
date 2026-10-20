"""Ending policies must cooperate with block convergence and fixed tokens."""
from pathlib import Path

import pytest
import torch

from diffusion_lm.bigram import BigramScorer, BigramViterbiSelector
from diffusion_lm.inference import InferenceSession, decode_denoising_state, denoise_stream, render_denoising_step


class EndingTokenizer:
    eos_token_id = 2
    unk_token_id = 0
    chat_template = 'template'
    name_or_path = 'toy'

    def apply_chat_template(self, *args, **kwargs):
        return [1]

    def convert_tokens_to_ids(self, token):
        return 6 if token == '<end_of_turn>' else 0

    def decode(self, ids, skip_special_tokens=False, **kwargs):
        vocabulary = {2: '<EOS>', 3: 'A', 4: 'B', 5: 'C', 6: '<EOT>', 7: 'MASK'}
        return ' '.join(vocabulary.get(i, '') for i in ids if not skip_special_tokens or i not in {0, 1, 2, 6})


def session_for(schedule, *, weak_prefix=False):
    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(1))
            self.inputs = []

        def forward(self, input_ids, **kwargs):
            self.inputs.append(input_ids.clone())
            targets = schedule(len(self.inputs))
            logits = torch.full((*input_ids.shape, 8), -100.)
            for offset in range(input_ids.shape[1] - 1):
                logits[0, offset + 1, targets[offset]] = 100.
            if weak_prefix:
                logits[0, 1] = 0.
                logits[0, 1, targets[0]] = .1
            return type('Output', (), dict(logits=logits))()
    model = Model()
    return InferenceSession(model, EndingTokenizer(), torch.device('cpu'), Path('.'), {}, 7)


def select(method, remasking_confidence="diffusion"):
    if method is None:
        return None
    return BigramViterbiSelector(BigramScorer.from_sequences([], 8), .5, scoring_method=method, remasking_confidence=remasking_confidence)


@pytest.mark.parametrize('ending', [2, 6])
@pytest.mark.parametrize('method', [None, 'conditional', 'pmi'])
def test_converged_ending_stops_remaining_blocks(ending, method):
    session = session_for(lambda call: [3, ending, 4, 4, 4, 4])
    states = list(denoise_stream(session, 'Q', 'S', 6, 6, 1., 0., 1, 42,
                                early_stopping=True, block_length=3, bigram_selector=select(method)))
    assert len(states) == len(session.model.inputs) == 2
    assert states[-1][0] == 'A'
    assert 'block 1/2' in states[-1][1] and 'remaining blocks skipped' in states[-1][1]
    assert f"answer finished ({'EOS' if ending == 2 else 'EOT'})" in states[-1][1]


@pytest.mark.parametrize('ending', [2, 6])
def test_ending_on_final_block_step_stops_following_blocks(ending):
    session = session_for(lambda call: [3, 4 if call == 1 else 5 if call == 2 else ending, 4, 4, 4, 4])
    states = list(denoise_stream(session, 'Q', 'S', 6, 6, 1., 0., 1, 42,
                                early_stopping=True, block_length=3))
    assert len(session.model.inputs) == 3
    assert 'remaining blocks skipped' in states[-1][1]


def test_block_convergence_without_ending_still_advances_to_next_block():
    session = session_for(lambda call: [3] * 6)
    states = list(denoise_stream(session, 'Q', 'S', 6, 6, 1., 0., 1, 42,
                                early_stopping=True, block_length=3))
    assert len(session.model.inputs) == 4  # Two converged iterations in each block.
    assert 'block 2/2' in states[-1][1]
    assert states[-1][0] == 'A A A A A A'
    assert 'answer finished' not in states[-1][1]


@pytest.mark.parametrize('ending', [2, 6])
def test_transient_ending_does_not_end_answer(ending):
    session = session_for(lambda call: [3, ending if call == 1 else 4 if call == 2 else 5, 4, 4, 4, 4])
    states = list(denoise_stream(session, 'Q', 'S', 6, 6, 1., 0., 1, 42,
                                early_stopping=True, block_length=3))
    assert any('block 2/2' in status for _, status, _ in states)
    assert all('answer finished' not in status for _, status, _ in states)


@pytest.mark.parametrize('ending', [2, 6])
@pytest.mark.parametrize('method', [None, 'conditional', 'pmi'])
@pytest.mark.parametrize('confidence_mode', ['diffusion', 'viterbi_margin'])
def test_early_convergence_cannot_bypass_delayed_ending_retention(ending, method, confidence_mode):
    session = session_for(lambda call: [3, ending, 4, 4, 4, 4])
    states = list(denoise_stream(session, 'Q', 'S', 6, 8, 1., 0., 1, 42,
        permanent_unmask=True, confidence_guided=True, proportional_unmask=False,
        early_stopping=True, confidence_eos_eot_inf=True, block_length=3,
        bigram_selector=select(method, confidence_mode), bigram_eos_delay_penalty=1.))
    assert len(states) == len(session.model.inputs) == 4  # Complete first block's delay schedule.
    assert all(int(ids[0, 2]) == 7 for ids in session.model.inputs[1:])
    assert 'answer finished' in states[-1][1] and 'remaining blocks skipped' in states[-1][1]


@pytest.mark.parametrize('ending', [2, 6])
def test_fixed_ending_does_not_stop_until_preceding_masks_are_resolved(ending):
    session = session_for(lambda call: [3 if call == 1 else 4, ending, 4, 4, 4, 4], weak_prefix=True)
    states = list(denoise_stream(session, 'Q', 'S', 6, 6, 1., 1., 2, 42,
        permanent_unmask=True, confidence_guided=True, proportional_unmask=False,
        early_stopping=True, block_length=3,
        bigram_selector=BigramViterbiSelector(BigramScorer.from_sequences([], 8), 0.)))
    assert int(session.model.inputs[1][0, 2]) == ending  # Ending was frozen on step one.
    assert int(session.model.inputs[1][0, 1]) == 7  # Its prefix was not yet finalized.
    assert 'answer finished' not in states[0][1]
    assert int(session.model.inputs[2][0, 1]) == 7  # The higher-confidence suffix was retained before the prefix.
    assert len(states) == 3 and 'answer finished' in states[-1][1]
    assert all('MASK' in text and 'answer finished' not in status for text, status, _ in states[:-1])


@pytest.mark.parametrize('ending', [2, 6])
def test_disabling_early_stopping_keeps_full_step_budget(ending):
    session = session_for(lambda call: [3, ending, 4, 4, 4, 4])
    states = list(denoise_stream(session, 'Q', 'S', 6, 6, 1., 0., 1, 42,
                                early_stopping=False, block_length=3))
    assert len(states) == len(session.model.inputs) == 6
    assert 'block 2/2' in states[-1][1]


@pytest.mark.parametrize('ending', [2, 6])
@pytest.mark.parametrize('delay', [False, True])
def test_bigram_ending_penalty_fades_and_final_step_is_unmodified(ending, delay):
    import math
    class RecordSelector:
        def __init__(self):
            self.logits = []
            self.delegate = BigramViterbiSelector(BigramScorer.from_sequences([], 8), 0.)
        def select_block(self, logits, *args, **kwargs):
            self.logits.append(logits.clone())
            return self.delegate.select_block(logits, *args, **kwargs)
    session = session_for(lambda call: [ending] * 4)
    original = session.model.forward
    def forward(input_ids, **kwargs):
        output = original(input_ids, **kwargs)
        output.logits[:, 1:, ending] = 2.
        output.logits[:, 1:, 3] = 1.
        return output
    session.model.forward = forward
    selector = RecordSelector()
    list(denoise_stream(session, 'Q', 'S', 4, 4, 1., 0., 1, 42,
        confidence_eos_eot_inf=delay, bigram_selector=selector, bigram_eos_delay_penalty=10.))
    assert len(session.model.inputs) == len(selector.logits) == 4  # No extra forwards.
    for step, logits in enumerate(selector.logits):
        expected = 2. - math.log(10.) * (1. - (step + 1) / 4) if delay else 2.
        assert logits[0, ending].item() == pytest.approx(expected)
        assert logits[0, 3] == 1.
    assert selector.logits[-1][0, ending] == 2.
    if delay:
        assert selector.logits[0][0].argmax() == 3  # It actually changes deterministic selection.


@pytest.mark.parametrize('penalty', [0., float('nan'), float('inf')])
def test_invalid_bigram_ending_penalty(penalty):
    session = session_for(lambda call: [3] * 3)
    with pytest.raises(ValueError, match='bigram_eos_delay_penalty'):
        list(denoise_stream(session, 'Q', 'S', 3, 3, 1., 0., 1, 42,
            bigram_selector=select('pmi'), bigram_eos_delay_penalty=penalty))


def test_eot_truncates_normal_decode_and_render_even_without_delay():
    from html.parser import HTMLParser
    class Spans(HTMLParser):
        def __init__(self):
            super().__init__(); self.active = False; self.text = ''
        def handle_starttag(self, tag, attrs):
            if tag == 'span': self.active = True
        def handle_endtag(self, tag):
            if tag == 'span': self.active = False
        def handle_data(self, data):
            if self.active: self.text += data
    tokenizer = EndingTokenizer()
    assert decode_denoising_state([3, 6, 4, 2], tokenizer, 7) == 'A'
    assert decode_denoising_state([3, 6, 4, 2], tokenizer, 7, show_eos_tokens=True) == 'A <EOT> B <EOS>'
    rendered = render_denoising_step([3, 6, 4, 2], [1.] * 4, 0, tokenizer, 7, 1, 2)
    parsed = Spans(); parsed.feed(rendered)
    assert parsed.text == 'A' and '1 output tokens' in rendered


@pytest.mark.parametrize('strength', [1., 10., 1000.])
def test_ending_prediction_policy_probabilities_determine_retention(strength, monkeypatch):
    # Position 0 has high EOS mass; suppressing EOS makes its A prediction
    # look more confident under the adjusted decoding policy. Capture this
    # established behavior; changing it alters low-NFE generation quality.
    session = session_for(lambda call: [3, 3, 3])
    raw = torch.full((3, 8), -100.)
    raw[0, [2, 3, 4]] = torch.tensor([4., 2., 0.])
    raw[1, [2, 3, 4]] = torch.tensor([0., 1., .5])
    raw[2, [3, 4]] = torch.tensor([.1, 0.])
    original_forward = session.model.forward
    def forward(input_ids, **kwargs):
        output = original_forward(input_ids, **kwargs)
        output.logits[0, 1:] = raw
        return output
    session.model.forward = forward
    import diffusion_lm.inference as inference
    render = inference.render_denoising_step
    probabilities = []
    def capture(*args, **kwargs):
        probabilities.append(torch.tensor(args[1]))
        return render(*args, **kwargs)
    monkeypatch.setattr(inference, 'render_denoising_step', capture)
    states = list(denoise_stream(session, 'Q', 'S', 3, 3, 1., 1., 8, 42,
        permanent_unmask=True, proportional_unmask=False, confidence_eos_eot_inf=True,
        bigram_selector=select('pmi'), bigram_eos_delay_penalty=strength))
    # A wins at position 0 only under the strongest early prediction penalty.
    selected = torch.tensor([3 if strength == 1000. else 2, 3, 3])
    policy = raw.clone()
    policy[:, [2, 6]] -= torch.log(torch.tensor(strength ** (2. / 3.)))
    expected = policy.softmax(-1).gather(1, selected[:, None]).squeeze(1)
    torch.testing.assert_close(probabilities[0], expected)
    retained = {1.: [7, 7, 3], 10.: [7, 3, 7], 1000.: [3, 7, 7]}
    assert session.model.inputs[1][0, 1:].tolist() == retained[strength]
    assert len(session.model.inputs) == len(states) == 3
