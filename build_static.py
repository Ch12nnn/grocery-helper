# -*- coding: utf-8 -*-
"""
build_static.py - 生成静态网页所需的数据文件 (data.json)
用于 GitHub Pages / Vercel / 纯静态部署，手机 4G/5G 网络下随时随地访问，无需常驻后台服务。
"""

import os
import sys
import io
import json
from datetime import datetime

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(CURRENT_DIR, "docs")
DATA_JSON_PATH = os.path.join(DOCS_DIR, "data.json")

from repair_data import repair_and_build_data

def build_static_data():
    return repair_and_build_data()

if __name__ == "__main__":
    build_static_data()
