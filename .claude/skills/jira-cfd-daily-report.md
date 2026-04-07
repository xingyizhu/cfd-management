# Jira CFD 团队每日工时统计与报告

## 用途
统计 Jira 上 CFD 团队全部成员的每日任务、时间追踪与原始预估，按天/周/月/季度维度汇总，并对当天工时不足 7.5 小时的成员发送邮件提醒。

## 执行步骤

### 第一步：获取 Accessible Resources

调用 `mcp__atlassian__getAccessibleAtlassianResources` 获取 cloudId。

### 第二步：通过 Atlassian Teams API 获取 CFD 团队成员

CFD 团队 ID 为 `3fd8537f-41c2-4c8e-b818-1e8cfea9746c`，Org ID 为 `5aka0cj1-0b28-1k26-79a4-15763431dkd2`，cloudId 为 `7cbc3ea4-3d05-4b08-96c2-47981214fbf0`。

**必须通过 Teams API 获取正式成员列表，不能用 project=CFD 的 JQL 推断成员。**

执行以下脚本拉取团队成员并写入 `/tmp/cfd_team_members.json`：

```bash
ATLASSIAN_USER_EMAIL="xingyizhu@ddmarketinghub.com" python3 << 'PYEOF'
import urllib.request, json, os, base64, urllib.error, urllib.parse

api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")
atl_user  = os.environ.get("ATLASSIAN_USER_EMAIL", "")
auth_str  = base64.b64encode(f"{atl_user}:{api_token}".encode()).decode()

TEAM_ID    = "3fd8537f-41c2-4c8e-b818-1e8cfea9746c"
ORG_ID     = "5aka0cj1-0b28-1k26-79a4-15763431dkd2"
CLOUD_URL  = "https://ddmarketinghub.atlassian.net"

# 第一步：通过 Teams API POST 获取成员 accountId 列表
url  = f"https://api.atlassian.com/gateway/api/public/teams/v1/org/{ORG_ID}/teams/{TEAM_ID}/members"
body = json.dumps({"maxResults": 100}).encode()
req  = urllib.request.Request(url, data=body, headers={
    "Authorization": f"Basic {auth_str}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}, method="POST")

try:
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
except urllib.error.HTTPError as e:
    print(json.dumps({"error": f"HTTP {e.code}", "body": e.read().decode()}))
    exit(1)

account_ids = [m.get("accountId") for m in data.get("results", []) if m.get("accountId")]

# 第二步：逐一查询 Jira 用户 API 获取 displayName
members = []
for aid in account_ids:
    api_url = f"{CLOUD_URL}/rest/api/3/user?accountId={urllib.parse.quote(aid)}"
    req2 = urllib.request.Request(api_url, headers={
        "Authorization": f"Basic {auth_str}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req2, timeout=10) as r:
            u = json.loads(r.read())
            members.append({
                "accountId":    aid,
                "displayName":  u.get("displayName", aid),
                "emailAddress": u.get("emailAddress", ""),
                "active":       u.get("active", True),
            })
    except Exception as e:
        members.append({"accountId": aid, "displayName": aid})

with open('/tmp/cfd_team_members.json', 'w') as f:
    json.dump({"members": members}, f, ensure_ascii=False, indent=2)

print(json.dumps({"member_count": len(members), "members": members}, ensure_ascii=False, indent=2))
PYEOF
```

### 第三步：确定统计时间范围

根据用户调用时的参数（或默认今天）确定以下维度的时间范围：
- **天**：当天（中国工作日）
- **周**：本周一到今天（跳过周末和节假日）
- **月**：本月1日到今天
- **季度**：本季度第1天到今天

**中国法定节假日判断**：执行以下 Bash 命令获取节假日列表：

```bash
python3 << 'PYEOF'
import urllib.request, json, datetime

year = datetime.date.today().year
try:
    url = f'https://date.nager.at/api/v3/PublicHolidays/{year}/CN'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as r:
        holidays = [h['date'] for h in json.loads(r.read())]
    print(json.dumps(holidays))
except Exception as e:
    # 兜底硬编码 2026 年中国法定节假日（根据国务院通知）
    hardcoded = [
        '2026-01-01',
        '2026-02-17','2026-02-18','2026-02-19','2026-02-20',
        '2026-02-21','2026-02-22','2026-02-23',
        '2026-04-05','2026-04-06','2026-04-07',
        '2026-05-01','2026-05-02','2026-05-03','2026-05-04','2026-05-05',
        '2026-05-31','2026-06-01','2026-06-02',
        '2026-10-01','2026-10-02','2026-10-03',
        '2026-10-04','2026-10-05','2026-10-06','2026-10-07',
    ]
    print(json.dumps(list(set(hardcoded))))
PYEOF
```

