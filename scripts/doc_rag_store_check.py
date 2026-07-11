from agent.config_models import DocRagConfig
from doc_rag.loader import MarkdownLoader
from doc_rag.chunker import MarkdownChunker
from doc_rag.models import DocumentRecord
from doc_rag.store import DocRagStore

cfg = DocRagConfig(source_root=".")
doc = MarkdownLoader(cfg).load_all().documents[0]
chunks = MarkdownChunker(cfg.chunking).chunk(doc)

record = DocumentRecord(
    doc_id=doc.doc_id,
    source_path=doc.source_path,
    title=doc.title,
    content_hash=doc.content_hash,
    file_mtime=doc.file_mtime,
    file_size=doc.file_size,
)

store = DocRagStore("/tmp/doc_rag_manual_test.db", vec_dim=1024)
store.replace_document_chunks(record, chunks)
print("document:", store.get_document(doc.source_path))
print("first_chunk:", store.get_chunk(chunks[0].chunk_id))
store.close()

