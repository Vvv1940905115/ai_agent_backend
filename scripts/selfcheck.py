#!/usr/bin/env python
"""
发布前一键自检脚本（无需任何密钥 / 无需联网）

用法：
    python scripts/selfcheck.py

依次执行 5 项检查，全部通过才打印「全部通过」并以 0 退出：
  1. 语法编译   —— compileall 检查 app / tests / scripts / conftest.py
  2. 导入检查   —— 能否成功 import app.main（暴露依赖缺失、循环导入等问题）
  3. 工具注册   —— @tool 装饰器注册的工具数量，以及各 Agent 引用的工具名是否都已注册
  4. 路由清单   —— 打印 FastAPI 实际注册的接口，确认路径符合预期
  5. 单元测试   —— 调用 pytest 跑全量用例（知识库走 local embedding、视频走 mock）

任何一项失败都会以非 0 退出码结束，便于接入 CI。
"""
import os
import subprocess
import sys

# 保证从任意目录执行都能 import 项目根下的 app 包
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("EMBEDDING_PROVIDER", "local")
os.environ.setdefault("VIDEO_GEN_PROVIDER", "mock")
os.environ.setdefault("VIDEO_GEN_MOCK_DELAY", "0")

FAILED = []


def step(title: str):
    print(f"\n{'=' * 60}\n[检查] {title}\n{'=' * 60}")


def fail(msg: str):
    FAILED.append(msg)
    print(f"  [失败] {msg}")


def ok(msg: str):
    print(f"  [通过] {msg}")


# ---------- 1. 语法编译 ----------
step("1/5 语法编译检查（compileall）")
targets = ["app", "tests", "scripts", "conftest.py"]
r = subprocess.run([sys.executable, "-m", "compileall", "-q", *targets],
                   cwd=ROOT, capture_output=True, text=True)
if r.returncode == 0 and not r.stdout.strip():
    ok("全部 .py 文件编译通过，无语法错误")
else:
    fail(f"存在语法错误：\n{r.stdout}{r.stderr}")

# ---------- 2. 导入检查 ----------
step("2/5 导入检查（import app.main）")
try:
    # 注意：必须用别名。因为后面 `import app.tools` 会把局部名 app 重新绑定为
    # 顶层包 app（Python import 语句的副作用），直接用 app 会指向包而非 FastAPI 实例。
    from app.main import app as fastapi_app  # noqa: F401
    ok("app.main 导入成功（依赖齐全，无循环导入）")
except Exception as e:
    fail(f"导入失败：{type(e).__name__}: {e}")
    print("\n自检中止：请先解决导入问题。")
    sys.exit(1)

# ---------- 3. 工具注册 ----------
step("3/5 工具注册检查（Agent 可用工具）")
try:
    import app.tools  # noqa: F401  触发注册
    from app.agent.tool import TOOL_REGISTRY
    from app.agents.geo_agent import GeoAgent
    from app.agents.short_video_agent import ShortVideoAgent
    from app.agents.topic_agent import TopicAgent
    from app.agents.video_pipeline_agent import VideoPipelineAgent

    print(f"  已注册工具 {len(TOOL_REGISTRY)} 个：")
    for n in sorted(TOOL_REGISTRY):
        print(f"    - {n}")

    for cls in (GeoAgent, ShortVideoAgent, TopicAgent, VideoPipelineAgent):
        missing = [t for t in cls.tool_names if t not in TOOL_REGISTRY]
        if missing:
            fail(f"{cls.__name__} 引用了未注册的工具：{missing}")
        else:
            ok(f"{cls.__name__} 的 {len(cls.tool_names)} 个工具均已注册")
except Exception as e:
    fail(f"工具注册检查异常：{type(e).__name__}: {e}")

# ---------- 4. 路由清单 ----------
step("4/5 接口路由清单")
try:
    rows = []
    for route in fastapi_app.routes:
        methods = getattr(route, "methods", None)
        if methods:
            rows.append((sorted(m for m in methods if m != "HEAD")[0], route.path))
    for m, p in sorted(rows, key=lambda x: x[1]):
        print(f"    {m:6s} {p}")
    ok(f"共 {len(rows)} 个接口路由")
except Exception as e:
    fail(f"路由读取失败：{type(e).__name__}: {e}")

# ---------- 5. 单元测试 ----------
step("5/5 单元测试（pytest）")
r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT,
                   capture_output=True, text=True)
tail = (r.stdout or "").strip().splitlines()
print("  " + ("\n  ".join(tail[-6:]) if tail else "(无输出)"))
if r.returncode == 0:
    ok("pytest 全部通过")
else:
    fail("pytest 存在失败用例")

# ---------- 汇总 ----------
print("\n" + "=" * 60)
if FAILED:
    print(f"自检未通过，共 {len(FAILED)} 项问题：")
    for i, m in enumerate(FAILED, 1):
        print(f"  {i}. {m}")
    sys.exit(1)
print("全部通过：代码无语法错误、依赖齐全、工具注册正常、测试通过。")
print("=" * 60)
sys.exit(0)
