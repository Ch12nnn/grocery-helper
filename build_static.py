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

from sh_market_price import (
    fetch_latest_price_article,
    download_xls,
    parse_price_xls
)

def build_static_data():
    os.makedirs(DOCS_DIR, exist_ok=True)

    print("🚀 正在获取上海市发改委最新菜价信息...")
    art_info = fetch_latest_price_article()
    cache_dir = os.path.join(CURRENT_DIR, "data")
    filepath = download_xls(art_info["xls_url"], cache_dir=cache_dir)
    
    # 解析全量数据
    parsed = parse_price_xls(filepath)

    # 按照分类组织商品
    categories = {}
    for p in parsed["products"]:
        c = p["category"]
        if c not in categories:
            categories[c] = []
        categories[c].append(p)

    data = {
        "title": art_info["title"],
        "date": parsed["date"],
        "summary": art_info["summary"],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": len(parsed["products"]),
        "categories": categories,
        "all_products": parsed["products"]
    }

    with open(DATA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 静态数据已成功构建: {DATA_JSON_PATH}")
    print(f"   采价日期: {parsed['date']}, 共包含 {len(parsed['products'])} 种监测食材。")
    return data

if __name__ == "__main__":
    build_static_data()
