"""4-bit QLoRA on a 13B model — fits in a single 24GB GPU."""
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                           TrainingArguments, Trainer)


def main():
    base = "meta-llama/Llama-2-13b-hf"
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype="bfloat16",
        bnb_4bit_use_double_quant=True,
    )
    tok = AutoTokenizer.from_pretrained(base)
    tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(base, quantization_config=bnb,
                                                  device_map="auto")
    model = prepare_model_for_kbit_training(model)

    lora = LoraConfig(r=64, lora_alpha=16, lora_dropout=0.1,
                       target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
                       task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)

    ds = load_dataset("databricks/databricks-dolly-15k", split="train[:5000]")
    ds = ds.map(lambda x: tok(x["instruction"] + "\n" + x["response"],
                                truncation=True, max_length=512), batched=True)

    Trainer(
        model=model,
        args=TrainingArguments(
            output_dir="adapters/qlora-13b",
            num_train_epochs=1,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=8,
            learning_rate=1e-4,
            bf16=True,
            optim="paged_adamw_8bit",
            logging_steps=10,
        ),
        train_dataset=ds,
    ).train()
    model.save_pretrained("adapters/qlora-13b")


if __name__ == "__main__":
    main()
