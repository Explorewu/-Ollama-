"""
辅助函数模块

提供通用的验证、响应构建、文本处理等功能
"""

import re
import logging
from typing import Tuple, Optional, Any, Dict, List

logger = logging.getLogger(__name__)


def success_response(data: Any = None, message: str = "操作成功", code: int = 200) -> Dict:
    """构建成功响应
    
    统一响应结构: {success, message, code, data}
    """
    return {
        "success": True,
        "message": message,
        "code": code,
        "data": data
    }


def error_response(message: str, code: int = 400, data: Any = None) -> Dict:
    """构建错误响应
    
    统一响应结构: {success, message, code, data}
    """
    return {
        "success": False,
        "message": message,
        "code": code,
        "data": data
    }


def validate_request(required_fields: List[str], data: Dict) -> Tuple[bool, str]:
    """验证请求必需字段"""
    for field in required_fields:
        if field not in data or data[field] is None:
            return False, f"缺少必需字段: {field}"
    return True, ""


def validate_string(value: str, field_name: str, min_len: int = 1, max_len: int = 10000) -> Tuple[bool, str]:
    """验证字符串字段"""
    if not isinstance(value, str):
        return False, f"{field_name} 必须是字符串"
    if len(value) < min_len:
        return False, f"{field_name} 长度不能小于 {min_len}"
    if len(value) > max_len:
        return False, f"{field_name} 长度不能超过 {max_len}"
    return True, ""


def validate_integer(value: Any, field_name: str, min_val: int = None, max_val: int = None) -> Tuple[bool, str]:
    """验证整数字段"""
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        return False, f"{field_name} 必须是整数"
    
    if min_val is not None and int_value < min_val:
        return False, f"{field_name} 不能小于 {min_val}"
    if max_val is not None and int_value > max_val:
        return False, f"{field_name} 不能大于 {max_val}"
    return True, ""


SENTENCE_ENDINGS = re.compile(r'[。！？\.!?\.\!\?]+')
CHINESE_PUNCTUATION = re.compile(r'[，、：；：《》【】""''（）()……～~]+')


def split_into_sentences(text: str) -> List[str]:
    """将文本按句子分割"""
    if not text:
        return []

    sentences = SENTENCE_ENDINGS.split(text)
    result = []
    buffer = ""

    for i, part in enumerate(sentences):
        buffer += part
        end_pos = 0
        for j in range(i + 1, len(text)):
            if text[j] in '。！？.!?':
                end_pos = j + 1
                break

        if end_pos > 0:
            if buffer.strip():
                result.append(buffer.strip())
            buffer = ""

    if buffer.strip():
        result.append(buffer.strip())

    return result


def chunk_by_sentences(text: str, min_chunk_size: int = 10, max_chunk_size: int = 100) -> List[str]:
    """将文本按句子分块"""
    sentences = split_into_sentences(text)

    if not sentences:
        return [text] if text else []

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(sentence) > max_chunk_size:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            sub_chunks = _split_long_sentence(sentence, max_chunk_size)
            chunks.extend(sub_chunks)
            continue

        if current_chunk and len(current_chunk) + len(sentence) + 1 <= max_chunk_size:
            current_chunk += " " + sentence
        elif current_chunk:
            chunks.append(current_chunk)
            current_chunk = sentence
        else:
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    return chunks if chunks else [text]


def _split_long_sentence(text: str, max_size: int) -> List[str]:
    """分割过长的句子"""
    parts = CHINESE_PUNCTUATION.split(text)
    result = []
    current = ""

    for part in parts:
        if current and len(current) + len(part) + 1 > max_size:
            result.append(current)
            current = part
        elif current:
            current += " " + part
        else:
            current = part

    if current:
        result.append(current)

    return result if result else [text]


def safe_get(dictionary: Dict, *keys, default=None):
    """安全获取嵌套字典值"""
    for key in keys:
        try:
            dictionary = dictionary[key]
        except (KeyError, TypeError):
            return default
    return dictionary
