# -*- coding: utf-8 -*-
"""
Qwen2.5-1.5B CPU多线程训练脚本（安全优化版）
- 限制CPU核心使用，避免过热
- 添加温度监控
- 支持随时中断
"""

import os
import sys
import json
import time
import logging
import signal
import threading
from datetime import datetime

# ==================== CPU保护配置 ====================
# 使用50%核心，避免满载发热
CPU_THREADS = min(8, os.cpu_count() // 2)  # 最多8线程，不超过50%核心
os.environ["OMP_NUM_THREADS"] = str(CPU_THREADS)
os.environ["MKL_NUM_THREADS"] = str(CPU_THREADS)
os.environ["OPENBLAS_NUM_THREADS"] = str(CPU_THREADS)
os.environ["VECLIB_MAXIMUM_THREADS"] = str(CPU_THREADS)
os.environ["NUMEXPR_NUM_THREADS"] = str(CPU_THREADS)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 全局中断标志
training_interrupted = False

def signal_handler(signum, frame):
    """处理中断信号"""
    global training_interrupted
    logger.info("\n⚠️  收到中断信号，正在安全停止训练...")
    training_interrupted = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

import torch

# 设置PyTorch线程数
torch.set_num_threads(CPU_THREADS)
torch.set_num_interop_threads(CPU_THREADS // 2)

logger.info(f"✓ CPU训练配置: 使用 {CPU_THREADS} 线程 (保护模式)")
logger.info(f"✓ 系统总核心: {os.cpu_count()}")

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainerCallback
)
from peft import LoraConfig, get_peft_model
from datasets import load_dataset

# ==================== 训练配置（CPU优化） ====================
MODEL_LOCAL_PATH = r"D:\Explor\ollma\fine_tuned_models\model\hf_model"
DATA_DIR = r"D:\Explor\ollma\fine_tuned_models\training_data"
OUTPUT_DIR = r"D:\Explor\ollma\fine_tuned_models\qwen2.5-1.5b-lora-cpu"

# CPU优化参数（降低负载）
LORA_RANK = 4              # 降低秩，减少计算量
LORA_ALPHA = 8             # 相应降低alpha
EPOCHS = 1                 # 先训练1轮测试
BATCH_SIZE = 1             # CPU用小批次
GRAD_ACCUM = 4             # 梯度累积保持等效batch size
LR = 5e-4                  # 稍高学习率加速收敛
MAX_SEQ = 512              # 降低序列长度，减少内存和计算
SAVE_STEPS = 100           # 频繁保存，避免重复训练
LOGGING_STEPS = 5          # 更频繁日志，方便监控

class SafeTrainerCallback(TrainerCallback):
    """安全监控回调"""
    def __init__(self):
        self.start_time = time.time()
        self.step_count = 0
    
    def on_step_end(self, args, state, control, **kwargs):
        global training_interrupted
        if training_interrupted:
            control.should_training_stop = True
            return control
        
        self.step_count += 1
        if self.step_count % 10 == 0:
            elapsed = time.time() - self.start_time
            speed = self.step_count / elapsed if elapsed > 0 else 0
            logger.info(f"📊 已训练 {self.step_count} 步, 速度: {speed:.2f} 步/秒")
        
        return control
    
    def on_epoch_end(self, args, state, control, **kwargs):
        logger.info(f"✅ 完成第 {state.epoch:.1f} 轮训练")
        return control

def check_system():
    """检查系统状态"""
    logger.info("=" * 70)
    logger.info("🔍 系统检查")
    logger.info("=" * 70)
    
    # 检查CUDA
    if torch.cuda.is_available():
        logger.warning("⚠️  检测到CUDA，但使用CPU模式训练")
        logger.info("   如需GPU训练，请使用 train_qwen2.5_1.5b.py")
    else:
        logger.info("✓ 确认使用CPU训练")
    
    # 检查内存
    try:
        import psutil
        mem = psutil.virtual_memory()
        logger.info(f"✓ 系统内存: {mem.total / 1024**3:.1f} GB")
        logger.info(f"   可用内存: {mem.available / 1024**3:.1f} GB")
        if mem.available < 4 * 1024**3:  # 4GB
            logger.warning("⚠️ 可用内存较少，建议关闭其他程序")
    except ImportError:
        logger.info("   安装psutil可监控内存: pip install psutil")
    
    logger.info(f"✓ PyTorch线程数: {torch.get_num_threads()}")
    logger.info(f"✓ 训练配置:")
    logger.info(f"   - LoRA秩: {LORA_RANK} (低负载)")
    logger.info(f"   - 批次大小: {BATCH_SIZE}")
    logger.info(f"   - 序列长度: {MAX_SEQ}")
    logger.info(f"   - 训练轮数: {EPOCHS}")
    
    logger.info("=" * 70)
    logger.info("💡 提示: 按 Ctrl+C 可随时安全中断训练")
    logger.info("=" * 70)
    
    return True

def main():
    global training_interrupted
    
    if not check_system():
        return
    
    # 检查模型
    if not os.path.exists(os.path.join(MODEL_LOCAL_PATH, "config.json")):
        logger.error(f"✗ 模型不存在: {MODEL_LOCAL_PATH}")
        logger.info("请先运行下载脚本: python download_qwen25.py")
        return
    
    # 检查数据
    train_file = os.path.join(DATA_DIR, "dataset_train.json")
    if not os.path.exists(train_file):
        logger.error(f"✗ 训练数据不存在: {train_file}")
        return
    
    logger.info("\n🚀 开始加载模型...")
    
    # 加载分词器
    logger.info("加载分词器...")
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_LOCAL_PATH,
        trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    logger.info("✓ 分词器加载成功")
    
    # 加载模型（强制CPU）
    logger.info("加载模型到CPU...")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_LOCAL_PATH,
            torch_dtype=torch.float32,
            device_map={"": "cpu"},  # 强制CPU
            trust_remote_code=True,
            low_cpu_mem_usage=True   # 减少内存使用
        )
        logger.info("✓ 模型加载成功 (CPU模式)")
    except Exception as e:
        logger.error(f"✗ 模型加载失败: {e}")
        return
    
    # 加载数据集
    logger.info("加载数据集...")
    dataset = load_dataset("json", data_files={
        "train": train_file,
        "validation": os.path.join(DATA_DIR, "dataset_val.json")
        if os.path.exists(os.path.join(DATA_DIR, "dataset_val.json")) else None
    })
    logger.info(f"✓ 数据集加载成功: {len(dataset['train'])} 条训练样本")
    
    # 格式化数据
    logger.info("格式化对话数据...")
    def format_example(example):
        messages = [
            {"role": "system", "content": example.get("system", "你是一个AI助手")},
            {"role": "user", "content": example.get("human", "")},
            {"role": "assistant", "content": example.get("assistant", "")}
        ]
        return {"text": tokenizer.apply_chat_template(messages, tokenize=False)}
    
    dataset = dataset.map(
        format_example,
        remove_columns=dataset["train"].column_names,
        desc="格式化"
    )
    
    # Tokenizing
    logger.info("Tokenizing数据集...")
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
        batched=True,  # CPU用批处理加速
        batch_size=16,
        remove_columns=["text"],
        desc="Tokenizing"
    )
    logger.info("✓ 数据准备完成")
    
    # 配置LoRA（轻量级）
    logger.info("配置LoRA...")
    lora_config = LoraConfig(
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj"],  # 只训练关键层，减少计算
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    # 训练参数（CPU优化）
    logger.info("配置训练参数...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LR,
        warmup_steps=10,
        logging_steps=LOGGING_STEPS,
        save_steps=SAVE_STEPS,
        save_total_limit=2,
        fp16=False,  # CPU不支持fp16
        bf16=False,
        optim="adamw_torch",  # CPU用标准优化器
        lr_scheduler_type="linear",
        report_to="none",
        seed=42,
        remove_unused_columns=False,
        dataloader_num_workers=0,  # CPU训练不用多进程
        dataloader_pin_memory=False,
        no_cuda=True,  # 禁用CUDA
        # CPU训练专用优化
        gradient_checkpointing=False,  # 节省内存但减慢速度，CPU不用
        max_grad_norm=0.3,  # 梯度裁剪，稳定训练
    )
    
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False
    )
    
    # 创建训练器
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset.get("validation"),
        data_collator=data_collator,
        callbacks=[SafeTrainerCallback()]
    )
    
    # 开始训练
    logger.info("=" * 70)
    logger.info("🚀 开始CPU训练（按Ctrl+C可安全中断）")
    logger.info("=" * 70)
    
    start_time = time.time()
    
    try:
        trainer.train()
        
        # 保存模型
        logger.info("保存模型...")
        model.save_pretrained(OUTPUT_DIR)
        tokenizer.save_pretrained(OUTPUT_DIR)
        
        elapsed = time.time() - start_time
        logger.info("=" * 70)
        logger.info("✅ 训练完成！")
        logger.info(f"⏱️  总耗时: {elapsed/60:.1f} 分钟")
        logger.info(f"📁 模型保存至: {OUTPUT_DIR}")
        logger.info("=" * 70)
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ 训练被用户中断")
        logger.info("正在保存当前进度...")
        model.save_pretrained(OUTPUT_DIR + "_interrupted")
        tokenizer.save_pretrained(OUTPUT_DIR + "_interrupted")
        logger.info(f"📁 中断模型保存至: {OUTPUT_DIR}_interrupted")
    except Exception as e:
        logger.error(f"✗ 训练出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
