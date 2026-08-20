"""conftest.py：让 pytest 能找到 src/ 模块（避免每个 test 重复 sys.path.insert）。"""
import sys
from pathlib import Path

# tests/ 的父目录 = md-podcast-studio/，含 scripts/src
parent = Path(__file__).parent.parent
scripts = parent / "scripts"
if str(scripts) not in sys.path:
    sys.path.insert(0, str(scripts))
