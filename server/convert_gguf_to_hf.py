# -*- coding: utf-8 -*-
"""
GGUF 模型转换工具
将本地 GGUF 模型转换为 Hugging Face 格式，用于 LoRA 微调训练
"""

import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def convert_gguf_to_hf(gguf_path: str, output_dir: str):
    """
    将 GGUF 模型转换为 Hugging Face 格式
    
    Args:
        gguf_path: GGUF 模型文件路径
        output_dir: 输出目录
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch
    
    gguf_path = os.path.abspath(gguf_path)
    gguf_dir = os.path.dirname(gguf_path)
    gguf_file = os.path.basename(gguf_path)
    output_dir = os.path.abspath(output_dir)
    
    if not os.path.exists(gguf_path):
        raise FileNotFoundError(f"GGUF 模型文件不存在: {gguf_path}")
    
    logger.info("=" * 60)
    logger.info("🔄 GGUF -> Hugging Face 格式转换")
    logger.info("=" * 60)
    logger.info(f"源文件: {gguf_path}")
    logger.info(f"输出目录: {output_dir}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info("正在加载分词器...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            gguf_dir,
            trust_remote_code=True,
            gguf_file=gguf_file
        )
        logger.info("✓ 分词器加载成功")
    except Exception as e:
        logger.error(f"✗ 分词器加载失败: {e}")
        raise
    
    logger.info("正在加载模型...")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            gguf_dir,
            torch_dtype=torch.float32,
            device_map="auto",
            trust_remote_code=True,
            gguf_file=gguf_file
        )
        logger.info("✓ 模型加载成功")
    except Exception as e:
        logger.error(f"✗ 模型加载失败: {e}")
        raise
    
    logger.info("正在保存模型（HF 格式）...")
    model.save_pretrained(output_dir, safe_serialization=True)
    tokenizer.save_pretrained(output_dir)
    logger.info("✓ 模型保存成功")
    
    logger.info("=" * 60)
    logger.info("✅ 转换完成！")
    logger.info(f"模型已保存至: {output_dir}")
    logger.info("=" * 60)
    
    return output_dir


def main():
    gguf_path = sys.argv[1] if len(sys.argv) > 1 else r"D:\Explor\ollma\fine_tuned_models\model\qwen2.5_3b.gguf"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else r"D:\Explor\ollma\fine_tuned_models\model\hf_model"
    
    convert_gguf_to_hf(gguf_path, output_dir)


if __name__ == "__main__":
    main()
