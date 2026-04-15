# -*- coding: utf-8 -*-
"""
Qwen2.5 LoRA 微调训练脚本
使用 Hugging Face 格式模型进行训练
"""

import os
import sys
import json
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

os.environ["HF_ENDPOINT"] = "https://www.modelscope.cn/hf-mirror"
os.environ["HF_HOME"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.environ["TRANSFORMERS_CACHE"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
    Trainer
)
from peft import LoraConfig, get_peft_model
from datasets import load_dataset

MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "training_data")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_qwen2.5_1.5b")
MAX_SEQ = 2048
LORA_RANK = 16
LORA_ALPHA = 32
EPOCHS = 3
BATCH_SIZE = 2

def main():
    logger.info("=" * 70)
    logger.info("开始 LoRA 微调训练")
    logger.info("=" * 70)

    logger.info(f"加载模型: {MODEL_NAME}")
    logger.info("加载分词器...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    logger.info("加载模型...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float32,
        device_map="auto",
        trust_remote_code=True
    )

    logger.info("加载数据集...")
    dataset = load_dataset("json", data_files={
        "train": os.path.join(DATA_DIR, "dataset_train.json"),
        "validation": os.path.join(DATA_DIR, "dataset_val.json")
    })

    logger.info("格式化对话数据...")
    def format_example(example):
        messages = [
            {"role": "system", "content": example["system"]},
            {"role": "user", "content": example["human"]},
            {"role": "assistant", "content": example["assistant"]}
        ]
        return {"text": tokenizer.apply_chat_template(messages, tokenize=False)}
    
    dataset = dataset.map(
        format_example,
        remove_columns=dataset["train"].column_names,
        desc="Formatting"
    )

    logger.info("Tokenizing 数据集...")
    def tokenize_function(examples):
        tokenized = tokenizer(
            examples["text"],
            truncation=True,
            max_length=MAX_SEQ,
            padding="max_length",
            return_tensors=None
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized
    
    dataset = dataset.map(
        tokenize_function,
        batched=False,
        remove_columns=["text"],
        desc="Tokenizing"
    )

    logger.info("配置 LoRA...")
    lora_config = LoraConfig(
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
        task_type="CAUSAL_LM"
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    logger.info("开始训练...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LR,
        warmup_ratio=0.05,
        logging_steps=10,
        save_steps=500,
        save_total_limit=3,
        fp16=False,
        optim="paged_adamw_32bit",
        lr_scheduler_type="cosine",
        report_to="none",
        seed=42,
        remove_unused_columns=False,
    )

    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset.get("validation"),
        data_collator=data_collator,
    )

    trainer.train()
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    logger.info("=" * 70)
    logger.info("训练完成！模型保存至: " + OUTPUT_DIR)
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
