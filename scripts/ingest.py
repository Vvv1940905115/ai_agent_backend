#!/usr/bin/env python
"""
知识库入库 CLI

用法：
  python scripts/ingest.py --text "企业知识文本..."
  python scripts/ingest.py --file ./docs/policy.txt --source 政策文档

依赖 settings.EMBEDDING_PROVIDER（local 无需密钥即可联调）。
"""
import argparse
import sys

from app.knowledge.ingest import ingest_document


def main():
    ap = argparse.ArgumentParser(description="知识库文档入库")
    ap.add_argument("--text", help="直接传入文本")
    ap.add_argument("--file", help="文本文件路径")
    ap.add_argument("--source", default="cli", help="来源标识")
    args = ap.parse_args()

    text = args.text
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    if not text:
        print("请提供 --text 或 --file")
        sys.exit(1)

    res = ingest_document(text, source=args.source)
    print("入库结果:", res)


if __name__ == "__main__":
    main()
