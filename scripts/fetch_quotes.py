#!/usr/bin/env python3
"""
实时行情获取工具 — 基于腾讯财经 API
支持 A股、港股、美股 实时行情查询

API: http://qt.gtimg.cn/q={code}
  - A股: sz000021 / sh600809
  - 港股: hk01810
  - 美股: usAAPL
  - 指数: sh000001 / sz399001 / hkHSI
  - 支持批量: 逗号分隔

无需认证，无需 Referer，返回 GBK 编码文本
"""

import sys
import urllib.request

# --- 默认关注列表 ---
PORTFOLIO = {
    "sz000021": "深科技",
    "sz000400": "许继电气",
    "sz002050": "三花智控",
    "sz002156": "通富微电",
    "sh600809": "山西汾酒",
    "hk01810":  "小米集团",
}

INDEXES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "hkHSI":    "恒生指数",
}

# 持仓成本（用于计算盈亏）
COST = {
    "sz000021": 29.21,
    "sz000400": 29.14,
    "sz002050": 42.97,
    "sz002156": 42.59,
    "sh600809": 152.83,
    "hk01810":  32.38,
}


def fetch_quotes(codes):
    """调用腾讯财经 API 获取实时行情原始数据"""
    url = f"http://qt.gtimg.cn/q={','.join(codes)}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("gbk")


def parse_quote(raw_line):
    """解析单条腾讯行情数据，返回结构化字典"""
    raw_line = raw_line.strip().rstrip(";").strip()
    if not raw_line or "=" not in raw_line:
        return None

    var_name, value = raw_line.split("=", 1)
    value = value.strip('"')
    fields = value.split("~")

    if len(fields) < 35:
        return None

    code_key = var_name.replace("v_", "")

    return {
        "code_key": code_key,
        "market": fields[0],       # 1=沪, 51=深, 100=港, 200=美
        "name": fields[1],
        "code": fields[2],
        "price": float(fields[3]) if fields[3] else 0,
        "prev_close": float(fields[4]) if fields[4] else 0,
        "open": float(fields[5]) if fields[5] else 0,
        "change": float(fields[31]) if fields[31] else 0,
        "change_pct": float(fields[32]) if fields[32] else 0,
        "high": float(fields[33]) if fields[33] else 0,
        "low": float(fields[34]) if fields[34] else 0,
        "datetime": fields[30],
    }


def format_pnl(price, cost):
    """格式化盈亏百分比"""
    if cost == 0:
        return "—"
    pnl = (price - cost) / cost * 100
    sign = "+" if pnl >= 0 else ""
    emoji = "🟢" if pnl > 0 else ("🔴" if pnl < -5 else "🟡")
    return f"{emoji} {sign}{pnl:.2f}%"


def main():
    codes = list(sys.argv[1:]) if len(sys.argv) > 1 else []
    show_portfolio = not codes

    if show_portfolio:
        codes = list(INDEXES.keys()) + list(PORTFOLIO.keys())

    raw = fetch_quotes(codes)
    lines = [l.strip() for l in raw.split(";") if l.strip()]

    quotes = []
    for line in lines:
        q = parse_quote(line)
        if q:
            quotes.append(q)

    if not quotes:
        print("⚠️  未获取到数据")
        return

    if show_portfolio:
        # 指数部分
        print("## 📈 市场指数\n")
        print(f"| 指数 | 最新价 | 涨跌 | 涨跌幅 | 最高 | 最低 |")
        print(f"|------|--------|------|--------|------|------|")
        for q in quotes:
            if q["code_key"] in INDEXES:
                sign = "+" if q["change"] >= 0 else ""
                print(f"| {q['name']} | {q['price']:.2f} | {sign}{q['change']:.2f} | {sign}{q['change_pct']:.2f}% | {q['high']:.2f} | {q['low']:.2f} |")
        print()

        # 持仓部分
        print("## 💼 持仓行情\n")
        print(f"| 标的 | 代码 | 最新价 | 涨跌幅 | 成本 | 盈亏 | 最高 | 最低 |")
        print(f"|------|------|--------|--------|------|------|------|------|")
        for q in quotes:
            if q["code_key"] in PORTFOLIO:
                cost = COST.get(q["code_key"], 0)
                pnl = format_pnl(q["price"], cost)
                sign = "+" if q["change_pct"] >= 0 else ""
                print(f"| {q['name']} | {q['code']} | {q['price']:.2f} | {sign}{q['change_pct']:.2f}% | {cost:.2f} | {pnl} | {q['high']:.2f} | {q['low']:.2f} |")
        print(f"\n> 数据时间: {quotes[-1]['datetime']}")
    else:
        # 自定义查询
        for q in quotes:
            cost = COST.get(q["code_key"], 0)
            pnl_str = f" | 盈亏: {format_pnl(q['price'], cost)}" if cost else ""
            sign = "+" if q["change_pct"] >= 0 else ""
            print(f"{q['name']}({q['code']}) 现价: {q['price']:.2f}  {sign}{q['change_pct']:.2f}%{pnl_str}")


if __name__ == "__main__":
    main()
