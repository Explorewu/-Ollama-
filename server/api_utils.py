"""
API工具函数模块 - API Utilities

提供后端API的统一工具函数，包括：
- 统一响应格式
- 错误处理
- 请求验证
- 日志记录

此模块不引入任何外部依赖，仅使用Python标准库
"""

import json
import logging
import traceback
from functools import wraps
from typing import Any, Dict, Optional, Callable

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 统一响应格式 ====================

def success_response(data: Any = None, message: str = "操作成功") -> Dict:
    """
    生成成功响应
    
    参数:
        data: 响应数据
        message: 成功消息
        
    返回:
        统一格式的成功响应字典
    """
    return {
        "success": True,
        "code": 200,
        "message": message,
        "data": data
    }


def error_response(message: str = "操作失败", code: int = 400, details: Any = None) -> Dict:
    """
    生成错误响应
    
    参数:
        message: 错误消息
        code: 错误代码
        details: 详细错误信息
        
    返回:
        统一格式的错误响应字典
    """
    return {
        "success": False,
        "code": code,
        "message": message,
        "details": details
    }


def validate_request(required_fields: list, request_data: Dict) -> tuple:
    """
    验证请求数据
    
    参数:
        required_fields: 必需字段列表
        request_data: 请求数据字典
        
    返回:
        (是否有效, 错误消息或None)
    """
    if not request_data:
        return False, "请求数据不能为空"
    
    missing_fields = []
    for field in required_fields:
        if field not in request_data or request_data[field] is None:
            missing_fields.append(field)
    
    if missing_fields:
        return False, f"缺少必需字段: {', '.join(missing_fields)}"
    
    return True, None


# ==================== 错误处理装饰器 ====================

def handle_api_errors(default_message: str = "服务器内部错误"):
    """
    API错误处理装饰器
    
    自动捕获异常并返回统一格式的错误响应
    
    使用示例:
        @handle_api_errors("获取数据失败")
        def get_data():
            # 可能抛出异常的代码
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"API错误 [{func.__name__}]: {error_msg}")
                logger.debug(traceback.format_exc())
                return error_response(
                    message=default_message,
                    code=500,
                    details=error_msg
                )
        return wrapper
    return decorator


# ==================== 数据验证函数 ====================

def validate_string(value: Any, field_name: str, min_length: int = 1, max_length: int = 10000) -> tuple:
    """
    验证字符串字段
    
    参数:
        value: 字段值
        field_name: 字段名称
        min_length: 最小长度
        max_length: 最大长度
        
    返回:
        (是否有效, 错误消息或None)
    """
    if not isinstance(value, str):
        return False, f"{field_name}必须是字符串"
    
    if len(value) < min_length:
        return False, f"{field_name}长度不能少于{min_length}个字符"
    
    if len(value) > max_length:
        return False, f"{field_name}长度不能超过{max_length}个字符"
    
    return True, None


def validate_integer(value: Any, field_name: str, min_value: Optional[int] = None, max_value: Optional[int] = None) -> tuple:
    """
    验证整数字段
    
    参数:
        value: 字段值
        field_name: 字段名称
        min_value: 最小值
        max_value: 最大值
        
    返回:
        (是否有效, 错误消息或None)
    """
    if not isinstance(value, int):
        try:
            value = int(value)
        except (ValueError, TypeError):
            return False, f"{field_name}必须是整数"
    
    if min_value is not None and value < min_value:
        return False, f"{field_name}不能小于{min_value}"
    
    if max_value is not None and value > max_value:
        return False, f"{field_name}不能大于{max_value}"
    
    return True, None


def validate_list(value: Any, field_name: str, min_length: int = 0, max_length: Optional[int] = None) -> tuple:
    """
    验证列表字段
    
    参数:
        value: 字段值
        field_name: 字段名称
        min_length: 最小长度
        max_length: 最大长度
        
    返回:
        (是否有效, 错误消息或None)
    """
    if not isinstance(value, list):
        return False, f"{field_name}必须是列表"
    
    if len(value) < min_length:
        return False, f"{field_name}至少需要{min_length}个元素"
    
    if max_length is not None and len(value) > max_length:
        return False, f"{field_name}不能超过{max_length}个元素"
    
    return True, None


# ==================== 日志工具 ====================

def log_api_call(func_name: str, params: Dict = None, level: str = "info"):
    """
    记录API调用日志
    
    参数:
        func_name: 函数名称
        params: 调用参数
        level: 日志级别
    """
    log_msg = f"API调用: {func_name}"
    if params:
        # 过滤敏感信息
        safe_params = {k: v for k, v in params.items() if k not in ['password', 'token', 'secret']}
        log_msg += f" | 参数: {safe_params}"
    
    if level == "debug":
        logger.debug(log_msg)
    elif level == "warning":
        logger.warning(log_msg)
    elif level == "error":
        logger.error(log_msg)
    else:
        logger.info(log_msg)


def log_performance(func_name: str, execution_time: float):
    """
    记录性能日志
    
    参数:
        func_name: 函数名称
        execution_time: 执行时间（秒）
    """
    logger.info(f"性能统计: {func_name} 执行时间 {execution_time:.3f}s")


# ==================== 常用工具函数 ====================

def safe_get(dictionary: Dict, key: str, default: Any = None) -> Any:
    """
    安全获取字典值
    
    参数:
        dictionary: 字典
        key: 键
        default: 默认值
        
    返回:
        键对应的值或默认值
    """
    if dictionary is None:
        return default
    return dictionary.get(key, default)


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断字符串
    
    参数:
        text: 原始文本
        max_length: 最大长度
        suffix: 后缀
        
    返回:
        截断后的文本
    """
    if not text or len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_timestamp(timestamp: int or float) -> str:
    """
    格式化时间戳
    
    参数:
        timestamp: 时间戳（毫秒或秒）
        
    返回:
        格式化后的时间字符串
    """
    from datetime import datetime
    
    # 判断是毫秒还是秒
    if timestamp > 1e10:
        timestamp = timestamp / 1000
    
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(timestamp)


