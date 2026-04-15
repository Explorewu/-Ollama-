# -*- coding: utf-8 -*-
"""
Qwen2.5-1.5B LoRA 微调训练脚本
直接从 HuggingFace 国内镜像下载模型进行训练
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

# 设置 HuggingFace 镜像
HF_MIRROR = "https://www.modelscope.cn/hf-mirror"

import torch
import huggingface_hub
from huggingface_hub import snapshot_download
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
    Trainer
)
from peft import LoraConfig, get_peft_model
from datasets import load_dataset

# ==================== 配置 ====================
MODEL_REPO = "Qwen/Qwen2.5-1.5B-Instruct"
MODEL_LOCAL_PATH = r"D:\Explor\ollma\fine_tuned_models\model\hf_model"
DATA_DIR = r"D:\Explor\ollma\fine_tuned_models\training_data"
OUTPUT_DIR = r"D:\Explor\ollma\fine_tuned_models\qwen2.5-1.5b-lora"

LORA_RANK = 8
LORA_ALPHA = 16
EPOCHS = 3
BATCH_SIZE = 2
GRAD_ACCUM = 8
LR = 3e-4
MAX_SEQ = 1536


def download_model():
    """从国内镜像下载模型"""
    global MODEL_REPO, MODEL_LOCAL_PATH
    
    if os.path.exists(os.path.join(MODEL_LOCAL_PATH, "config.json")):
        logger.info(f"✓ 模型已存在于本地: {MODEL_LOCAL_PATH}")
        return MODEL_LOCAL_PATH
    
    logger.info(f"从镜像下载模型: {MODEL_REPO}")
    logger.info(f"输出目录: {MODEL_LOCAL_PATH}")
    
    os.makedirs(os.path.dirname(MODEL_LOCAL_PATH), exist_ok=True)
    
    try:
        huggingface_hub.hf_hub_download(
            repo_id=MODEL_REPO,
            filename="config.json",
            repo_type="model",
            local_dir=MODEL_LOCAL_PATH,
            local_dir_use_symlinks=False
        )
        logger.info("✓ 模型下载成功！")
        return MODEL_LOCAL_PATH
    except Exception as e:
        logger.warning(f"直接下载失败: {e}")
        logger.info("尝试使用 snapshot_download...")
        
        try:
            snapshot_download(
                repo_id=MODEL_REPO,
                repo_type="model",
                local_dir=MODEL_LOCAL_PATH,
                local_dir_use_symlinks=False,
                endpoint=HF_MIRROR
            )
            logger.info("✓ 模型下载成功！")
            return MODEL_LOCAL_PATH
        except Exception as e2:
            logger.error(f"镜像下载也失败: {e2}")
            logger.info("回退到 HuggingFace 官方源...")
            
            try:
                snapshot_download(
                    repo_id=MODEL_REPO,
                    repo_type="model",
                    local_dir=MODEL_LOCAL_PATH,
                    local_dir_use_symlinks=False
                )
                logger.info("✓ 从官方源下载成功！")
                return MODEL_LOCAL_PATH
            except Exception as e3:
                logger.error(f"所有下载方式都失败: {e3}")
                return None


def main():
    logger.info("=" * 70)
    logger.info("开始 Qwen2.5-1.5B LoRA 微调训练")
    logger.info("=" * 70)
    
    logger.info(f"模型仓库: {MODEL_REPO}")
    logger.info(f"模型本地路径: {MODEL_LOCAL_PATH}")
    logger.info(f"数据目录: {DATA_DIR}")
    logger.info(f"输出目录: {OUTPUT_DIR}")
    
    # 检查CUDA
    if torch.cuda.is_available():
        logger.info(f"✓ CUDA 可用: {torch.cuda.get_device_name(0)}")
        device_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        logger.info(f"  显存: {device_mem:.1f} GB")
    else:
        logger.warning("⚠️ CUDA 不可用，将使用 CPU 训练（速度较慢）")
    
    # 下载模型
    logger.info("准备模型...")
    model_path = download_model()
    if not model_path:
        logger.error("✗ 模型下载失败，训练终止")
        return
    
    # 加载分词器
    logger.info("加载分词器...")
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    logger.info("✓ 分词器加载成功")
    
    # 加载模型
    logger.info("加载模型...")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float32,
            device_map="auto",
            trust_remote_code=True
        )
        logger.info("✓ 模型加载成功")
    except Exception as e:
        logger.error(f"✗ 模型加载失败: {e}")
        logger.info("尝试使用 CPU...")
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float32,
            device_map={"": "cpu"},
            trust_remote_code=True
        )
        logger.info("✓ 模型加载成功 (CPU模式)")
    
    # 加载数据集
    logger.info("加载数据集...")
    train_file = os.path.join(DATA_DIR, "dataset_train.json")
    val_file = os.path.join(DATA_DIR, "dataset_val.json")
    
    if not os.path.exists(train_file):
        logger.error(f"✗ 训练数据不存在: {train_file}")
        logger.info("请先运行 model_fine_tune.py 生成训练数据")
        return
    
    dataset = load_dataset("json", data_files={
        "train": train_file,
        "validation": val_file if os.path.exists(val_file) else None
    })
    logger.info(f"✓ 数据集加载成功: {len(dataset['train'])} 条训练样本")
    
    # 格式化对话数据
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
    logger.info("✓ 数据格式化完成")
    
    # Tokenizing
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
    logger.info("✓ Tokenizing 完成")
    
    # 配置 LoRA
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
    
    # 训练参数
    logger.info("配置训练参数...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LR,
        warmup_ratio=0.05,
        logging_steps=10,
        save_steps=300,
        save_total_limit=3,
        fp16=False,
        optim="paged_adamw_32bit",
        lr_scheduler_type="cosine",
        report_to="none",
        seed=42,
        remove_unused_columns=False,
        dataloader_pin_memory=False,
        dataloader_num_workers=0,
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
    
    # 开始训练
    logger.info("=" * 70)
    logger.info("开始训练...")
    logger.info("=" * 70)
    
    trainer.train()
    
    # 保存模型
    logger.info("保存模型...")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    
    logger.info("=" * 70)
    logger.info("✅ 训练完成！")
    logger.info(f"模型保存至: {OUTPUT_DIR}")
    logger.info("=" * 70)
    
    logger.info("\n📦 导出到 Ollama:")
    logger.info(f"  1. 转换模型: python convert_hf_to_gguf.py {OUTPUT_DIR}")
    logger.info(f"  2. 创建 Modelfile")
    logger.info(f"  3. ollama create literary-assistant -f Modelfile")


if __name__ == "__main__":
    main()
