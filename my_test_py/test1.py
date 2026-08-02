from agent.config_models import DocRagConfig
from doc_rag.loader import MarkdownLoader

cfg = DocRagConfig(source_root=".")
result = MarkdownLoader(cfg).load_all()

print("documents:", len(result.documents))
for doc in result.documents:
    print(doc.source_path, doc.title, doc.content_hash[:8])

print("errors:", [(e.source_path, e.error_type) for e in result.errors])
