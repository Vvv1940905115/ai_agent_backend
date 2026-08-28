"""
工具聚合层。

把各业务模块的工具（@tool 装饰的函数）在此统一 import，
确保服务启动时 TOOL_REGISTRY 已全部注册；Agent 直接按名字引用即可。
"""
from app.agent.tool import TOOL_REGISTRY  # noqa: F401

# 触发各模块装饰器注册（必须 import 才有副作用）
from app.tools import integration_tools  # noqa: F401
from app.tools import video_tools  # noqa: F401
from app.geo import tools as geo_tools  # noqa: F401  (GEO 工具在 app/geo/tools.py)
from app.tools import knowledge_tools  # noqa: F401
from app.tools import topic_tools  # noqa: F401  (新增：AI 选题工具)
from app.tools import video_gen_tools  # noqa: F401  (新增：文生视频/图生视频工具)
