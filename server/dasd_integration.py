# =====================================================
# DASD-4B-Thinking 后端集成
# 功能：Ollma 系统后端 API 集成
# 路径：<project_root>\server\dasd_integration.py
# =====================================================

import requests
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class DASDIntegration:
    """DASD-4B-Thinking 模型集成类"""
    
    def __init__(self, ollama_host: str = "http://localhost:11434"):
        """
        初始化 DASD 集成
        
        Args:
            ollama_host: Ollama 服务地址
        """
        self.ollama_host = ollama_host
        self.model_name = "dasd-4b-thinking"
        self.api_url = f"{ollama_host}/api/generate"
        self.tags_url = f"{ollama_host}/api/tags"
    
    def is_available(self) -> bool:
        """检查模型是否可用"""
        try:
            response = requests.get(self.tags_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return any(self.model_name in m["name"] for m in models)
            return False
        except Exception as e:
            logger.error(f"检查模型可用性失败: {e}")
            return False
    
    def chat(self, prompt: str, 
             temperature: float = 0.9,
             max_tokens: int = 32768,
             stream: bool = False) -> Dict[str, Any]:
        """
        发送对话请求
        
        Args:
            prompt: 输入提示词
            temperature: 温度参数 (0.1-2.0)，推理模型推荐 0.9
            max_tokens: 最大生成 token 数，推理模型推荐 32768
            stream: 是否流式输出
            
        Returns:
            Dict: 包含 response 和统计信息的字典
        """
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "top_k": 50,
                    "top_p": 0.95,
                    "repeat_penalty": 1.0,
                    "frequency_penalty": 0.0,
                    "mirostat": 0,
                    "num_batch": 1,
                    "think": True
                }
            }
            
            response = requests.post(self.api_url, json=payload, timeout=120)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "response": data.get("response", ""),
                    "model": self.model_name,
                    "stats": {
                        "total_duration": data.get("total_duration", 0),
                        "load_duration": data.get("load_duration", 0),
                        "prompt_eval_count": data.get("prompt_eval_count", 0),
                        "eval_count": data.get("eval_count", 0),
                        "eval_duration": data.get("eval_duration", 0)
                    }
                }
            else:
                logger.error(f"API 请求失败: {response.status_code}")
                return {
                    "success": False,
                    "error": f"API 请求失败: {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            logger.error("请求超时")
            return {"success": False, "error": "请求超时"}
        except Exception as e:
            logger.error(f"对话请求失败: {e}")
            return {"success": False, "error": str(e)}
    
    def chat_stream(self, prompt: str, 
                    temperature: float = 0.9,
                    max_tokens: int = 32768):
        """
        流式对话生成
        
        Args:
            prompt: 输入提示词
            temperature: 温度参数，推理模型推荐 0.9
            max_tokens: 最大生成 token 数，推理模型推荐 32768
            
        Yields:
            str: 生成的文本片段
        """
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "top_k": 50,
                    "top_p": 0.95,
                    "repeat_penalty": 1.0,
                    "frequency_penalty": 0.0,
                    "mirostat": 0,
                    "num_batch": 1,
                    "think": True
                }
            }
            
            with requests.post(self.api_url, json=payload, stream=True, timeout=120) as response:
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line.decode('utf-8'))
                        if "response" in data:
                            yield data["response"]
                            
        except Exception as e:
            logger.error(f"流式请求失败: {e}")
            yield f"错误: {str(e)}"
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        try:
            response = requests.get(self.tags_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                model = next((m for m in models if self.model_name in m["name"]), None)
                
                if model:
                    return {
                        "name": model["name"],
                        "size": model.get("size", 0),
                        "digest": model.get("digest", ""),
                        "available": True
                    }
            
            return {"available": False}
            
        except Exception as e:
            logger.error(f"获取模型信息失败: {e}")
            return {"available": False, "error": str(e)}


# 便捷函数
def get_dasd_chat():
    """获取 DASD 聊天实例"""
    return DASDIntegration()


# 示例用法
if __name__ == "__main__":
    dasd = DASDIntegration()
    
    # 检查可用性
    print("检查模型可用性...")
    if dasd.is_available():
        print("✓ 模型可用")
        
        # 获取模型信息
        info = dasd.get_model_info()
        print(f"模型信息: {json.dumps(info, ensure_ascii=False, indent=2)}")
        
        # 测试对话
        print("\n测试对话...")
        result = dasd.chat("请用一句话介绍你自己")
        
        if result["success"]:
            print(f"回答: {result['response']}")
            print(f"统计: {json.dumps(result['stats'], indent=2)}")
        else:
            print(f"错误: {result['error']}")
    else:
        print("✗ 模型不可用，请先部署模型")
