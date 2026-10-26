"""Time the exact 1B training operations using random weights, without downloads.

This measures throughput only, never learning quality. Architecture and adapter
settings match the experimental Colab; inputs are synthetic 256-token sequences.
"""
from pathlib import Path
import json
import sys
import time
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import torch
from accelerate import Accelerator
from peft import LoraConfig, get_peft_model
from transformers import AutoConfig, AutoModelForCausalLM
from diffusion_lm.distillation import causal_teacher_logits, selected_distillation_loss
from diffusion_lm.loss import selected_denoising_loss
from diffusion_lm.modeling import forward_bidirectional_selected
from train import load_training_config


def synchronize(device):
    if device.type == "mps":
        torch.mps.synchronize()
    elif device.type == "cuda":
        torch.cuda.synchronize()


def main():
    torch.manual_seed(42)
    recipe = load_training_config("llama", "quick")
    architecture = AutoConfig.from_pretrained(recipe["model_name_or_path"],
        revision=recipe["model_revision"], local_files_only=True)
    model = AutoModelForCausalLM.from_config(architecture, dtype=torch.float16)
    model.config.use_cache = False
    model.config.is_causal = False
    for parameter in model.parameters():
        parameter.requires_grad = False
    model = get_peft_model(model, LoraConfig(r=128, lora_alpha=128, lora_dropout=0,
                          target_modules=["q_proj", "v_proj"], bias="none", task_type="CAUSAL_LM"))
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    accelerator = Accelerator(mixed_precision="fp16")
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-5)
    model, optimizer = accelerator.prepare(model, optimizer)
    print(f"Device: {accelerator.device}; parameters: {sum(p.numel() for p in model.parameters()):,}", flush=True)
    labels = torch.randint(20, architecture.vocab_size, (1, 256), device=accelerator.device)
    answer = torch.zeros_like(labels, dtype=torch.bool)
    answer[:, 64:224] = True
    padding = torch.zeros_like(answer)
    padding[:, 224:] = True
    labels[padding] = 2
    mask = (answer | padding) & (torch.arange(256, device=accelerator.device)[None] % 2 == 0)
    noised = labels.clone()
    noised[mask] = 9
    batch = dict(labels=labels, answer_mask=answer, padding_mask=padding, loss_mask=mask,
                 sampled_t=torch.tensor([0.5], device=accelerator.device))
    measurements = {}
    for name, weight in (("baseline", 0.0), ("distilled", 0.5)):
        times = []
        for step in range(7):
            synchronize(accelerator.device)
            started = time.perf_counter()
            model.train()
            with accelerator.autocast():
                teacher = causal_teacher_logits(accelerator.unwrap_model(model), labels, mask) if weight else None
                logits, rows, positions = forward_bidirectional_selected(model, noised, padding, mask)
            logits = logits.float()
            loss, _ = selected_denoising_loss(logits, labels[rows, positions], rows, mask.sum(1),
                batch["sampled_t"], answer | padding, answer_padding_weights=(0.9, 0.1),
                selected_answer_mask=answer[rows, positions], selected_padding_mask=padding[rows, positions],
                answer_lengths=answer.sum(1), padding_lengths=padding.sum(1))
            if weight:
                kd = selected_distillation_loss(logits, teacher, batch, dict(temperature=1., chunk_size=64),
                    use_t_weighting=True, answer_padding_weights=(0.9, 0.1), eos_padding_loss=True)
                loss = (1-weight)*loss + weight*kd
            accelerator.backward(loss)
            accelerator.clip_grad_norm_(model.parameters(), 0.5)
            optimizer.step()
            optimizer.zero_grad()
            synchronize(accelerator.device)
            elapsed = time.perf_counter() - started
            print(f"{name} step {step + 1}: {elapsed:.3f}s", flush=True)
            if step >= 2:
                times.append(elapsed)
            del teacher, logits, loss
        measurements[name] = dict(seconds_per_update=median(times), measured_steps=times,
                                  estimated_1000_updates_minutes=median(times) * 1000 / 60)
    target = ROOT / "results/device-throughput.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(device=str(accelerator.device), random_weights=True,
        sequence_length=256, batch_size=1, gradient_accumulation_steps=1,
        measurements=measurements), indent=2) + "\n")
    print(json.dumps(measurements, indent=2), flush=True)


if __name__ == "__main__":
    main()
