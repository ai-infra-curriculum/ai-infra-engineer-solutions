"""Single-GPU LoRA on Mistral-7B."""
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (AutoModelForCausalLM, AutoTokenizer,
                           TrainingArguments, Trainer)


def main():
    base = "mistralai/Mistral-7B-Instruct-v0.2"
    tok = AutoTokenizer.from_pretrained(base)
    model = AutoModelForCausalLM.from_pretrained(base, torch_dtype="bfloat16",
                                                  device_map="auto")

    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                       target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    ds = load_dataset("databricks/databricks-dolly-15k", split="train[:1000]")
    def format_fn(ex):
        return {"text": f"### Instruction:\n{ex['instruction']}\n\n### Response:\n{ex['response']}"}
    ds = ds.map(format_fn).map(lambda x: tok(x["text"], truncation=True, max_length=512),
                                  batched=True)

    args = TrainingArguments(
        output_dir="adapters/dolly-lora",
        num_train_epochs=2,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        bf16=True,
        logging_steps=10,
        save_strategy="epoch",
    )
    Trainer(model=model, args=args, train_dataset=ds).train()
    model.save_pretrained("adapters/dolly-lora")


if __name__ == "__main__":
    main()
