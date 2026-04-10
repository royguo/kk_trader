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

# --- 关注列表（A股/港股） ---
WATCHLIST = {
    # AI数据中心 / NAND存储产业链
    "hk07709":  {"name": "南方2x海力士",    "yahoo": "7709.HK"},
    "sh603986": {"name": "兆易创新",        "yahoo": "603986.SS"},
    "sh688008": {"name": "澜起科技",        "yahoo": "688008.SS"},
    "sz301308": {"name": "江波龙",          "yahoo": "301308.SZ"},
    # 港股科技龙头
    "hk00700":  {"name": "腾讯控股",        "yahoo": "0700.HK"},
    "hk03690":  {"name": "美团",            "yahoo": "3690.HK"},
    "hk09888":  {"name": "百度集团",        "yahoo": "9888.HK"},
    "hk09988":  {"name": "阿里巴巴",        "yahoo": "9988.HK"},
    # 消费/传媒
    "hk09992":  {"name": "泡泡玛特",        "yahoo": "9992.HK"},
    "sz002400": {"name": "省广集团",        "yahoo": "002400.SZ"},
    # 光模块
    "sz300308": {"name": "中际旭创",        "yahoo": "300308.SZ"},
    "sz300502": {"name": "新易盛",          "yahoo": "300502.SZ"},
    "sz300394": {"name": "天孚通信",        "yahoo": "300394.SZ"},
    "sz002281": {"name": "光迅科技",        "yahoo": "002281.SZ"},
    # 电力/新能源
    "sh600900": {"name": "长江电力",        "yahoo": "600900.SS"},
    "sh600406": {"name": "国电南瑞",        "yahoo": "600406.SS"},
    "sh601985": {"name": "中国核电",        "yahoo": "601985.SS"},
    # 电池/储能
    "sz300750": {"name": "宁德时代",        "yahoo": "300750.SZ"},
    "sz300014": {"name": "亿纬锂能",        "yahoo": "300014.SZ"},
    "sz002594": {"name": "比亚迪",          "yahoo": "002594.SZ"},
    # 人形机器人
    "sh601689": {"name": "拓普集团",        "yahoo": "601689.SS"},
    "sh688017": {"name": "绿的谐波",        "yahoo": "688017.SS"},
    "sz300124": {"name": "汇川技术",        "yahoo": "300124.SZ"},
    # 世界模型/AI算力
    "hk00020":  {"name": "商汤科技",        "yahoo": "0020.HK"},
    "sh688256": {"name": "寒武纪",          "yahoo": "688256.SS"},
    "sh688111": {"name": "金山办公",        "yahoo": "688111.SS"},
}

# --- 美股关注列表（单独处理，腾讯API用 us 前缀） ---
US_WATCHLIST = {
    "usSNDK":   {"name": "闪迪",    "yahoo": "SNDK"},
    "usNVDA":   {"name": "英伟达",  "yahoo": "NVDA"},
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
        tencent_codes = list(INDEXES.keys()) + list(PORTFOLIO.keys()) + list(WATCHLIST.keys()) + list(US_WATCHLIST.keys())
        yahoo_syms = [v["yahoo"] for v in list(INDEXES.values()) + list(PORTFOLIO.values()) + list(WATCHLIST.values()) + list(US_WATCHLIST.values())]
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

        # --- 关注列表（A股/港股） ---
        print("\n## 👀 关注列表\n")
        print("| 标的 | 现价 | 涨跌幅 | 验证 | 备注 |")
        print("|------|------|--------|------|------|")
        for code_key, info in WATCHLIST.items():
            td = tencent_data.get(code_key, {})
            yp = yahoo_data.get(info["yahoo"], 0)
            tp = td.get("price", 0)
            price, st, note = cross_validate(tp, yp)
            chg = td.get("change_pct", 0)
            sign = "+" if chg >= 0 else ""
            print("| %s | %.2f | %s%.2f%% | %s | %s |" % (
                info["name"], price, sign, chg, status_emoji(st), note))

        # --- 美股关注列表 ---
        for code_key, info in US_WATCHLIST.items():
            td = tencent_data.get(code_key, {})
            yp = yahoo_data.get(info["yahoo"], 0)
            tp = td.get("price", 0)
            price, st, note = cross_validate(tp, yp)
            chg = td.get("change_pct", 0)
            sign = "+" if chg >= 0 else ""
            print("| %s | %.2f | %s%.2f%% | %s | %s |" % (
                info["name"], price, sign, chg, status_emoji(st), note))

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
