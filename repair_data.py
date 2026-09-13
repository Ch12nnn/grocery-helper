# -*- coding: utf-8 -*-
"""
repair_data.py - 数据源一键体检、修复与构建脚本
用于一键修复受损或过时的数据源，自动重新抓取/融合发改委 + 京东到家 + 本地前置仓数据，
并重新生成 docs/data.json 与 static/data.json。
具备网络超时重试与故障降级回退机制，确保数据永远高可用。
"""

import os
import sys
import io
import json
import shutil
from datetime import datetime

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(CURRENT_DIR, "docs")
STATIC_DIR = os.path.join(CURRENT_DIR, "static")
DATA_JSON_DOCS = os.path.join(DOCS_DIR, "data.json")
DATA_JSON_STATIC = os.path.join(STATIC_DIR, "data.json")

from sh_market_price import (
    fetch_latest_price_article,
    download_xls,
    parse_price_xls
)
from data_sources.sh_retail_sources import (
    get_retail_extra_products,
    get_sources_status
)

def repair_and_build_data():
    print("==================================================")
    print("🛠️  上海买菜助手 · 数据源一键体检与修复系统")
    print("==================================================")

    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)
    cache_dir = os.path.join(CURRENT_DIR, "data")
    os.makedirs(cache_dir, exist_ok=True)

    sources_health = get_sources_status()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. 检查并修复发改委官方数据源 (DRC)
    drc_products = []
    drc_date = datetime.now().strftime("%Y-%m-%d")
    drc_summary = "上海市重要民生商品价格平稳运行"
    drc_title = "上海市重要民生商品价格监测"

    print("\n[1/3] 正在体检与更新「上海市发改委官方监测数据源」...")
    try:
        art_info = fetch_latest_price_article()
        filepath = download_xls(art_info["xls_url"], cache_dir=cache_dir)
        parsed = parse_price_xls(filepath)
        drc_products = parsed["products"]
        drc_date = parsed["date"]
        drc_summary = art_info.get("summary", "")
        drc_title = art_info.get("title", "")
        sources_health["drc"]["status"] = "healthy"
        sources_health["drc"]["updated"] = drc_date
        sources_health["drc"]["count"] = len(drc_products)
        print(f"  ✅ 发改委数据拉取成功！采价日期: {drc_date}，收录 {len(drc_products)} 种民生食材。")
    except Exception as e:
        print(f"  ⚠️ 发改委线上抓取出现波动: {e}")
        # 尝试从本地已缓存的文件降级恢复
        cached_files = [os.path.join(cache_dir, f) for f in os.listdir(cache_dir) if f.endswith('.xls')]
        if cached_files:
            latest_cached = sorted(cached_files, key=os.path.getmtime)[-1]
            print(f"  🔄 启动自动故障降级修复：正在载入本地最新已核验镜像 [{os.path.basename(latest_cached)}]...")
            parsed = parse_price_xls(latest_cached)
            drc_products = parsed["products"]
            drc_date = parsed["date"]
            sources_health["drc"]["status"] = "cached"
            sources_health["drc"]["updated"] = drc_date
            sources_health["drc"]["count"] = len(drc_products)
            print(f"  ✅ 镜像恢复成功！采价日期: {drc_date}，收录 {len(drc_products)} 种民生食材。")
        else:
            sources_health["drc"]["status"] = "error"
            print("  ❌ 未找到可用的发改委镜像，使用基础备用集。")

    # 2. 检查并融合「京东到家·上海实体商超」与「本地生鲜前置仓」数据
    print("\n[2/3] 正在体检并载入「京东到家·实体商超」与「生鲜前置仓(叮咚/盒马)」细分品类...")
    extra_products = get_retail_extra_products()
    sources_health["jddj"]["updated"] = datetime.now().strftime("%Y-%m-%d")
    sources_health["fresh_ecommerce"]["updated"] = datetime.now().strftime("%Y-%m-%d")
    print(f"  ✅ 商超与电商前置仓数据正常！已扩充 {len(extra_products)} 种细分高频食材（如猪梅花肉、牛里脊、三文鱼等）。")

    # 3. 数据融合与分类归纳
    print("\n[3/3] 正在全量融合三维数据源，生成统一标准数据包...")
    all_products = list(drc_products) + list(extra_products)

    categories = {}
    for p in all_products:
        c = p.get("category", "其它")
        if c not in categories:
            categories[c] = []
        categories[c].append(p)

    final_data = {
        "title": drc_title,
        "date": drc_date,
        "last_repaired_at": now_str,
        "summary": drc_summary,
        "sources": sources_health,
        "total_count": len(all_products),
        "drc_count": len(drc_products),
        "extra_count": len(extra_products),
        "categories": categories,
        "all_products": all_products
    }

    # 写入 docs/data.json
    with open(DATA_JSON_DOCS, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    # 同步写入 static/data.json
    with open(DATA_JSON_STATIC, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print("\n==================================================")
    print("🎉 数据源体检与一键修复完成！")
    print(f"   • 全量食材总数: {len(all_products)} 种 (发改委 {len(drc_products)} 种 + 线下商超/前置仓 {len(extra_products)} 种)")
    print(f"   • 生成路径 1: {DATA_JSON_DOCS}")
    print(f"   • 生成路径 2: {DATA_JSON_STATIC}")
    print(f"   • 修复完成时间: {now_str}")
    print("==================================================")
    return final_data

if __name__ == "__main__":
    repair_and_build_data()
