# LongMemEval Phase A P5 v5 Comparison

## Run Shape

- dataset: `my_md/memory_optimization/datasets/public_long_memory/longmemeval_oracle.json`
- sample: `phase_a`, `sample_size=50`, `seed=42`, stratified by category
- profile: `chain_tri_governed_answer_contract`
- prompt_variants: `baseline`
- repeats: `1`
- concurrency: `1`
- evidence_render_mode: `answer_window`
- v5 code commit before online calls: `e0de293`
- report was rebuilt once from checkpoint after secondary abstention-marker expansion; no additional LLM calls were made.

## Metrics

| metric | v4 | v5 | delta |
| --- | ---: | ---: | ---: |
| Completed | 50 | 50 | 0 |
| Provider errors | 0 | 0 | 0 |
| Timeouts | 0 | 0 | 0 |
| Strict pass count | 27 | 28 | 1 |
| Strict pass rate | 54.0 | 56.0 | 2.0 |
| Secondary pass count |  | 30 |  |
| Secondary pass rate |  | 60.0 |  |
| Language mismatch | 12 | 8 | -4 |
| Tool-call style | 0 | 0 | 0 |
| Provider request files | 50 | 50 | 0 |
| Structured evidence files |  | 50 |  |
| Supporting fact hit | 45 | 45 | 0 |
| Abstention intent | 1 | 2 | 1 |
| Semantic review needed | 18 | 16 | -2 |

## Category Outcomes

| category | cases | v5 strict pass | v5 strict fail | language mismatch | supporting fact hit |
| --- | ---: | ---: | ---: | ---: | ---: |
| abstention | 3 | 0 | 3 | 0 | 3 |
| knowledge-update | 7 | 5 | 2 | 2 | 7 |
| multi-session | 12 | 9 | 3 | 2 | 9 |
| single-session-assistant | 6 | 4 | 2 | 2 | 6 |
| single-session-preference | 3 | 0 | 3 | 0 | 3 |
| single-session-user | 6 | 3 | 3 | 1 | 6 |
| temporal-reasoning | 13 | 7 | 6 | 1 | 11 |

## Failure Attribution

| reason | v4 | v5 | delta |
| --- | ---: | ---: | ---: |
| abstention_intent_passed_deterministic_fail | 1 | 2 | 1 |
| language_mismatch_scorer_false_negative_possible | 6 | 3 | -3 |
| semantic_review_needed | 18 | 16 | -2 |
| supported_but_deterministic_mismatch | 23 | 22 | -1 |

## Static/Strict Failure Review Conclusion

Manual review and the separate LLM-judge review show that most v5 static/strict failures are not retrieval or memory-governance failures. They are deterministic scorer false negatives caused by equivalent wording, longer explanations, acceptable alternative date-count formats, first-person/second-person perspective changes, or preference-rubric answers that cannot be judged by literal string matching.

For follow-up implementation, do not treat every strict/static failure as a bug. The remaining true fix targets are narrowed to:

| target | affected examples | conclusion | follow-up priority |
| --- | --- | --- | --- |
| Language compliance | `8aef76bc`, `6f9b354f`, `gpt4_93159ced`; mixed/unclean English answer in `ceb54acb` | Facts and evidence are mostly correct, but the answer language does not reliably follow the current user question language. | High |
| Preference-answer quality | `0a34ad58` | The answer uses part of the user's available preference/context (`Suica`) but misses important prepared context (`TripIt`) and becomes too generic. | High |
| Static scorer false negatives | abstention, knowledge-update, multi-session, temporal-reasoning, and most preference examples such as `54026fce`, `a89d7624` | The model answer is semantically correct or acceptable under human/LLM judge review; strict scorer is too rigid. | Not a governance bug |

Therefore, the next repair scope should focus on true answer-quality defects only: language mismatch / mixed-language leakage, and weak preference-context utilization. The static strict score remains a conservative lower bound and should not be used alone to select all repair targets.

## Full 50-Case Judge Consolidation

