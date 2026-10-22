import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import PreTrainedModel
from model_config import CustomTransformerConfig

class CustomTransformerModel(PreTrainedModel):
    config_class = CustomTransformerConfig

    def __init__(self, config):
        super().__init__(config)

    def forward(self, input_ids, labels=None, **kwargs):
        batch_size, seq_len = input_ids.shape
        device = input_ids.device
        masking_type = getattr(self.config, "masking_type", "bidirectional")

        if masking_type == 'bidirectional':
            base_mask = torch.ones(seq_len, seq_len, dtype=torch.bool, device=device)
        elif masking_type == 'bidirectional_masked':
            base_mask = torch.ones(seq_len, seq_len, dtype=torch.bool, device=device)
            base_mask.fill_diagonal_(False)
        elif masking_type == 'unidirectional':
            base_mask = torch.tril(torch.ones(seq_len, seq_len, dtype=torch.bool, device=device))
        else:
            raise ValueError(f"Unknown masking type: {masking_type}")

        attention_mask = base_mask.unsqueeze(0).unsqueeze(1).expand(batch_size, 1, seq_len, seq_len).clone()
        attention_mask = attention_mask.to(dtype=torch.float32)


        with torch.autocast("mps", dtype=torch.float16):
            outputs = self.llama(
                input_ids,
                attention_mask=attention_mask,
                output_hidden_states=True,
                use_cache=False,
                **kwargs
            )

        logits = outputs.logits[:, :, :self.config.vocab_size].view(batch_size, seq_len, self.config.vocab_size)
        loss = None

        if labels is not None:
            assert labels.shape == (batch_size, seq_len)
            loss_fct = nn.CrossEntropyLoss()
            loss = loss_fct(logits.view(-1, self.config.vocab_size), labels.view(-1))

        return {"loss": loss, "logits": logits} if loss is not None else {"logits": logits}
