from __future__ import annotations

import argparse
import asyncio

from agent.config import load_config
from doc_rag.retriever import DocRagRetriever


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one Document RAG retrieval.")
    parser.add_argument("query", nargs="*", help="query text")
    parser.add_argument("--config", default="config.toml", help="config file path")
    parser.add_argument("--top-k", type=int, default=None, help="override top_k")
    return parser


async def _main() -> None:
    args = _parser().parse_args()
    query = " ".join(args.query).strip() or "agent runtime"
    cfg = load_config(args.config)
    result = await DocRagRetriever(cfg).search(query, top_k=args.top_k)

    print("query:", query)
    print("trace_id:", result.trace_id)
    print("error:", result.error)
    print("latency_ms:", result.latency_ms)
    print("hits:", len(result.hits))
    for hit in result.hits:
        print("---")
        print("rank:", hit.rank)
        print("score:", hit.score)
        print("source_path:", hit.source_path)
        print("heading_path:", hit.heading_path)
        print("chunk_id:", hit.chunk_id)
        print("snippet:", hit.snippet)


if __name__ == "__main__":
    asyncio.run(_main())
