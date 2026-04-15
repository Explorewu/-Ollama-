#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
漏洞过滤器 - 只保留真正需要修复的漏洞
"""

import json
from pathlib import Path

def filter_vulnerabilities(report_file: str = "vulnerability_report.json"):
    """过滤漏洞"""
    
    with open(report_file, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    vulnerabilities = report["vulnerabilities"]
    
    # 真正需要关注的高危漏洞
    high_priority = []
    
    for vuln in vulnerabilities:
        # 只保留 HIGH 级别
        if vuln["severity"] != "high":
            continue
        
        # 过滤误报
        code = vuln["code_snippet"]
        
        # 过滤掉 f-string 的误报
        if "f\"" in code or "f'" in code:
            # 但保留真正的路径遍历
            if any(x in code for x in ["request", "user", "input", "path"]):
                high_priority.append(vuln)
            continue
        
        # 保留真正的安全问题
        high_priority.append(vuln)
    
    # 统计
    by_category = {}
    for vuln in high_priority:
        cat = vuln["category"]
        by_category[cat] = by_category.get(cat, 0) + 1
    
    print(f"\n{'='*60}")
    print(f"真正需要修复的 HIGH 级别漏洞: {len(high_priority)} 个")
    print(f"{'='*60}\n")
    
    print("按分类统计:")
    for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    
    print(f"\n{'='*60}")
    print(f"详细列表:")
    print(f"{'='*60}\n")
    
    for vuln in high_priority[:100]:  # 只显示前 100 个
        snippet = vuln["code_snippet"][:60]
        print(f"[{vuln['id']}] {vuln['category']} - {vuln['file']}:{vuln['line']}")
        print(f"    {snippet}...")
        print(f"    Impact: {vuln['impact']}")
        print(f"    Fix: {vuln['recommendation']}")
        print()
    
    # 保存过滤后的报告
    filtered_report = {
        "timestamp": report["timestamp"],
        "total_filtered": len(high_priority),
        "vulnerabilities": high_priority
    }
    
    output_file = "filtered_vulnerabilities.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_report, f, ensure_ascii=False, indent=2)
    
    print(f"\n过滤后的报告已保存: {output_file}")
    
    return high_priority

if __name__ == "__main__":
    filter_vulnerabilities()
