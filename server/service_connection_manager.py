"""
服务连接管理器 - Service Connection Manager

提供统一的服务连接管理，包括：
- HTTP 连接池管理（复用连接，减少开销）
- 健康检查心跳（实时监控服务状态）
- 自动重连机制（服务恢复后自动连接）
- 熔断降级（服务故障时快速失败）
- 统一超时配置（避免请求卡死）

使用方式：
    from service_connection_manager import ServiceConnectionManager
    
    manager = ServiceConnectionManager()
    response = manager.request('ollama', '/api/tags')
"""

import time
import json
import logging
import threading
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from functools import wraps
import urllib.request
import urllib.error
import ssl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """服务状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceConfig:
    """服务配置"""
    name: str
    base_url: str
    timeout: float = 30.0
    connect_timeout: float = 5.0
    max_retries: int = 3
    retry_delay: float = 1.0
    health_check_interval: float = 30.0
    health_check_endpoint: str = ""
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_time: float = 60.0


@dataclass
class ServiceMetrics:
    """服务指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    last_response_time: float = 0.0
    consecutive_failures: int = 0
    last_success_time: float = 0.0
    last_failure_time: float = 0.0
    status: ServiceStatus = ServiceStatus.UNKNOWN
    
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def record_success(self, response_time: float):
        """记录成功请求"""
        self.total_requests += 1
        self.successful_requests += 1
        self.last_response_time = response_time
        self.last_success_time = time.time()
        self.consecutive_failures = 0
        
        self.response_times.append(response_time)
        self._update_avg_response_time()
        
        if self.status != ServiceStatus.HEALTHY:
            self.status = ServiceStatus.HEALTHY
    
    def record_failure(self):
        """记录失败请求"""
        self.total_requests += 1
        self.failed_requests += 1
        self.last_failure_time = time.time()
        self.consecutive_failures += 1
        
        if self.consecutive_failures >= 5:
            self.status = ServiceStatus.UNHEALTHY
        elif self.consecutive_failures >= 2:
            self.status = ServiceStatus.DEGRADED
    
    def _update_avg_response_time(self):
        """更新平均响应时间"""
        if self.response_times:
            self.avg_response_time = sum(self.response_times) / len(self.response_times)


class CircuitBreaker:
    """
    熔断器
    
    当服务连续失败达到阈值时，熔断器打开，拒绝所有请求
    经过一段时间后，熔断器进入半开状态，允许少量请求通过测试
    如果测试成功，熔断器关闭；否则继续打开
    """
    
    def __init__(self, threshold: int = 5, reset_time: float = 60.0):
        self.threshold = threshold
        self.reset_time = reset_time
        self.failures = 0
        self.last_failure_time = 0
        self.state = "closed"
        self._lock = threading.Lock()
    
    def can_execute(self) -> bool:
        """检查是否可以执行请求"""
        with self._lock:
            if self.state == "closed":
                return True
            
            if self.state == "open":
                if time.time() - self.last_failure_time >= self.reset_time:
                    self.state = "half_open"
                    return True
                return False
            
            return True
    
    def record_success(self):
        """记录成功"""
        with self._lock:
            self.failures = 0
            self.state = "closed"
    
    def record_failure(self):
        """记录失败"""
        with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()
            
            if self.failures >= self.threshold:
                self.state = "open"


class ConnectionPool:
    """
    HTTP 连接池
    
    复用 HTTP 连接，减少连接建立开销
    """
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self._connections: Dict[str, deque] = {}
        self._lock = threading.Lock()
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE
    
    def get_connection(self, host: str) -> Optional[urllib.request.OpenerDirector]:
        """获取连接"""
        with self._lock:
            if host not in self._connections:
                self._connections[host] = deque(maxlen=self.max_connections)
            
            pool = self._connections[host]
            if pool:
                return pool.pop()
            
            return None
    
    def return_connection(self, host: str, opener: urllib.request.OpenerDirector):
        """归还连接"""
        with self._lock:
            if host not in self._connections:
                self._connections[host] = deque(maxlen=self.max_connections)
            
            pool = self._connections[host]
            if len(pool) < self.max_connections:
                pool.append(opener)
    
    def clear(self, host: str = None):
        """清空连接池"""
        with self._lock:
            if host:
                self._connections.pop(host, None)
            else:
                self._connections.clear()


