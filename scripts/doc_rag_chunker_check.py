from agent.config_models import DocRagConfig
from doc_rag.loader import MarkdownLoader
from doc_rag.chunker import MarkdownChunker

cfg = DocRagConfig(source_root=".")
doc = MarkdownLoader(cfg).load_all().documents[0]
chunks = MarkdownChunker(cfg.chunking).chunk(doc)

print("chunks:", len(chunks))
for c in chunks:
    print("---")
    print("chunk_id:", c.chunk_id)
    print("chunk_key:", c.chunk_key)
    print("heading_path:", c.heading_path)
    print("char_count:", c.char_count)
    print("metadata:", c.metadata)
    print(c.content[:120])

