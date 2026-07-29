import torch
from accelerate import Accelerator
from torch.optim import AdamW


def test_tiny_model_can_train_save_and_resume(tmp_path):
    accelerator = Accelerator()
    model = torch.nn.Linear(2, 2)
    optimizer = AdamW(model.parameters(), lr=.1)
    model, optimizer = accelerator.prepare(model, optimizer)
    x, y = torch.tensor([[1., 0.]]), torch.tensor([1])
    optimizer.zero_grad(); loss = torch.nn.functional.cross_entropy(model(x), y); accelerator.backward(loss); optimizer.step()
    validation_loss = torch.nn.functional.cross_entropy(model(x), y).detach().cpu()
    assert torch.isfinite(validation_loss)
    saved = {k: v.detach().cpu().clone() for k, v in accelerator.unwrap_model(model).state_dict().items()}
    checkpoint = tmp_path / "checkpoint-1"; accelerator.save_state(checkpoint)
    with torch.no_grad():
        for p in accelerator.unwrap_model(model).parameters(): p.add_(7)
    accelerator.load_state(checkpoint)
    for name, value in accelerator.unwrap_model(model).state_dict().items():
        assert torch.equal(value.cpu(), saved[name])
