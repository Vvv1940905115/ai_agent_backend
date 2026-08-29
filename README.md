# AI Agent 业务后端系统（安装与配置教程）

面向企业业务场景的**可扩展 AI Agent 后端**：通用工具调用框架 + 多平台集成（飞书 / 企业微信 / 多维表格）+ 多模型（豆包 / DeepSeek / 通义千问）+ 短视频分析 + GEO 地理 Agent + 向量知识库，提供 FastAPI 接口、零依赖 Web 控制台，以及 Docker 一键部署。

> 本文档重点说明「怎么把项目跑起来 + 怎么配密钥」。所有命令均已按 Windows / macOS / Linux 分别给出，照着一步一步做即可。

---

## 目录

- [一、环境要求](#一环境要求)
- [二、快速开始（三种方式任选）](#二快速开始三种方式任选)
  - [方式 A：本地 Python 虚拟环境（推荐开发/调试）](#方式-a本地-python-虚拟环境推荐开发调试)
  - [方式 B：Docker Compose（推荐生产 / 一键部署）](#方式-bdocker-compose推荐生产--一键部署)
  - [方式 C：Docker 手动构建运行](#方式-cdocker-手动构建运行)
- [三、配置文件 `.env` 完整说明](#三配置文件-env-完整说明)
- [四、启动后验证](#四启动后验证)
- [五、Web 控制台使用（含「每人自带 API 配置」）](#五web-控制台使用含每人自带-api-配置)
- [六、接口调用示例（curl）](#六接口调用示例curl)
- [七、运行测试](#七运行测试)
- [八、知识库命令行入库（CLI）](#八知识库命令行入库cli)
- [九、生产部署补充（Nginx 反向代理）](#九生产部署补充nginx-反向代理)
- [十、常见问题与排错](#十常见问题与排错)
- [十一、系统架构](#十一系统架构)
- [十二、项目目录结构](#十二项目目录结构)

---

## 一、环境要求

| 项目 | 要求 | 说明 |
|---|---|---|
| Python | **3.10 及以上**（已在 3.11 / 3.13 验证） | 依赖 `numpy==2.1.3`、`pydantic>=2.7` 等需要较新版本；3.13 用户请使用带 `cp313` 预编译包的版本 |
| pip | 最新版 | 建议先 `python -m pip install -U pip` |
| Git | 任意较新版本 | 用于拉取代码、提交 |
| Docker（可选） | 20.10+ / Docker Compose v2 | 仅当你想用容器部署时需要 |
| 网络 | 访问大模型 API 的网络 | 选题 / Agent / 短视频分析需联网调用大模型；知识库检索可用 `local` 模式离线验证 |

> **国内网络提示**：`pip install` 若速度慢或超时，可全程加 `-i https://pypi.tuna.tsinghua.edu.cn/simple` 使用清华镜像（下文命令已内置该选项）。

---

## 二、快速开始（三种方式任选）

> 三种方式最终效果完全一致：服务监听 `0.0.0.0:8000`，提供 `/`（Web 控制台）、`/docs`（Swagger）、`/api/*`、`/health`。

### 方式 A：本地 Python 虚拟环境（推荐开发/调试）

**第 1 步：获取代码**

```bash
git clone <你的仓库地址> ai_agent_backend
cd ai_agent_backend
```

**第 2 步：创建并激活虚拟环境**

- Windows（PowerShell / CMD）：
  ```bash
  python -m venv .venv
  .venv\Scripts\activate
  ```
- macOS / Linux：
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

> 激活后命令行前面会出现 `(.venv)` 前缀，表示后续命令都装在隔离环境里，不会污染系统 Python。

**第 3 步：安装依赖**

```bash
python -m pip install -U pip
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> 依赖清单见 `requirements.txt`：fastapi、uvicorn、openai、httpx、beautifulsoup4、numpy、tenacity、python-dotenv、pytest 等。
> 若安装 `numpy`/`pydantic` 报「找不到预编译包」，说明 Python 版本过旧，请升级到 3.11+。

**第 4 步：准备配置文件 `.env`**

项目根目录已提供模板 `.env.example`，复制为 `.env` 后填入你自己的密钥：

```bash
# Windows（PowerShell / CMD）：
copy .env.example .env

# macOS / Linux：
cp .env.example .env
```

然后用编辑器（VS Code / 记事本 / `vim`）打开 `.env` 填值。最少只需：
- 填一个 LLM 密钥（DeepSeek / 豆包 / 通义任一个），否则选题、Agent、短视频分析无法运行；
- 知识库可用 `EMBEDDING_PROVIDER=local`（默认即是）**免密钥**先跑通离线链路；
- 视频生成可用 `VIDEO_GEN_PROVIDER=mock`（默认即是）**免密钥**跑通全链路。

> `.env` 已在 `.gitignore` 中，**不会被提交**，可放心填真实密钥。

**第 5 步：启动服务**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- `--reload`：代码改动自动重启，仅用于开发；生产部署去掉该参数。
- 看到日志打印 `Uvicorn running on http://0.0.0.0:8000` 即启动成功。

**第 6 步：打开浏览器验证**

- Web 控制台：`http://localhost:8000/`
- 接口文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

---

### 方式 B：Docker Compose（推荐生产 / 一键部署）

**第 1 步：准备 `.env`**

```bash
cp .env.example .env      # 然后编辑填入真实密钥
vim .env                  # 或直接用编辑器打开
```

**第 2 步：构建并后台启动**

```bash
docker compose up -d --build
```

**第 3 步：验证**

```bash
curl http://localhost:8000/health
# 期望返回：{"code":0,"status":"ok","service":"ai-agent-backend"}
```

> 容器已配置健康检查（`HEALTHCHECK`），可用 `docker ps` 查看 `STATUS` 是否为 `healthy`。
> 向量库 `./data/vector_store` 与 `./logs` 已挂载为卷，容器重建不丢数据。

常用命令：

```bash
docker compose logs -f web          # 实时查看日志
docker compose down                # 停止并删除容器（数据卷保留）
docker compose restart web          # 重启服务
```

---

### 方式 C：Docker 手动构建运行

```bash
# 1. 准备 .env
cp .env.example .env && vim .env

# 2. 构建镜像
docker build -t ai-agent-backend:1.0.0 .

# 3. 运行容器（把 .env 与持久化目录挂进去）
docker run -d --name ai-agent-backend \
  -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/data/vector_store:/app/data/vector_store" \
  -v "$(pwd)/logs:/app/logs" \
  --restart unless-stopped \
  ai-agent-backend:1.0.0

# 4. 验证
curl http://localhost:8000/health
```

> `Dockerfile` 基于 `python:3.11-slim`，内置清华 PyPI 源加速、以非 root 用户 `appuser` 运行、暴露 8000 端口。

---

## 三、配置文件 `.env` 完整说明

所有变量均由 `app/core/config.py` 通过 `pydantic-settings` 读取。**未填写的可选项留空即可**，程序会走默认值或给出明确报错。

### 3.1 服务基础

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_NAME` | `ai-agent-backend` | 服务名，仅用于日志/接口标题 |
| `HOST` | `0.0.0.0` | 监听地址，容器/服务器部署保持默认 |
| `PORT` | `8000` | 监听端口 |
| `LOG_LEVEL` | `INFO` | 日志级别：`DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `REQUEST_TIMEOUT` | `30` | 单次请求超时（秒） |

### 3.2 大模型（LLM，OpenAI 兼容接口）

这是**最核心**的配置。三选一作为全局默认模型；也可以不填，在 Web 控制台里给**每个使用者单独配置**（见第五章）。

| 变量 | 默认值 | 说明 / 申请地址 |
|---|---|---|
| `LLM_PROVIDER` | `deepseek` | 当前全局模型：`doubao` / `deepseek` / `qwen` |
| `LLM_MODEL` | `deepseek-chat` | 未单独指定各供应商模型时生效的兜底模型名 |
| `DEEPSEEK_API_KEY` | 空 | DeepSeek 密钥。申请：https://platform.deepseek.com → API keys |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v3` | DeepSeek 兼容接口地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek 模型名 |
| `DOUBAO_API_KEY` | 空 | 豆包（火山方舟）密钥。申请：https://console.volcengine.com/ark → 创建推理接入点 |
| `DOUBAO_BASE_URL` | `https://ark.cn-beijing.volces.com/api/v3` | 火山方舟兼容接口地址 |
| `DOUBAO_MODEL` | `ep-xxxxxxxx` | 火山方舟「推理接入点 ID」（非模型名，形如 `ep-xxxxxx`） |
| `QWEN_API_KEY` | 空 | 通义千问密钥。申请：https://dashscope.aliyun.com → API 密钥 |
| `QWEN_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | DashScope 兼容模式地址 |
| `QWEN_MODEL` | `qwen-plus` | 通义千问模型名 |

> **最简配置**：把 `LLM_PROVIDER` 设成你有的那家，并填对应 `XXX_API_KEY` 即可；其余两家留空不影响。

### 3.3 外部平台集成（飞书 / 企业微信 / 多维表格）

这些**全部可选**，不填则对应推送/落库功能不可用，但其他功能照常。

| 变量 | 用途 | 申请位置 |
|---|---|---|
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书自建应用鉴权 | 飞书开放平台 → 创建企业自建应用 |
| `FEISHU_BOT_WEBHOOK` | 飞书群机器人推送（免鉴权） | 飞书群 → 设置 → 群机器人 → 添加 Webhook |
| `WECOM_CORPID` / `WECOM_CORPSECRET` / `WECOM_AGENT_ID` | 企业微信自建应用 | 企业微信管理后台 → 应用管理 |
| `BITABLE_APP_TOKEN` / `BITABLE_TABLE_ID` | 多维表格读写 | 飞书多维表格 URL 中提取（链接里的 `base/xxx` 与表格 `tblxxx`） |

### 3.4 向量知识库

| 变量 | 默认值 | 说明 |
|---|---|---|
| `EMBEDDING_PROVIDER` | `local` | 向量化来源：`qwen` / `doubao` / `local`（本地兜底，**无需网络/密钥**，仅用于联调） |
| `EMBEDDING_DIM` | `256` | 本地 embedding 维度（用云端 embedding 时以实际模型维度为准） |
| `VECTOR_DB_PATH` | `./data/vector_store` | 向量库存放目录，Docker 已挂卷持久化 |

> 想完全离线体验？保持 `EMBEDDING_PROVIDER=local` 即可，知识库检索、入库都能跑。

### 3.5 抓取策略（反爬友好）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SCRAPE_RATE_LIMIT` | `1.0` | 抓取网页时相邻请求最小间隔（秒） |
| `USER_AGENT` | `Mozilla/5.0 (compatible; AIgentBot/1.0; ...)` | 抓取时使用的 UA |

### 3.6 AI 选题

| 变量 | 默认值 | 说明 |
|---|---|---|
| `TOPIC_DEFAULT_COUNT` | `5` | 默认生成数量（接口可覆盖） |
| `TOPIC_DEFAULT_STYLE` | `科普` | 默认风格（接口可覆盖） |
| `TOPIC_DEDUPE_THRESHOLD` | `0.7` | 选题去重相似度阈值（0–1，越高越严格） |

### 3.7 文生视频 / 图生视频（异步任务）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `VIDEO_GEN_PROVIDER` | `mock` | `mock`（默认，**离线联调无需密钥**） / `generic`（对接你的第三方 HTTP API） |
| `VIDEO_GEN_API_URL` | 空 | generic 模式填第三方文生视频 API 地址 |
| `VIDEO_GEN_API_KEY` | 空 | generic 模式填第三方密钥 |
| `VIDEO_GEN_POLL_INTERVAL` | `5` | 后台轮询间隔（秒） |
| `VIDEO_GEN_TASK_TIMEOUT` | `600` | 单任务超时（秒），超时标记 `timeout` |
| `VIDEO_GEN_MAX_RETRIES` | `3` | 限流/可重试错误最大重试次数（指数退避） |
| `VIDEO_GEN_MOCK_DELAY` | `2` | mock 模式模拟生成耗时（秒） |
| `WECOM_NOTIFY_USER` | `@all` | 任务状态变更通知的企微接收人（`@all` 或具体 userid） |

### 3.8 配置完成后自检清单

- [ ] 已复制出 `.env`（不是改 `.env.example`）
- [ ] 至少填了**一个** `XXX_API_KEY`，且 `LLM_PROVIDER` 与之对应
- [ ] 知识库用 `local`、视频用 `mock` 可先零密钥联调
- [ ] 飞书/企微/多维表格如暂不用，对应项保持空

---

## 四、启动后验证

服务起来后，先确认健康接口：

```bash
curl http://localhost:8000/health
# {"code":0,"status":"ok","service":"ai-agent-backend"}
```

再打开浏览器：

- `http://localhost:8000/` → Web 控制台（推荐，点几下就能用）
- `http://localhost:8000/docs` → Swagger 接口调试页（可直接在线试每个接口）

---

## 五、Web 控制台使用（含「每人自带 API 配置」）

服务启动后，浏览器访问 `http://localhost:8000/` 即用，**无需命令行**。控制台覆盖全部能力：

| 模块 | 功能 |
|---|---|
| 选题中心 | 按行业/风格/数量生成选题，展示质量分、等级、排名；勾选或按 `top_n` 一键审核优选 |
| 视频生成 | 提交文生视频任务，按 `task_id` 查询进度或自动轮询 |
| 知识库 | 检索 / 导入文档片段 |
| Agent | 运行 short_video / geo / topic / video_pipeline 四类智能体 |
| 短视频解析 | 输入链接或文案，分析结构、钩子与可复用要素 |

### 重点特性：每人自带 API 配置

不想依赖全局 `.env` 的密钥？点右上角 **⚙ API 配置**：

1. 选择服务商（DeepSeek / 豆包 / 通义 / 自定义 OpenAI 兼容）；
2. 填写模型名与 API Key（选「自定义」时需填 Base URL）；
3. 可选：高级里单独配置云端向量（embedding）密钥；
4. 点「保存」——配置仅存本机浏览器 `localStorage`，**每次请求自动携带**；
5. 顶部状态会从红点「未配置模型」变为绿点「模型：xxx / 模型名」。

多人共用同一控制台时，各人填各人的 Key，互不干扰；清空即回落到服务端全局 `.env` 配置。填错 Key 时接口会返回清晰中文提示（如「API Key 无效或已过期」），不会抛出原始堆栈。

---

## 六、接口调用示例（curl）

> 以下示例默认服务在 `http://localhost:8000`。需要 LLM 的接口请确保已配置对应密钥。

**健康检查**
```bash
curl http://localhost:8000/health
```

**AI 选题生成（自动去重 / 打分 / 排序）**
```bash
curl -X POST http://localhost:8000/api/topic/generate \
  -H 'Content-Type: application/json' \
  -d '{"industry":"美妆","style":"科普","count":5,"use_knowledge":false}'
```

**选题审核优选（取排名前 3）**
```bash
curl -X POST http://localhost:8000/api/topic/approve \
  -H 'Content-Type: application/json' \
  -d '{"batch_id":"batch_xxxx","top_n":3}'
```

**知识库入库（免密钥，local embedding）**
```bash
curl -X POST http://localhost:8000/api/knowledge/ingest \
  -H 'Content-Type: application/json' \
  -d '{"text":"年假政策：入职满一年享5天年假。","source":"hr"}'
```

**知识库检索**
```bash
curl -X POST http://localhost:8000/api/knowledge/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"年假几天","top_k":1}'
```

**GEO 距离（自然语言，走 Geo Agent，需 LLM 密钥）**
```bash
curl -X POST http://localhost:8000/api/geo/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"北京到上海的直线距离是多少公里？"}'
```

**短视频纯文本分析（无需抓取）**
```bash
curl -X POST http://localhost:8000/api/short-video/analyze-text \
  -H 'Content-Type: application/json' \
  -d '{"title":"3分钟学会AI剪辑","text":"本期分享用AE自动生成字幕的技巧..."}'
```

**运行短视频分析 Agent（含推送/落库工具，需对应密钥）**
```bash
curl -X POST http://localhost:8000/api/agent/run \
  -H 'Content-Type: application/json' \
  -d '{"agent_type":"short_video","user_input":"分析这条文案并推送给运营群：用AI做短视频太香了"}'
```

**视频生成（mock 模式免密钥）**
```bash
# 1) 提交任务，立即返回 task_id
curl -X POST http://localhost:8000/api/video/submit \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"科技感产品宣传片，蓝色调，15秒","duration":5,"resolution":"1280x720","style":"cinematic"}'

# 2) 按返回的 task_id 查询进度
curl http://localhost:8000/api/video/status/{video_task_id}
```

**全链路（参考短视频 → 生成选题 → 提交视频生成）**
```bash
curl -X POST http://localhost:8000/api/pipeline/topic-to-video \
  -H 'Content-Type: application/json' \
  -d '{"video_url":"<公开分享链接>","industry":"美妆","style":"科普","count":3,"write_to_bitable":true,"notify":true}'
```

---

## 七、运行测试

项目内置 pytest 用例（覆盖接口、视频异步链路、选题质量增强）。**无需任何密钥**即可跑通（知识库用 local embedding、视频用 mock）：

```bash
# 激活虚拟环境后
pytest -q
```

若用 Docker，在容器内执行：
```bash
docker compose exec web pytest -q
```

---

## 八、知识库命令行入库（CLI）

除了 Web 控制台和接口，还可用脚本批量入库：

```bash
# 直接传文本
python scripts/ingest.py --text "企业知识文本..."

# 从文件读取
python scripts/ingest.py --file ./docs/policy.txt --source 政策文档
```

依赖 `EMBEDDING_PROVIDER`（设 `local` 则免密钥联调）。

---

## 九、生产部署补充（Nginx 反向代理）

将 8000 端口通过域名暴露时，建议在前面加 Nginx（示例片段）：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;   # 视频/长任务适当调大
    }
}
```

> 提示：`app/main.py` 中 CORS 当前为 `allow_origins=["*"]`，生产环境请改为具体前端域名。

---

## 十、常见问题与排错

**Q1：启动报 `Address already in use` / 端口被占用？**
先查谁占了 8000：
- Windows：`netstat -ano | findstr :8000`，用 `taskkill /PID <pid> /F` 结束；
- macOS / Linux：`lsof -i :8000` 或 `sudo fuser -k 8000/tcp`。
或换端口：`uvicorn app.main:app --port 8080`。

**Q2：`pip install` 装 `numpy` / `pydantic` 失败？**
多为 Python 版本过旧（<3.10）导致找不到预编译包。请升级到 **3.11+**。仍慢可加清华镜像：`-i https://pypi.tuna.tsinghua.edu.cn/simple`。

**Q3：调用选题 / Agent 返回 401 或「API Key 无效」？**
检查 `.env` 里 `LLM_PROVIDER` 与对应 `XXX_API_KEY` 是否匹配、是否复制完整、是否前后有空格。或在 Web 控制台用「⚙ API 配置」单独填你自己的 Key 测试。

**Q4：知识库检索报错 / 结果为空？**
确认 `EMBEDDING_PROVIDER=local`（默认）可离线跑；若用云端 embedding，需填对应密钥与正确维度。先调 `/api/knowledge/ingest` 入库再检索。

**Q5：视频任务一直 `processing`？**
mock 模式约 2 秒（由 `VIDEO_GEN_MOCK_DELAY` 控制）即转成功；generic 模式取决于第三方 API。超时（`VIDEO_GEN_TASK_TIMEOUT`）会标记 `timeout` 并通知。可用 `/api/video/status/{id}` 实时查。

**Q6：改了 `.env` 不生效？**
`.env` 在**服务启动时**读取。修改后需**重启服务**（本地 Ctrl+C 后重跑 uvicorn；Docker 用 `docker compose restart web`）。

**Q7：容器重建后任务状态丢了？**
向量库与日志已挂卷 `./data/vector_store`、`./logs`，默认不丢；只有连同卷一起删除才会丢失。

---

## 十一、系统架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                          外部接入 / 客户端                             │
│   飞书开放平台 │ 企业微信 │ 飞书多维表格 │ 短视频平台(网页) │ 大模型API  │
└───────┬──────────────┬───────────────┬──────────────┬─────────────┘
        │              │               │              │
        ▼              ▼               ▼              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       FastAPI 后端 (app/main.py)                      │
│  /api/agent/run │ /api/short-video/* │ /api/geo/* │ /api/knowledge/*  │
│  全局异常捕获 │ 日志 │ CORS │ /health │ 静态挂载 Web 控制台 /           │
└───────┬──────────────┬───────────────┬──────────────┬─────────────────┘
        │              │               │              │
        ▼              ▼               ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐
│ 业务 Agent  │ │  集成层     │ │  短视频模块  │ │  向量知识库        │
│ ShortVideo  │ │ Feishu/     │ │ fetcher(礼貌)│ │ embeddings(多供应商)│
│ Geo         │ │ WeCom/      │ │ analyzer(LLM)│ │ vector_store(numpy)│
│ (BaseAgent) │ │ Bitable     │ │              │ │ ingest/search      │
└──────┬──────┘ └──────┬──────┘ └──────┬───────┘ └─────────┬─────────┘
       │               │               │                 │
       └───────────────┴───────┬───────┴─────────────────┘
                               ▼
                  ┌──────────────────────────┐
                  │  通用 Agent 框架          │
                  │  tool 注册表 + LLM 适配   │
                  │  (BaseAgent 工具调用循环) │
                  └──────────────────────────┘
```

**模块关系要点**
- `app/agent` 是核心：所有业务 Agent 都继承 `BaseAgent`，靠 `tool_names` 声明可用工具。
- `app/tools` 聚合所有 `@tool` 注册，服务启动时 import 即完成注册。
- 集成层、短视频、GEO、知识库均向工具表注册能力，Agent 通过名字动态分发调用（ReAct 循环）。
- LLM 层统一 OpenAI 兼容接口，切换模型只改环境变量（或控制台单独配置）。

---

## 十二、项目目录结构

```
ai_agent_backend/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example                 # 密钥模板（复制为 .env 后填值）
├── README.md
├── app/
│   ├── main.py                  # FastAPI 入口 + 挂载 Web 控制台
│   ├── core/                    # 配置/日志/异常
│   │   ├── config.py            # 全局配置中心（读取 .env）
│   │   ├── logging.py
│   │   └── exceptions.py
│   ├── agent/                   # 通用 Agent 框架
│   │   ├── tool.py              # 工具注册表 + @tool 装饰器
│   │   ├── llm.py               # 多模型适配（豆包/DeepSeek/通义）+ 每用户覆盖
│   │   └── base.py              # BaseAgent 工具调用循环
│   ├── integrations/            # 外部平台客户端
│   │   ├── feishu.py
│   │   ├── wecom.py
│   │   └── bitable.py
│   ├── video/                   # 短视频模块
│   │   ├── fetcher.py           # 礼貌抓取 + OG 元数据
│   │   └── analyzer.py          # 大模型内容分析
│   ├── geo/                     # GEO 模块
│   │   └── tools.py             # 地理编码/距离/范围
│   ├── knowledge/               # 向量知识库
│   │   ├── embeddings.py        # 向量化（含本地兜底）
│   │   ├── vector_store.py      # numpy 向量库
│   │   └── ingest.py            # 入库/检索封装
│   ├── topic/                   # AI 选题模块
│   │   ├── selection.py         # TopicSelector：批量生成 + 质量增强
│   │   ├── quality.py           # 去重/打分/热度优选（纯标准库，离线可跑）
│   │   └── store.py             # 选题批次存储 + 人工审核
│   ├── video_gen/               # 文生视频/图生视频（异步）
│   │   ├── client.py            # VideoGenClient（mock/generic）
│   │   └── generator.py         # VideoTaskManager：提交/轮询/超时/限流
│   ├── agents/                  # 业务 Agent 链路
│   │   ├── short_video_agent.py
│   │   ├── geo_agent.py
│   │   ├── topic_agent.py
│   │   └── video_pipeline_agent.py
│   ├── tools/                   # 工具聚合 + 各业务工具
│   │   ├── integration_tools.py
│   │   ├── video_tools.py
│   │   ├── geo_tools.py
│   │   ├── knowledge_tools.py
│   │   ├── topic_tools.py
│   │   └── video_gen_tools.py
│   └── routers/                 # API 路由
│       ├── agent.py             # /api/agent/run
│       ├── short_video.py       # /api/short-video/*
│       ├── geo.py               # /api/geo/query
│       ├── knowledge.py         # /api/knowledge/*
│       └── topic.py             # /api/topic/* /api/video/* /api/pipeline/*
├── frontend/                    # 零依赖 Web 控制台（index.html/styles.css/app.js）
├── scripts/
│   └── ingest.py                # 知识库入库 CLI
├── tests/
│   ├── test_api.py
│   ├── test_topic_pipeline.py
│   └── test_topic_quality.py
├── data/vector_store/           # 向量库持久化（运行时生成，已挂卷）
└── logs/                        # 日志（运行时生成）
```

> 更多接口字段与质量增强说明，可在启动后访问 `/docs` 直接查看，或用源码 `app/topic/quality.py`、`app/routers/topic.py` 对照。
