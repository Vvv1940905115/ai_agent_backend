"""
pytest 根目录配置文件（保持空实现即可，作用是让 pytest 把项目根目录加入 sys.path）。

背景：tests/ 目录下没有 __init__.py，pytest 默认只把 tests/ 目录插入 sys.path，
导致 `pytest -q` 时 `from app.main import app` 报 ModuleNotFoundError。
pytest 会自动加载 rootdir 下的 conftest.py，并把它所在目录插入 sys.path，
从而让裸 `pytest -q` 与 `python -m pytest -q` 表现一致。
"""
