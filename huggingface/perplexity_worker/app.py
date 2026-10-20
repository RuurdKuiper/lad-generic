"""Private, temporary Phi-4 scoring worker for saved generation experiments."""
import gc
import math
import os

import gradio as gr
import spaces
import torch
from huggingface_hub import snapshot_download
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

MODEL = 'microsoft/phi-4'
REVISION = os.environ['REFERENCE_REVISION']
PATH = snapshot_download(MODEL, revision=REVISION,
                         allow_patterns=['*.json', '*.safetensors', '*.model', '*.tiktoken'])
TOKENIZER = AutoTokenizer.from_pretrained(PATH)


@spaces.GPU(size='large', duration=180)
def score(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 240:
        raise gr.Error('Provide 1–240 keyed answers.')
    if any(not isinstance(r.get('text'), str) or len(r['text']) > 16000 for r in rows):
        raise gr.Error('Invalid answer.')
    model = AutoModelForCausalLM.from_pretrained(
        PATH, torch_dtype=torch.bfloat16, device_map={'': 0},
        quantization_config=BitsAndBytesConfig(load_in_4bit=True,
            bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16)).eval()
    results = []
    try:
        with torch.inference_mode():
            for row in rows:
                ids = TOKENIZER(row['text'], return_tensors='pt',
                                add_special_tokens=True).input_ids.to('cuda')
                count = ids.shape[1] - 1
                nll = None
                if count > 0:
                    logits = model(input_ids=ids, use_cache=False).logits[:, :-1].float()
                    nll = torch.nn.functional.cross_entropy(
                        logits.transpose(1, 2), ids[:, 1:], reduction='sum').item()
                    del logits
                results.append(dict(key=row['key'], nll=nll, tokens=max(0, count),
                    perplexity=math.exp(nll / count) if nll is not None else None))
        return dict(model=MODEL, revision=REVISION, quantization='NF4 double quantization, BF16 compute',
                    conditioning='Standalone answers, add_special_tokens=True; first token unscored', results=results)
    finally:
        del model
        gc.collect()
        torch.cuda.empty_cache()


with gr.Blocks() as demo:
    gr.Markdown('Private Phi-4 perplexity evaluation worker')
    inputs = gr.JSON(label='Keyed answers')
    outputs = gr.JSON(label='Token counts and summed negative log likelihood')
    gr.Button('Score').click(score, inputs, outputs, api_name='score')
demo.queue(default_concurrency_limit=1).launch(ssr_mode=False)
