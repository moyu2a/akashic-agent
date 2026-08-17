# LongMemEval Phase A v4 Report Breakdown

生成时间：2026-08-17

## 一句话结论

v4 的严格 deterministic 通过率是 `27/50 = 54.0%`，但这个数字低估了当前链路的真实表现。失败的 23 条里，`23/23` 都带有 `supported_but_deterministic_mismatch`，`45/50` 全量 case 能在发送给模型的证据中检测到 supporting fact。也就是说，当前主要问题已经不是“记忆没有被送到模型”，而是“公开集 gold answer 与模型自然回答之间的评分层不够鲁棒”。

## 三层读数

| 层级 | 指标 | 当前结果 | 应如何解释 |
| --- | --- | ---: | --- |
| L0 工程链路 | completed / error / timeout / request snapshot | 50/50, 0 error, 0 timeout, 0 snapshot mutation | 评测链路可信，可以用来做后续 Phase B。 |
| L1 严格分数 | deterministic pass | 27/50 | 可横向比较 v3/v4，但偏保守。 |
| L2 证据支持 | supporting_fact_hit | 45/50 | 多数 case 证据已进入模型上下文。 |
| L3 语义复核 | semantic_review_needed | 18/50 | 这些不应只看 contains，需要 judge/rubric。 |

## v3 到 v4 的真实变化

| 项 | v3 | v4 | 判断 |
| --- | ---: | ---: | --- |
| strict pass | 21/50 | 27/50 | 明确提升。 |
| language mismatch | 46/50 observed | 12/50 | 全局中文诱导基本修掉，但还有残留。 |
| request_time 锚点 | 线上日期污染 | 0/50 使用线上日期 | 日期链路修复有效。 |
| request capture 污染 | 存在 answer 写回污染 | 0/50 snapshot mutation | 调试证据可信。 |
| sent evidence gold hit | 27/50 | 28/50 | 证据直含 gold 只小幅提升。 |
| supporting fact hit | v3 未统计 | 45/50 | v4 新增诊断显示召回/注入不是主瓶颈。 |

## 按题型拆解

| Category | Pass | Fail | 主要问题 |
| --- | ---: | ---: | --- |
| abstention | 0/3 | 3/3 | 模型表达了证据不足，但 deterministic scorer 不接受同义拒答。 |
| knowledge-update | 4/7 | 3/7 | 多数回答语义正确，但附带新旧状态解释或中文表达导致 contains 不稳定。 |
| multi-session | 8/12 | 4/12 | 数值/多跳题常答对核心值，但没有严格匹配 gold 字符串。 |
| single-session-assistant | 5/6 | 1/6 | 基本可用，剩余是长枚举答案与 gold 表述不完全一致。 |
| single-session-preference | 0/3 | 3/3 | 这类 gold 是偏好 rubric，不适合 exact/contains。 |
| single-session-user | 4/6 | 2/6 | 剩余主要是英文问题中文回答造成 scorer false negative。 |
| temporal-reasoning | 6/13 | 7/13 | 日期锚点已修，但 inclusive/exclusive day count、长列表和语言仍影响判分。 |

## 失败归因总表

| Attribution | Count | 含义 | 优先级 |
| --- | ---: | --- | --- |
| supported_but_deterministic_mismatch | 23 | 证据支持存在，但 strict scorer 没判过。 | P0：拆分 semantic/rubric score。 |
| semantic_review_needed | 18 | 偏好、长答案、同义表达或复杂推理需要复核。 | P0：引入 judge 或人工抽检。 |
| language_mismatch_scorer_false_negative_possible | 6 | 英文问题仍被中文回答。 | P1：继续收紧全局语言跟随。 |
| abstention_intent_passed_deterministic_fail | 1 | 拒答意图正确但 gold 文本不匹配。 | P1：abstention 单独评分。 |

## 失败 Case 分层