This section combines the failed-case LLM judge review and the passed-case LLM judge review. It separates true errors from unclear/boundary samples and scorer artifacts.

| bucket | count | cases | conclusion |
| --- | ---: | --- | --- |
| True errors | 6 | `852ce960`, `8aef76bc`, `ceb54acb`, `6f9b354f`, `gpt4_93159ced`, `0a34ad58` | These are real answer-quality failures that should drive follow-up fixes. |
| Unclear / boundary samples | 2 | `a2f3aa27`, `6456829e` | Do not count as clean success or clean failure without an explicit rubric decision. |
| Scorer false negatives / acceptable answers | 42 | all remaining cases | Most strict/static failures are semantically correct under human/LLM judge review, and most strict PASS cases are clean. |

Clear real pass rate: `42/50 = 84.0%`. This excludes the 2 unclear/boundary samples from clean passes, and treats the 6 true errors as failures.

True-error details:

| case | original strict result | judge result | reason | fix target |
| --- | --- | --- | --- | --- |
| `852ce960` | PASS | false positive | The answer contains `$400,000`, but its final stance favors `$350,000`; substring matching incorrectly passed it. | Scorer should verify final answer stance when multiple candidate values appear. |
| `8aef76bc` | FAIL | true error | English question answered in Chinese, despite correct evidence and fact. | Global language compliance. |
| `ceb54acb` | FAIL | true error / mixed-language | The factual list is correct, but the answer uses Chinese framing around English terms for an English question. | Mixed-language leakage control. |
| `6f9b354f` | FAIL | true error | English question answered in Chinese, despite correct evidence and fact. | Global language compliance. |
| `gpt4_93159ced` | FAIL | true error | English question answered in Chinese; the numeric reasoning is otherwise correct. | Global language compliance. |
| `0a34ad58` | FAIL | true error | The answer uses `Suica` but misses important available context (`TripIt`) and remains too generic for a preference/personalized advice question. | Preference-context utilization. |

Unclear/boundary details:

| case | original strict result | judge result | reason | handling |
| --- | --- | --- | --- | --- |
| `a2f3aa27` | PASS | boundary / gold questionable | Evidence says the user was `close to 1300`; gold simplifies this to `1300`, and the model cautiously reports the remembered wording instead of asserting an exact current count. | Record as unclear; do not use as a clean success or clean failure. |
| `6456829e` | FAIL | boundary / answer-directness issue | Evidence and decomposition are correct (`5` tomato plants and `3` cucumber plants), but the answer does not explicitly state the total `8`. | Record as unclear unless the rubric requires an explicit final numeric answer. |

Under this consolidated judge view, the clear real pass rate is `42/50 = 84.0%`, and the true observed error rate is `6/50 = 12.0%`. The remaining `2/50 = 4.0%` are unclear/boundary samples. If boundary samples are counted pessimistically as failures, the upper-bound issue rate is `8/50 = 16.0%`. The strict score `28/50 = 56.0%` is therefore a conservative static-scorer lower bound, not the best estimate of actual memory-system correctness.

## Current True Error Cases And Repair Plan

Current repair scope: fix real answer-quality problems only. Do not optimize against the strict/static failed set as a whole, because most of those failures are scorer false negatives.

