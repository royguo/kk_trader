# 工具脚本

> 存放数据获取、分析辅助、自动化等 Python/Shell 脚本。

## 已完成脚本

| 脚本 | 用途 | 状态 |
|------|------|------|
| `fetch_quotes.py` | 实时行情获取（A股/港股/美股） | ✅ 可用 |

### fetch_quotes.py

基于腾讯财经 API，获取实时行情数据。

```bash
python3 scripts/fetch_quotes.py                # 查询全部持仓 + 指数
python3 scripts/fetch_quotes.py usAAPL usNVDA   # 自定义查询美股
python3 scripts/fetch_quotes.py hk00700 hk09988  # 自定义查询港股
```

无外部依赖，仅使用 Python 标准库。

## 规划中的脚本

| 脚本 | 用途 | 状态 |
|------|------|------|
| `portfolio_report.py` | 生成持仓报告 | 🔲 待开发 |
| `backtest.py` | 策略回测工具 | 🔲 待开发 |

---

*脚本将根据实际需求逐步开发*
