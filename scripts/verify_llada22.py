#!/usr/bin/env python3
"""Check pinned model compatibility with tiny weights, or smoke-test the deployed Space."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "huggingface/llada22_space"))
from streaming import MODEL_ID, MODEL_REVISION, NativeStreamer


def tiny():
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(2)
    config = AutoConfig.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=True)
    for key, value in dict(hidden_size=32, intermediate_size=64, moe_intermediate_size=16,
                           num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1,
                           head_dim=16, rotary_dim=8, num_experts=4, num_experts_per_tok=2,
                           expert_capacity=4, n_group=1, topk_group=1).items():
        setattr(config, key, value)
    config._attn_implementation = "sdpa"
    # Downloads remote Python code only, never the 16B model weights.
    model = AutoModelForCausalLM.from_config(config, trust_remote_code=True,
                                             code_revision=MODEL_REVISION).eval()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=True)
    encoded = tokenizer.apply_chat_template([dict(role="user", content="Hi")],
                                             add_generation_prompt=True, tokenize=True, return_tensors="pt")
    inputs = encoded if isinstance(encoded, torch.Tensor) else encoded["input_ids"]
    for block in (32, 64):
        options = dict(gen_length=5, block_length=block, steps=2, temperature=0.,
                       max_post_steps=0, max_steps_per_block=16)
        torch.manual_seed(42)
        expected = model.generate(inputs=inputs, **options)
        torch.manual_seed(42)
        frames = list(NativeStreamer(model).stream(inputs, **options))
        assert frames[-1].tokens == expected[0].tolist()
    print(json.dumps(dict(tiny_moe_sdpa=True, native_stream_parity=True,
                          routing_block_lengths=[32, 64], revision=MODEL_REVISION)))


def live(space):
    from gradio_client import Client
    client = Client(space)
    records = []
    for method in ("Confidence-guided", "BG + TG Viterbi (Gumbel)"):
        status, html = client.predict("What is the capital of France?", "You are a helpful assistant.",
                                       32, 8, 32, 0., 16, "Prediction iteration", method, 1.,
                                       .5, 0., 4, True, 128, api_name="/generate")
        assert status.startswith("Complete"), status
        assert "Plain text / copy code" in html
        records.append(dict(method=method, status=status, html=html))
    out = ROOT / "artifacts/llada22/live-verification.json"
    out.write_text(json.dumps(dict(space=space, cases=records), indent=2) + "\n")
    print(json.dumps(dict(space=space, passed=len(records), record=str(out))))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tiny", action="store_true")
    p.add_argument("--space")
    args = p.parse_args()
    if not args.tiny and not args.space:
        p.error("Select --tiny and/or --space Ruurd/llada2.2-mini")
    if args.tiny:
        tiny()
    if args.space:
        live(args.space)


if __name__ == "__main__":
    main()
