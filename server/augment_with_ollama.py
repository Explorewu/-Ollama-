# -*- coding: utf-8 -*-
"""
使用Ollama模型进行增量训练（通过API方式）
利用已有模型生成更多训练数据，提升模型质量
"""

import os
import json
import time
import logging
import requests
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"

# 角色设定
PERSONAS = [
    {
        "name": "古代书生",
        "system": "你是一位温文尔雅的古代书生，饱读诗书，谈吐文雅。请用古典雅致的语言风格与用户交流，适当引用诗词典故。",
        "topics": ["月亮", "春天", "秋天", "山水", "离别", "思念", "饮酒", "赏花"]
    },
    {
        "name": "文学大师", 
        "system": "你是一位精通古典诗词的文学大师，请创作符合格律要求的原创诗词。",
        "topics": ["七言绝句", "五言律诗", "词牌-水调歌头", "词牌-清平乐", "现代诗"]
    },
    {
        "name": "故事讲述者",
        "system": "你是一位擅长讲述民间故事的说书人，语言生动有趣，情节引人入胜。",
        "topics": ["神话故事", "民间传说", "历史典故", "成语故事"]
    }
]

def generate_conversation(persona, topic, existing_data=None):
    """使用Ollama生成对话数据"""
    
    # 构建提示词
    system_prompt = f"""你是{persona['name']}。{persona['system']}

请根据以下主题生成一段高质量的对话训练数据，格式为JSON：
{{
    "system": "系统提示词",
    "human": "用户问题",
    "assistant": "助手回答"
}}

主题：{topic}
要求：
1. human问题要自然、具体
2. assistant回答要符合角色设定，高质量
3. 只输出JSON格式，不要其他内容"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": system_prompt,
                "system": persona['system'],
                "stream": False,
                "options": {
                    "temperature": 0.8,
                    "top_p": 0.9
                }
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('response', '')
            
            # 尝试解析JSON
            try:
                # 清理可能的Markdown代码块
                content = content.replace('```json', '').replace('```', '').strip()
                data = json.loads(content)
                
                # 验证必要字段
                if all(k in data for k in ['system', 'human', 'assistant']):
                    return data
                else:
                    logger.warning(f"生成的数据缺少必要字段: {content[:100]}")
                    return None
                    
            except json.JSONDecodeError:
                logger.warning(f"JSON解析失败: {content[:100]}")
                return None
        else:
            logger.error(f"API调用失败: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"生成对话时出错: {e}")
        return None

def augment_training_data():
    """扩充训练数据"""
    
    logger.info("=" * 70)
    logger.info("🚀 开始扩充训练数据")
    logger.info("=" * 70)
    
    # 读取现有数据
    data_dir = r"D:\Explor\ollma\fine_tuned_models\training_data"
    train_file = os.path.join(data_dir, "dataset_train.json")
    
    existing_data = []
    if os.path.exists(train_file):
        with open(train_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        logger.info(f"✓ 读取现有数据: {len(existing_data)} 条")
    
    # 生成新数据
    new_data = []
    total_targets = 50  # 目标生成50条新数据
    
    logger.info(f"🎯 目标生成 {total_targets} 条新训练数据")
    logger.info("⏳ 这可能需要10-20分钟，请耐心等待...")
    
    for persona in PERSONAS:
        logger.info(f"\n📝 生成 {persona['name']} 的对话...")
        
        for topic in persona['topics']:
            for i in range(2):  # 每个主题生成2条
                logger.info(f"  主题: {topic} ({i+1}/2)")
                
                data = generate_conversation(persona, topic, existing_data)
                if data:
                    new_data.append(data)
                    logger.info(f"  ✓ 成功生成第 {len(new_data)} 条数据")
                
                # 每生成5条保存一次
                if len(new_data) % 5 == 0 and new_data:
                    save_augmented_data(existing_data + new_data, data_dir)
                
                time.sleep(1)  # 避免请求过快
                
                if len(new_data) >= total_targets:
                    break
            
            if len(new_data) >= total_targets:
                break
        
        if len(new_data) >= total_targets:
            break
    
    # 合并并保存
    all_data = existing_data + new_data
    save_augmented_data(all_data, data_dir)
    
    logger.info("=" * 70)
    logger.info(f"✅ 数据扩充完成！")
    logger.info(f"📊 原有数据: {len(existing_data)} 条")
    logger.info(f"📊 新增数据: {len(new_data)} 条")
    logger.info(f"📊 总计: {len(all_data)} 条")
    logger.info("=" * 70)
    
    return all_data

def save_augmented_data(data, data_dir):
    """保存扩充后的数据"""
    os.makedirs(data_dir, exist_ok=True)
    
    # 分割训练集和验证集 (90:10)
    split_idx = int(len(data) * 0.9)
    train_data = data[:split_idx]
    val_data = data[split_idx:]
    
    # 保存
    with open(os.path.join(data_dir, "dataset_train.json"), 'w', encoding='utf-8') as f:
        json.dump(train_data, f, ensure_ascii=False, indent=2)
    
    with open(os.path.join(data_dir, "dataset_val.json"), 'w', encoding='utf-8') as f:
        json.dump(val_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"💾 已保存: 训练集 {len(train_data)} 条, 验证集 {len(val_data)} 条")

def create_modelfile():
    """创建优化的Modelfile"""
    
    modelfile_content = '''FROM qwen2.5:3b

SYSTEM """你是一位精通中国古典文学的AI助手。你擅长：
1. 创作符合格律的古典诗词（绝句、律诗、词牌）
2. 用典雅的文言文风格交流
3. 讲述生动的民间故事和历史典故
4. 引用经典诗词，意境优美

请用中文回答，保持文雅、含蓄、有意境的风格。"""

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_ctx 4096

LICENSE Apache-2.0
'''
    
    output_path = r"D:\Explor\ollma\fine_tuned_models\Modelfile"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(modelfile_content)
    
    logger.info(f"✅ Modelfile已创建: {output_path}")

def main():
    logger.info("=" * 70)
    logger.info("🎭 Ollama模型增量训练工具")
    logger.info("=" * 70)
    
    # 检查Ollama
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            logger.info("✓ Ollama服务运行正常")
        else:
            logger.error("✗ Ollama服务未响应")
            return
    except:
        logger.error("✗ 无法连接到Ollama，请确保Ollama已启动")
        logger.info("   运行: ollama serve")
        return
    
    # 扩充数据
    augment_training_data()
    
    # 创建Modelfile
    create_modelfile()
    
    logger.info("\n" + "=" * 70)
    logger.info("🎉 所有步骤完成！")
    logger.info("=" * 70)
    logger.info("\n📦 创建微调模型:")
    logger.info("   ollama create literary-assistant -f fine_tuned_models\\Modelfile")
    logger.info("\n🚀 测试模型:")
    logger.info("   ollama run literary-assistant")
    logger.info("\n💡 提示: 虽然这不是传统意义上的'训练'，但通过扩充高质量")
    logger.info("   训练数据并优化系统提示词，可以达到类似微调的效果！")

if __name__ == "__main__":
    main()