### 第四步：检查 Supabase 缓存

在查询 Jira 之前，先检查数据库中是否已有当前统计周期的数据。若已存在，跳过第五步（Jira 查询），直接进入第六步展示。

```bash
python3 << 'PYEOF'
import urllib.request, json, os
from datetime import date, timedelta

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://onsxzhkogrzdwqftqsea.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9uc3h6aGtvZ3J6ZHdxZnRxc2VhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUyODcyMjcsImV4cCI6MjA5MDg2MzIyN30.cypeq-AoPKA1ngdnGq2HX9lYE5KmBz5ZdO4ZMlCQB0M")

HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Accept": "application/json"}

today = date.today().isoformat()
d     = date.today()
week  = (d - timedelta(days=d.weekday())).isoformat()
qkey  = f"{d.year}-Q{(d.month-1)//3+1}"

def query(table, filter_param):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filter_param}&limit=1"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

results = {}
try:
    results['daily']     = len(query("worklog_daily",     f"work_date=eq.{today}")) > 0
    results['weekly']    = len(query("worklog_weekly",    f"week_start=eq.{week}")) > 0
    results['quarterly'] = len(query("worklog_quarterly", f"quarter_key=eq.{qkey}")) > 0
except Exception as e:
    results = {'daily': False, 'weekly': False, 'quarterly': False, 'error': str(e)}

print(json.dumps(results))
PYEOF
```

**判断逻辑**：
- 若 `daily == true`（今日数据已存在）→ **跳过第五步**，直接执行第六步从数据库读取展示
- 若 `daily == false` → 继续执行第五步从 Jira 拉取并入库

### 第五步：查询 Jira 并写入数据库（仅缓存未命中时执行）

**若第四步判断今日数据已存在，跳过本步直接到第六步。**

使用以下 JQL 获取目标时间范围内所有含 worklog 的 Issue（范围取本季度第1天到今天，覆盖日/周/季度三个维度）：

```jql
worklogAuthor in ({comma_separated_accountIds}) AND worklogDate >= "{quarterStart}" AND worklogDate <= "{today}"
```

通过 `mcp__atlassian__searchJiraIssuesUsingJql` 获取，fields 参数包含：
```
["summary", "status", "issuetype", "assignee", "timespent", "timeoriginalestimate", "worklog"]
```

**注意**：若 issue 的 worklog 超过 20 条，需使用 `mcp__atlassian__getJiraIssue` 单独获取并分页（worklog startAt 递增）。

获取后执行以下脚本完成**聚合 + 写入 Supabase**（脚本同原第五步，见下方）：