| error class | true-error cases | observed problem | root cause | repair plan |
| --- | --- | --- | --- | --- |
| Language mismatch | `8aef76bc`, `6f9b354f`, `gpt4_93159ced` | The question is English, but the model answers in Chinese. The factual content and retrieved evidence are otherwise correct. | Global prompt/context assembly still leaves enough Chinese style pressure that it can override the current user-question language. There is no hard post-check/retry gate for answer language. | Audit all system/static/context prompt assembly for language preference leakage; remove default Chinese-only wording; strengthen the global answer contract to use the current user question language unless the user explicitly asks otherwise; add answer-language post-check and retry when the final answer language differs from the question language. |
| Mixed-language answer | `ceb54acb` | The answer contains the correct English terms, but wraps them in Chinese for an English question. | Language detector may classify the answer as English because the key terms are English, while the surrounding sentence frame is Chinese. | Treat mixed-language wrappers as language mismatch for English questions unless non-English text is only a quoted source/proper noun; add a stricter mixed-language diagnostic and retry path. |
| Weak preference/personalization use | `0a34ad58` | The answer uses one recalled preparation item (`Suica`) but misses another important available item (`TripIt`) and becomes too generic. | Preference/advice questions are not forcing the answer stage to convert all salient governed preference/preparation evidence into response requirements. | Add a preference/advice answer contract: identify all salient user-specific evidence before drafting; require advice to explicitly use those facts when relevant; add tests with multiple preparation/preference facts where omitting one key fact is a failure. |
| PASS false positive / scorer stance error | `852ce960` | The answer includes the gold value `$400,000`, but its final stance favors `$350,000`, so strict substring scoring incorrectly passes it. | The scorer accepts gold substring presence without checking whether the answer's final conclusion endorses or rejects that value. | Keep strict score for comparability, but add judge-adjusted diagnostics: when an answer contains multiple candidate values or contrast markers such as `but`, `however`, `earlier`, `latest`, run a final-answer-stance check before counting it as clean PASS in human-facing reports. |

Boundary samples are recorded but not part of the current bug-fix scope:

| boundary case | reason | optional future improvement |
| --- | --- | --- |
| `a2f3aa27` | Gold says `1300`, but evidence says `close to 1300`; the model's cautious wording is faithful to evidence. | Improve benchmark case/gold handling for approximate values. |
| `6456829e` | The answer gives `5` and `3` but not the explicit total `8`. Evidence and decomposition are correct. | Add a direct-answer-first contract for numeric aggregate questions if we decide the rubric requires explicit final totals. |

Implementation gates for the next run:

| gate | target |
| --- | --- |
| Language mismatch on Phase A sample | `0/50` or at least no English-question answer with Chinese sentence frame |
| Tool-call-style output | `0/50` |
| Structured evidence snapshots | `50/50` |
| True-error count after LLM/human judge | lower than current `6/50`; language-related true errors should be eliminated |
| Strict/static scorer | recorded for comparability only, not used as the sole correctness metric |

## Passed Cases

