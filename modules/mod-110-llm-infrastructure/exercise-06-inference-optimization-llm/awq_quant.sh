#!/usr/bin/env bash
# Quantize Mistral-7B to AWQ 4-bit. Runs once (~30min), reused thereafter.
python - <<'EOF'
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer

model_path = "mistralai/Mistral-7B-Instruct-v0.2"
quant_path = "models/mistral-7b-awq"

q_config = {"zero_point": True, "q_group_size": 128, "w_bit": 4, "version": "GEMM"}
tok = AutoTokenizer.from_pretrained(model_path)
model = AutoAWQForCausalLM.from_pretrained(model_path)
model.quantize(tok, quant_config=q_config)
model.save_quantized(quant_path)
tok.save_pretrained(quant_path)
EOF
