# -*- coding: utf-8 -*-
"""
前后端 API 接口匹配度检查工具

功能：
1. 扫描前端所有 API 调用
2. 扫描后端所有 API 定义
3. 对比匹配度并生成详细报告
"""

import os
import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from enum import Enum

class Severity(Enum):
    CRITICAL = "🔴 严重"      # 功能完全不可用
    HIGH = "🟠 高"           # 主要功能受影响
    MEDIUM = "🟡 中"         # 次要功能受影响
    LOW = "🟢 低"            # 轻微问题或建议
    INFO = "🔵 信息"         # 仅供参考

@dataclass
class ApiEndpoint:
    """API 端点定义"""
    path: str
    methods: Set[str]
    source_file: str
    line_number: int
    params: Dict = field(default_factory=dict)
    response_fields: List[str] = field(default_factory=list)
    
    def __hash__(self):
        return hash((self.path, frozenset(self.methods)))
    
    def __eq__(self, other):
        return self.path == other.path and self.methods == other.methods

@dataclass
class MismatchItem:
    """不匹配项"""
    severity: Severity
    frontend_endpoint: Optional[ApiEndpoint]
    backend_endpoint: Optional[ApiEndpoint]
    issue_type: str
    description: str
    suggestion: str

class ApiInterfaceChecker:
    """API 接口匹配度检查器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.frontend_apis: List[ApiEndpoint] = []
        self.backend_apis: List[ApiEndpoint] = []
        self.mismatches: List[MismatchItem] = []
        
    def scan_frontend(self):
        """扫描前端 API 调用"""
        web_dir = self.project_root / "web"
        
        # 匹配 fetch/axios 调用的正则
        patterns = [
            # fetch('/api/xxx') 或 fetch(`${base}/api/xxx`)
            (r'fetch\s*\(\s*[\`\'"]([^\`\'"]*\/api\/[^\`\'"\$\{]*)[\`\'"]', 'GET'),
            (r'fetch\s*\(\s*[`\']([^`\']*\$\{[^}]+\}[^`\']*\/api\/[^`\']*)[`\']', 'GET'),
            # fetch(url, { method: 'POST' })
            (r'fetch\s*\([^,]+,\s*\{[^}]*method\s*:\s*[\'"](\w+)[\'"]', 'METHOD'),
            # axios.get('/api/xxx')
            (r'axios\.(\w+)\s*\(\s*[\'"]([^\'"]*\/api\/[^\'"]*)[\'"]', 'AXIOS'),
        ]
        
        for js_file in web_dir.rglob("*.js"):
            if "node_modules" in str(js_file):
                continue
                
            content = js_file.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                # 查找 API 路径
                api_matches = re.findall(r'["\'](\/api\/[^"\'\s\$\{]+)["\']', line)
                for match in api_matches:
                    # 尝试从上下文推断 HTTP 方法
                    method = self._infer_http_method(line, content, line_num)
                    
                    endpoint = ApiEndpoint(
                        path=match,
                        methods={method},
                        source_file=str(js_file.relative_to(self.project_root)),
                        line_number=line_num
                    )
                    
                    # 避免重复添加相同的端点
                    if endpoint not in self.frontend_apis:
                        self.frontend_apis.append(endpoint)
        
        # 扫描 HTML 文件
        for html_file in web_dir.rglob("*.html"):
            content = html_file.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                api_matches = re.findall(r'["\'](\/api\/[^"\'\s\$\{]+)["\']', line)
                for match in api_matches:
                    method = self._infer_http_method(line, content, line_num)
                    endpoint = ApiEndpoint(
                        path=match,
                        methods={method},
                        source_file=str(html_file.relative_to(self.project_root)),
                        line_number=line_num
                    )
                    if endpoint not in self.frontend_apis:
                        self.frontend_apis.append(endpoint)
        
        print(f"✅ 扫描到 {len(self.frontend_apis)} 个前端 API 调用")
        
    def _infer_http_method(self, line: str, context: str, line_num: int) -> str:
        """根据上下文推断 HTTP 方法"""
        line_lower = line.lower()
        
        # 直接看当前行
        if 'method' in line_lower:
            if "'post'" in line_lower or '"post"' in line_lower:
                return 'POST'
            elif "'put'" in line_lower or '"put"' in line_lower:
                return 'PUT'
            elif "'delete'" in line_lower or '"delete"' in line_lower:
                return 'DELETE'
            elif "'patch'" in line_lower or '"patch"' in line_lower:
                return 'PATCH'
        
        # 看关键词
        if any(word in line_lower for word in ['create', 'add', 'save', 'submit', 'generate']):
            return 'POST'
        if any(word in line_lower for word in ['delete', 'remove', 'clear']):
            return 'DELETE'
        if any(word in line_lower for word in ['update', 'modify', 'edit', 'set']):
            return 'PUT' if 'put' in line_lower else 'POST'
        
        return 'GET'
    
    def scan_backend(self):
        """扫描后端 API 定义"""
        api_dir = self.project_root / "server" / "api"
        
        for py_file in api_dir.glob("*.py"):
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                # 匹配 @app.route('/api/xxx', methods=['GET', 'POST'])
                route_match = re.search(
                    r"@app\.route\s*\(\s*['\"]([^'\"]+)['\"]\s*(?:,\s*methods\s*=\s*\[(.*?)\])?\s*\)",
                    line
                )
                
                if route_match:
                    path = route_match.group(1)
                    methods_str = route_match.group(2)
                    
                    if methods_str:
                        methods = set(m.strip().strip('"\'') for m in methods_str.split(','))
                    else:
                        methods = {'GET'}
                    
                    endpoint = ApiEndpoint(
                        path=path,
                        methods=methods,
                        source_file=str(py_file.relative_to(self.project_root)),
                        line_number=line_num
                    )
                    self.backend_apis.append(endpoint)
        
        print(f"✅ 扫描到 {len(self.backend_apis)} 个后端 API 定义")
    
    def compare(self):
        """对比前后端接口"""
        print("\n🔍 开始对比前后端接口...")
        
        # 创建后端 API 字典，方便查找
        backend_dict: Dict[str, ApiEndpoint] = {}
        for api in self.backend_apis:
            for method in api.methods:
                key = f"{method}:{api.path}"
                backend_dict[key] = api
        
        # 检查前端调用的 API 后端是否支持
        for frontend_api in self.frontend_apis:
            for method in frontend_api.methods:
                key = f"{method}:{frontend_api.path}"
                
                if key not in backend_dict:
                    # 尝试模糊匹配（忽略方法）
                    path_exists = any(
                        api.path == frontend_api.path 
                        for api in self.backend_apis
                    )
                    
                    if path_exists:
                        # 路径存在但方法不匹配
                        backend_api = next(
                            api for api in self.backend_apis 
                            if api.path == frontend_api.path
                        )
                        self.mismatches.append(MismatchItem(
                            severity=Severity.HIGH,
                            frontend_endpoint=frontend_api,
                            backend_endpoint=backend_api,
                            issue_type="HTTP 方法不匹配",
                            description=f"前端调用 {method}，但后端只支持 {backend_api.methods}",
                            suggestion=f"统一使用 {backend_api.methods} 方法，或后端添加 {method} 支持"
                        ))
                    else:
                        # 路径完全不存在
                        self.mismatches.append(MismatchItem(
                            severity=Severity.CRITICAL,
                            frontend_endpoint=frontend_api,
                            backend_endpoint=None,
                            issue_type="API 未实现",
                            description=f"前端调用 {frontend_api.path}，但后端无此接口",
                            suggestion="后端需要实现此接口，或前端移除调用"
                        ))
        
        # 检查后端定义的 API 前端是否使用（可选，用于发现僵尸接口）
        frontend_paths = {api.path for api in self.frontend_apis}
        for backend_api in self.backend_apis:
            if backend_api.path not in frontend_paths:
                # 检查是否是标准接口（如 health、status）
                if not any(x in backend_api.path for x in ['health', 'status', 'stats']):
                    self.mismatches.append(MismatchItem(
                        severity=Severity.LOW,
                        frontend_endpoint=None,
                        backend_endpoint=backend_api,
                        issue_type="API 未被前端使用",
                        description=f"后端定义了 {backend_api.path}，但前端未调用",
                        suggestion="确认是否为冗余接口，或前端需要添加调用"
                    ))
        
        print(f"⚠️  发现 {len(self.mismatches)} 个不匹配项")
    
    def generate_report(self) -> str:
        """生成检查报告"""
        lines = []
        lines.append("# 🔍 前后端 API 接口匹配度检查报告")
        lines.append("")
        lines.append(f"**生成时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**项目路径**: {self.project_root}")
        lines.append("")
        
        # 统计概览
        lines.append("## 📊 统计概览")
        lines.append("")
        lines.append(f"| 指标 | 数量 |")
        lines.append(f"|------|------|")
        lines.append(f"| 前端 API 调用 | {len(self.frontend_apis)} |")
        lines.append(f"| 后端 API 定义 | {len(self.backend_apis)} |")
        lines.append(f"| 不匹配项 | {len(self.mismatches)} |")
        lines.append("")
        
        # 按严重程度分组
        severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
        
        for severity in severity_order:
            items = [m for m in self.mismatches if m.severity == severity]
            if items:
                lines.append(f"## {severity.value} 问题 ({len(items)} 个)")
                lines.append("")
                
                for i, item in enumerate(items, 1):
                    lines.append(f"### {i}. {item.issue_type}")
                    lines.append("")
                    lines.append(f"**问题描述**: {item.description}")
                    lines.append("")
                    
                    if item.frontend_endpoint:
                        lines.append(f"**前端位置**: `{item.frontend_endpoint.source_file}:{item.frontend_endpoint.line_number}`")
                        lines.append(f"**前端调用**: `{item.frontend_endpoint.methods} {item.frontend_endpoint.path}`")
                    
                    if item.backend_endpoint:
                        lines.append(f"**后端位置**: `{item.backend_endpoint.source_file}:{item.backend_endpoint.line_number}`")
                        lines.append(f"**后端定义**: `{item.backend_endpoint.methods} {item.backend_endpoint.path}`")
                    
                    lines.append("")
                    lines.append(f"**建议**: {item.suggestion}")
                    lines.append("")
                    lines.append("---")
                    lines.append("")
        
        # 完整的 API 列表
        lines.append("## 📋 完整的 API 列表")
        lines.append("")
        
        lines.append("### 前端调用的 API")
        lines.append("")
        lines.append("| 路径 | 方法 | 来源文件 | 行号 |")
        lines.append("|------|------|----------|------|")
        for api in sorted(self.frontend_apis, key=lambda x: x.path):
            methods = ', '.join(sorted(api.methods))
            lines.append(f"| {api.path} | {methods} | {api.source_file} | {api.line_number} |")
        lines.append("")
        
        lines.append("### 后端定义的 API")
        lines.append("")
        lines.append("| 路径 | 方法 | 来源文件 | 行号 |")
        lines.append("|------|------|----------|------|")
        for api in sorted(self.backend_apis, key=lambda x: x.path):
            methods = ', '.join(sorted(api.methods))
            lines.append(f"| {api.path} | {methods} | {api.source_file} | {api.line_number} |")
        lines.append("")
        
        return '\n'.join(lines)
    
    def run(self):
        """运行完整检查流程"""
        print("=" * 60)
        print("🔍 前后端 API 接口匹配度检查")
        print("=" * 60)
        print()
        
        self.scan_frontend()
        self.scan_backend()
        self.compare()
        
        report = self.generate_report()
        
        # 保存报告
        report_path = self.project_root / "tests" / "API_INTERFACE_REPORT.md"
        report_path.write_text(report, encoding='utf-8')
        
        print(f"\n✅ 报告已保存: {report_path}")
        
        return report


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    checker = ApiInterfaceChecker(project_root)
    checker.run()
