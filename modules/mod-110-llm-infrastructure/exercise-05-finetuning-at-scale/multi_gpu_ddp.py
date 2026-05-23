"""Multi-GPU DDP fine-tune. Launch with `torchrun --nproc-per-node=4 multi_gpu_ddp.py`."""
import os

from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (AutoModelForCausalLM, AutoTokenizer,
                           TrainingArguments, Trainer)


def main():
    local_rank = int(os.environ.get("LOCAL_RANK", 0))
    base = "meta-llama/Llama-2-13b-hf"
    tok = AutoTokenizer.from_pretrained(base)
    tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(base, torch_dtype="bfloat16")

    lora = LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"],
                       task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)

    ds = load_dataset("databricks/databricks-dolly-15k", split="train[:5000]")
    ds = ds.map(lambda x: tok(x["instruction"] + "\n" + x["response"],
                                truncation=True, max_length=512), batched=True)

    Trainer(
        model=model,
        args=TrainingArguments(
            output_dir="adapters/ddp-13b",
            num_train_epochs=1,
            per_device_train_batch_size=4,
            gradient_accumulation_steps=4,
            learning_rate=2e-4,
            bf16=True,
            ddp_find_unused_parameters=False,
            local_rank=local_rank,
            logging_steps=10,
        ),
        train_dataset=ds,
    ).train()


if __name__ == "__main__":
    main()