| Case | Category | 主因 | 当前答案形态 | 处理建议 |
| --- | --- | --- | --- | --- |
| `60bf93ed_abs` | abstention | scorer false negative | 明确说没有 iPad case 购买/到货记录。 | abstention intent 判 PASS，strict 仍保留 FAIL。 |
| `88432d0a_abs` | abstention | scorer false negative | 明确说过去两周没有 egg tart 烘焙记录。 | abstention intent 判 PASS。 |
| `c8090214_abs` | abstention | scorer false negative | 明确说无法判断，因为没有买 iPad 的证据。 | abstention intent 判 PASS。 |
| `031748ae` | knowledge-update | scorer false negative | 回答了刚入职带 4 人、现在 5 人。 | normalized/semantic 应判 PASS。 |
| `830ce83f` | knowledge-update | language + scorer | 中文回答 Rachel 搬回 suburbs。 | 同语言修正后应判 PASS。 |
| `e493bb7c` | knowledge-update | scorer false negative | 回答画目前挂在 bedroom/bed 上方。 | semantic 应判 PASS。 |
| `60472f9c` | multi-session | scorer false negative | 回答 Two，并列出两个项目。 | 数字同义 `two=2` 应判 PASS。 |
| `6456829e` | multi-session | answer format issue | 回答 5 棵番茄 + 3 棵黄瓜，但未合计 8。 | 可判部分正确；prompt 可要求先给最终数值。 |
| `b3c15d39` | multi-session | scorer false negative | 回答 5 days，gold 也接受 5 days。 | normalized 应判 PASS。 |
| `gpt4_7fce9456` | multi-session | language + long answer | 中文长答列出 4 处房产和原因。 | 语义/rubric 复核。 |
| `ceb54acb` | single-session-assistant | long answer mismatch | 列出四个术语，但格式与 gold 不完全一致。 | list-set overlap scorer。 |
| `0a34ad58` | single-session-preference | rubric needed | 使用 Suica 等个性化信息，但未覆盖 TripIt。 | rubric judge，可能部分通过。 |
| `54026fce` | single-session-preference | rubric needed | 围绕 virtual coffee breaks 给建议。 | rubric judge。 |
| `a89d7624` | single-session-preference | rubric needed | 利用 Brandon Flowers/live music 记忆给 Denver 建议。 | rubric judge，可能较高。 |
| `4100d0a0` | single-session-user | language + scorer | 中文回答 Irish and Italian。 | 同语言修正后应判 PASS。 |
| `f4f1d8a4` | single-session-user | language + scorer | 中文回答 sister。 | 同语言修正后应判 PASS。 |
| `0bc8ad93` | temporal-reasoning | over-answer / ambiguity | 对 two months ago 与 earlier museum visit 做了区分，没有直接输出 No。 | prompt 要求先给最终答案，再解释。 |
| `eac54add` | temporal-reasoning | scorer false negative | 回答 signed a contract with first freelance client。 | semantic 应判 PASS。 |
| `gpt4_1d80365e` | temporal-reasoning | language + accepted variant | 中文回答 3 天，gold 接受 2/3 天。 | 同语言修正后应判 PASS。 |
| `gpt4_4929293a` | temporal-reasoning | language + scorer | 中文回答 Michael engagement party 先发生。 | 同语言修正后应判 PASS。 |
| `gpt4_8279ba02` | temporal-reasoning | scorer false negative | 回答 10 days ago，gold 接受 10/11 days。 | normalized 应判 PASS。 |
| `gpt4_93159ced` | temporal-reasoning | scorer false negative | 回答 4 years 9 months。 | normalized 应判 PASS。 |
| `gpt4_d6585ce8` | temporal-reasoning | language + long list | 中文列出音乐活动顺序。 | 同语言 + ordered-list overlap scorer。 |

## 当前分数应该如何汇报

建议以后报告拆成三行，而不是只报一个 accuracy：

| 分数 | 当前值 | 用途 |
| --- | ---: | --- |
| strict deterministic accuracy | 27/50 = 54.0% | 与 v3/v4、后续版本做稳定横向比较。 |
| evidence-supported answer rate | 45/50 = 90.0% | 衡量记忆召回和证据注入链路。 |
| semantic/rubric pending rate | 18/50 = 36.0% | 标记需要 judge 或人工复核的样本，不应直接算系统失败。 |

不要把 `supporting_fact_hit=45/50` 当成准确率。它只能说明证据进入了模型上下文，不代表最终答案一定正确。

## 下一步建议

1. 保留 strict deterministic score，不要删除，作为可重复基线。
2. 新增 `semantic_judge_score`：只对 deterministic fail 且非 tool/error 的 case 进行二级判分。
3. 单独实现 abstention scorer：识别 “not enough information / not mentioned / cannot determine / 不知道 / 无法确认”。
4. preference 类不要用 contains，改用 rubric judge，检查是否利用用户已有资源、历史偏好和避免项。
5. 对数值题加入 answer normalization：`two=2`、`5 + 3 = 8`、`10 days ago` 与 `10 days ago. 11 days acceptable`。
6. 继续处理语言残留：目标是 English-question language mismatch 从 `12/50` 降到 `<=5/50`。

## Phase B 前的判断

Phase A v4 的工程 gate 已经满足，可以进入 Phase B。但 Phase B 的报告必须同步采用三层指标，否则 Full 500 条里 preference、abstention、temporal long-answer 会继续被 strict scorer 系统性低估。
