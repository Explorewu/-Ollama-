# -*- coding: utf-8 -*-
"""
Ollama Hub 模块全面体检工具

功能：
1. 扫描所有 Python 模块
2. 检测语法错误、依赖缺失、运行时异常
3. 分类：无用/可修复/不可修复
4. 生成完整状态报告

运行方式:
    python tests/module_health_check.py
"""

import os
import sys
import ast
import json
import time
import importlib
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

PROJECT_DIR = Path(__file__).resolve().parent.parent
SERVER_DIR = PROJECT_DIR / "server"
sys.path.insert(0, str(SERVER_DIR))


@dataclass
class ModuleStatus:
    """模块状态数据类"""
    name: str
    path: str
    category: str = "unknown"  # useless / fixable / unfixable / healthy
    syntax_ok: bool = True
    imports_ok: bool = True
    runtime_ok: bool = False
    has_logic: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_deps: List[str] = field(default_factory=list)
    fix_suggestions: List[str] = field(default_factory=list)
    diagnosis: str = ""
    line_count: int = 0


class ModuleScanner:
    """模块扫描器"""
    
    def __init__(self):
        self.results: Dict[str, ModuleStatus] = {}
        self.start_time = time.time()
        self.total_modules = 0
        self.healthy_count = 0
        self.fixable_count = 0
        self.unfixable_count = 0
        self.useless_count = 0
    
    def scan_all_modules(self):
        """扫描所有 Python 模块"""
        print("=" * 80)
        print("  🔍 Ollama Hub 模块全面体检")
        print(f"  扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  项目目录: {PROJECT_DIR}")
        print("=" * 80)
        
        # 收集所有 Python 文件
        py_files = list(PROJECT_DIR.rglob("*.py"))
        
        # 排除虚拟环境、缓存、测试文件
        exclude_dirs = {
            "__pycache__", ".git", "node_modules", ".venv",
            "venv", "env", ".env", "tests", "fine_tuned_models"
        }
        
        filtered_files = []
        for f in py_files:
            rel_path = f.relative_to(PROJECT_DIR)
            parts = rel_path.parts
            
            skip = any(ex in parts for ex in exclude_dirs)
            if not skip and f.stat().st_size > 50:
                filtered_files.append(f)
        
        print(f"\n📊 发现 {len(filtered_files)} 个 Python 模块\n")
        
        for i, file_path in enumerate(sorted(filtered_files), 1):
            rel_name = file_path.relative_to(PROJECT_DIR).as_posix()
            
            status = ModuleStatus(
                name=file_path.stem,
                path=rel_name,
                line_count=self._count_lines(file_path)
            )
            
            print(f"  [{i}/{len(filtered_files)}] 检查: {rel_name}")
            
            # 1. 语法检查
            self._check_syntax(file_path, status)
            
            # 2. 导入检查（只检查 server 目录下的核心模块）
            if self._is_core_module(rel_name):
                self._check_imports(file_path, status)
                
                # 3. 运行时检查（尝试实际导入）
                if status.syntax_ok:
                    self._check_runtime(file_path, status)
            
            # 4. 逻辑完整性检查
            self._check_logic_completeness(file_path, status)
            
            # 5. 分类
            self._classify_module(status)
            
            self.results[rel_name] = status
        
        return self.results
    
    def _count_lines(self, path: Path) -> int:
        """统计代码行数"""
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0
    
    def _is_core_module(self, rel_path: str) -> bool:
        """判断是否为核心模块（需要深度检查）"""
        core_prefixes = [
            "server/api/",
            "server/utils/",
            "server/local_model_loader.py",
            "server/intelligent_api.py",
            "server/memory_service.py",
            "server/context_manager.py",
            "server/summary_service.py",
            "server/function_engine.py",
            "server/rag_service.py",
            "server/web_search_service.py",
            "server/asr/",
            "server/hybrid_group_chat_",
            "server/smart_cache.py",
            "server/security_utils.py",
            "server/service_connection_manager.py",
            "server/api_key_service.py",
            "server/prompt_optimizer.py",
            "server/intent_classifier.py",
            "server/conversation_memory.py",
            "server/text_segmenter.py",
            "server/loop_guard.py",
            "server/model_paths.py",
            "server/api_utils.py",
        ]
        return any(rel_path.startswith(p) for p in core_prefixes)
    
    def _check_syntax(self, file_path: Path, status: ModuleStatus):
        """检查语法错误"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            
            ast.parse(source)
            status.syntax_ok = True
        except SyntaxError as e:
            status.syntax_ok = False
            status.errors.append(f"语法错误 (行{e.lineno}): {e.msg}")
            status.diagnosis = f"Python 语法不兼容或文件损坏"
    
    def _check_imports(self, file_path: Path, status: ModuleStatus):
        """检查导入依赖"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            imported_modules = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_modules.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported_modules.add(node.module.split('.')[0])
            
            missing = []
            for mod_name in imported_modules:
                if mod_name.startswith('.'):
                    continue
                
                try:
                    importlib.import_module(mod_name)
                except ImportError:
                    if mod_name not in ['builtins', '__future__']:
                        missing.append(mod_name)
            
            status.missing_deps = missing
            status.imports_ok = len(missing) == 0
            
            if missing:
                status.warnings.append(f"缺少依赖: {', '.join(missing[:10])}")
                
        except Exception as e:
            status.errors.append(f"导入分析失败: {e}")
    
    def _check_runtime(self, file_path: Path, status: ModuleStatus):
        """检查运行时导入"""
        try:
            module_name = file_path.stem
            parent_dir = file_path.parent.name
            
            if parent_dir == 'api':
                full_import = f"api.{module_name}"
            elif parent_dir == 'utils':
                full_import = f"utils.{module_name}"
            elif parent_dir == 'asr':
                full_import = f"asr.{module_name}"
            else:
                full_import = module_name
            
            spec = importlib.util.spec_from_file_location(full_import, str(file_path))
            if spec and spec.loader:
                try:
                    module = importlib.util.module_from_spec(spec)
                    
                    old_modules = sys.modules.get(full_import)
                    try:
                        sys.modules[full_import] = module
                        spec.loader.exec_module(module)
                        status.runtime_ok = True
                    except Exception as e:
                        error_msg = str(e).split('\n')[0][:100]
                        status.errors.append(f"运行时错误: {error_msg}")
                        status.runtime_ok = False
                    finally:
                        if old_modules is not None:
                            sys.modules[full_import] = old_modules
                        elif full_import in sys.modules:
                            del sys.modules[full_import]
                            
                except Exception as e:
                    status.errors.append(f"模块加载失败: {str(e)[:100]}")
                    
        except Exception as e:
            status.warnings.append(f"运行时检查跳过: {str(e)[:80]}")
    
    def _check_logic_completeness(self, file_path: Path, status: ModuleStatus):
        """检查逻辑完整性"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            code_lines = [l.strip() for l in lines 
                         if l.strip() and not l.strip().startswith('#')
                         and not l.strip().startswith('"""')
                         and not l.strip().startswith("'''")]
            
            has_code = len(code_lines) > 10
            has_function_def = any('def ' in l or 'class ' in l for l in code_lines)
            has_return_or_yield = any(
                'return' in l or 'yield' in l or 'pass' in l 
                for l in code_lines[-20:] if l
            ) if code_lines else False
            
            if not has_code:
                status.has_logic = False
                status.diagnosis = "空文件或仅有注释"
            elif not has_function_def:
                status.has_logic = False
                status.diagnosis = "无函数/类定义，可能是配置文件"
            elif not has_return_or_yield and has_function_def:
                status.warnings.append("部分函数可能缺少返回值")
                
        except Exception:
            pass
    
    def _classify_module(self, status: ModuleStatus):
        """分类模块"""
        if not status.syntax_ok:
            if status.line_count < 100:
                status.category = "useless"
                status.diagnosis = "语法错误且代码量小，修复价值低"
                self.useless_count += 1
            else:
                status.category = "fixable"
                status.fix_suggestions = ["修复语法错误"]
                self.fixable_count += 1
            return
        
        if not status.missing_deps and status.runtime_ok:
            status.category = "healthy"
            self.healthy_count += 1
            return
        
        critical_missing = [
            dep for dep in status.missing_deps
            if dep in ['flask', 'requests', 'torch', 'transformers']
        ]
        
        if critical_missing:
            status.category = "fixable"
            status.fix_suggestions = [f"安装缺失依赖: pip install {' '.join(critical_missing)}"]
            self.fixable_count += 1
            return
        
        if status.missing_deps:
            optional_missing = all(
                dep in ['ctransformers', 'llama_cpp', 'PIL', 'Pillow',
                       'diffusers', 'soundfile', 'pydub', 'silero',
                       'openai_whisper', 'faster_whisper', 'whisper']
                for dep in status.missing_deps
            )
            
            if optional_missing:
                status.category = "fixable"
                status.fix_suggestions = ["安装可选依赖以启用完整功能"]
                self.fixable_count += 1
            else:
                status.category = "fixable"
                self.fixable_count += 1
            return
        
        if not status.runtime_ok and status.syntax_ok:
            error_text = '\n'.join(status.errors)
            
            critical_patterns = [
                'ModuleNotFoundError',
                'ImportError',
                'OSError',
                'ConnectionRefusedError'
            ]
            
            has_critical = any(p in error_text for p in critical_patterns)
            
            if has_critical:
                status.category = "fixable"
                self.fixable_count += 1
            else:
                status.category = "unfixable"
                status.diagnosis = "存在无法自动修复的运行时问题"
                self.unfixable_count += 1
            return
        
        if not status.has_logic and status.line_count < 200:
            status.category = "useless"
            self.useless_count += 1
            return
        
        status.category = "healthy"
        self.healthy_count += 1
    
    def generate_report(self) -> Dict[str, Any]:
        """生成报告"""
        elapsed = time.time() - self.start_time
        
        categories = {
            "healthy": [],
            "fixable": [],
            "unfixable": [],
            "useless": []
        }
        
        for name, status in sorted(self.results.items()):
            categories[status.category].append({
                "name": name,
                "path": status.path,
                "line_count": status.line_count,
                "errors": status.errors,
                "warnings": status.warnings,
                "missing_deps": status.missing_deps,
                "diagnosis": status.diagnosis,
                "fix_suggestions": status.fix_suggestions,
                "syntax_ok": status.syntax_ok,
                "imports_ok": status.imports_ok,
                "runtime_ok": status.runtime_ok
            })
        
        report = {
            "scan_info": {
                "timestamp": datetime.now().isoformat(),
                "elapsed_seconds": round(elapsed, 2),
                "total_modules_scanned": len(self.results),
                "project_directory": str(PROJECT_DIR)
            },
            "statistics": {
                "total": len(self.results),
                "healthy": self.healthy_count,
                "fixable": self.fixable_count,
                "unfixable": self.unfixable_count,
                "useless": self.useless_count,
                "health_rate": f"{(self.healthy_count / max(len(self.results), 1)) * 100:.1f}%"
            },
            "categories": categories,
            "critical_issues": self._extract_critical_issues(),
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _extract_critical_issues(self) -> List[Dict]:
        """提取关键问题"""
        issues = []
        
        for name, status in self.results.items():
            if status.errors:
                for err in status.errors[:2]:
                    issues.append({
                        "module": name,
                        "severity": "error",
                        "message": err,
                        "category": status.category
                    })
        
        return issues[:30]
    
    def _generate_recommendations(self) -> List[str]:
        """生成建议"""
        recs = []
        
        if self.fixable_count > 0:
            recs.append(f"有 {self.fixable_count} 个可修复模块，建议按优先级处理")
        
        if self.unfixable_count > 0:
            recs.append(f"⚠️ 有 {self.unfixable_count} 个可能无法修复的模块，需要人工审查")
        
        if self.useless_count > 0:
            recs.append(f"🗑️ 有 {self.useless_count} 个可能无用的模块，考虑清理")
        
        all_missing_deps = set()
        for status in self.results.values():
            all_missing_deps.update(status.missing_deps)
        
        if all_missing_deps:
            recs.append(f"统一安装缺失依赖: pip install {' '.join(sorted(all_missing_deps)[:15])}")
        
        return recs


def print_report(report: Dict[str, Any]):
    """打印格式化报告"""
    stats = report["statistics"]
    
    print("\n" + "=" * 80)
    print("  📋 Ollama Hub 模块体检报告")
    print("=" * 80)
    
    print(f"\n  统计概览:")
    print(f"    总计模块:   {stats['total']}")
    print(f"    ✅ 健康:     {stats['healthy']}")
    print(f"    🔧 可修复:   {stats['fixable']}")
    print(f"    ❌ 不可修复: {stats['unfixable']}")
    print(f"    🗑️ 无用:     {stats['useless']}")
    print(f"    健康率:     {stats['health_rate']}")
    
    categories_data = report["categories"]
    
    if categories_data["useless"]:
        print(f"\n{'─' * 70}")
        print(f"  🗑️ 无用模块 ({len(categories_data['useless'])}个)")
        print(f"{'─' * 70}")
        for m in categories_data["useless"]:
            print(f"    ✗ {m['path']}")
            if m.get('diagnosis'):
                print(f"       原因: {m['diagnosis']}")
    
    if categories_data["unfixable"]:
        print(f"\n{'─' * 70}")
        print(f"  ❌ 不可修复模块 ({len(categories_data['unfixable'])}个)")
        print(f"{'─' * 70}")
        for m in categories_data["unfixable"]:
            print(f"    ✗ {m['path']}")
            if m.get('errors'):
                for e in m['errors'][:2]:
                    print(f"       错误: {e[:60]}")
            if m.get('diagnosis'):
                print(f"       诊断: {m['diagnosis']}")
    
    if categories_data["fixable"]:
        print(f"\n{'─' * 70}")
        print(f"  🔧 可修复模块 ({len(categories_data['fixable'])}个)")
        print(f"{'─' * 70}")
        for m in categories_data["fixable"][:25]:
            print(f"    ⚠ {m['path']} ({m['line_count']}行)")
            if m.get('missing_deps'):
                print(f"       缺少依赖: {', '.join(m['missing_deps'][:5])}")
            if m.get('errors'):
                for e in m['errors'][:1]:
                    print(f"       问题: {e[:60]}")
            if m.get('fix_suggestions'):
                print(f"       建议: {m['fix_suggestions'][0][:60]}")
        
        if len(categories_data["fixable"]) > 25:
            print(f"    ... 还有 {len(categories_data['fixable']) - 25} 个可修复模块")
    
    if categories_data["healthy"]:
        print(f"\n{'─' * 70}")
        print(f"  ✅ 健康模块 ({len(categories_data['healthy'])}个)")
        print(f"{'─' * 70}")
        for m in categories_data["healthy"][:20]:
            print(f"    ✓ {m['path']}")
        if len(categories_data["healthy"]) > 20:
            print(f"    ... 还有 {len(categories_data['healthy']) - 20} 个健康模块")
    
    if report.get("critical_issues"):
        print(f"\n{'─' * 70}")
        print(f"  ⚠️ 关键问题列表")
        print(f"{'─' * 70}")
        for issue in report["critical_issues"][:15]:
            icon = "❌" if issue["severity"] == "error" else "⚠️"
            print(f"    {icon} [{issue['module']}] {issue['message'][:65]}")
    
    if report.get("recommendations"):
        print(f"\n{'─' * 70}")
        print(f"  💡 建议")
        print(f"{'─' * 70}")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"    {i}. {rec}")
    
    print("\n" + "=" * 80)


def main():
    scanner = ModuleScanner()
    
    scanner.scan_all_modules()
    
    report = scanner.generate_report()
    
    print_report(report)
    
    output_file = PROJECT_DIR / "tests" / "module_health_report.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n  📄 详细报告已保存至: {output_file}")
    
    return 0


if __name__ == "__main__":
    main()
