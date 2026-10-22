import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from diffusion_lm.bigram import BigramScorer


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DECODING = load_module("lad_decoding_test", ROOT / "huggingface/lad_space/lad_decoding.py")


def app_functions(names, namespace):
    """Test the hosted inference functions without loading the legacy 8B model."""
    tree = ast.parse((ROOT / "huggingface/lad_space/app.py").read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    for function in functions:
        function.decorator_list = []
    exec(compile(ast.Module(body=functions, type_ignores=[]), "lad_app", "exec"), namespace)
    return namespace


@pytest.mark.parametrize("length", [1, 8, 64, 128, 256])
@pytest.mark.parametrize("temperature,top_k,weight", [(0, 3, .5), (2, 1, .5), (2, 3, 0)])
def test_lad_greedy_limits_preserve_prompt_and_return_full_vocabulary_confidence(length, temperature, top_k, weight):
    scorer = BigramScorer.from_sequences([[0, 1, 2]] * 10, 3)
    logits = torch.randn(length + 2, 3, generator=torch.Generator().manual_seed(7))
    current = [2, 1] + [0] * length
    selected, confidence = DECODING.select_lad_answer(
        logits, current, 2, scorer, temperature=temperature, top_k=top_k, weight=weight,
    )
    assert selected[:2] == current[:2]
    assert selected[2:] == logits[2:].argmax(-1).tolist()
    expected = logits[2:].softmax(-1).gather(1, torch.tensor(selected[2:])[:, None]).squeeze(1)
    torch.testing.assert_close(confidence[2:], expected)
    assert confidence.shape == (length + 2,)


def test_viterbi_replaces_visible_tokens_without_remasking_and_uses_prompt_boundary():
    scorer = BigramScorer.from_sequences([[0, 1]] * 100 + [[2, 2]] * 100, 3)
    logits = torch.tensor([[0., 0., 0.], [.1, 0., -.1]])
    selected, _ = DECODING.select_lad_answer(logits, [0, 2], 1, scorer)
    assert selected == [0, 1]  # Visible answer 2 is editable; boundary favors 0 -> 1.


def test_lad_rejects_incompatible_vocabulary_and_empty_answer():
    scorer = BigramScorer.from_sequences([[0, 1]], 3)
    with pytest.raises(ValueError, match="vocabulary"):
        DECODING.select_lad_answer(torch.zeros(2, 4), [0, 1], 1, scorer)
    with pytest.raises(ValueError, match="answer position"):
        DECODING.select_lad_answer(torch.zeros(2, 3), [0, 1], 2, scorer)


@pytest.mark.parametrize("strategy", ["PMI Viterbi", "PMI Viterbi + Repetition Penalty"])
def test_lad_runs_one_forward_per_iteration_and_corrects_unmasked_output(strategy):
    scorer = BigramScorer.from_sequences([[0, 1]] * 100 + [[2, 2]] * 100, 3)
    seen = []

    def forward(*, input_ids):
        seen.append(input_ids[0].tolist())
        logits = torch.tensor([[[0., 0., 0.], [.1, 0., -.1]]])
        if len(seen) > 1:
            logits[0, 1] = torch.tensor([-10., -10., 10.])
        return {"logits": logits}

    namespace = app_functions({"_generate_step"}, dict(
        torch=torch, model=SimpleNamespace(device=torch.device("cpu"), __call__=forward),
        eos_token_id=2, _bigram_scorer=lambda: scorer,
        select_lad_answer=DECODING.select_lad_answer, BIGRAM_WEIGHT=.5,
        PMI_MIN_COUNT=1, PMI_CLIP=2., ENDING_TOKEN_IDS=(2,),
    ))
    # Special methods are looked up on the type, rather than an instance attribute.
    class Model:
        device = torch.device("cpu")

        def __call__(self, **kwargs):
            return forward(**kwargs)

    namespace["model"] = Model()
    generate = namespace["_generate_step"]
    selected, _ = generate([0, 2], 1., 3, answer_start=1,
                           decoding_strategy=strategy, temperature=2.)
    assert selected == [0, 1]
    corrected, _ = generate(selected, 1., 3, answer_start=1,
                            decoding_strategy=strategy, temperature=2.)
    assert corrected == [0, 2]
    assert seen == [[0, 2], [0, 1]]  # No mask or additional scoring forward.


def test_original_lad_strategy_ignores_gamma_and_new_zero_gamma_matches_exactly():
    scorer = BigramScorer.from_sequences([[0, 1, 0, 1]] * 20, 3)
    logits = torch.tensor([[[.1, .2, 0.]] * 6])

    class Model:
        device = torch.device("cpu")

        def __call__(self, **kwargs):
            return {"logits": logits.clone()}

    namespace = app_functions({"_generate_step"}, dict(
        torch=torch, model=Model(), eos_token_id=2, _bigram_scorer=lambda: scorer,
        select_lad_answer=DECODING.select_lad_answer, BIGRAM_WEIGHT=.5, PMI_MIN_COUNT=1, PMI_CLIP=2., ENDING_TOKEN_IDS=(2,),
    ))
    generate = namespace["_generate_step"]
    original, original_confidence = generate([2] * 6, 1., 3, answer_start=1,
        decoding_strategy="PMI Viterbi", repetition_penalty_strength=99.)
    zero, zero_confidence = generate([2] * 6, 1., 3, answer_start=1,
        decoding_strategy="PMI Viterbi + Repetition Penalty", repetition_penalty_strength=0.)
    assert zero == original
    np.testing.assert_array_equal(zero_confidence, original_confidence)


def test_default_sampling_preserves_legacy_distribution_and_seeded_draws():
    tree = ast.parse((ROOT / "huggingface/lad_space/infer.py").read_text())
    filtering = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "filter_logits")
    namespace = {"torch": torch}
    exec(compile(ast.Module(body=[filtering], type_ignores=[]), "lad_infer", "exec"), namespace)
    logits = torch.tensor([[[.1, .5, -.2], [.3, .1, .4], [1., -.4, .1]]])

    class Model:
        device = torch.device("cpu")

        def __call__(self, **kwargs):
            return {"logits": logits.clone()}

    namespace.update(model=Model(), eos_token_id=2)
    app_functions({"_generate_step"}, namespace)
    adjusted = logits.clone()
    adjusted[:, :, 2] += .2
    filtered = namespace["filter_logits"](adjusted, top_k=2, top_p=.9)
    probabilities = filtered.clamp(min=-1e8, max=1e4).softmax(-1)[0].clamp(min=1e-8, max=1.)
    torch.manual_seed(17)
    expected = torch.multinomial(probabilities, num_samples=1).squeeze(-1)
    torch.manual_seed(17)
    selected, confidence = namespace["_generate_step"]([0, 0, 0], .9, 2, eos_bias=.2)
    assert selected == expected.tolist()
    np.testing.assert_allclose(confidence, probabilities.gather(1, expected[:, None]).squeeze(1).numpy())


