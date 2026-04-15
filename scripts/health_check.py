#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ollama 服务健康检查工具
功能: 系统性检测 Ollama 连接问题，提供详细诊断报告
作者: AI Assistant
版本: 1.0
"""

import sys
import socket
import time
import json
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from urllib.parse import urljoin

# 尝试导入 requests，如果没有则使用 urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error
    import ssl


class Colors:
    """终端颜色输出"""
    OK = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    INFO = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class OllamaHealthChecker:
    """Ollama 健康检查器"""
    
    def __init__(self, host: str = "localhost", port: int = 11434, timeout: int = 10):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}"
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "host": host,
            "port": port,
            "checks": [],
            "issues": [],
            "recommendations": []
        }
        
    def log(self, level: str, message: str):
        """输出日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = {
            "OK": Colors.OK,
            "WARNING": Colors.WARNING,
            "ERROR": Colors.ERROR,
            "INFO": Colors.INFO
        }.get(level, Colors.RESET)
        
        print(f"[{timestamp}] {color}[{level}]{Colors.RESET} {message}")
        
        self.report["checks"].append({
            "time": timestamp,
            "level": level,
            "message": message
        })
        
        if level in ["WARNING", "ERROR"]:
            self.report["issues"].append(message)
    
    def check_tcp_connection(self) -> bool:
        """检查 TCP 连接"""
        self.log("INFO", f"检查 TCP 连接到 {self.host}:{self.port}...")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            
            if result == 0:
                self.log("OK", "TCP 连接成功")
                return True
            else:
                error_msg = f"TCP 连接失败 (错误码: {result})"
                self.log("ERROR", error_msg)
                self.report["recommendations"].append(
                    "服务可能未启动，请执行: ollama serve"
                )
                return False
        except Exception as e:
            self.log("ERROR", f"TCP 连接异常: {str(e)}")
            return False
    
    def check_http_response(self) -> Tuple[bool, Optional[Dict]]:
        """检查 HTTP 响应"""
        self.log("INFO", f"检查 HTTP 服务: {self.base_url}/api/tags")
        
        url = f"{self.base_url}/api/tags"
        
        try:
            if HAS_REQUESTS:
                response = requests.get(url, timeout=self.timeout)
                status_code = response.status_code
                
                if status_code == 200:
                    data = response.json()
                    self.log("OK", f"HTTP 200 OK，发现 {len(data.get('models', []))} 个模型")
                    return True, data
                else:
                    self.log("ERROR", f"HTTP {status_code}")
                    return False, None
            else:
                # 使用 urllib
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                with urllib.request.urlopen(url, timeout=self.timeout, context=ctx) as response:
                    status_code = response.getcode()
                    data = json.loads(response.read().decode('utf-8'))
                    
                    if status_code == 200:
                        self.log("OK", f"HTTP 200 OK，发现 {len(data.get('models', []))} 个模型")
                        return True, data
                    else:
                        self.log("ERROR", f"HTTP {status_code}")
                        return False, None
                        
        except requests.exceptions.ConnectionError as e:
            self.log("ERROR", f"连接被拒绝: {str(e)}")
            self.report["recommendations"].extend([
                "1. 确认 Ollama 服务已启动: ollama serve",
                "2. 检查端口是否正确: netstat -ano | findstr :11434",
                "3. 检查防火墙设置"
            ])
            return False, None
        except requests.exceptions.Timeout:
            self.log("ERROR", "连接超时")
            self.report["recommendations"].append("服务响应缓慢，请检查系统资源")
            return False, None
        except Exception as e:
            self.log("ERROR", f"HTTP 请求异常: {str(e)}")
            return False, None
    
    def test_chat_api(self, model: str = "qwen:7b") -> bool:
        """测试 Chat API"""
        self.log("INFO", f"测试 Chat API (模型: {model})...")
        
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False
        }
        
        try:
            if HAS_REQUESTS:
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    self.log("OK", "Chat API 响应正常")
                    return True
                else:
                    self.log("ERROR", f"Chat API 返回 HTTP {response.status_code}")
                    return False
            else:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                    if response.getcode() == 200:
                        self.log("OK", "Chat API 响应正常")
                        return True
                    else:
                        self.log("ERROR", f"Chat API 返回 HTTP {response.getcode()}")
                        return False
                        
        except Exception as e:
            self.log("ERROR", f"Chat API 测试失败: {str(e)}")
            return False
    
    def check_models(self) -> List[str]:
        """检查已安装的模型"""
        self.log("INFO", "获取已安装模型列表...")
        
        url = f"{self.base_url}/api/tags"
        models = []
        
        try:
            if HAS_REQUESTS:
                response = requests.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get('name', 'unknown') for m in data.get('models', [])]
            else:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                with urllib.request.urlopen(url, timeout=self.timeout, context=ctx) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    models = [m.get('name', 'unknown') for m in data.get('models', [])]
            
            if models:
                self.log("OK", f"找到 {len(models)} 个模型:")
                for model in models[:5]:  # 只显示前5个
                    self.log("INFO", f"  - {model}")
                if len(models) > 5:
                    self.log("INFO", f"  ... 还有 {len(models) - 5} 个模型")
            else:
                self.log("WARNING", "未安装任何模型")
                self.report["recommendations"].append(
                    "请安装模型: ollama pull qwen:7b"
                )
            
            return models
            
        except Exception as e:
            self.log("ERROR", f"获取模型列表失败: {str(e)}")
            return []
    
    def run_all_checks(self) -> Dict:
        """运行所有检查"""
        print(f"\n{Colors.BOLD}{'='*50}{Colors.RESET}")
        print(f"{Colors.BOLD}Ollama 健康检查报告{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*50}{Colors.RESET}\n")
        
        print(f"目标: {self.base_url}")
        print(f"时间: {self.report['timestamp']}\n")
        
        # 1. TCP 连接检查
        tcp_ok = self.check_tcp_connection()
        
        if not tcp_ok:
            self.log("ERROR", "TCP 连接失败，跳过后续检查")
            return self.report
        
        # 2. HTTP 响应检查
        http_ok, data = self.check_http_response()
        
        if not http_ok:
            self.log("ERROR", "HTTP 服务异常，跳过后续检查")
            return self.report
        
        # 3. 模型列表检查
        models = self.check_models()
        
        # 4. Chat API 测试（如果有模型）
        if models:
            self.test_chat_api(models[0])
        
        return self.report
    
    def print_summary(self):
        """打印检查摘要"""
        print(f"\n{Colors.BOLD}{'='*50}{Colors.RESET}")
        print(f"{Colors.BOLD}检查摘要{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*50}{Colors.RESET}\n")
        
        issue_count = len(self.report["issues"])
        
        if issue_count == 0:
            print(f"{Colors.OK}[全部通过] 未发现连接问题！{Colors.RESET}")
            print("\nOllama 服务运行正常，可以正常使用。\n")
        else:
            print(f"{Colors.ERROR}[发现问题] 发现 {issue_count} 个问题{Colors.RESET}\n")
            
            if self.report["recommendations"]:
                print(f"{Colors.BOLD}建议操作:{Colors.RESET}")
                for rec in self.report["recommendations"]:
                    print(f"  {Colors.INFO}•{Colors.RESET} {rec}")
                print()
    
    def save_report(self, filename: str = "ollama_health_report.json"):
        """保存报告到文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.report, f, ensure_ascii=False, indent=2)
            print(f"{Colors.INFO}报告已保存: {filename}{Colors.RESET}\n")
        except Exception as e:
            print(f"{Colors.ERROR}保存报告失败: {str(e)}{Colors.RESET}\n")


def continuous_monitor(checker: OllamaHealthChecker, interval: int = 30, duration: int = 300):
    """持续监控模式"""
    print(f"\n{Colors.BOLD}开始持续监控 (间隔: {interval}秒, 持续: {duration}秒){Colors.RESET}\n")
    
    start_time = time.time()
    check_count = 0
    failure_count = 0
    
    while time.time() - start_time < duration:
        check_count += 1
        print(f"\n{Colors.BOLD}--- 检查 #{check_count} ---{Colors.RESET}")
        
        tcp_ok = checker.check_tcp_connection()
        if tcp_ok:
            http_ok, _ = checker.check_http_response()
            if not http_ok:
                failure_count += 1
        else:
            failure_count += 1
        
        elapsed = int(time.time() - start_time)
        remaining = duration - elapsed
        
        print(f"\n{Colors.INFO}已运行: {elapsed}秒, 剩余: {remaining}秒{Colors.RESET}")
        print(f"{Colors.INFO}成功率: {((check_count - failure_count) / check_count * 100):.1f}%{Colors.RESET}")
        
        if remaining > 0:
            time.sleep(min(interval, remaining))
    
    print(f"\n{Colors.BOLD}{'='*50}{Colors.RESET}")
    print(f"{Colors.BOLD}监控完成{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*50}{Colors.RESET}\n")
    print(f"总检查次数: {check_count}")
    print(f"失败次数: {failure_count}")
    print(f"成功率: {((check_count - failure_count) / check_count * 100):.1f}%")


def main():
    parser = argparse.ArgumentParser(
        description='Ollama 服务健康检查工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python health_check.py                    # 基本检查
  python health_check.py -H 192.168.1.100   # 检查远程主机
  python health_check.py -p 11435           # 使用非标准端口
  python health_check.py -m                 # 持续监控模式
        """
    )
    
    parser.add_argument('-H', '--host', default='localhost',
                        help='Ollama 主机地址 (默认: localhost)')
    parser.add_argument('-p', '--port', type=int, default=11434,
                        help='Ollama 端口 (默认: 11434)')
    parser.add_argument('-t', '--timeout', type=int, default=10,
                        help='连接超时时间 (默认: 10秒)')
    parser.add_argument('-m', '--monitor', action='store_true',
                        help='持续监控模式')
    parser.add_argument('-i', '--interval', type=int, default=30,
                        help='监控间隔 (默认: 30秒)')
    parser.add_argument('-d', '--duration', type=int, default=300,
                        help='监控持续时间 (默认: 300秒)')
    parser.add_argument('-o', '--output', default='ollama_health_report.json',
                        help='报告输出文件')
    parser.add_argument('--no-save', action='store_true',
                        help='不保存报告文件')
    
    args = parser.parse_args()
    
    # 创建检查器
    checker = OllamaHealthChecker(
        host=args.host,
        port=args.port,
        timeout=args.timeout
    )
    
    # 运行检查
    if args.monitor:
        continuous_monitor(checker, args.interval, args.duration)
    else:
        checker.run_all_checks()
        checker.print_summary()
        
        if not args.no_save:
            checker.save_report(args.output)


if __name__ == "__main__":
    main()
