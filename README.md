# CFD 团队工时统计系统

统计 Jira CFD 项目全体成员的每日工时，按日/周/季度维度汇总，缓存至 Supabase，对当日工时不足 7.5h 的成员发送邮件提醒；Web UI 同时提供任务估时看板。

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入真实配置

# 3a. CLI 模式
python main.py --no-email

# 3b. Web UI 模式
streamlit run app.py
# 访问 http://localhost:8501
```

## CLI 参数

| 参数 | 说明 |
|------|------|
| `--date YYYY-MM-DD` | 指定统计日期（默认今天） |
| `--no-email` | 只生成报告，不发送邮件 |
| `--week-only` | 只输出本周维度 |
| `--quarter-only` | 只输出本季度维度 |

## 配置说明

详见 `.env.example` 和 `CLAUDE.md`。Web UI 默认使用极速读取模式（`WEBUI_AUTO_SYNC_ON_QUERY=false`），仅在勾选“强制重新拉取 Jira”后刷新时回源 Jira。

## 技术栈

- Python 3.10+
- Atlassian REST API v3 / Teams API
- Supabase (PostgreSQL)
- Streamlit（Web UI）
- SMTP（邮件提醒）

## Web UI Task Estimate Board

- 任务估时看板整合为一个模块，可在“无预估任务”和“高预估任务”视图之间切换。
- `Issue` 列支持直接跳转到 Jira 详情页（`{ATLASSIAN_CLOUD_URL}/browse/{issue_key}`）。