class ServiceConnectionManager:
    """
    服务连接管理器
    
    统一管理所有后端服务的连接，提供：
    - 连接池管理
    - 健康检查
    - 自动重连
    - 熔断降级
    - 请求统计
    
    使用示例:
        manager = ServiceConnectionManager()
        manager.register_service('ollama', 'http://localhost:11434')
        
        response = manager.request('ollama', '/api/tags')
        if response:
            print(response)
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._services: Dict[str, ServiceConfig] = {}
        self._metrics: Dict[str, ServiceMetrics] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._connection_pool = ConnectionPool()
        self._health_check_thread = None
        self._running = False
        
        self._request_queue: deque = deque(maxlen=1000)
        self._request_lock = threading.Lock()
        
        self._default_configs = {
            'ollama': ServiceConfig(
                name='ollama',
                base_url='http://localhost:11434',
                timeout=120.0,
                health_check_endpoint='/api/tags'
            ),
            'backend_api': ServiceConfig(
                name='backend_api',
                base_url='http://localhost:5001',
                timeout=60.0,
                health_check_endpoint='/api/health'
            ),
            'summary_api': ServiceConfig(
                name='summary_api',
                base_url='http://localhost:5002',
                timeout=30.0,
                health_check_endpoint='/api/summary/health'
            ),
            'vision_api': ServiceConfig(
                name='vision_api',
                base_url='http://localhost:5003',
                timeout=60.0,
                health_check_endpoint='/api/llama_cpp_image/health'
            ),
            'native_image_api': ServiceConfig(
                name='native_image_api',
                base_url='http://localhost:5004',
                timeout=60.0,
                health_check_endpoint='/api/native_llama_cpp_image/health'
            )
        }
        
        for name, config in self._default_configs.items():
            self.register_service(name, config.base_url, config.__dict__)
    
    def register_service(self, name: str, base_url: str, 
                         config_override: Dict[str, Any] = None):
        """
        注册服务
        
        参数:
            name: 服务名称
            base_url: 服务基础 URL
            config_override: 配置覆盖
        """
        default_config = self._default_configs.get(name, ServiceConfig(
            name=name,
            base_url=base_url
        ))
        
        config_dict = {
            'name': name,
            'base_url': base_url,
            'timeout': default_config.timeout,
            'connect_timeout': default_config.connect_timeout,
            'max_retries': default_config.max_retries,
            'retry_delay': default_config.retry_delay,
            'health_check_interval': default_config.health_check_interval,
            'health_check_endpoint': default_config.health_check_endpoint,
            'circuit_breaker_threshold': default_config.circuit_breaker_threshold,
            'circuit_breaker_reset_time': default_config.circuit_breaker_reset_time
        }
        
        if config_override:
            config_dict.update(config_override)
        
        config = ServiceConfig(**config_dict)
        self._services[name] = config
        self._metrics[name] = ServiceMetrics()
        self._circuit_breakers[name] = CircuitBreaker(
            threshold=config.circuit_breaker_threshold,
            reset_time=config.circuit_breaker_reset_time
        )
        
        logger.info(f"服务已注册: {name} -> {base_url}")
    
    def request(self, service_name: str, endpoint: str, 
                method: str = 'GET', data: Any = None,
                headers: Dict[str, str] = None,
                timeout: float = None) -> Optional[Dict]:
        """
        发送请求
        
        参数:
            service_name: 服务名称
            endpoint: API 端点
            method: HTTP 方法
            data: 请求数据
            headers: 请求头
            timeout: 超时时间（秒）
            
        返回:
            响应数据字典，失败返回 None
        """
        if service_name not in self._services:
            logger.error(f"未知服务: {service_name}")
            return None
        
        config = self._services[service_name]
        circuit_breaker = self._circuit_breakers[service_name]
        metrics = self._metrics[service_name]
        
        if not circuit_breaker.can_execute():
            logger.warning(f"服务 {service_name} 熔断器已打开，请求被拒绝")
            return None
        
        url = f"{config.base_url}{endpoint}"
        actual_timeout = timeout or config.timeout
        
        for attempt in range(config.max_retries):
            start_time = time.time()
            
            try:
                req = urllib.request.Request(url, method=method)
                
                req.add_header('Content-Type', 'application/json')
                req.add_header('Accept', 'application/json')
                if headers:
                    for key, value in headers.items():
                        req.add_header(key, value)
                
                if data and method in ['POST', 'PUT', 'PATCH']:
                    req.data = json.dumps(data).encode('utf-8')
                
                response = urllib.request.urlopen(
                    req, 
                    timeout=actual_timeout
                )
                
                response_time = time.time() - start_time
                response_data = response.read().decode('utf-8')
                
                circuit_breaker.record_success()
                metrics.record_success(response_time)
                
                try:
                    return json.loads(response_data)
                except json.JSONDecodeError:
                    return {'raw': response_data}
                    
            except urllib.error.URLError as e:
                metrics.record_failure()
                circuit_breaker.record_failure()
                
                if attempt < config.max_retries - 1:
                    logger.warning(
                        f"服务 {service_name} 请求失败 (尝试 {attempt + 1}/{config.max_retries}): {e}"
                    )
                    time.sleep(config.retry_delay * (attempt + 1))
                else:
                    logger.error(f"服务 {service_name} 请求最终失败: {e}")
                    return None
                    
            except Exception as e:
                metrics.record_failure()
                circuit_breaker.record_failure()
                logger.error(f"服务 {service_name} 请求异常: {e}")
                return None
        
        return None
    
    def health_check(self, service_name: str = None) -> Dict[str, Any]:
        """
        健康检查
        
        参数:
            service_name: 服务名称，为 None 时检查所有服务
            
        返回:
            健康状态字典
        """
        results = {}
        
        services_to_check = [service_name] if service_name else list(self._services.keys())
        
        for name in services_to_check:
            if name not in self._services:
                results[name] = {'status': 'unknown', 'error': '服务未注册'}
                continue
            
            config = self._services[name]
            metrics = self._metrics[name]
            
            if not config.health_check_endpoint:
                results[name] = {
                    'status': metrics.status.value,
                    'metrics': self._get_metrics_summary(metrics)
                }
                continue
            
            start_time = time.time()
            response = self.request(name, config.health_check_endpoint, timeout=5.0)
            response_time = time.time() - start_time
            
            if response is not None:
                results[name] = {
                    'status': 'healthy',
                    'response_time': round(response_time, 3),
                    'metrics': self._get_metrics_summary(metrics)
                }
            else:
                results[name] = {
                    'status': 'unhealthy',
                    'response_time': None,
                    'metrics': self._get_metrics_summary(metrics)
                }
        
        return results
    
    def _get_metrics_summary(self, metrics: ServiceMetrics) -> Dict:
        """获取指标摘要"""
        return {
            'total_requests': metrics.total_requests,
            'success_rate': (
                round(metrics.successful_requests / metrics.total_requests * 100, 2)
                if metrics.total_requests > 0 else 0
            ),
            'avg_response_time': round(metrics.avg_response_time, 3),
            'consecutive_failures': metrics.consecutive_failures
        }
    
    def get_all_metrics(self) -> Dict[str, Dict]:
        """获取所有服务指标"""
        return {
            name: self._get_metrics_summary(metrics)
            for name, metrics in self._metrics.items()
        }
    
    def start_health_monitor(self, interval: float = 30.0):
        """启动健康监控线程"""
        if self._running:
            return
        
        self._running = True
        
        def monitor_loop():
            while self._running:
                try:
                    self.health_check()
                except Exception as e:
                    logger.error(f"健康检查异常: {e}")
                
                time.sleep(interval)
        
        self._health_check_thread = threading.Thread(
            target=monitor_loop, 
            daemon=True,
            name="HealthMonitor"
        )
        self._health_check_thread.start()
        logger.info("健康监控线程已启动")
    
    def stop_health_monitor(self):
        """停止健康监控"""
        self._running = False
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5.0)
        logger.info("健康监控线程已停止")
    
    def reset_circuit_breaker(self, service_name: str = None):
        """重置熔断器"""
        if service_name:
            if service_name in self._circuit_breakers:
                self._circuit_breakers[service_name] = CircuitBreaker()
                self._metrics[service_name].consecutive_failures = 0
                logger.info(f"服务 {service_name} 熔断器已重置")
        else:
            for name in self._circuit_breakers:
                self._circuit_breakers[name] = CircuitBreaker()
                self._metrics[name].consecutive_failures = 0
            logger.info("所有服务熔断器已重置")


def get_connection_manager() -> ServiceConnectionManager:
    """获取连接管理器单例"""
    return ServiceConnectionManager()


if __name__ == '__main__':
    manager = get_connection_manager()
    
    print("=== 服务健康检查 ===")
    health = manager.health_check()
    for service, status in health.items():
        print(f"{service}: {status['status']}")
    
    print("\n=== 测试 Ollama 请求 ===")
    models = manager.request('ollama', '/api/tags')
    if models:
        print(f"获取到 {len(models.get('models', []))} 个模型")