# ==================== 响应构建器 ====================

class ResponseBuilder:
    """
    响应构建器类
    
    提供链式调用来构建响应
    
    使用示例:
        response = ResponseBuilder().success().data(result).message("查询成功").build()
    """
    
    def __init__(self):
        self._success = True
        self._code = 200
        self._message = ""
        self._data = None
    
    def success(self, message: str = "操作成功"):
        """设置成功状态"""
        self._success = True
        self._code = 200
        self._message = message
        return self
    
    def error(self, message: str = "操作失败", code: int = 400):
        """设置错误状态"""
        self._success = False
        self._code = code
        self._message = message
        return self
    
    def data(self, data: Any):
        """设置响应数据"""
        self._data = data
        return self
    
    def message(self, message: str):
        """设置响应消息"""
        self._message = message
        return self
    
    def build(self) -> Dict:
        """构建响应字典"""
        return {
            "success": self._success,
            "code": self._code,
            "message": self._message,
            "data": self._data
        }


# ==================== 分页工具 ====================

def paginate(data: list, page: int = 1, page_size: int = 10) -> Dict:
    """
    分页处理
    
    参数:
        data: 数据列表
        page: 当前页码（从1开始）
        page_size: 每页数量
        
    返回:
        分页结果字典
    """
    if not data:
        return {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0
        }
    
    total = len(data)
    total_pages = (total + page_size - 1) // page_size
    
    # 确保页码有效
    page = max(1, min(page, total_pages))
    
    start = (page - 1) * page_size
    end = start + page_size
    
    return {
        "items": data[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


# ==================== 导出便捷函数 ====================

__all__ = [
    # 响应函数
    'success_response',
    'error_response',
    'ResponseBuilder',
    
    # 验证函数
    'validate_request',
    'validate_string',
    'validate_integer',
    'validate_list',
    
    # 装饰器
    'handle_api_errors',
    
    # 日志函数
    'log_api_call',
    'log_performance',
    
    # 工具函数
    'safe_get',
    'truncate_string',
    'format_timestamp',
    'paginate'
]
