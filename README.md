# AI Agent 业务后端系统 · 安装配置全流程教程

面向企业业务场景的**可扩展 AI Agent 后端**：通用工具调用框架 + 多平台集成（飞书 / 企业微信 / 多维表格）+ 多模型（DeepSeek / 豆包 / 通义千问）+ 短视频分析 + GEO 地理 Agent + 向量知识库 + AI 视频生成（9:16 / 16:9 四种生成方式），提供 FastAPI 接口、零依赖 Web 控制台与 Docker 一键部署。

> 本文档按「从零到跑起来」的顺序编写，**每一步都给出 Windows / macOS / Linux 对应命令**。
> 文档中所有结论均在 **Windows 11 + Python 3.13.12** 环境实测验证（见文末「验证记录」）。

---

## 目录

- [零、30 秒速览](#零30-秒速览)
- [一、环境要求](#一环境要求)
- [二、快速开始（三种方式任选）](#二快速开始三种方式任选)
  - [方式 A：本地 Python 虚拟环境（推荐开发/调试）](#方式-a本地-python-虚拟环境推荐开发调试)
  - [方式 B：Docker Compose（推荐生产 / 一键部署）](#方式-bdocker-compose推荐生产--一键部署)
  - [方式 C：Docker 手动构建运行](#方式-cdocker-手动构建运行)
- [三、密钥申请教程（三家大模型，任选其一）](#三密钥申请教程三家大模型任选其一)
- [四、配置文件 `.env` 逐项详解](#四配置文件-env-逐项详解)
- [五、启动与验证](#五启动与验证)
- [六、发布前自检（确认代码无报错）](#六发布前自检确认代码无报错)
- [七、Web 控制台使用](#七web-控制台使用)
- [八、接口调用示例（curl 全集）](#八接口调用示例curl-全集)
- [九、运行测试](#九运行测试)
- [十、知识库命令行入库（CLI）](#十知识库命令行入库cli)
- [十一、生产部署（Nginx 反向代理 / systemd）](#十一生产部署nginx-反向代理--systemd)
- [十二、常见问题与排错（FAQ）](#十二常见问题与排错faq)
- [十三、系统架构](#十三系统架构)
- [十四、项目目录结构](#十四项目目录结构)
- [十五、本次维护记录](#十五本次维护记录)

---

## 零、30 秒速览

```bash
# 1. 装依赖（建议用虚拟环境）
python -m venv .venv && .venv/Scripts/activate        # Windows
python -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 2. 生成配置文件并填一个大模型密钥
cp .env.example .env          # Windows 用 copy .env.example .env

# 3. 启动
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. 打开浏览器
#    Web 控制台  http://localhost:8000/
#    接口文档    http://localhost:8000/docs
```

**零密钥也能跑通的部分**：知识库（默认 `local` 本地向量）、AI 视频生成（默认 `mock` 模拟）、GEO 距离计算（纯数学）。
**必须配密钥的部分**：选题生成、Agent 对话、短视频内容分析（三者都需调用大模型）。

---

## 一、环境要求

| 项目 | 要求 | 说明 |
|---|---|---|
| Python | **3.10 及以上**（实测 3.13.12 通过） | 依赖 `numpy==2.1.3`、`pydantic>=2.7`，需要较新版本才有预编译 wheel |
| pip | 最新版 | 先执行 `python -m pip install -U pip` |
| Git | 任意较新版本 | 拉取代码、提交 |
| Docker（可选） | 20.10+ / Compose v2 | 仅容器部署需要；本机未安装也不影响方式 A |
| 网络 | 需能访问对应大模型 API | 知识库检索可用 `local` 模式离线验证 |

### 1.1 关于 pip 镜像源（国内用户必看）

实测结论（2026-08，Windows 本机）：

| 镜像源 | 实测结果 | 建议 |
|---|---|---|
| `https://mirrors.aliyun.com/pypi/simple/` | ✅ **安装成功** | **国内首选** |
| `https://pypi.tuna.tsinghua.edu.cn/simple` | ❌ SSL 握手失败（`UNEXPECTED_EOF_WHILE_READING`） | 若你那边可用也可用 |
| `https://pypi.org/simple` | 海外服务器首选 | 国内较慢 |

> 若安装时报 `SSLError` / `SSL: UNEXPECTED_EOF_WHILE_READING`，**换源即可**，不是代码问题。
> 本文档后续所有 `pip install` 默认使用阿里云镜像。

---

## 二、快速开始（三种方式任选）

> 三种方式最终效果一致：服务监听 `0.0.0.0:8000`，提供 `/`（Web 控制台）、`/docs`（Swagger）、`/api/*`、`/health`。

### 方式 A：本地 Python 虚拟环境（推荐开发/调试）

#### 第 1 步：获取代码

```bash
git clone git@github.com:Vvv1940905115/ai_agent_backend.git
cd ai_agent_backend
```

#### 第 2 步：创建并激活虚拟环境

- **Windows（PowerShell）**：
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  ```
  若提示「禁止运行脚本」，改用 CMD：
  ```cmd
  .venv\Scripts\activate.bat
  ```
- **Windows（Git Bash）**：
  ```bash
  python -m venv .venv
  source .venv/Scripts/activate
  ```
- **macOS / Linux**：
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

> 激活后命令行出现 `(.venv)` 前缀，表示后续操作都在隔离环境内，不会污染系统 Python。

#### 第 3 步：安装依赖

```bash
python -m pip install -U pip -i https://mirrors.aliyun.com/pypi/simple/
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

依赖清单（`requirements.txt`）：

| 依赖 | 用途 |
|---|---|
| `fastapi` / `uvicorn[standard]` | Web 框架与 ASGI 服务器 |
| `pydantic` / `pydantic-settings` | 数据校验与 `.env` 配置读取 |
| `openai` | 三家大模型的 OpenAI 兼容客户端 |
| `httpx` / `beautifulsoup4` | HTTP 请求与网页元数据提取 |
| `numpy` | 向量相似度计算 |
| `tenacity` | 视频生成 API 限流重试（指数退避） |
| `python-dotenv` / `python-multipart` | 环境加载 / 表单解析 |
| `pytest` | 单元测试 |

> 若 `numpy` / `pydantic` 报「找不到预编译包」，说明 Python 版本过旧（<3.10），请升级后再装。

#### 第 4 步：生成 `.env` 并填密钥

```bash
# Windows（CMD / PowerShell）：
copy .env.example .env

# macOS / Linux / Git Bash：
cp .env.example .env
```

然后用编辑器打开 `.env`：

- 至少填**一个**大模型密钥（见[第三章](#三密钥申请教程三家大模型任选其一)）；
- 知识库保持 `EMBEDDING_PROVIDER=local`（默认）、视频保持 `VIDEO_GEN_PROVIDER=mock`（默认），即可**免密钥**跑通这两条链路。

> `.env` 已写入 `.gitignore`，**不会被提交**，可放心填真实密钥。

#### 第 5 步：启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- `--reload` 为热重载，仅开发使用；生产请去掉。
- 出现 `Uvicorn running on http://0.0.0.0:8000` 即启动成功。

#### 第 6 步：验证

- Web 控制台：http://localhost:8000/
- 接口文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health → 应返回 `{"code":0,"status":"ok","service":"ai-agent-backend"}`

---

### 方式 B：Docker Compose（推荐生产 / 一键部署）

```bash
# 1. 准备 .env
cp .env.example .env      # 编辑填入真实密钥

# 2. 构建并后台启动
docker compose up -d --build

# 3. 验证
curl http://localhost:8000/health
```

常用命令：

```bash
docker compose logs -f web     # 实时日志
docker compose ps              # 查看状态（STATUS 应为 healthy）
docker compose restart web     # 重启
docker compose down            # 停止并删除容器（数据卷保留）
docker compose exec web python scripts/selfcheck.py   # 容器内自检
```

> - 向量库 `./data/vector_store` 与 `./logs` 已挂卷，容器重建不丢数据。
> - 镜像构建默认使用阿里云 PyPI 源。如需换源：
>   ```bash
>   docker compose build --build-arg PIP_INDEX_URL=https://pypi.org/simple
>   ```
> - 已新增 `.dockerignore`：`.env`、`.git`、`data/`、`logs/`、`__pycache__/` 等**不会进入镜像**，避免密钥泄漏。

---

### 方式 C：Docker 手动构建运行

```bash
# 1. 准备 .env
cp .env.example .env

# 2. 构建镜像
docker build -t ai-agent-backend:1.0.0 .

# 3. 运行容器
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

> 镜像基于 `python:3.11-slim`，内置 pip 源加速、以非 root 用户 `appuser` 运行、带 `HEALTHCHECK`。

---

## 三、密钥申请教程（三家大模型，任选其一）

只需挑**一家**配好即可。三家均为 OpenAI 兼容协议，切换只改 `LLM_PROVIDER`。

### 3.1 DeepSeek（推荐新手，中文效果好、便宜）

1. 打开 https://platform.deepseek.com ，注册 / 登录。
2. 左侧「API keys」→「创建 API Key」，复制生成的 `sk-xxxxx`（**只显示一次，务必保存**）。
3. 在 `.env` 填写：
   ```ini
   LLM_PROVIDER=deepseek
   DEEPSEEK_API_KEY=sk-你的密钥
   DEEPSEEK_BASE_URL=https://api.deepseek.com
   DEEPSEEK_MODEL=deepseek-chat
   ```
4. 模型说明：
   - `deepseek-chat`：经典模型，官方标记 2026-07-24 弃用，但**保持兼容可正常使用**；
   - `deepseek-v4-flash` / `deepseek-v4-pro`：新版，推荐新项目使用。
5. `DEEPSEEK_BASE_URL` 三个值均实测可用（返回 401 即表示端点有效、只差鉴权）：
   `https://api.deepseek.com`（官方推荐）、`https://api.deepseek.com/v1`、`https://api.deepseek.com/v3`。

### 3.2 豆包 / 火山方舟 Ark

1. 打开 https://console.volcengine.com/ark ，开通「火山方舟」服务。
2. 左侧「API Key 管理」→ 创建 API Key，复制。
3. **关键一步**：在「模型推理」→「创建推理接入点」，选择模型后得到**接入点 ID**，形如 `ep-2024xxxxxx-xxxxx`。
4. 在 `.env` 填写：
   ```ini
   LLM_PROVIDER=doubao
   DOUBAO_API_KEY=你的密钥
   DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
   DOUBAO_MODEL=ep-2024xxxxxx-xxxxx
   ```
   > ⚠️ `DOUBAO_MODEL` 必须填**推理接入点 ID**（`ep-` 开头），**不是模型名**。沿用模板里的 `ep-xxxxxxxx` 占位符会调用失败。

### 3.3 通义千问 / DashScope

1. 打开 https://dashscope.aliyun.com ，登录阿里云账号并开通服务。
2. 右上角头像 →「API 密钥」→「创建新的 API 密钥」，复制。
3. 在 `.env` 填写：
   ```ini
   LLM_PROVIDER=qwen
   QWEN_API_KEY=sk-你的密钥
   QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
   QWEN_MODEL=qwen-plus
   ```

### 3.4 验证密钥是否配好

启动服务后执行（会真实调用一次大模型，产生极少量费用）：

```bash
curl -X POST http://localhost:8000/api/short-video/analyze-text \
  -H 'Content-Type: application/json' \
  -d '{"title":"3分钟学会AI剪辑","text":"本期分享用AE自动生成字幕的技巧"}'
```

- 返回结构化 JSON（summary/tags/sentiment/category/suggest）→ 配置成功；
- 返回 `{"code":400,"message":"缺少 API Key..."}` → `.env` 没填或没重启服务；
- 返回 `{"code":401,"message":"API Key 无效或已过期..."}` → 密钥复制不全/已失效。

---

## 四、配置文件 `.env` 逐项详解

所有变量由 `app/core/config.py` 通过 `pydantic-settings` 读取。**未填写的可选项留空即可**。

### 4.1 服务基础

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_NAME` | `ai-agent-backend` | 服务名，用于日志与接口标题 |
| `HOST` | `0.0.0.0` | 监听地址，容器/服务器部署保持默认 |
| `PORT` | `8000` | 监听端口 |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `REQUEST_TIMEOUT` | `30` | 单次外部请求超时（秒） |

### 4.2 大模型（LLM）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LLM_PROVIDER` | `deepseek` | 全局默认模型：`deepseek` / `doubao` / `qwen` |
| `LLM_MODEL` | `deepseek-chat` | 兜底模型名（各供应商有 `*_MODEL` 时优先用后者） |
| `DEEPSEEK_API_KEY` / `_BASE_URL` / `_MODEL` | 空 / `https://api.deepseek.com` / `deepseek-chat` | 见 [3.1](#31-deepseek推荐新手中文效果好便宜) |
| `DOUBAO_API_KEY` / `_BASE_URL` / `_MODEL` | 空 / `https://ark.cn-beijing.volces.com/api/v3` / `ep-xxxxxxxx` | 见 [3.2](#32-豆包--火山方舟-ark) |
| `QWEN_API_KEY` / `_BASE_URL` / `_MODEL` | 空 / `https://dashscope.aliyuncs.com/compatible-mode/v1` / `qwen-plus` | 见 [3.3](#33-通义千问--dashscope) |

### 4.3 外部平台集成（全部可选）

不填则对应功能不可用，但不影响其他模块。

| 变量 | 用途 | 申请位置 |
|---|---|---|
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书自建应用鉴权 | 飞书开放平台 → 创建企业自建应用 |
| `FEISHU_BOT_WEBHOOK` | 飞书群机器人推送（免鉴权，最省事） | 飞书群 → 设置 → 群机器人 → 添加 Webhook |
| `WECOM_CORPID` / `WECOM_CORPSECRET` / `WECOM_AGENT_ID` | 企业微信自建应用 | 企业微信管理后台 → 应用管理 |
| `BITABLE_APP_TOKEN` / `BITABLE_TABLE_ID` | 飞书多维表格读写 | 多维表格链接中提取：`/base/<app_token>` 与 `?table=<table_id>` |

### 4.4 向量知识库

| 变量 | 默认值 | 说明 |
|---|---|---|
| `EMBEDDING_PROVIDER` | `local` | `local`（本地哈希兜底，**免密钥离线**）/ `qwen` / `doubao` |
| `EMBEDDING_DIM` | `256` | 本地 embedding 维度 |
| `VECTOR_DB_PATH` | `./data/vector_store` | 向量库目录（Docker 已挂卷） |

> ⚠️ `local` 是**哈希词袋**向量，不是语义向量，检索分数可能偏低（如 0.0）。它只用于跑通链路与离线联调，**生产请切换为 `qwen` 或 `doubao`** 以获得真实语义检索效果。

### 4.5 抓取策略（反爬友好）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SCRAPE_RATE_LIMIT` | `1.0` | 抓取网页的最小请求间隔（秒） |
| `USER_AGENT` | `Mozilla/5.0 (compatible; AIgentBot/1.0; ...)` | 抓取时使用的 UA，建议改成你自己的标识 |

### 4.6 AI 选题

| 变量 | 默认值 | 说明 |
|---|---|---|
| `TOPIC_DEFAULT_COUNT` | `5` | 默认生成数量（接口可覆盖） |
| `TOPIC_DEFAULT_STYLE` | `科普` | 默认风格（接口可覆盖） |
| `TOPIC_DEDUPE_THRESHOLD` | `0.7` | 去重相似度阈值（0–1，越高越严格） |

### 4.7 AI 视频生成（异步任务）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `VIDEO_GEN_PROVIDER` | `mock` | `mock`（默认，**离线免密钥**）/ `generic`（对接第三方 HTTP API） |
| `VIDEO_GEN_API_URL` | 空 | generic 模式的第三方 API 地址 |
| `VIDEO_GEN_API_KEY` | 空 | generic 模式的第三方密钥 |
| `VIDEO_GEN_POLL_INTERVAL` | `5` | 后台轮询间隔（秒） |
| `VIDEO_GEN_TASK_TIMEOUT` | `600` | 单任务超时（秒），超时标记 `timeout` |
| `VIDEO_GEN_MAX_RETRIES` | `3` | 限流/可重试错误的最大重试次数（指数退避） |
| `VIDEO_GEN_MOCK_DELAY` | `2` | mock 模式模拟生成耗时（秒） |
| `WECOM_NOTIFY_USER` | `@all` | 任务状态通知的企微接收人（`@all` 或具体 userid） |

**四种生成方式（`mode`）**

| mode | 含义 | 必填参考项 |
|---|---|---|
| `text2video` | 文生视频（仅文字） | 无 |
| `image2video` | 图生视频 | `ref_image`（图片 URL 或 base64 dataURL） |
| `video2video` | 视频生视频 | `ref_video`（视频 URL 或 base64 dataURL） |
| `frame2video` | 首尾帧生视频 | `first_frame` + `last_frame` |

**两种比例（`aspect_ratio`）**：`16:9` 横版 / `9:16` 竖版。
选竖版时后端自动交换宽高：`1920x1080` → `1080x1920`、`2K` → `1440x2560`，并在请求体带上 `aspect_ratio` 字段。

**`generic` 适配器默认契约（OpenAI 兼容风格）**

提交：`POST {VIDEO_GEN_API_URL}/v1/video/generations`

```json
{
  "model": "seedance_2_5",
  "prompt": "科技感产品宣传片，蓝色调，15秒",
  "duration": 15,
  "resolution": "1080x1920",
  "aspect_ratio": "9:16",
  "style": "cinematic",
  "mode": "image2video",
  "image": "<参考图 URL 或 base64 dataURL>"
}
```

- 公共字段：`model` / `prompt` / `duration` / `resolution`（竖版已自动转置）/ `aspect_ratio` / `style` / `mode`。
- 按方式注入素材字段：`image2video` → `image`；`video2video` → `video`；`frame2video` → `first_frame` + `last_frame`；`text2video` 无附加字段。
- 响应需包含 `id` / `task_id` / `taskId` 任意一个。

查询：`GET {VIDEO_GEN_API_URL}/v1/video/generations/{task_id}`
响应需包含 `status`/`state`、`progress`、`video_url`/`url`/`output`、`error`。

> ⚠️ 前端下拉里的「Seedance / Minmax H3」只是模型选项与校验规则，**不会自动映射到对应厂商的官方 API**。若对接字节 Seedance、MiniMax 等自有协议，请按真实字段修改 `app/video_gen/client.py` 的 `_generic_submit` / `_generic_query`，或新增一个 provider 分支。

### 4.8 配置自检清单

- [ ] 已从 `.env.example` 复制出 `.env`（**不是直接改 `.env.example`**）
- [ ] 至少填了**一个** `XXX_API_KEY`，且 `LLM_PROVIDER` 与之对应
- [ ] 若用豆包，`DOUBAO_MODEL` 已改成你自己的 `ep-` 接入点 ID
- [ ] `.env` 修改后**已重启服务**
- [ ] 暂不用的飞书/企微/多维表格保持留空即可

---

## 五、启动与验证

```bash
curl http://localhost:8000/health
# 期望：{"code":0,"status":"ok","service":"ai-agent-backend"}
```

然后打开：

- http://localhost:8000/ → Web 控制台（推荐，点几下就能用）
- http://localhost:8000/docs → Swagger 在线调试页
- http://localhost:8000/openapi.json → OpenAPI 契约

**服务启动后实际注册的接口（19 个路由）**：

```
GET    /health                          健康检查
GET    /                                Web 控制台（静态页）
POST   /api/agent/run                   运行业务 Agent
POST   /api/short-video/analyze-url     按链接解析短视频
POST   /api/short-video/analyze-text    按文案解析短视频
POST   /api/geo/query                   GEO 自然语言查询
POST   /api/knowledge/ingest            知识库入库
POST   /api/knowledge/search            知识库检索
POST   /api/topic/generate              批量生成选题
POST   /api/topic/approve               选题审核优选
GET    /api/topic/batch/{batch_id}      查询批次
GET    /api/video/models                视频模型/比例/方式清单
POST   /api/video/submit                提交视频生成任务
POST   /api/video/test-config           测试视频 API 连通性
GET    /api/video/status/{task_id}      查询任务状态
POST   /api/pipeline/topic-to-video     全链路：解析→选题→生成视频
GET    /docs  /redoc  /openapi.json     接口文档
```

---

## 六、发布前自检（确认代码无报错）

项目内置一键自检脚本，**无需密钥、无需联网**：

```bash
python scripts/selfcheck.py
```

它会依次执行 5 项检查，全部通过才打印「全部通过」并以 0 退出：

1. **语法编译** —— `compileall` 检查 `app` / `tests` / `scripts` / `conftest.py`
2. **导入检查** —— 能否 `import app.main`（暴露依赖缺失、循环导入）
3. **工具注册** —— 16 个 `@tool` 是否全部注册，4 个 Agent 引用的工具名是否都存在
4. **路由清单** —— 打印 FastAPI 实际注册的接口
5. **单元测试** —— 调用 pytest 跑全量用例

也可以手动分步执行：

```bash
# 1) 语法编译（无输出即通过）
python -m compileall -q app tests scripts conftest.py

# 2) 单元测试（12 passed）
pytest -q

# 3) 可选：静态分析（需先 pip install pyflakes）
python -m pyflakes app scripts tests conftest.py
```

> 期望结果：`12 passed`，无 failed / error。
> 若 `pytest` 报 `ModuleNotFoundError: No module named 'app'`，说明虚拟环境未激活或依赖未装全 —— 项目根目录的 `conftest.py` 已负责把项目根加入 `sys.path`，请确认你在**项目根目录**下执行。

---

## 七、Web 控制台使用

浏览器访问 `http://localhost:8000/`，零依赖、无需命令行，覆盖全部能力：

| 模块 | 功能 |
|---|---|
| 选题中心 | 按行业/风格/数量生成选题，展示质量分、等级、排名；勾选或按 `top_n` 一键审核优选 |
| AI 视频 | 选择模型 / 比例（9:16・16:9）/ 生成方式，提交四种生成任务，按 `task_id` 查询或自动轮询；支持本地文件上传与预览 |
| 知识库 | 检索 / 导入文档片段 |
| Agent | 运行 `short_video` / `geo` / `topic` / `video_pipeline` 四类智能体 |
| 短视频解析 | 输入链接或文案，分析结构、钩子与可复用要素 |

### AI 视频模块操作步骤

1. **先配 API（可选）**：点右上角 **⚙ API 配置**，选服务商（mock 离线联调 / DeepSeek / 豆包 / 通义 / 自定义 OpenAI 兼容），填 Base URL 与 Key，保存即生效（存浏览器 `localStorage`）。新人可直接用 `mock` 跑通全流程。
2. **填任务参数**：
   - 模型：Seedance 2.0 Mini / 2.0 Fast / 2.0 标准版 / 2.5 / Minmax H3（切换模型会自动更新可选时长上限与分辨率）。
   - 比例：横版 `16:9` / 竖版 `9:16`（竖版时分辨率自动转置）。
   - 生成方式：文生视频 / 图生视频 / 视频生视频 / 首尾帧生视频（切换会自动显隐对应素材输入框）。
   - 参考素材：可**粘贴公网 URL** 或**选本地文件**（本地文件转 base64 提交，并在框内预览）。
3. **提交与查询**：点「提交任务」拿到 `task_id` 并自动回填；用「查询进度」或「自动轮询」查看状态与成片。
4. **脚本化调用**：`window.AIVideo.set({model, duration, resolution, style, prompt, aspect_ratio, mode, ref_image, ref_video, first_frame, last_frame})` 可给表单赋值，`AIVideo.get()` 导出当前表单。

### 重点特性：每人自带 API 配置

不想依赖全局 `.env`？点右上角 **⚙ API 配置**：

1. 选择服务商（DeepSeek / 豆包 / 通义 / 自定义 OpenAI 兼容）；
2. 填写模型名与 API Key（选「自定义」时需填 Base URL）；
3. 可选：高级里单独配置云端向量（embedding）密钥；
4. 点「保存」——配置仅存本机浏览器 `localStorage`，**每次请求自动携带**；
5. 顶部状态从红点「未配置模型」变为绿点「模型：xxx」。

多人共用同一控制台时各填各的 Key，互不干扰；清空即回落到服务端全局 `.env` 配置。Key 填错时接口返回清晰中文提示（如「API Key 无效或已过期」），不会抛原始堆栈。

---

## 八、接口调用示例（curl 全集）

> 默认服务地址 `http://localhost:8000`。

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

**GEO 距离（自然语言，走 Geo Agent）**
```bash
curl -X POST http://localhost:8000/api/geo/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"北京到上海的直线距离是多少公里？"}'
```

**短视频纯文本分析**
```bash
curl -X POST http://localhost:8000/api/short-video/analyze-text \
  -H 'Content-Type: application/json' \
  -d '{"title":"3分钟学会AI剪辑","text":"本期分享用AE自动生成字幕的技巧..."}'
```

**运行业务 Agent（short_video / geo / topic / video_pipeline）**
```bash
curl -X POST http://localhost:8000/api/agent/run \
  -H 'Content-Type: application/json' \
  -d '{"agent_type":"short_video","user_input":"分析这条文案并推送给运营群：用AI做短视频太香了"}'
```

**视频模型清单（前端下拉据此渲染）**
```bash
curl http://localhost:8000/api/video/models
```

**文生视频（横版 16:9）**
```bash
curl -X POST http://localhost:8000/api/video/submit \
  -H 'Content-Type: application/json' \
  -d '{"model":"seedance_2_5","prompt":"科技感产品宣传片，蓝色调，15秒","duration":15,"resolution":"2K","style":"cinematic","mode":"text2video","aspect_ratio":"16:9"}'
```

**图生视频（竖版 9:16，需 ref_image）**
```bash
curl -X POST http://localhost:8000/api/video/submit \
  -H 'Content-Type: application/json' \
  -d '{"model":"seedance_2_5","prompt":"让这张图动起来","duration":10,"resolution":"1920x1080","mode":"image2video","aspect_ratio":"9:16","ref_image":"https://example.com/poster.jpg"}'
```

**视频生视频（ref_video）**
```bash
curl -X POST http://localhost:8000/api/video/submit \
  -H 'Content-Type: application/json' \
  -d '{"model":"seedance_2_5","prompt":"把这段视频改成水墨风格","duration":8,"mode":"video2video","aspect_ratio":"16:9","ref_video":"https://example.com/src.mp4"}'
```

**首尾帧生视频**
```bash
curl -X POST http://localhost:8000/api/video/submit \
  -H 'Content-Type: application/json' \
  -d '{"model":"seedance_2_0_std","prompt":"从首帧平滑过渡到尾帧","duration":8,"mode":"frame2video","aspect_ratio":"9:16","first_frame":"https://example.com/first.png","last_frame":"https://example.com/last.png"}'
```

**测试视频 API 连通性（不提交计费任务）**
```bash
curl -X POST http://localhost:8000/api/video/test-config \
  -H 'Content-Type: application/json' \
  -d '{"provider":"generic","api_url":"https://your-api.example.com","api_key":"YOUR_KEY"}'
```

**查询任务进度**
```bash
curl http://localhost:8000/api/video/status/{video_task_id}
```

**全链路（解析短视频 → 生成选题 → 提交视频生成）**
```bash
curl -X POST http://localhost:8000/api/pipeline/topic-to-video \
  -H 'Content-Type: application/json' \
  -d '{"video_url":"<公开分享链接>","industry":"美妆","style":"科普","count":3,"write_to_bitable":true,"notify":true}'
```

### 错误响应速查

| HTTP | code | 典型场景 | 处理 |
|---|---|---|---|
| 400 | 400 | 缺少 API Key / 参数不合法 / 模型不支持所选时长分辨率 | 按 `message` 修正配置或参数 |
| 401 | 401 | 自填的 API Key 无效或过期 | 重填 Key |
| 404 | 404 | 批次/任务不存在 | 检查 `batch_id`/`task_id` |
| 422 | 422 | 请求体字段校验失败 | 看 `detail` 里的字段错误 |
| 502 | 502 | 抓取失败 / 大模型接口调用失败 | 检查 URL、base_url、网络 |

---

## 九、运行测试

```bash
# 激活虚拟环境后，在项目根目录执行
pytest -q
# 期望：12 passed

# Docker 环境
docker compose exec web pytest -q
```

覆盖范围（无需任何密钥）：

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/test_api.py` | `/health`、知识库入库+检索、GEO 距离工具、未知 Agent 类型返回 400 |
| `tests/test_topic_pipeline.py` | 视频生成 mock 全链路（提交→轮询→获取 URL）、选题批次审核 |
| `tests/test_topic_quality.py` | 选题去重 / 打分 / 热度优选 |

---

## 十、知识库命令行入库（CLI）

```bash
# 直接传文本
python scripts/ingest.py --text "企业知识文本..."

# 从文件读取
python scripts/ingest.py --file ./docs/policy.txt --source 政策文档
```

---

## 十一、生产部署（Nginx 反向代理 / systemd）

### Nginx 反代

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

> `app/main.py` 中 CORS 当前为 `allow_origins=["*"]`，生产请改为具体前端域名。

### systemd 服务（Linux）

```ini
[Unit]
Description=AI Agent Backend
After=network.target

[Service]
WorkingDirectory=/opt/ai_agent_backend
ExecStart=/opt/ai_agent_backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
EnvironmentFile=/opt/ai_agent_backend/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ai-agent-backend
sudo journalctl -u ai-agent-backend -f
```

---

## 十二、常见问题与排错（FAQ）

**Q1：启动报 `Address already in use`（端口被占用）？**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <pid> /F
# macOS / Linux
lsof -i :8000          # 或 sudo fuser -k 8000/tcp
```
或换端口：`uvicorn app.main:app --port 8080`。

**Q2：`pip install` 报 SSL 错误或超时？**
换镜像源（实测清华源在本机会 SSL 握手失败，改用阿里源即可）：
```bash
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

**Q3：`pytest` 报 `ModuleNotFoundError: No module named 'app'`？**
确认：① 虚拟环境已激活；② 依赖已安装；③ 在**项目根目录**执行。根目录的 `conftest.py` 会把项目根加入 `sys.path`；若仍失败，用 `python -m pytest -q` 代替 `pytest -q`。

**Q4：调用选题 / Agent 返回「缺少 API Key」？**
检查 `.env` 中 `LLM_PROVIDER` 与对应 `XXX_API_KEY` 是否匹配、是否复制完整、前后有无空格；修改后**必须重启服务**。或在控制台用「⚙ API 配置」单独填自己的 Key 测试。

**Q5：豆包返回模型不存在 / 404？**
`DOUBAO_MODEL` 必须填火山方舟的**推理接入点 ID**（`ep-` 开头），不是模型名。模板里的 `ep-xxxxxxxx` 是占位符。

**Q6：知识库检索结果不理想 / score 为 0？**
默认 `EMBEDDING_PROVIDER=local` 是哈希词袋向量，仅用于跑通链路。生产请改为 `qwen` 或 `doubao` 并配置对应密钥，以获得真实语义检索。也可先确认已调用 `/api/knowledge/ingest` 入库。

**Q7：视频任务一直是 `processing`？**
mock 模式默认 2 秒后成功（由 `VIDEO_GEN_MOCK_DELAY` 控制），但后台轮询间隔为 `VIDEO_GEN_POLL_INTERVAL`（默认 5 秒），所以最长要等 5–7 秒才刷新为 `succeeded`，属正常现象。generic 模式取决于第三方 API；超过 `VIDEO_GEN_TASK_TIMEOUT` 会标记 `timeout`。

**Q8：改了 `.env` 不生效？**
`.env` 在**服务启动时**读取，修改后需重启（本地 Ctrl+C 重跑 uvicorn；Docker 用 `docker compose restart web`）。

**Q9：容器重建后任务状态丢了？**
向量库与日志已挂卷 `./data/vector_store`、`./logs`，默认不丢；只有连同卷一起删除才会丢失。

**Q10：飞书/企微推送没收到？**
确认对应变量已填写且服务已重启；推送失败会在日志里留 `WARNING`（飞书通知失败 / 企微通知失败），可据此定位。

---

## 十三、系统架构

```
┌────────────────────────────────────────────────────────────────────────┐
│                          外部接入 / 客户端                               │
│   飞书开放平台 │ 企业微信 │ 飞书多维表格 │ 短视频平台(网页) │ 大模型 API   │
└───────┬──────────────┬───────────────┬──────────────┬─────────────────┘
        ▼              ▼               ▼              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       FastAPI 后端 (app/main.py)                        │
│  /api/agent/run │ /api/short-video/* │ /api/geo/* │ /api/knowledge/*    │
│  /api/topic/* │ /api/video/* │ /api/pipeline/*                          │
│  全局异常捕获 │ 日志 │ CORS │ /health │ 静态挂载 Web 控制台 /            │
└───────┬──────────────┬───────────────┬──────────────┬─────────────────┘
        ▼              ▼               ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐
│ 业务 Agent   │ │  集成层      │ │  短视频模块   │ │  向量知识库         │
│ ShortVideo  │ │ Feishu/     │ │ fetcher(礼貌) │ │ embeddings(多供应商) │
│ Geo/Topic/  │ │ WeCom/      │ │ analyzer(LLM) │ │ vector_store(numpy) │
│ VideoPipeline│ │ Bitable     │ │              │ │ ingest/search       │
└──────┬──────┘ └──────┬──────┘ └──────┬───────┘ └─────────┬───────────┘
       │               │               │                   │
       └───────────────┴───────┬───────┴───────────────────┘
                               ▼
                  ┌──────────────────────────┐
                  │  通用 Agent 框架           │
                  │  tool 注册表 + LLM 适配    │
                  │  (BaseAgent 工具调用循环)  │
                  └──────────────────────────┘
```

**模块关系要点**

- `app/agent` 是核心：所有业务 Agent 继承 `BaseAgent`，靠 `tool_names` 声明可用工具。
- `app/tools/__init__.py` 聚合所有 `@tool` 注册，`main.py` 启动时 import 即完成注册（共 16 个工具）。
- 集成层、短视频、GEO、知识库、选题、视频生成均向工具表注册能力，Agent 按名字动态分发调用（ReAct 循环）。
- LLM 层统一 OpenAI 兼容接口，切换模型只改环境变量，或在控制台单独配置。
- **异步任务闭环**：`VideoTaskManager` 后台线程轮询第三方状态，终态时自动推送飞书/企微并回写多维表格；任务持久化在 `data/vector_store/video_tasks.pkl`，重启可续跑。

---

## 十四、项目目录结构

```
ai_agent_backend/
├── Dockerfile                   # 镜像构建（python:3.11-slim，非 root 运行）
├── docker-compose.yml           # 一键部署（挂卷 data/logs）
├── .dockerignore                # 构建上下文排除清单（含 .env，防密钥泄漏）
├── requirements.txt             # 依赖清单
├── .env.example                 # 配置模板（复制为 .env 后填值）
├── conftest.py                  # 让 pytest 把项目根加入 sys.path
├── README.md
├── app/
│   ├── main.py                  # FastAPI 入口 + 挂载 Web 控制台
│   ├── core/                    # 配置 / 日志 / 异常 / 异步任务存储
│   │   ├── config.py            # 全局配置中心（读取 .env）
│   │   ├── logging.py
│   │   ├── exceptions.py        # BusinessError + 全局异常处理器
│   │   └── task_store.py        # 异步任务持久化（pickle + 线程锁）
│   ├── agent/                   # 通用 Agent 框架
│   │   ├── tool.py              # 工具注册表 + @tool 装饰器
│   │   ├── llm.py               # 多模型适配 + 每用户覆盖（contextvar）
│   │   └── base.py              # BaseAgent 工具调用循环
│   ├── agents/                  # 业务 Agent
│   │   ├── short_video_agent.py
│   │   ├── geo_agent.py
│   │   ├── topic_agent.py
│   │   └── video_pipeline_agent.py
│   ├── integrations/            # 外部平台客户端
│   │   ├── feishu.py  wecom.py  bitable.py
│   ├── video/                   # 短视频模块
│   │   ├── fetcher.py           # 礼貌抓取 + OG 元数据
│   │   └── analyzer.py          # 大模型内容分析
│   ├── geo/tools.py             # 地理编码/距离/范围
│   ├── knowledge/               # 向量知识库
│   │   ├── embeddings.py        # 向量化（含本地兜底）
│   │   ├── vector_store.py      # numpy 向量库
│   │   └── ingest.py            # 入库/检索封装
│   ├── topic/                   # AI 选题模块
│   │   ├── selection.py         # TopicSelector：批量生成 + 质量增强
│   │   ├── quality.py           # 去重/打分/热度优选（纯标准库，离线可跑）
│   │   └── store.py             # 选题批次存储 + 人工审核
│   ├── video_gen/               # AI 视频生成（异步，9:16 / 16:9，四种方式）
│   │   ├── client.py            # VideoGenClient（mock/generic，竖版自动转置）
│   │   └── generator.py         # VideoTaskManager：提交/轮询/超时/重试/通知
│   ├── tools/                   # 工具聚合 + 各业务工具（共 16 个）
│   └── routers/                 # API 路由
│       ├── agent.py  short_video.py  geo.py  knowledge.py  topic.py
├── frontend/                    # 零依赖 Web 控制台（index.html / styles.css / app.js）
├── scripts/
│   ├── ingest.py                # 知识库入库 CLI
│   └── selfcheck.py             # 发布前一键自检
├── tests/                       # pytest 用例（12 个，无需密钥）
├── data/vector_store/           # 向量库与任务持久化（运行时生成，已挂卷）
└── logs/                        # 日志（运行时生成）
```

---

## 十五、本次维护记录

本次维护对全量代码做了静态分析与运行验证，修复并改进如下（均已实测）：

| # | 问题 | 位置 | 处理 |
|---|---|---|---|
| 1 | **确定性 Bug**：`run_topic_to_video_pipeline()` 使用了未导入的 `settings`，调用 `/api/pipeline/topic-to-video` 且 `write_to_bitable=true`（默认值）时必抛 `NameError` → 500 | `app/agents/video_pipeline_agent.py:78` | 补 `from app.core.config import settings` |
| 2 | **测试跑不起来**：裸 `pytest -q` 报 `ModuleNotFoundError: No module named 'app'`（README 原本推荐该命令） | 项目根 | 新增 `conftest.py`，把项目根加入 `sys.path` |
| 3 | 缺 API Key 返回 500「服务器内部错误」，语义不准（配置问题 ≠ 服务器故障） | `app/agent/llm.py` | 改为 `BusinessError(400)`，返回可执行的中文提示 |
| 4 | 全链路接口抓取失败返回 500，与 `/api/short-video/analyze-url` 的 502 不一致 | `app/routers/topic.py` | 统一为 502，且业务异常（400/401）原样透出 |
| 5 | Docker 构建会把 `.env` 打进镜像，存在密钥泄漏风险 | 项目根 | 新增 `.dockerignore` |
| 6 | Dockerfile 内置清华源，本机实测 SSL 握手失败导致构建中断 | `Dockerfile` | 默认改为阿里云源 + `PIP_INDEX_URL` 支持 `--build-arg` 覆盖 + 失败自动回退官方源 |
| 7 | `DEEPSEEK_BASE_URL` 默认 `/v3` 非官方推荐值 | `config.py` / `llm.py` / `.env.example` | 改为官方 `https://api.deepseek.com`（`/v1`、`/v3` 实测仍可用） |
| 8 | 清理未使用的 import（`json`/`field`/`math`/`uuid` 等） | 5 个文件 | 已移除 |
| 9 | 缺少一键自检手段 | `scripts/selfcheck.py` | 新增：编译 / 导入 / 工具注册 / 路由 / 测试 五项检查 |
| 10 | `python-multipart` 仅作为间接依赖 | `requirements.txt` | 显式声明，消除 Starlette 版本兼容警告 |

### 验证记录

- **环境**：Windows 11 + Python 3.13.12（隔离虚拟环境）
- **依赖安装**：阿里云镜像成功安装全部 40+ 依赖
- **静态分析**：`pyflakes` 全项目扫描，**无未定义名称、无致命错误**
- **单元测试**：`pytest -q` → **12 passed**
- **一键自检**：`python scripts/selfcheck.py` → **全部通过（退出码 0）**
- **接口冒烟**（实际启动 uvicorn + curl）：
  - `/health` → 200 OK
  - 知识库入库 + 检索 → 正常返回命中片段
  - 视频提交 → 轮询 → `succeeded` + `video_url`（mock 全链路）
  - 参数校验：缺 ref_image / 超时长 → 400 并给出明确原因
  - 缺 Key → 400；无效 Key → 401；全链路抓取失败 → 502
  - 前端：`/`（21KB HTML）、`/docs`、`/app.js`、`/styles.css` 均 200 正常
  - 工具注册：16 个工具全部注册，4 个 Agent 引用的工具名全部命中
- **未验证项**：Docker 镜像构建与 `docker compose up`（本机未安装 Docker）；相关命令按 Dockerfile / compose 配置静态核对可用。

---

## 许可证

MIT License
