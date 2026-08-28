# AI Agent 业务后端系统

面向企业业务场景的**可扩展 AI Agent 后端**：通用工具调用框架 + 多平台集成（飞书/企微/多维表格）+ 多模型（豆包/DeepSeek/通义千问）+ 短视频分析 + GEO 地理 Agent + 向量知识库，提供 FastAPI 接口、Docker 一键部署。

---

## 1. 系统架构

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
│  全局异常捕获 │ 日志 │ CORS │ /health                                 │
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
- LLM 层统一 OpenAI 兼容接口，切换模型只改环境变量。

### 项目目录树

```
ai_agent_backend/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example                 # 密钥模板（复制为 .env 后填值）
├── README.md
├── app/
│   ├── main.py                  # FastAPI 入口
│   ├── core/                    # 配置/日志/异常
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── exceptions.py
│   ├── agent/                   # 通用 Agent 框架
│   │   ├── tool.py              # 工具注册表 + @tool 装饰器
│   │   ├── llm.py               # 多模型适配（豆包/DeepSeek/通义）
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
│   ├── agents/                  # 业务 Agent 链路
│   │   ├── short_video_agent.py
│   │   └── geo_agent.py
│   ├── tools/                   # 工具聚合 + 各业务工具
│   │   ├── integration_tools.py
│   │   ├── video_tools.py
│   │   ├── geo_tools.py
│   │   └── knowledge_tools.py
│   └── routers/                 # API 路由
│       ├── agent.py
│       ├── short_video.py
│       ├── geo.py
│       └── knowledge.py
├── scripts/
│   └── ingest.py                # 知识库入库 CLI
├── tests/
│   └── test_api.py              # pytest 用例
├── data/vector_store/           # 向量库持久化（运行时生成）
└── logs/                        # 日志（运行时生成）
```

---

## 2. 环境变量 / 密钥清单（需提前申请）

| 变量 | 用途 | 哪里申请 |
|---|---|---|
| `LLM_PROVIDER` | 当前对话模型：doubao/deepseek/qwen | 见下 |
| `DEEPSEEK_API_KEY` | DeepSeek 对话（默认供应商） | platform.deepseek.com → API keys |
| `DOUBAO_API_KEY` / `DOUBAO_MODEL` | 豆包（火山方舟）：key + 推理接入点ID | volcanoengine.com → 方舟 → 创建接入点 |
| `QWEN_API_KEY` | 通义千问（对话/embedding 通用） | dashscope.aliyun.com → API 密钥 |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书应用鉴权 | 飞书开放平台 → 创建企业自建应用 |
| `FEISHU_BOT_WEBHOOK` | 飞书群机器人推送（可选） | 飞书群 → 设置 → 群机器人 → Webhook |
| `WECOM_CORPID` / `WECOM_CORPSECRET` / `WECOM_AGENT_ID` | 企业微信自建应用 | 企业微信管理后台 → 应用管理 |
| `BITABLE_APP_TOKEN` / `BITABLE_TABLE_ID` | 多维表格读写 | 飞书多维表格 URL 中提取 |
| `EMBEDDING_PROVIDER` | 向量化来源：qwen/doubao/local | 同大模型密钥 |
| `VECTOR_DB_PATH` | 向量库存放目录 | 默认 `./data/vector_store` |
| `SCRAPE_RATE_LIMIT` | 抓取限速(秒) | 默认 1.0 |

> 仅本地联调可把 `LLM_PROVIDER` 留空（仍需一个 key 才能跑 Agent），`EMBEDDING_PROVIDER=local` 可免密钥验证知识库链路。

---

## 3. 本地运行

```bash
cd ai_agent_backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # 编辑填入密钥
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

测试（无需密钥即可验证知识库/Geo 本地链路）：
```bash
pytest -q
```

---

## 4. Linux 部署

```bash
# 1. 传代码到服务器，进入目录
# 2. 准备环境变量
cp .env.example .env && vim .env   # 填入真实密钥

