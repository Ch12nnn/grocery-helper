# -*- coding: utf-8 -*-
"""
sh_market_price.py - 上海市主副食品/菜品价格采集与解析模块
数据来源：上海市发展和改革委员会（价格监测中心 / 价格监管动态）
"""

import os
import re
import urllib.request
import urllib.parse
from datetime import datetime
import xlrd

BASE_URL = "https://fgw.sh.gov.cn"
LIST_URL = "https://fgw.sh.gov.cn/fgw_jgjgdt/index.html"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def fetch_latest_price_article():
    """获取发改委最新一篇主副食品价格监测文章链接及简报"""
    req = urllib.request.Request(LIST_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    match = re.search(r'<a[^>]*href="([^"]+)"[^>]*title="(上海市主要主副食品品种价格信息表[^"]+)"', html)
    if not match:
        raise RuntimeError("未在上海发改委官网找到最新价格信息表文章，请检查网络或网站结构")

    rel_url = match.group(1)
    title = match.group(2)
    article_url = urllib.parse.urljoin(BASE_URL, rel_url)

    # 抓取文章正文以获取宏观涨跌简述及 .xls 附件链接
    req_art = urllib.request.Request(article_url, headers=HEADERS)
    with urllib.request.urlopen(req_art, timeout=12) as resp_art:
        art_html = resp_art.read().decode("utf-8", errors="ignore")

    # 提取概况摘要
    summary_lines = []
    paragraphs = re.findall(r'<p[^>]*>([\s\S]*?)</p>', art_html)
    for p in paragraphs:
        pt = re.sub(r'<[^>]+>', '', p).replace("&emsp;", "").strip()
        if any(k in pt for k in ["监测", "主要蔬菜", "零售均价", "肉禽蛋"]):
            summary_lines.append(pt)

    # 提取 .xls 附件下载链接
    xls_match = re.search(r'href="([^"]+\.xls)"', art_html)
    if not xls_match:
        raise RuntimeError(f"在文章 {article_url} 中未找到价格表格 (.xls) 附件链接")

    xls_url = urllib.parse.urljoin(BASE_URL, xls_match.group(1))

    return {
        "title": title,
        "article_url": article_url,
        "xls_url": xls_url,
        "summary": "\n".join(summary_lines)
    }

def download_xls(xls_url, cache_dir="data"):
    """下载最新的价格表格文件（带本地缓存）"""
    os.makedirs(cache_dir, exist_ok=True)
    filename = os.path.basename(urllib.parse.urlparse(xls_url).path)
    if not filename.endswith(".xls"):
        filename = f"price_{datetime.now().strftime('%Y%m%d')}.xls"
    filepath = os.path.join(cache_dir, filename)

    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        req = urllib.request.Request(xls_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
        with open(filepath, "wb") as f:
            f.write(content)

    return filepath

def parse_price_xls(filepath, target_district=""):
    """
    解析发改委价格 Excel 文件
    返回所有菜品的均价、全市区县区间及指定区价格
    """
    wb = xlrd.open_workbook(filepath)
    sheet = wb.sheet_by_index(0)

    # 提取采价日期
    date_str = ""
    for r in range(min(5, sheet.nrows)):
        cell_val = str(sheet.cell_value(r, 0)).strip()
        m = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)', cell_val)
        if m:
            date_str = m.group(1)
            break

    # 解析表头列（第 3~6 行）
    categories = [str(sheet.cell_value(3, c)).strip() for c in range(2, sheet.ncols)]
    items = [str(sheet.cell_value(4, c)).strip() for c in range(2, sheet.ncols)]
    specs = [str(sheet.cell_value(5, c)).strip() for c in range(2, sheet.ncols)]
    units = [str(sheet.cell_value(6, c)).strip() for c in range(2, sheet.ncols)]
    city_avgs = [sheet.cell_value(7, c) for c in range(2, sheet.ncols)]

    # 收集各采样点的价格以计算区间、菜场均价与商超上限价
    market_prices = {c: [] for c in range(2, sheet.ncols)}
    wet_market_prices = {c: [] for c in range(2, sheet.ncols)}
    supermarket_prices = {c: [] for c in range(2, sheet.ncols)}
    district_prices = {c: [] for c in range(2, sheet.ncols)}

    SUPERMARKET_KEYWORDS = ['超市', '大润发', '联华', '农工商', '卖场', '店', '生鲜超市']

    for r in range(8, sheet.nrows):
        district = str(sheet.cell_value(r, 0)).strip()
        market_name = str(sheet.cell_value(r, 1)).strip()

        # 过滤底部的说明和标注行
        if not district or any(k in district for k in ['说明', '上海市', '注']):
            continue

        source_label = f"{district}·{market_name}" if market_name else district
        is_supermarket = any(k in market_name for k in SUPERMARKET_KEYWORDS)

        for c in range(2, sheet.ncols):
            val = sheet.cell_value(r, c)
            try:
                p = float(val)
                if p > 0:
                    market_prices[c].append((p, source_label))
                    if is_supermarket:
                        supermarket_prices[c].append(p)
                    else:
                        wet_market_prices[c].append(p)

                    if target_district and target_district in district:
                        district_prices[c].append(p)
            except (ValueError, TypeError):
                continue

    products = []
    for idx in range(len(items)):
        col = idx + 2
        name = items[idx]
        cat = categories[idx]
        spec = specs[idx]
        unit = units[idx]
        if not name:
            continue

        try:
            city_avg = float(city_avgs[idx])
        except (ValueError, TypeError):
            city_avg = 0.0

        all_p = market_prices[col]
        if all_p:
            all_p_sorted = sorted(all_p, key=lambda x: x[0])
            min_p, min_source = all_p_sorted[0]
            max_p, max_source = all_p_sorted[-1]
        else:
            min_p, min_source = city_avg, "发改委综合采样"
            max_p, max_source = city_avg, "发改委综合采样"

        # 线下菜市场真实零售均价
        wm_p = wet_market_prices[col]
        market_avg = (sum(wm_p) / len(wm_p)) if wm_p else city_avg

        # 大型商超天花板参考均价
        sm_p = supermarket_prices[col]
        supermarket_avg = (sum(sm_p) / len(sm_p)) if sm_p else 0.0

        dist_p = district_prices[col]
        district_avg = (sum(dist_p) / len(dist_p)) if dist_p else 0.0

        products.append({
            "category": cat,
            "name": name,
            "spec": spec,
            "display_name": f"{name}({spec})" if spec else name,
            "unit": unit,
            "city_avg": city_avg,
            "market_avg": market_avg,
            "supermarket_avg": supermarket_avg,
            "min_price": min_p,
            "min_source": min_source,
            "max_price": max_p,
            "max_source": max_source,
            "district_avg": district_avg
        })

    return {
        "date": date_str or datetime.now().strftime("%Y年%m月%d日"),
        "products": products
    }


SYNONYMS = {
    "鲜猪肉": ["猪肉"],
    "鲜鸡蛋": ["鸡蛋"],
    "五花肉": ["肋条肉", "带皮后腿肉"],
    "排骨": ["肋排"],
    "番茄": ["西红柿"],
    "空心菜": ["蕹菜"],
    "菜薹": ["菜苔"],
}

def filter_favorite_products(products, favorites):
    """
    根据用户配置的常买清单过滤菜品
    支持关键字模糊匹配、同义词（如“五花肉”对应“肋条肉”，“番茄”对应“西红柿”）
    """
    if not favorites:
        return products

    matched = []
    seen = set()

    for fav in favorites:
        fav_clean = fav.strip()
        if not fav_clean:
            continue

        # 候选匹配词集合
        search_terms = [fav_clean]
        for syn_key, syn_vals in SYNONYMS.items():
            if syn_key in fav_clean or fav_clean in syn_key:
                search_terms.extend(syn_vals)

        # 同时也剥离括号中的规格进行匹配
        base_term = re.sub(r'[\(（].*?[\)）]', '', fav_clean).strip()
        if base_term and base_term not in search_terms:
            search_terms.append(base_term)

        for p in products:
            label = f"{p['name']} {p['spec']} {p['category']} {p['display_name']}"
            is_match = False
            for term in search_terms:
                if term in label or (len(term) >= 2 and label in term):
                    is_match = True
                    break

            if is_match and p['display_name'] not in seen:
                seen.add(p['display_name'])
                matched.append(p)

    return matched


def get_latest_price_report(favorites=None, target_district=""):
    """完整执行流程：爬取 -> 解析 -> 过滤 -> 返回完整报告数据"""
    art_info = fetch_latest_price_article()
    filepath = download_xls(art_info["xls_url"])
    parsed = parse_price_xls(filepath, target_district=target_district)

    filtered = filter_favorite_products(parsed["products"], favorites)

    return {
        "title": art_info["title"],
        "date": parsed["date"],
        "summary": art_info["summary"],
        "target_district": target_district,
        "total_items": len(parsed["products"]),
        "matched_items": filtered
    }

if __name__ == "__main__":
    print("正在获取上海市发改委最新菜价数据...")
    favs = ["青菜", "鸡毛菜", "西红柿", "黄瓜", "土豆", "鲜猪肉", "鸡蛋", "基围虾", "苹果"]
    report = get_latest_price_report(favorites=favs, target_district="闵行区")
    print(f"\n【{report['title']}】 (采价日期: {report['date']})")
    print(f"发改委宏观简报:\n{report['summary']}\n")
    print(f"{'类别':<6} | {'品名':<16} | {'单位':<8} | {'全市均价':<8} | {'菜场区间':<14}")
    print("-" * 65)
    for p in report["matched_items"]:
        range_str = f"{p['min_price']:.2f} ~ {p['max_price']:.2f}"
        print(f"{p['category']:<6} | {p['display_name']:<16} | {p['unit']:<8} | {p['city_avg']:<8.2f} | {range_str:<14}")
