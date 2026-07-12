# RAG Docs

这个目录记录 Document RAG、GraphRAG、LLM Wiki、LoRA/RAG 相关设计、实验和面试表达。

## 文档列表

- [09-document-rag-extension-plan.md](./09-document-rag-extension-plan.md): Document RAG、GraphRAG、LLM Wiki、LoRA 等后续延伸计划。
- [10-document-rag-design.md](./10-document-rag-design.md): Document RAG 设计边界、数据结构、工具接口和接入方式。
- [11-document-rag-implementation-plan.md](./11-document-rag-implementation-plan.md): Document RAG 两周实施计划和任务状态。
- [12-document-rag-params-experiments.md](./12-document-rag-params-experiments.md): Document RAG 参数实验记录。
- [13-document-rag-evaluation.md](./13-document-rag-evaluation.md): Document RAG 评估集、指标和结果记录。
- [14-document-rag-interview-notes.md](./14-document-rag-interview-notes.md): Document RAG / GraphRAG / LLM Wiki 相关面试表达。
- [15-document-rag-p0-p3-implementation-plan.md](./15-document-rag-p0-p3-implementation-plan.md): Document RAG 第一阶段 P0-P3 文件级实现计划。
- [16-document-rag-p4-p6-implementation-plan.md](./16-document-rag-p4-p6-implementation-plan.md): Document RAG 第二阶段 P4-P6 实现计划、验证结果和手动测试记录。
- [17-document-rag-p7-tools-plan.md](./17-document-rag-p7-tools-plan.md): Document RAG 工具接入 P7-P8 实现计划。
- [18-document-rag-p9-citation-plan.md](./18-document-rag-p9-citation-plan.md): Document RAG 回答引用规则 P9 实现计划。
- [19-document-rag-p10-intent-preload-plan.md](./19-document-rag-p10-intent-preload-plan.md): Document RAG 强文档意图 turn-local 工具预加载计划。
- [20-document-rag-p10a2-tool-boundary-design.md](./20-document-rag-p10a2-tool-boundary-design.md): P10a.2 Turn Tool Boundary Manager 设计，覆盖工具访问、预算、证据完成、账本和审计边界。

## 使用规则

- 讨论 RAG 路线、设计、实验参数和评估结果时，更新对应专题文档。
- 发现 RAG 方向的阶段性问题或改进结果时，统一更新 `../governance/03-domain-evolution.md` 的 RAG 分节。
- 形成完整问题闭环时，再同步沉淀到 `../governance/06-star-log.md`。

## 后续更新提示词

```text
请根据本次 RAG 讨论/设计/实验结果，更新 my_md/rag 下相关文档；如果涉及 RAG 方向演进，请同步更新 my_md/governance/03-domain-evolution.md 的 RAG 分节。
```