# 3. Docker 方式（推荐）
docker compose up -d --build
curl http://localhost:8000/health

# 或裸机方式
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > logs/app.log 2>&1 &
```

反向代理（Nginx 片段）见 README 下方「部署补充」。

---

## 5. 接口验证案例

```bash
# 健康检查
curl http://localhost:8000/health

# 知识库入库
curl -X POST http://localhost:8000/api/knowledge/ingest \
  -H 'Content-Type: application/json' \
  -d '{"text":"年假政策：入职满一年享5天年假。","source":"hr"}'

# 知识库检索
curl -X POST http://localhost:8000/api/knowledge/search \
  -H 'Content-Type: application/json' -d '{"query":"年假几天","top_k":1}'

# GEO 距离（自然语言，走 Geo Agent）
curl -X POST http://localhost:8000/api/geo/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"北京到上海的直线距离是多少公里？"}'

# 短视频纯文本分析（无需抓取）
curl -X POST http://localhost:8000/api/short-video/analyze-text \
  -H 'Content-Type: application/json' \
  -d '{"title":"3分钟学会AI剪辑","text":"本期分享用AE自动生成字幕的技巧..."}'

# 运行短视频分析 Agent（含推送/落库工具）
curl -X POST http://localhost:8000/api/agent/run \
  -H 'Content-Type: application/json' \
  -d '{"agent_type":"short_video","user_input":"分析这条文案并推送给运营群：用AI做短视频太香了"}'
```

> GEO / Agent 链路需要配置对应 LLM 密钥；飞书/企微/多维表格推送需配置相应密钥，缺省会返回清晰错误提示。

---

## 6. 新增模块：AI 选题 / 文生视频 / 全链路（选题→脚本→生成视频）

### 6.1 新增文件（相对原项目）

```
app/
├── core/
│   └── task_store.py          # 【新增】通用异步任务状态存储（视频生成任务持久化+状态机）
├── topic/                     # 【新增】AI 选题模块
│   ├── selection.py           #   TopicSelector：批量生成选题/脚本大纲 + 组装视频 Prompt
│   └── store.py               #   TopicBatchStore：选题批次存储 + 人工审核
├── video_gen/                 # 【新增】文生视频/图生视频模块
│   ├── client.py              #   VideoGenClient：第三方 API 适配（mock/generic）+ 异常(RateLimit/VideoGenError)
│   └── generator.py           #   VideoTaskManager：提交/后台轮询/结果/超时限流处理/通知
├── agents/
│   ├── topic_agent.py         #   【新增】TopicAgent
│   └── video_pipeline_agent.py#   【新增】VideoPipelineAgent + run_topic_to_video_pipeline(方案B)
├── tools/
│   ├── topic_tools.py         #   【新增】topic_generate_batch / topic_approve
│   └── video_gen_tools.py     #   【新增】video_generate_submit / video_query_status
└── routers/
    └── topic.py               #   【新增】/api/topic/* /api/video/* /api/pipeline/*
tests/
└── test_topic_pipeline.py     # 【新增】视频异步链路 + 选题审核测试
```

> 原有 `config.py / .env.example / requirements.txt / tools/__init__.py / main.py / routers/agent.py / integrations/bitable.py` 也已同步改动（新增字段/路由/工具注册/update_record）。

### 6.2 新增环境变量 / 密钥

| 变量 | 用途 | 说明 |
|---|---|---|
| `VIDEO_GEN_PROVIDER` | 视频生成 provider | `mock`(默认,离线联调) \| `generic`(对接第三方 HTTP API) |
| `VIDEO_GEN_API_URL` | 第三方文生视频 API 地址 | generic 模式填写，如 `https://your-vendor.com` |
| `VIDEO_GEN_API_KEY` | 第三方 API 密钥 | generic 模式填写 |
| `VIDEO_GEN_POLL_INTERVAL` | 后台轮询间隔(秒) | 默认 5 |
| `VIDEO_GEN_TASK_TIMEOUT` | 单任务超时(秒) | 默认 600，超过判 `timeout` |
| `VIDEO_GEN_MAX_RETRIES` | 限流最大重试次数 | 默认 3 |
| `VIDEO_GEN_MOCK_DELAY` | mock 模拟生成耗时(秒) | 默认 2 |
| `WECOM_NOTIFY_USER` | 企微任务通知接收人 | 默认 `@all` |
| `TOPIC_DEFAULT_COUNT` / `TOPIC_DEFAULT_STYLE` | 选题默认参数 | 接口可覆盖 |

