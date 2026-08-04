#!/usr/bin/env python3
"""
win_utf8.py — Windows 控制台 UTF-8 修复工具（模块）

在 Windows 下，Python 输出 UTF-8 中文会被 PowerShell 控制台按 GBK 解码导致乱码。
在脚本入口调用 ensure_utf8_console() 即可自动修复，无需用户手动设置。

用法：
    import win_utf8
    win_utf8.ensure_utf8_console()
"""
import sys
import os


def ensure_utf8_console():
    """让 Windows 控制台正确显示 UTF-8 中文。无副作用，非 Windows 直接返回。"""
    # 1. Python 侧：stdout 强制 UTF-8
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # 2. 仅 Windows：通过 ctypes 设置控制台输出代码页为 UTF-8 (65001)
    if os.name != "nt":
        return
    try:
        import ctypes
        # 把控制台输出代码页设为 UTF-8，并同步 Windows 函数
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass


if __name__ == "__main__":
    ensure_utf8_console()
    print("UTF-8 控制台测试：中文正常显示 -> 新建项目 / 9:16 / 2K / Nano Banana 2")