```bash
python3 << 'PYEOF'
import json, urllib.request, urllib.error, os
from datetime import datetime, date, timedelta, timezone
from collections import defaultdict

with open('/tmp/cfd_jira_data.json', 'r') as f:
    data = json.load(f)

issues       = data.get('issues', [])
member_ids   = set(data.get('member_ids', []))
holidays     = set(data.get('chinese_holidays', []))
target_date  = date.fromisoformat(data.get('target_date', date.today().isoformat()))
daily_target = data.get('daily_target_hours', 7.5)

def s2h(seconds): return round((seconds or 0) / 3600, 2)
def week_start(d): return (d - timedelta(days=d.weekday())).isoformat()
def quarter(d): return f"{d.year}-Q{(d.month-1)//3+1}"
def is_workday(d_str):
    d = date.fromisoformat(d_str)
    return d.weekday() < 5 and d_str not in holidays

dims  = ['daily', 'weekly', 'quarterly']
stats = {dim: defaultdict(lambda: defaultdict(
    lambda: {'logged': 0, 'estimated': 0, 'issues': set(), 'name': '', 'counted': []}
)) for dim in dims}

for issue in issues:
    key      = issue['key']
    fields   = issue.get('fields', {})
    orig_est = fields.get('timeoriginalestimate', 0) or 0
    worklogs = fields.get('worklog', {}).get('worklogs', [])
    for wl in worklogs:
        author = wl.get('author', {})
        aid    = author.get('accountId', '')
        if aid not in member_ids:
            continue
        started = wl.get('started', '')[:10]
        if not is_workday(started):
            continue
        ts    = wl.get('timeSpentSeconds', 0)
        name  = author.get('displayName', aid)
        d_obj = date.fromisoformat(started)
        for dim, pk in {'daily': started, 'weekly': week_start(d_obj), 'quarterly': quarter(d_obj)}.items():
            s = stats[dim][aid][pk]
            s['logged'] += ts
            s['name']    = name
            s['issues'].add(key)
            if dim == 'daily' and key not in s['counted']:
                s['estimated'] += orig_est
                s['counted'].append(key)

today_str    = target_date.isoformat()
under_logged = []
for aid, periods in stats['daily'].items():
    if today_str in periods:
        s  = periods[today_str]
        lh = s2h(s['logged'])
        if lh < daily_target:
            under_logged.append({'accountId': aid, 'name': s['name'], 'logged_hours': lh})
with open('/tmp/cfd_under_logged.json', 'w') as f:
    json.dump({'under_logged': under_logged, 'target_date': today_str, 'daily_target': daily_target}, f, ensure_ascii=False)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://onsxzhkogrzdwqftqsea.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9uc3h6aGtvZ3J6ZHdxZnRxc2VhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUyODcyMjcsImV4cCI6MjA5MDg2MzIyN30.cypeq-AoPKA1ngdnGq2HX9lYE5KmBz5ZdO4ZMlCQB0M")
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
           "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"}
now_ts = datetime.now(timezone.utc).isoformat()

def upsert_batch(table, rows):
    if not rows: return 0
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{table}",
        data=json.dumps(rows, ensure_ascii=False).encode(), headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15): pass
        return len(rows)
    except urllib.error.HTTPError as e:
        print(f"  ❌ {table}: {e.status} {e.read().decode()[:200]}")
        return 0

n1 = upsert_batch("worklog_daily", [
    {"account_id": aid, "display_name": s['name'], "work_date": pk,
     "logged_sec": s['logged'], "estimated_sec": s['estimated'],
     "issue_count": len(s['issues']), "issue_keys": list(s['issues']), "updated_at": now_ts}
    for aid, periods in stats['daily'].items() for pk, s in periods.items()])
n2 = upsert_batch("worklog_weekly", [
    {"account_id": aid, "display_name": s['name'], "week_start": pk,
     "logged_sec": s['logged'], "estimated_sec": s['estimated'],
     "issue_count": len(s['issues']), "issue_keys": list(s['issues']), "updated_at": now_ts}
    for aid, periods in stats['weekly'].items() for pk, s in periods.items()])
n3 = upsert_batch("worklog_quarterly", [
    {"account_id": aid, "display_name": s['name'], "quarter_key": pk,
     "logged_sec": s['logged'], "estimated_sec": s['estimated'],
     "issue_count": len(s['issues']), "issue_keys": list(s['issues']), "updated_at": now_ts}
    for aid, periods in stats['quarterly'].items() for pk, s in periods.items()])

print(f"✅ 写入 Supabase：daily={n1}条，weekly={n2}条，quarterly={n3}条")
PYEOF
```

### 第六步：从数据库读取并展示报告（缓存命中或入库后均执行）

**无论第四步缓存命中还是第五步入库后，都执行此步从 Supabase 读取并输出报告。**

