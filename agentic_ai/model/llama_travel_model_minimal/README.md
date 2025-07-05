# Minimal Travel Model for Inference

This is a minimal version of the Llama-3-8B travel model fine-tuned on Alpaca dataset.

## Essential Files:
- `tokenizer.json` - 8.66 MB
- `tokenizer_config.json` - 0.05 MB
- `special_tokens_map.json` - 0.00 MB
- `adapter_model.safetensors` - 640.06 MB
- `adapter_config.json` - 0.00 MB
- `README.md` - 0.00 MB

**Total size:** 648.78 MB
**Extracted on:** 2025-06-24 17:38:07

## Usage Example:
```python
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained('path/to/this/folder')

# Load base model
base_model = AutoModelForCausalLM.from_pretrained(
    'meta-llama/Meta-Llama-3-8B-Instruct',
    torch_dtype=torch.float16,
    device_map='auto'
)

# Load LoRA adapter
model = PeftModel.from_pretrained(base_model, 'path/to/this/folder')
```

## Testing Commands:
```bash
# Test the minimal model
python test_minimal_model.py
```