> 新增第三方依赖：`tenacity`（限流指数退避）。Docker 无需额外操作，`requirements.txt` 已包含。

### 6.3 新增接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/topic/generate` | 批量生成选题（可选基于知识库 / 写多维表格待审核） |
| POST | `/api/topic/approve` | 人工审核，标记优质选题进入下一环节 |
| GET | `/api/topic/batch/{id}` | 查看批次选题与审核状态 |
| POST | `/api/video/submit` | 提交视频生成任务（异步），返回 `task_id` |
| GET | `/api/video/status/{id}` | 查询视频生成任务状态/结果 |
| POST | `/api/pipeline/topic-to-video` | 方案B 全链路：解析参考短视频→生成选题→提交视频生成 |
| POST | `/api/agent/run` (`agent_type=topic` / `video_pipeline`) | 新增两个业务 Agent |

### 6.4 本地测试（新增部分）

```bash
pytest -q        # 现有 6 个用例全过（含视频异步链路 + 选题审核）
```

### 6.5 部署与任务异常处理说明（Linux）

- **异步任务**：`POST /api/video/submit` 立即返回 `task_id`，真正视频 URL 由后台守护线程轮询第三方 API 获取。`VIDEO_GEN_PROVIDER=mock` 时无需任何密钥即可跑通全链路。
- **失败处理**：第三方返回非 4xx 业务失败 → 任务标记 `failed` → 推送飞书/企微通知（不阻塞主流程）。
- **超时处理**：任务创建起超过 `VIDEO_GEN_TASK_TIMEOUT` 仍 `processing` → 标记 `timeout` 并通知。
- **限流处理**：HTTP 429 → `RateLimitError` → 指数退避重试（tenacity + 管理器双层），超过 `VIDEO_GEN_MAX_RETRIES` 判 `failed`。
- **结果闭环**：任务终态（成功/失败/超时）时，自动推送飞书群机器人 + 企业微信，并把「视频链接/状态」回写其关联的多维表格记录。
- **Docker 注意**：任务状态与选题批次持久化在 `./data/vector_store`（已挂卷），容器重建后轮询线程会在启动时 `ensure_poller()` 续跑未完成任务。

### 6.6 全链路调用示例（方案B）

```bash
# 1) 生成选题（可选写多维表格待审核）
curl -X POST http://localhost:8000/api/topic/generate \
  -H 'Content-Type: application/json' \
  -d '{"industry":"美妆","style":"科普","count":3,"use_knowledge":false,"write_to_bitable":true}'

# 2) 人工审核（用第1步返回的 batch_id 与某个 topic id）
curl -X POST http://localhost:8000/api/topic/approve \
  -H 'Content-Type: application/json' \
  -d '{"batch_id":"batch_xxxx","topic_ids":["t1"]}'

# 3) 直接走方案B全链路：解析参考短视频 -> 生成选题 -> 提交视频生成
curl -X POST http://localhost:8000/api/pipeline/topic-to-video \
  -H 'Content-Type: application/json' \
  -d '{"video_url":"<公开分享链接>","industry":"美妆","style":"科普","count":3,"write_to_bitable":true,"notify":true}'

# 4) 查询视频生成任务（用第3步返回的 video_task_id）
curl http://localhost:8000/api/video/status/{video_task_id}
```

