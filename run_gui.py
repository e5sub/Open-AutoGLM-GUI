#!/usr/bin/env python3
"""
启动 Phone Agent GUI 的简单脚本
"""

import subprocess
import sys
import os

def main():
    print("启动 Phone Agent GUI...")
    # 直接导入并调用 gui.main()，避免使用子进程（打包后会导致重复弹窗/递归启动）
    try:
        import gui
        gui.main()
    except Exception as e:
        print(f"启动 GUI 失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()