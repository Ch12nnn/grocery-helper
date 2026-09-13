# -*- coding: utf-8 -*-
"""
main.py - 上海买菜助手控制台数据同步与行情查看
用法：
  python main.py             # 抓取发改委最新菜价并刷新 docs/data.json 静态数据
  python main.py --preview   # 在控制台打印当前常买菜品均价行情
"""

import sys
import io
import os
import json
import argparse
from datetime import datetime

# 解决 Windows 控制台默认编码可能导致的中文输出乱码问题
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from sh_market_price import get_latest_price_report
from build_static import build_static_data

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        'favorites': ['青菜', '鸡毛菜', '西红柿', '黄瓜', '土豆', '鲜猪肉(精瘦肉)', '鲜鸡蛋'],
        'target_district': ''
    }

def print_price_summary(report):
    print("\n" + "=" * 68)
    print(f"  🥬 {report['title']}")
    print("=" * 68)
    print(f"{'品名':<16} {'菜场均价(基准)':<14} {'商超均价(上限)':<14} {'采价区间':<14}")
    print("-" * 68)
    for item in report.get('matched_items', []):
        name = item['display_name']
        m_avg = f"{item['market_avg']:.2f}元/斤" if item.get('market_avg') else f"{item['city_avg']:.2f}元/斤"
        s_avg = f"{item['supermarket_avg']:.2f}元/斤" if item.get('supermarket_avg') else '-'
        rng = f"{item['min_price']:.1f}~{item['max_price']:.1f}元"
        print(f"{name:<16} {m_avg:<14} {s_avg:<14} {rng:<14}")
    print("=" * 68 + "\n")

def main():
    parser = argparse.ArgumentParser(description='上海买菜助手：数据更新与行情查看')
    parser.add_argument('--preview', action='store_true', help='在控制台预览常买菜品价格')
    args = parser.parse_args()

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 开始同步上海市发改委最新菜价...")
    build_static_data()

    cfg = load_config()
    report = get_latest_price_report(
        favorites=cfg.get('favorites', []),
        target_district=cfg.get('target_district', '')
    )
    print_price_summary(report)
    print('💡 提示：双击 start_web.bat 可启动手机/电脑自适应比价网页。')

if __name__ == '__main__':
    main()
