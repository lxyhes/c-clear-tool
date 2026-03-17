#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试空间分析功能 - 快速版"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import DiskSpaceAnalyzer

def test_analyzer():
    print("=" * 60)
    print("测试 C盘空间分析功能 (快速版)")
    print("=" * 60)
    
    analyzer = DiskSpaceAnalyzer()
    
    # 只测试一个目录
    test_path = os.path.join(os.environ['USERPROFILE'], "Downloads")
    
    if not os.path.exists(test_path):
        print(f"测试目录不存在: {test_path}")
        return
    
    print(f"\n测试目录: {test_path}")
    print("-" * 60)
    
    # 使用PowerShell方法
    print("\n1. 使用PowerShell方法...")
    try:
        size1 = analyzer._get_dir_size_ntfs_fast(test_path)
        print(f"   结果: {format_size(size1)}")
    except Exception as e:
        print(f"   失败: {e}")
        size1 = 0
    
    # 使用Python快速扫描
    print("\n2. 使用Python快速扫描...")
    try:
        size2 = analyzer._python_fast_scan(test_path, max_files=5000)
        print(f"   结果: {format_size(size2)}")
    except Exception as e:
        print(f"   失败: {e}")
        size2 = 0
    
    # 比较
    print("\n" + "-" * 60)
    if size1 > 0 and size2 > 0:
        diff = abs(size1 - size2) / max(size1, size2) * 100
        print(f"差异: {diff:.1f}%")
        if diff < 10:
            print("✓ 结果基本一致")
        elif diff < 30:
            print("△ 结果有一定偏差（可能快速扫描只统计了部分文件）")
        else:
            print("✗ 结果偏差较大，需要检查代码")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

def format_size(size):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

if __name__ == "__main__":
    test_analyzer()