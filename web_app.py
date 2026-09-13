# -*- coding: utf-8 -*-
"""
web_app.py - 上海买菜助手 Web 应用程序
提供自适应手机/电脑界面的即时比价、常买菜品自定义配置与微信推送服务。
无需安装任何外部 Web 框架，基于 Python 标准库多线程 HTTP 服务构建。
"""

import sys
import os
import json
import socket
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

# 保证标准输出编码为 UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(CURRENT_DIR, "docs")
CONFIG_PATH = os.path.join(CURRENT_DIR, "config.json")


from sh_market_price import get_latest_price_report, download_xls, parse_price_xls, fetch_latest_price_article

# 全局内存缓存
_CACHE = {
    "data": None,
    "last_fetched": None
}

def get_lan_ip():
    """获取本机局域网 IP 地址（供手机在同一 WiFi 下访问）"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def load_config():
    """读取配置文件"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "favorites": ["青菜", "鸡毛菜", "西红柿", "黄瓜", "土豆", "鲜猪肉(精瘦肉)", "鲜鸡蛋"],
        "target_district": ""
    }

def save_config(cfg):
    """保存配置文件"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get_cached_market_data(force_reload=False):
    """获取全量市场菜价数据（带缓存）"""
    cfg = load_config()
    target_district = cfg.get("target_district", "")
    
    if _CACHE["data"] is None or force_reload:
        art_info = fetch_latest_price_article()
        filepath = download_xls(art_info["xls_url"], cache_dir=os.path.join(CURRENT_DIR, "data"))
        parsed = parse_price_xls(filepath, target_district=target_district)
        
        # 按类别分组
        categories = {}
        for p in parsed["products"]:
            c = p["category"]
            if c not in categories:
                categories[c] = []
            categories[c].append(p)

        _CACHE["data"] = {
            "title": art_info["title"],
            "date": parsed["date"],
            "summary": art_info["summary"],
            "target_district": target_district,
            "categories": categories,
            "all_products": parsed["products"]
        }
    return _CACHE["data"]

class GroceryRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/data":
            self.send_json_response(get_cached_market_data())
        elif path == "/api/config":
            self.send_json_response(load_config())
        elif path == "/" or not os.path.exists(os.path.join(STATIC_DIR, path.lstrip("/"))):
            # 默认返回 index.html
            self.path = "/index.html"
            return super().do_GET()
        else:
            return super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/api/compare":
            self.handle_compare(payload)
        elif path == "/api/config":
            self.handle_save_config(payload)
        elif path == "/api/reload":
            get_cached_market_data(force_reload=True)
            self.send_json_response({"success": True, "message": "菜价数据已刷新为最新"})
        else:
            self.send_error(404, "API endpoint not found")

    def handle_compare(self, payload):
        """
        核心比价逻辑：
        输入: item_name (菜品名称), user_price (用户输入的单价)
        输出: benchmark (基准均价), diff (差额), diff_pct (差额百分比), status (评级)
        """
        item_name = payload.get("item_name", "").strip()
        try:
            user_price = float(payload.get("user_price", 0))
        except (ValueError, TypeError):
            self.send_json_response({"success": False, "error": "请输入有效的价格数字"}, status=400)
            return

        data = get_cached_market_data()
        target_product = None

        for p in data["all_products"]:
            if item_name in p["display_name"] or item_name == p["name"] or p["name"] in item_name:
                target_product = p
                break

        if not target_product:
            self.send_json_response({"success": False, "error": f"未在监测库中找到菜品 '{item_name}'"}, status=404)
            return

        cfg = load_config()
        # 默认优先以全市零售均价为基准
        benchmark = target_product["city_avg"]
        benchmark_label = "全市菜市场零售均价"

        # 如果用户指定了区域并且该区域有有效均价，也可同时作为对比
        district_avg = target_product.get("district_avg", 0)
        has_district = district_avg > 0 and bool(cfg.get("target_district"))

        diff = user_price - benchmark
        diff_pct = (diff / benchmark * 100.0) if benchmark > 0 else 0.0

        # 智能评级
        if diff_pct <= -15.0:
            status = "CHEAP"
            status_text = "超值实惠"
            color = "#10b981" # 翠绿
            icon = "🔥"
            advice = f"比全市均价便宜了 {abs(diff_pct):.1f}%！价格非常划算，成色若新鲜建议果断入手。"
        elif -15.0 < diff_pct <= 10.0:
            status = "FAIR"
            status_text = "价格公道"
            color = "#3b82f6" # 蓝色
            icon = "✅"
            advice = f"与全市均价相差不大（偏差 {diff_pct:+.1f}%），处于菜市场正常的合理波动区间。"
        elif 10.0 < diff_pct <= 30.0:
            status = "EXPENSIVE"
            status_text = "略微偏贵"
            color = "#f59e0b" # 琥珀黄
            icon = "⚠️"
            advice = f"比全市均价高出 {diff_pct:.1f}%（高了约 {diff:.2f} 元/斤）。如果品相一般，可尝试跟摊主抹零还价。"
        else:
            status = "OVERPRICED"
            status_text = "明显偏贵"
            color = "#ef4444" # 红色
            icon = "🛑"
            advice = f"比全市均价高出了整整 {diff_pct:.1f}%（贵了约 {diff:.2f} 元/斤）！定价明显偏高，建议换一家摊位或去超市/平价菜专柜。"

        result = {
            "success": True,
            "product": target_product,
            "user_price": user_price,
            "benchmark": benchmark,
            "benchmark_label": benchmark_label,
            "district_avg": district_avg if has_district else None,
            "district_name": cfg.get("target_district") if has_district else None,
            "diff": round(diff, 2),
            "diff_pct": round(diff_pct, 1),
            "min_price": target_product["min_price"],
            "max_price": target_product["max_price"],
            "status": status,
            "status_text": status_text,
            "color": color,
            "icon": icon,
            "advice": advice
        }
        self.send_json_response(result)

    def handle_save_config(self, payload):
        """保存用户配置（如自定义关注的常买菜品）"""
        cfg = load_config()
        if "favorites" in payload:
            cfg["favorites"] = payload["favorites"]
        if "target_district" in payload:
            cfg["target_district"] = payload["target_district"]
        save_config(cfg)
        # 刷新缓存区县
        get_cached_market_data(force_reload=True)
        self.send_json_response({"success": True, "config": cfg})

    def send_json_response(self, data, status=200):
        """返回 JSON 响应"""
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

def run_server(port=5000):
    os.makedirs(STATIC_DIR, exist_ok=True)
    lan_ip = get_lan_ip()

    server = ThreadingHTTPServer(('0.0.0.0', port), GroceryRequestHandler)
    print("=" * 65)
    print("  🥬 上海买菜助手 Web 应用程序已成功启动！")
    print("=" * 65)
    print(f"  💻 电脑浏览器访问:  http://localhost:{port}")
    print(f"  📱 手机同一WiFi访问: http://{lan_ip}:{port}")
    print("-" * 65)
    print("  💡 提示: 手机连上家里同一个 Wi-Fi，在浏览器中输入上述手机地址，")
    print("           买菜时即可随时在手机上输入单价进行实时差额比对！")
    print("=" * 65 + "\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        server.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    run_server(port)