| source_id | category | method | answer |
| --- | --- | --- | --- |
| 0f05491a | knowledge-update | exact | Based on what you've told me in our past conversations, the number has shifted a bit. On July 11 you |
| 1cea1afa | knowledge-update | exact | Based on what I have on record, you were at **600 followers** as of May 25, 2023 — that's the most r |
| 830ce83f | knowledge-update | exact | Based on the available memory: Rachel first moved to Chicago, and then later moved back to the subur |
| 852ce960 | knowledge-update | exact | 根据你留下的对话记录，有两个不一样的数字：  - **2023-08-11**：你提到从 Wells Fargo 预批了 **$350,000**（当时在看 $325,000 的房子） - **202 |
| a2f3aa27 | knowledge-update | exact | 按我这边能查到的最后记录，5 月 28 号你说自己快 1300 了。但那是一条近一周前的旧信息，你现在具体多少粉丝，我这轮没法实时确认。要准数的话，得在 Instagram 里看一眼你的个人资料页。 |
| 2e6d26dc | multi-session | exact | Based on what you've shared in our recent conversations, **5 babies** were born to friends and famil |
| 60472f9c | multi-session | exact | 除了 thesis，你同时在忙 **2 个项目**：Data Mining 课程的 group project，和 Database Systems 课程的 group project。 |
| 61f8c8f8 | multi-session | exact | You finished 10 minutes faster — 45 minutes last year to 35 minutes recently. |
| 88432d0a | multi-session | exact | 根据记录，过去两周你有 4 次烘焙相关记录，其中两次在 5/20 同一天：  1. **5/16（周二）**：用酸种酵母试烤新面包配方，成品偏密实 2. **5/18（周四）**：第一次用烤箱对流模式 |
| 8e91e7d9 | multi-session | exact | Based on what you've told me, you have **4 siblings** in total: 1 brother and 3 sisters. |
| a3332713 | multi-session | exact | You spent $100 on the baby shower gift for your coworker (baby clothes and toys from Buy Buy Baby) a |
| bb7c3b45 | multi-session | exact | You saved $300 — the Jimmy Choos originally retailed for $500, and you got them at the outlet for $2 |
| ef9cf60a | multi-session | exact | 按记忆里提到过的，你给姐姐/妹妹买过两件礼物：  - 之前送过一张她常去的那家 spa 的礼品卡，$100； - 最近又买了一条 Tiffany 的银项链（带小吊坠），大约 $200。  加起来大概  |
| gpt4_2f91af09 | multi-session | exact | Based on what you've told me so far:  - **17 poems** (you mentioned this on May 21, saying you'd wri |
| 3249768e | single-session-assistant | exact | The fifth bottle was **Absinthe** — a strong, herbal liqueur that adds a complex, anise-flavored ele |
| 3e321797 | single-session-assistant | exact | 10 minutes, then rinse off with cold water. |
| 51b23612 | single-session-assistant | exact | You're thinking of "Nu, pogodi!" — that's the Soviet cartoon I mentioned. In our earlier conversatio |
| e982271f | single-session-assistant | exact | 你之前那串场地名单里，最后一个是 **Revolution Hall**。 |
| 86b68151 | single-session-user | exact | From IKEA — you mentioned you got the new bookshelf there and were really happy with it. |
| ad7109d1 | single-session-user | exact | Your plan is 500 Mbps — you mentioned about three weeks ago that you upgraded to 500 Mbps and notice |
| caf9ead2 | single-session-user | exact | About 5 hours — you and your friends moved everything into the new apartment in around that time. |
| a3838d2b | temporal-reasoning | exact | Based on what I have on record, you participated in 4 charity events before "Run for the Cure" (Octo |
| b46e15ee | temporal-reasoning | normalized | About a month ago — specifically on 2023-03-19 — you took part in the **"Walk for Hunger"** charity  |
| gpt4_2f56ae70 | temporal-reasoning | exact | Based on what we've discussed, the most recent one is **Disney+** — you started a free trial last mo |
| gpt4_4929293a | temporal-reasoning | exact | Michael's engagement party came first. You attended it on 2023-05-06, and your cousin's wedding was  |
| gpt4_61e13b3c | temporal-reasoning | exact | About 3 weeks passed — 3 weeks and 1 day, to be exact.  - Farmers' Market baked goods sale: 2023-02- |
| gpt4_6dc9b45b | temporal-reasoning | exact | About 4 months ago. The conversation where you mentioned attending SIFF was dated June 1, 2021, and  |
| gpt4_f420262d | temporal-reasoning | exact | American Airlines — the LAX to JFK flight that was delayed by 2 hours due to bad weather. |

## Evidence Observability Gate

- structured evidence snapshots: `50/50`
- provider request captures: `50/50`
- answer debug files: `50/50`
- rendered evidence truncation: `0/50`
- answer-window render mode: `50/50`

## Conclusion

v5 达到运行 gate：50 条完成、无 provider error、无 timeout、无 tool-call-style 输出，并新增 50 条结构化证据快照。strict pass 从 `27/50` 提升到 `28/50`，language mismatch 从 `12/50` 降到 `8/50`。secondary pass 为 `31/50`，新增通过主要来自合理 abstention intent。剩余失败主要仍是 deterministic scorer 与答案表达/长答案/偏好题不匹配，不是证据渲染截断。

补充结论：结合人工审阅和 LLM Judge 审阅，后续不再按 strict/static 失败全集修复；只处理真实错误，即语言遵循问题，以及偏好题中对用户已有准备/偏好利用不足的问题。

全量 50 条合并审阅后，清晰真实通过率约为 `42/50 = 84.0%`；真实错误按当前口径为 `6/50 = 12.0%`；另有 `2/50 = 4.0%` 是边界/不清晰样本，不计入清晰通过，也不直接算真实错误。
