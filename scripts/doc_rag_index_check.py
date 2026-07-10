from __future__ import annotations

import argparse
import asyncio

from agent.config import load_config
from core.net.http import (
    SharedHttpResources,
    clear_default_shared_http_resources,
    configure_default_shared_http_resources,
)
from doc_rag.indexer import DocRagIndexer, IndexOptions


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Document RAG indexing once.")
    parser.add_argument("--config", default="config.toml", help="config file path")
    parser.add_argument("--rebuild", action="store_true", help="force reindex")
    parser.add_argument("--dry-run", action="store_true", help="scan without writing")
    return parser


async def _main() -> None:
    args = _parser().parse_args()
    cfg = load_config(args.config)
    http_resources = SharedHttpResources()
    configure_default_shared_http_resources(http_resources)
    try:
        summary = await DocRagIndexer(cfg).run(
            IndexOptions(rebuild=args.rebuild, dry_run=args.dry_run)
        )
    finally:
        clear_default_shared_http_resources(http_resources)
        await http_resources.aclose()

    print("status:", summary.status)
    print("run_id:", summary.run_id)
    print("docs_scanned:", summary.docs_scanned)
    print("docs_indexed:", summary.docs_indexed)
    print("docs_skipped:", summary.docs_skipped)
    print("docs_deleted:", summary.docs_deleted)
    print("docs_failed:", summary.docs_failed)
    print("chunks_created:", summary.chunks_created)
    print("embedding_failed:", summary.embedding_failed)
    print("store_path:", cfg.doc_rag.store_path)
    if summary.error:
        print("error:", summary.error)


if __name__ == "__main__":
    asyncio.run(_main())
