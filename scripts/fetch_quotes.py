#!/usr/bin/env python3
"""
实时行情获取工具 -- 双数据源交叉验证

数据源:
  1. 腾讯财经 API (qt.gtimg.cn) -- 主力源
  2. Yahoo Finance API (query1.finance.yahoo.com) -- 验证源

双源策略:
  - 同时从两个源获取价格
  - 若两源价格偏差 > 1%, 标记警告
  - 若某源不可用, 回退到单源并标注
"""

import sys
import json
import urllib.request

# --- 持仓配置 ---
PORTFOLIO = {
    "sz000021": {"name": "深科技",   "yahoo": "000021.SZ", "cost": 29.21},
    "sz000400": {"name": "许继电气", "yahoo": "000400.SZ", "cost": 29.14},
    "sz002050": {"name": "三花智控", "yahoo": "002050.SZ", "cost": 42.97},
    "sz002156": {"name": "通富微电", "yahoo": "002156.SZ", "cost": 42.59},
    "sh600809": {"name": "山西汾酒", "yahoo": "600809.SS", "cost": 152.83},
    "hk01810":  {"name": "小米集团", "yahoo": "1810.HK",   "cost": 32.38},
}

INDEXES = {
    "sh000001": {"name": "上证指数", "yahoo": "000001.SS"},
    "sz399001": {"name": "深证成指", "yahoo": "399001.SZ"},
    "sz399006": {"name": "创业板指", "yahoo": "399006.SZ"},
    "hkHSI":    {"name": "恒生指数", "yahoo": "^HSI"},
}

DEVIATION_THRESHOLD = 0.01  # 1% 偏差阈值


# ========== 数据源 1: 腾讯财经 ==========

def fetch_tencent(codes):
    """从腾讯财经获取行情"""
    url = "http://qt.gtimg.cn/q=" + ",".join(codes)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("gbk")
    except Exception as e:
        sys.stderr.write("Warning: Tencent API failed: %s\n" % e)
        return {}

    result = {}
    for line in raw.split(";"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        var_name, value = line.split("=", 1)
        fields = value.strip('"').split("~")
        if len(fields) < 35:
            continue
        code_key = var_name.replace("v_", "")
        try:
            result[code_key] = {
                "name": fields[1],
                "price": float(fields[3]) if fields[3] else 0,
                "prev_close": float(fields[4]) if fields[4] else 0,
                "change_pct": float(fields[32]) if fields[32] else 0,
                "high": float(fields[33]) if fields[33] else 0,
                "low": float(fields[34]) if fields[34] else 0,
                "datetime": fields[30],
            }
        except (ValueError, IndexError):
            continue
    return result


# ========== 数据源 2: Yahoo Finance ==========

def fetch_yahoo(symbols):
    """从 Yahoo Finance 获取行情"""
    result = {}
    for sym in symbols:
        url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
               + sym + "?interval=1d&range=1d")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            meta = data["chart"]["result"][0]["meta"]
            result[sym] = float(meta["regularMarketPrice"])
        except Exception:
            continue
    return result


# ========== 交叉验证 ==========

def cross_validate(tencent_price, yahoo_price):
    """比较两源价格, 返回 (final_price, status, note)"""
    if tencent_price and yahoo_price:
        avg = (tencent_price + yahoo_price) / 2
        dev = abs(tencent_price - yahoo_price) / avg
        if dev > DEVIATION_THRESHOLD:
            return avg, "WARN", "dev %.2f%% (T:%.2f/Y:%.2f)" % (dev*100, tencent_price, yahoo_price)
        return tencent_price, "OK", ""
    elif tencent_price:
        return tencent_price, "T_ONLY", ""
    elif yahoo_price:
        return yahoo_price, "Y_ONLY", ""
    return 0, "FAIL", "both sources failed"


def status_emoji(status):
    return {"OK": "✅", "WARN": "⚠️", "T_ONLY": "🅰️", "Y_ONLY": "🅱️", "FAIL": "❌"}.get(status, "?")


def format_pnl(price, cost):
    if cost == 0 or price == 0:
        return "---"
    pnl = (price - cost) / cost * 100
    sign = "+" if pnl >= 0 else ""
    emoji = "🟢" if pnl > 0 else ("🔴" if pnl < -5 else "🟡")
    return "%s %s%.2f%%" % (emoji, sign, pnl)


def main():
    custom_codes = list(sys.argv[1:]) if len(sys.argv) > 1 else []
    show_portfolio = not custom_codes

    if show_portfolio:
        tencent_codes = list(INDEXES.keys()) + list(PORTFOLIO.keys())
        yahoo_syms = [v["yahoo"] for v in list(INDEXES.values()) + list(PORTFOLIO.values())]
    else:
        tencent_codes = custom_codes
        yahoo_syms = []

    # 获取双源数据
    tencent_data = fetch_tencent(tencent_codes)
    yahoo_data = fetch_yahoo(yahoo_syms) if yahoo_syms else {}

    if not tencent_data and not yahoo_data:
        print("Error: both data sources failed!")
        return

    if show_portfolio:
        # --- 指数 ---
        print("## 📈 市场指数\n")
        print("| 指数 | 最新价 | 涨跌幅 | 最高 | 最低 | 验证 |")
        print("|------|--------|--------|------|------|------|")
        for code_key, info in INDEXES.items():
            td = tencent_data.get(code_key, {})
            yp = yahoo_data.get(info["yahoo"], 0)
            tp = td.get("price", 0)
            price, st, note = cross_validate(tp, yp)
            chg = td.get("change_pct", 0)
            sign = "+" if chg >= 0 else ""
            print("| %s | %.2f | %s%.2f%% | %.2f | %.2f | %s |" % (
                info["name"], price, sign, chg,
                td.get("high", 0), td.get("low", 0), status_emoji(st)))
        print()

        # --- 持仓 ---
        print("## 💼 持仓行情（双源验证）\n")
        print("| 标的 | 现价 | 涨跌幅 | 成本 | 盈亏 | 验证 | 备注 |")
        print("|------|------|--------|------|------|------|------|")
        for code_key, info in PORTFOLIO.items():
            td = tencent_data.get(code_key, {})
            yp = yahoo_data.get(info["yahoo"], 0)
            tp = td.get("price", 0)
            price, st, note = cross_validate(tp, yp)
            chg = td.get("change_pct", 0)
            sign = "+" if chg >= 0 else ""
            pnl = format_pnl(price, info["cost"])
            print("| %s | %.2f | %s%.2f%% | %.2f | %s | %s | %s |" % (
                info["name"], price, sign, chg, info["cost"], pnl, status_emoji(st), note))

        # --- 摘要 ---
        dt = ""
        for td in tencent_data.values():
            if td.get("datetime"):
                dt = td["datetime"]
                break
        print("\n> 数据时间: %s | 腾讯: %d/%d | 雅虎: %d/%d" % (
            dt,
            len(tencent_data), len(tencent_codes),
            len(yahoo_data), len(yahoo_syms)))

    else:
        for code_key, td in tencent_data.items():
            sign = "+" if td["change_pct"] >= 0 else ""
            print("%s(%s) %.2f  %s%.2f%%" % (
                td["name"], code_key, td["price"], sign, td["change_pct"]))


if __name__ == "__main__":
    main()