```bash
python3 << 'PYEOF'
import urllib.request, json, os
from datetime import date, timedelta

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://onsxzhkogrzdwqftqsea.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9uc3h6aGtvZ3J6ZHdxZnRxc2VhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUyODcyMjcsImV4cCI6MjA5MDg2MzIyN30.cypeq-AoPKA1ngdnGq2HX9lYE5KmBz5ZdO4ZMlCQB0M")
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Accept": "application/json"}

d     = date.today()
today = d.isoformat()
week  = (d - timedelta(days=d.weekday())).isoformat()
qkey  = f"{d.year}-Q{(d.month-1)//3+1}"
DAILY_TARGET = 7.5

def fetch(table, param):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{param}&order=display_name"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def s2h(sec): return round((sec or 0) / 3600, 2)

daily_rows     = fetch("worklog_daily",     f"work_date=eq.{today}")
weekly_rows    = fetch("worklog_weekly",    f"week_start=eq.{week}")
quarterly_rows = fetch("worklog_quarterly", f"quarter_key=eq.{qkey}")

under_logged = [r for r in daily_rows if s2h(r['logged_sec']) < DAILY_TARGET]

print(f"# CFD 团队工时统计报告（来源：数据库缓存）")
print(f"统计日期：{today}  |  本周：{week} 起  |  本季度：{qkey}\n")

print("## 今日（日维度）")
if daily_rows:
    print("| 成员 | 已记录(h) | 预估(h) | Issue数 | 状态 |")
    print("|------|:--------:|:------:|:------:|------|")
    for r in daily_rows:
        lh = s2h(r['logged_sec'])
        ok = lh >= DAILY_TARGET
        print(f"| {r['display_name']} | {lh} | {s2h(r['estimated_sec'])} | {r['issue_count']} | {'✅ 达标' if ok else '⚠️ 不足'} |")
else:
    print("今日暂无工时记录。")

print("\n## 本周（周维度）")
if weekly_rows:
    print("| 成员 | 已记录(h) | 预估(h) | Issue数 |")
    print("|------|:--------:|:------:|:------:|")
    for r in weekly_rows:
        print(f"| {r['display_name']} | {s2h(r['logged_sec'])} | {s2h(r['estimated_sec'])} | {r['issue_count']} |")
else:
    print("本周暂无数据。")

print(f"\n## 本季度（{qkey}）")
if quarterly_rows:
    print("| 成员 | 已记录(h) | 预估(h) | Issue数 |")
    print("|------|:--------:|:------:|:------:|")
    for r in quarterly_rows:
        print(f"| {r['display_name']} | {s2h(r['logged_sec'])} | {s2h(r['estimated_sec'])} | {r['issue_count']} |")
else:
    print("本季度暂无数据。")

# 写出今日不足名单供邮件步骤使用
with open('/tmp/cfd_under_logged.json', 'w') as f:
    json.dump({'under_logged': [{'accountId': r['account_id'], 'name': r['display_name'],
        'logged_hours': s2h(r['logged_sec'])} for r in under_logged],
        'target_date': today, 'daily_target': DAILY_TARGET}, f, ensure_ascii=False)

if under_logged:
    print(f"\n⚠️ 今日工时不足 {DAILY_TARGET}h 的成员（共 {len(under_logged)} 人）：")
    for r in under_logged:
        lh = s2h(r['logged_sec'])
        print(f"  - {r['display_name']}：{lh}h，差 {round(DAILY_TARGET - lh, 2)}h")
else:
    print("\n✅ 今日所有有记录成员工时均达标")
PYEOF
```

### 第七步：对今日工时不足 7.5 小时的成员发送邮件

读取上一步生成的 `/tmp/cfd_under_logged.json`，结合用户提供的 SMTP 配置和邮箱映射，发送提醒邮件：

```bash
python3 << 'PYEOF'
import smtplib, json, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 读取配置（从环境变量或 /tmp/cfd_smtp_config.json）
with open('/tmp/cfd_under_logged.json') as f:
    payload = json.load(f)

# SMTP 配置从 /tmp/cfd_smtp_config.json 读取
with open('/tmp/cfd_smtp_config.json') as f:
    cfg = json.load(f)

smtp_host   = cfg['host']
smtp_port   = int(cfg['port'])
smtp_user   = cfg['user']
smtp_pass   = cfg['password']
sender      = cfg.get('sender', smtp_user)
email_map   = cfg.get('member_email_map', {})  # accountId -> email
email_domain = cfg.get('email_domain', '')

under_logged = payload['under_logged']
target_date  = payload['target_date']
daily_target = payload.get('daily_target', 7.5)

sent, skipped = [], []

for member in under_logged:
    name  = member['name']
    aid   = member['accountId']
    lh    = member['logged_hours']
    diff  = round(daily_target - lh, 2)

    email = email_map.get(aid)
    if not email:
        skipped.append(f"{name}（无邮箱映射）")
        continue

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'【工时提醒】{target_date} 工时记录不足提醒'
    msg['From']    = sender
    msg['To']      = email

    text = f"""Hi {name}，

系统检测到您今天（{target_date}）在 Jira 中的工时记录为 {lh} 小时，
距离标准工时 {daily_target} 小时还差 {diff} 小时。

请及时在 Jira 中补充今日的工作记录，以确保项目进度统计的准确性。

此邮件由系统自动发送，请勿回复。
CFD 团队管理系统"""

    html = f"""<html><body>
<p>Hi <strong>{name}</strong>，</p>
<p>系统检测到您今天（<strong>{target_date}</strong>）在 Jira 中的工时记录为
<strong>{lh} 小时</strong>，距离标准工时 {daily_target} 小时还差
<strong style="color:red">{diff} 小时</strong>。</p>
<p>请及时在 Jira 中补充今日的工作记录，以确保项目进度统计的准确性。</p>
<br><p style="color:gray;font-size:12px">此邮件由系统自动发送，请勿回复。<br>CFD 团队管理系统</p>
</body></html>"""

    msg.attach(MIMEText(text, 'plain', 'utf-8'))
    msg.attach(MIMEText(html,  'html',  'utf-8'))

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as srv:
                srv.login(smtp_user, smtp_pass)
                srv.sendmail(sender, [email], msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as srv:
                srv.starttls()
                srv.login(smtp_user, smtp_pass)
                srv.sendmail(sender, [email], msg.as_string())
        print(f"  ✅ 已发送至 {name} <{email}>")
        sent.append(name)
    except Exception as e:
        print(f"  ❌ 发送失败 {name} <{email}>: {e}")
        skipped.append(f"{name}（发送失败: {e}）")

print(f"\n邮件发送完成：成功 {len(sent)} 封，跳过 {len(skipped)} 封")
if skipped:
    print("跳过详情：" + "、".join(skipped))
PYEOF
```