@pytest.mark.parametrize("permanent_unmasking", [False, True])
def test_lad_loop_keeps_visible_tokens_editable_and_aligns_noising_confidence(permanent_unmasking):
    seen, noising_confidence = [], []
    tokenizer = SimpleNamespace(
        convert_ids_to_tokens=lambda ids: list(map(str, ids)),
        decode=lambda ids, **kwargs: " ".join(map(str, ids)),
    )

    def generate(ids, *args, **kwargs):
        seen.append(ids[:])
        return [0, len(seen), 3], np.array([0., .2, .7])

    def noise(ids, answer_start, tokenizer, confidences, *args, **kwargs):
        noising_confidence.append(list(confidences))
        return ids[:], []

    namespace = app_functions({"run_diffusion_loop"}, dict(
        tokenizer=tokenizer, mask_token_id=9, eos_token_id=8,
        noisify_answer=lambda ids, *args, **kwargs: (ids[:], []),
        confidence_guided_noising=noise, _generate_step=generate,
        get_noising_schedule=lambda *args, **kwargs: 1.,
        render_html=lambda label, text: text,
        highlight_tokens=lambda *args, **kwargs: "", html_escape=lambda text: text,
    ))
    list(namespace["run_diffusion_loop"](
        [0, 9, 9], 1, 2, 0, 0, 1, 0, True, permanent_unmasking,
        .01, 1., 16, 2, 3, "PMI Viterbi", 2.,
    ))
    assert seen == [[0, 9, 9], [0, 1, 3]]
    assert noising_confidence == [[.2, .7]]


def test_lad_bundle_contains_shared_scorer_and_can_be_rebuilt(tmp_path):
    publisher = load_module("publish_lad_test", ROOT / "huggingface/publish_lad_viterbi.py")
    checkpoint = tmp_path / "llama.pt"
    checkpoint.write_bytes(b"test checkpoint")
    destination = tmp_path / "bundle"
    publisher.make_space_bundle(destination, checkpoint)
    publisher.make_space_bundle(destination, checkpoint)
    assert (destination / "bigram.pt").read_bytes() == checkpoint.read_bytes()
    assert (destination / "src/diffusion_lm/bigram.py").read_bytes() == (ROOT / "src/diffusion_lm/bigram.py").read_bytes()
    assert not (destination / "src/diffusion_lm/inference.py").exists()
    assert (destination / "models.py").is_file()


def test_missing_lad_checkpoint_stops_publication(tmp_path):
    publisher = load_module("publish_lad_missing_test", ROOT / "huggingface/publish_lad_viterbi.py")
    with pytest.raises(FileNotFoundError):
        publisher.make_space_bundle(tmp_path / "bundle", tmp_path / "missing.pt")