**SMTP 配置文件格式** `/tmp/cfd_smtp_config.json`：
```json
{
  "host": "smtp.exmail.qq.com",
  "port": 465,
  "user": "notify@yourcompany.com",
  "password": "your_auth_code",
  "sender": "CFD工时系统 <notify@yourcompany.com>",
  "email_domain": "@yourcompany.com",
  "member_email_map": {
    "accountId_001": "zhangsan@yourcompany.com",
    "accountId_002": "lisi@yourcompany.com"
  }
}
```

### 第八步：汇总输出

在对话中输出完整报告 + 是否命中缓存 + 邮件发送结果摘要 + WebUI 访问地址（http://localhost:3399）。

---

## 配置说明

首次使用前，请确认以下信息：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `CFD_PROJECT_KEY` | Jira 项目 Key | `CFD` |
| `SMTP_HOST` | 邮件服务器地址 | `smtp.exmail.qq.com` |
| `SMTP_PORT` | 端口 | `465`（SSL）或 `587`（TLS） |
| `SMTP_USER` | 发件账号 | `notify@company.com` |
| `SMTP_PASSWORD` | 邮箱授权码 | 运行时输入 |
| `MEMBER_EMAIL_MAP` | accountId → 邮箱 | JSON 映射 |
| `DAILY_TARGET_HOURS` | 日工时目标 | `7.5` |

---

## 调用示例

```
/jira-cfd-daily-report
/jira-cfd-daily-report date=2026-04-03
/jira-cfd-daily-report date=2026-04-03 no-email
/jira-cfd-daily-report week-only
/jira-cfd-daily-report month-only
```

参数说明：
- `date=YYYY-MM-DD`：指定统计日期（默认今天）
- `no-email`：只生成报告，不发送邮件
- `week-only` / `month-only` / `quarter-only`：只输出指定维度

---

## 注意事项

1. **工作日判断**：使用中国官方节假日。调休补班日（如春节前后的周六）需在配置中添加到 `EXTRA_WORKDAYS` 列表。
2. **Worklog 分页**：Jira API 每次最多返回 20 条 worklog。若 issue worklog 超出，需使用 `getJiraIssue` 单独分页获取（`worklog.startAt` 递增直到 `worklog.total`）。
3. **邮箱获取**：Jira `accountId` 不直接暴露邮箱，需预先维护 `member_email_map`，或通过公司 AD/HR 系统同步。
4. **时区处理**：Jira worklog `started` 字段含时区偏移（如 `+0800`），统计时取日期部分即可，无需额外转换。
5. **权限要求**：执行账号需有 CFD 项目的 Browse Issues 权限及 Worklog 读取权限。
6. **定时执行**：建议配合 `cron` 或公司 CI/CD 在每天 18:00（北京时间）自动触发：
   ```cron
   0 10 * * 1-5 claude -p "/jira-cfd-daily-report" --no-email=false
   ```
