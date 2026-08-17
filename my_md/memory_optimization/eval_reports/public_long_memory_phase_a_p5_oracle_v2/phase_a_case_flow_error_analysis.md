# LongMemEval Phase A v2 Case Flow Error Analysis

## Run Summary

- `benchmark`: `longmemeval`
- `phase`: `phase_a`
- `profile`: `chain_tri_governed_answer_contract`
- `dataset_case_count`: `500`
- `sampled_case_count`: `50`
- `completed_call_count`: `50`
- `provider_error_count`: `0`
- `timeout_count`: `0`
- `malformed_checkpoint_line_count`: `0`
- `checkpoint_provenance_mismatch_count`: `0`
- `fresh_checkpoint_valid`: `True`
- `public_answer_pass_count`: `1`
- `public_answer_pass_rate`: `2.0`
- `scorer_unable_to_score_count`: `20`
- `scorer_unable_to_score_rate`: `40.0`
- `answer_rule_pass_rate`: `100.0`
- `memory_grounding_pass_rate`: `100.0`
- `avg_latency_ms`: `14447.68`
- `total_token_count`: `384489`
- `case_flow_records_jsonl`: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v2/phase_a_case_flow_records.jsonl`

## Category Outcome

| category | total | pass | exact | deterministic_mismatch | tool_call_only |
| --- | ---: | ---: | ---: | ---: | ---: |
| abstention | 3 | 0 | 0 | 1 | 2 |
| knowledge-update | 7 | 0 | 0 | 4 | 3 |
| multi-session | 12 | 0 | 0 | 9 | 3 |
| single-session-assistant | 6 | 0 | 0 | 3 | 3 |
| single-session-preference | 3 | 0 | 0 | 3 | 0 |
| single-session-user | 6 | 0 | 0 | 3 | 3 |
| temporal-reasoning | 13 | 1 | 1 | 6 | 6 |

## Evidence Flow Findings

- Raw oracle history contains an obvious gold literal/number for `33/50` cases by conservative string scan.
- Sent `allowed_evidence` block contains an obvious gold literal/number for only `9/50` cases.
- Model emitted tool-call-like text in `21/50` cases; tool audit DB recorded real executed tool events in `0/50` cases.
- Historical v2 artifacts do not include the complete Chat Completions request payload. The available sent-side artifact is `answer_debug.evidence_block_text`, plus session DB user/assistant messages.
- Session DB records only the user question and final assistant answer for each case. It does not store the memory evidence block or provider message list.

## Root Cause Analysis

| Layer | Evidence | Effect |
| --- | --- | --- |
| Adapter/report scoring | AgentLoop `answer_rule_pass_rate=100%`, public scorer pass `2%` | Existing AgentLoop rule for production governed P5 ignores gold answer terms and only checks governed memory grounding; public benchmark needs separate answer scorer. |
| Evidence rendering | `memory2/eval_answer_contract.py::_compact(limit=180)` truncates each session summary; sampled raw sessions are often 15k-25k chars | Gold facts often exist in raw oracle history but are absent from sent `allowed_evidence`, so the model cannot answer even when retrieval IDs are correct. |
| Agent behavior | 20 answers contain DSML/tool-call-like text; tool audit count is 0 | Model tried to request more retrieval/source lookup as text, but eval loop `max_iterations=2` and no actual tool execution path for these emitted calls means final answer is not produced. |
| Dataset/task fit | LongMemEval oracle session can contain the answer deep inside a long session, not necessarily near the first 180 chars | P5 evidence contract was tuned for compact memory summaries, not long transcript evidence chunks. |
| Language/scoring | Several preference/abstention answers are semantically close but deterministic string scorer marks mismatch | Need semantic judge/manual review tier before using final public score, but this is secondary to missing evidence/tool-call-only. |

## Passed Case

| source_id | category | question | gold | answer excerpt |
| --- | --- | --- | --- | --- |
| gpt4_2f56ae70 | temporal-reasoning | Which streaming service did I start using most recently? | Disney+ | 按我这边能看到的记录，最近开始用的是 **Disney+**——上个月你还在免费试用期，当时找不到一部看过的纪录片。 Netflix、Hulu 和 Amazon Prime 是过去 6 个月里一直在用的，Hulu 上你还在追《使女的故事》。 |

## Representative Failed Flow Records

| source_id | category | method | raw gold hit | sent evidence gold hit | tool text | tool audit events | failure summary |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 60bf93ed_abs | abstention | tool_call_only | False | False | True | 0 | model requested lookup/tool instead of final answer |
| 88432d0a_abs | abstention | deterministic_mismatch | False | False | False | 0 | sent evidence did not expose gold or model answered from incomplete evidence |
| c8090214_abs | abstention | tool_call_only | True | True | True | 0 | model requested lookup/tool instead of final answer |
| 031748ae | knowledge-update | deterministic_mismatch | True | False | False | 0 | sent evidence did not expose gold or model answered from incomplete evidence |
| 0f05491a | knowledge-update | deterministic_mismatch | True | False | False | 0 | sent evidence did not expose gold or model answered from incomplete evidence |
| 1cea1afa | knowledge-update | tool_call_only | True | False | True | 0 | model requested lookup/tool instead of final answer |
| 830ce83f | knowledge-update | deterministic_mismatch | True | False | False | 0 | sent evidence did not expose gold or model answered from incomplete evidence |
| 852ce960 | knowledge-update | tool_call_only | True | False | True | 0 | model requested lookup/tool instead of final answer |

## Full Case Table

| idx | source_id | category | pass | method | raw_gold_hit | evidence_gold_hit | tool_text | question | gold | answer excerpt |
| ---: | --- | --- | ---: | --- | ---: | ---: | ---: | --- | --- | --- |
| 0 | 60bf93ed_abs | abstention | False | tool_call_only | False | False | True | How many days did it take for my iPad case to arrive after I bought it? | The information provided is not enough. You did not mention buying an iPad case. | 我先查一下记忆里有没有 iPad 保护壳的购买和到货记录。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="recall_memory"> <｜｜DSML｜｜parameter name="query" string="true">用户购买 iPad 保护壳之后多少天到货</｜｜DSML｜｜parameter> <｜｜D |
| 1 | 88432d0a_abs | abstention | False | deterministic_mismatch | False | False | False | How many times did I bake egg tarts in the past two weeks? | The information provided is not enough. You did not mention baking egg tarts. | 嗯，你问的是过去两周烤了几次蛋挞。我先翻一下记忆里的原始记录再答你。 |
| 2 | c8090214_abs | abstention | False | tool_call_only | True | True | True | How many days before I bought my iPad did I attend the Holiday Market? | The information provided is not enough. You mentioned getting the iPhone 13 Pro and attending the market, but you did no | 嗯，这个问题涉及具体时间线，我先查一下原始记录。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="search_messages"> <｜｜DSML｜｜parameter name="query" string="true">iPad 购买 日期</｜｜DSML｜｜parameter> </｜｜DSML｜｜invoke> |
| 3 | 031748ae | knowledge-update | False | deterministic_mismatch | True | False | False | How many engineers do I lead when I just started my new role as Senior Software Engineer? How many engineers do I lead now? | When you just started your new role as Senior Software Engineer, you led 4 engineers. Now, you lead 5 engineers | 这个我还真答不了。现有记忆里只有你规划团队出游、要找活动建议的记录，没有你升 Senior Software Engineer 时或现在带多少工程师的信息。 所以"刚上任带几个、现在带几个"，我这边证据不足，不能瞎编。你要是想让我记下来，跟我说个数就行。 |
| 4 | 0f05491a | knowledge-update | False | deterministic_mismatch | True | False | False | How many stars do I need to reach the gold level on my Starbucks Rewards app? | 120 | 这个我说不准，不能瞎给你个数。 我这边能用的历史记忆里没有 Starbucks Rewards 的相关内容，只有超市促销和 Sephora 那类的记录。而且这类积分等级规则经常变，凭旧印象给你报一个星数，万一错了会误导你。 建议你直接打开 app 看“Rewards”页面，或者官网的奖励说明，那里是最新的。 |
| 5 | 1cea1afa | knowledge-update | False | tool_call_only | True | False | True | How many Instagram followers do I currently have? | 600 | 我先查一下我这边有没有能读你 Instagram 数据的入口。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="tool_search"> <｜｜DSML｜｜parameter name="query" string="true">select:instagram</｜｜DSML｜｜parameter> </｜｜DSML |
| 6 | 830ce83f | knowledge-update | False | deterministic_mismatch | True | False | False | Where did Rachel move to after her recent relocation? | the suburbs | 我翻了下目前能用的记忆记录，里面只有你们在计划佛罗里达海滩小镇和科罗拉多徒步旅行的事，没有任何关于 Rachel 或者她搬家的信息。 所以这个我答不了，不能凭空编。你要是想让我找，可以给我多点线索，比如大概什么时候聊的，我再去翻翻。 |
| 7 | 852ce960 | knowledge-update | False | tool_call_only | True | False | True | What was the amount I was pre-approved for when I got my mortgage from Wells Fargo? | $400,000 | <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="recall_memory"> <｜｜DSML｜｜parameter parameter="query" string="true">用户从 Wells Fargo 获得抵押贷款时预批准的金额是多少</｜｜DSML｜｜parameter> </｜｜DSML｜｜invoke> |
| 8 | a2f3aa27 | knowledge-update | False | tool_call_only | True | False | True | How many followers do I have on Instagram now? | 1300 | 我先看看手边有没有能查 Instagram 的工具。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="tool_search"> <｜｜DSML｜｜parameter name="query" string="true">select:Instagram</｜｜DSML｜｜parameter> </｜｜DSML｜｜inv |
| 9 | e493bb7c | knowledge-update | False | deterministic_mismatch | True | False | True | Where is the painting 'Ethereal Dreams' by Emma Taylor currently hanging? | in my bedroom | 嗯，这个问题得先查一下我之前记的内容。让我看看。 <tool_use> {"name": "fetch_messages", "arguments": {"source_refs": ["e493bb7c_history_0001", "e493bb7c_history_0002"], "context": 3}} </tool_use> |
| 10 | 2e6d26dc | multi-session | False | deterministic_mismatch | True | False | False | How many babies were born to friends and family members in the last few months? | 5 | 按我这边看到的记录，最近几个月出生的有 2 个——你姨妈的双胞胎 Ava 和 Lily，四月生的。 还有一个朋友那边是"即将办 baby shower"，还没到出生那一步。所以暂时是 2 个。 |
| 11 | 60472f9c | multi-session | False | deterministic_mismatch | True | True | False | How many projects have I been working on simultaneously, excluding my thesis? | 2 | 我这边能查到的记录，全是围绕你论文的——找数据集、找 AI 医疗诊断的研究论文、图像分类相关的文献。 论文之外的项目，一条都没有记录到。所以这个"同时在做几个项目"我没法给你个数，按现有证据就是没有。 如果你记得之前聊过别的项目，我可以再翻翻历史确认一下。 |
| 12 | 61f8c8f8 | multi-session | False | deterministic_mismatch | True | False | False | How much faster did I finish the 5K run compared to my previous year's time? | 10 minutes | 嗯……这个我还真说不上来。 我能看到的记忆里，只有你当时开始为 5K 训练、让我帮你做训练计划那段，还有一次你提慈善烘焙义卖、说“顺便我刚……”的记录。里面没有记下你这次完赛时间和去年的成绩，所以我算不出你比去年快了多少。 你要是把两次的时间发我，我立刻帮你算。 |
| 13 | 6456829e | multi-session | False | tool_call_only | True | True | True | How many plants did I initially plant for tomatoes and cucumbers? | 8 | 我先查一下记忆里有没有种植数量的记录。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="read_file"> <｜｜DSML｜｜parameter name="file" string="true">/home/jjh/git_work/akashic-agent/.worktrees/memory-governanc |
| 14 | 88432d0a | multi-session | False | deterministic_mismatch | True | True | False | How many times did I bake something in the past two weeks? | 4 | 能确定的实际烘焙记录是 1 次：你周二用 sourdough starter 试了个新面包配方。 另外有一段你提到"我做了个好吃的"，但记忆摘要被截断了，不确定那算不算烘焙、时间对不对，所以没法数进去。 找晚宴甜点建议、打算烤鸡翅、计划周末试意大利面包——这些都还是计划/咨询阶段，没动手，不算。 |
| 15 | 8e91e7d9 | multi-session | False | tool_call_only | True | False | True | What is the total number of siblings I have? | 4 | 嗯，我问一下记忆里有没有记过这个。先查一下。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="recall_memory"> <｜｜DSML｜｜parameter name="query" string="true">用户有几个兄弟姐妹 sibling brother sister 家庭</｜｜DSML｜｜paramet |
| 16 | a3332713 | multi-session | False | deterministic_mismatch | True | False | False | What is the total amount I spent on gifts for my coworker and brother? | $200 | 我先查一下这两条记忆的完整内容。 |
| 17 | b3c15d39 | multi-session | False | deterministic_mismatch | False | False | False | How many days did it take for me to receive the new remote shutter release after I ordered it? | 5 days. 6 days (including the last day) is also acceptable. | 这个我查不到。我目前能确认的记录里没有你下单新快门线的事，也没提到收货花了几天，不能瞎编一个数字给你。你要是记得大概下单或到货的日期，我可以帮你推算一下。 |
| 18 | bb7c3b45 | multi-session | False | deterministic_mismatch | False | False | False | How much did I save on the Jimmy Choo heels? | $300 | 从我这边的记录看，只记得你在 outlet mall 买了新的 Jimmy Choo 高跟鞋，但没有存原价和实付价的具体数字。所以省了多少，我这边算不出来，没法确认。 |
| 19 | ef9cf60a | multi-session | False | deterministic_mismatch | False | False | False | How much did I spend on gifts for my sister? | $300 | 查了一下记录，你的礼物还没有实际花钱的金额——那次聊的是明年生日想送她一次 spa 水疗体验，只是想法，没提价格。 $200 那个预算是给你侄女的，不是给姐姐/妹妹的。 |
| 20 | gpt4_2f91af09 | multi-session | False | deterministic_mismatch | False | False | False | How many total pieces of writing have I completed since I started writing again three weeks ago, including short stories, poems, and pieces for the writing chal | 23 | 我只敢按有记录的来说：你之前提过已经写了五篇短篇。诗歌和写作挑战作品的数量，我这边没有能核实的计数，所以三类的总数我给不出来。 |
| 21 | gpt4_7fce9456 | multi-session | False | tool_call_only | True | True | True | How many properties did I view before making an offer on the townhouse in the Brookside neighborhood? | I viewed four properties before making an offer on the townhouse in the Brookside neighborhood. The reasons I didn't mak | 我先查一下原始记录，确认你说的"看了多少套"这个细节。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="search_messages"> <｜｜DSML｜｜parameter name="query" string="true">Brookside townhouse offer viewed properties</ |
| 22 | 3249768e | single-session-assistant | False | tool_call_only | True | False | True | I'm looking back at our previous conversation about building a cocktail bar. You recommended five bottles to make the widest variety of gin-based cocktails. Can | Absinthe | 我先回源看一下那次对话的原文，确认第五瓶再答你。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="search_messages"> <｜｜DSML｜｜parameter name="query" string="true">5 bottles widest variety cocktails gin</｜｜DSML｜｜ |
| 23 | 3e321797 | single-session-assistant | False | deterministic_mismatch | True | False | False | I wanted to follow up on our previous conversation about natural remedies for dark circles under the eyes. You mentioned applying tomato juice mixed with lemon  | 10 minutes | 我查了一下我们之前的记录，里面只提到了第一条黄瓜片敷 10–15 分钟。番茄汁加柠檬汁这个，我在可用的历史里没找到对应的时长信息，所以没法给你一个确切数字。 要不你就按黄瓜那 10–15 分钟作参考？不过这个我没法保证是对的——如果当时真说过时长，可能没被记录下来。 |
| 24 | 51b23612 | single-session-assistant | False | tool_call_only | True | False | True | I was going through our previous conversation about political propaganda and humor, and I was wondering if you could remind me of that Soviet cartoon you mentio | Nu, pogodi! | 嗯，让我翻一下当时的对话记录。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="recall_memory"> <｜｜DSML｜｜parameter name="query" string="true">用户和助手讨论政治宣传中的幽默和讽刺，提到了苏联卡通讽刺西方文化</｜｜DSML｜｜parameter> <｜｜DSM |
| 25 | 8aef76bc | single-session-assistant | False | tool_call_only | True | False | True | I'm going back to our previous conversation about DIY home decor projects using recycled materials. Can you remind me what sealant you recommended for the newsp | Mod Podge or another sealant | 我先回看一下那次对话的原文，确认密封剂推荐。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="fetch_messages"> <｜｜DSML｜｜parameter name="source_ref" string="true">8aef76bc_history_0001</｜｜DSML｜｜parameter> <｜｜D |
| 26 | ceb54acb | single-session-assistant | False | deterministic_mismatch | False | False | False | In our previous chat, you suggested 'sexual compulsions' and a few other options for alternative terms for certain behaviors. Can you remind me what the other f | I suggested 'sexual fixations', 'problematic sexual behaviors', 'sexual impulsivity', and 'compulsive sexuality'. | 我能核对的记录里，只保留了 **"sexual compulsions"** 这一个建议。 另外四个，当时应该列过，但完整列表没留在我的可回源证据里。我没法确定具体是哪几个，不想凭印象编给你。 如果你愿意，我现在可以重新帮你整理一组替代说法，你再挑。 |
| 27 | e982271f | single-session-assistant | False | deterministic_mismatch | True | False | False | I was going through our previous chat. Can you remind me of the name of the last venue you recommended in the list of popular venues in Portland for indie music | Revolution Hall | 嗯，我核了一下那次的记录。当时你问的是 Portland 的 indie 音乐人通常怎么做推广，我的回复主要在说明我作为 AI 没有个人经验、也不收集这类数据——记录里没有出现推荐场地的清单。所以"名单里最后一个 venue"这个，我没法报名字，因为那会儿确实没到列场地那一步。 要是你现在想要一份 Portland 的 indie 演出场地整理，说一声，我去 |
| 28 | 0a34ad58 | single-session-preference | False | deterministic_mismatch | False | False | False | I’m a bit anxious about getting around Tokyo. Do you have any helpful tips? | The user would prefer responses that utilize their existing resources, such as their Suica card and TripIt app, to provi | 刚到东京想着怎么跑确实容易慌，但其实东京的公共交通对游客挺友好的，别担心 (・ω・) 几个实用的： **卡片** - 直接手机 Apple Pay 里开一张 Suica 或 Pasmo（iPhone 秒开，充值也方便），进出站刷手机就行，便利店也能刷。 - 地铁、JR、巴士通用，不用分开买票。 **导航** - 就用 Google Maps，日本的公共交通导 |
| 29 | 54026fce | single-session-preference | False | deterministic_mismatch | False | False | False | I've been thinking about ways to stay connected with my colleagues. Any suggestions? | The user would prefer responses that acknowledge their desire for social interaction and collaboration while working rem | 嗯，你之前提过——喜欢在家办公的自由，但少了茶水间那种随意聊天的机会。那方向就是：要社交，但别让社交变成新的负担。 几个轻量的想法： - 约同事 "virtual coffee"，一周一次，15 分钟，不聊工作，聊周末干了啥、最近看了什么。选一两个聊得来的人就行，不用扩散到全组。 - 工作群里开个闲聊频道（如果还没有的话），随手丢点好玩的、表情包、生活碎片进 |
| 30 | a89d7624 | single-session-preference | False | deterministic_mismatch | False | False | False | I'm planning a trip to Denver soon. Any suggestions on what to do there? | The user would prefer responses that take into account their previous experience in Denver, specifically their interest  | 嗯，Denver 啊。你之前在 Red Rocks 看过 The Killers，那个经典打卡点你已经去过了。不过 Red Rocks 不在市区，在 Morrison，说 Denver 行程的话可以把它当成一个"再看一场"的选项——你要是确定了出行日期，我可以帮你查查那几天 Red Rocks 有没有排期。 市区这边，一般推荐 Meow Wolf 的 Con |
| 31 | 4100d0a0 | single-session-user | False | deterministic_mismatch | False | False | False | What is my ethnicity? | A mix of Irish and Italian | 嗯，这个我现在没法给你确定答案。我记忆里能对上号的线索只有一条：你之前问过办护照的事，在意大利护照和美国护照之间犹豫，让我讲两者的好处。 这只能让我推测，你可能跟意大利或美国有身份上的联系——但这是推测，不是确凿记录。你的族裔信息我没存过。 你要是愿意直接告诉我，我就记下来。 |
| 32 | 6f9b354f | single-session-user | False | tool_call_only | True | False | True | What color did I repaint my bedroom walls? | a lighter shade of gray | 我需要先查一下记忆库，看看有没有关于卧室墙壁颜色的记录。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="recall_memory"> <｜｜DSML｜｜parameter name="query" string="true">用户把卧室墙壁重新刷成了新的颜色</｜｜DSML｜｜parameter> <｜｜DSML｜｜ |
| 33 | 86b68151 | single-session-user | False | deterministic_mismatch | True | False | False | Where did I buy my new bookshelf from? | IKEA | 我这边没有你买书架的记录。 能查到的历史只有你之前问过整理衣柜的 app 推荐，和书架无关。所以这个我说不准，没法编。 |
| 34 | ad7109d1 | single-session-user | False | deterministic_mismatch | True | False | False | What speed is my new internet plan? | 500 Mbps | 这个我真不知道。记忆里只有咱俩聊过笔记本电池的事，没有你网络套餐的记录；而且我也没法直接查你运营商账号。 你要是把套餐名、签约速度或者测速结果发我，我可以帮你看看实际达不达标。 |
| 35 | caf9ead2 | single-session-user | False | tool_call_only | True | False | True | How long did it take to move to the new apartment? | 5 hours | 嗯，我先查一下那条记录的完整内容。 让我看看历史日志里这条 evidence 的原文。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="read_file"> <｜｜DSML｜｜parameter name="file" string="true">/home/jjh/git_work/akashic-agent/.wo |
| 36 | f4f1d8a4 | single-session-user | False | tool_call_only | True | False | True | Who gave me a new stand mixer as a birthday gift? | my sister | <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="bash"> <｜｜DSML｜｜parameter name="command" string="true">grep -n "f4f1d8a4_history_0001" /home/jjh/git_work/akashic-agent/.worktrees/memory |
| 37 | 0bc8ad93 | temporal-reasoning | False | deterministic_mismatch | False | False | False | I mentioned visiting a museum two months ago. Did I visit with a friend or not? | No, you did not visit with a friend. | 嗯，我先查一下当时那条博物馆的记忆原文，确认到底是怎么说的。 我先检索一下相关消息。 |
| 38 | a3838d2b | temporal-reasoning | False | tool_call_only | True | True | True | How many charity events did I participate in before the 'Run for the Cure' event? | 4 | 这个问题需要确认时间线，我先查一下记忆原文。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="recall_memory"> <｜｜DSML｜｜parameter name="query" string="true">用户在 Run for the Cure 慈善跑活动之前参加过什么慈善活动</｜｜DSML｜｜param |
| 39 | b46e15ee | temporal-reasoning | False | tool_call_only | False | False | True | What charity event did I participate in a month ago? | the 'Walk for Hunger' charity event | 我先查一下记忆里这几个慈善活动的时间线，确认哪个对应"一个月前"。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="read_file"> <｜｜DSML｜｜parameter name="file" string="true">/home/jjh/git_work/akashic-agent/.worktrees/me |
| 40 | eac54add | temporal-reasoning | False | tool_call_only | False | False | True | What was the significant buisiness milestone I mentioned four weeks ago? | I signed a contract with my first client. | 嗯，我先翻一下当时的记录。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="bash"> <｜｜DSML｜｜parameter name="command" string="true">cd /home/jjh/git_work/akashic-agent/.worktrees/memory-governance-eva |
| 41 | gpt4_1d80365e | temporal-reasoning | False | deterministic_mismatch | True | False | False | How many days did I spend on my solo camping trip to Yosemite National Park? | 2 days. 3 days (including the last day) is also acceptable. | 这个我没法确认。我能看到的记录里，你聊过的是 Eastern Sierra 的徒步和露营计划，没有提到自己 solo 去 Yosemite 露营、更没说住了几天。所以天数我没有依据，不好编。 |
| 42 | gpt4_2f56ae70 | temporal-reasoning | True | exact | True | True | False | Which streaming service did I start using most recently? | Disney+ | 按我这边能看到的记录，最近开始用的是 **Disney+**——上个月你还在免费试用期，当时找不到一部看过的纪录片。 Netflix、Hulu 和 Amazon Prime 是过去 6 个月里一直在用的，Hulu 上你还在追《使女的故事》。 |
| 43 | gpt4_4929293a | temporal-reasoning | False | deterministic_mismatch | True | False | False | Which event happened first, my cousin's wedding or Michael's engagement party? | Michael's engagement party | 这个我现在判断不了。 记忆里只有两次你聊自己婚礼筹备的记录，一次是选场地，一次是找 planner。两段摘要里都带了“顺便说，我刚从……”这种话头，但具体是哪场活动、先后顺序，都没有留下来。 我不能瞎猜。你要是记得大概时间，告诉我，我记下来。 |
| 44 | gpt4_61e13b3c | temporal-reasoning | False | deterministic_mismatch | False | False | False | How many weeks passed between the time I sold homemade baked goods at the Farmers' Market for the last time and the time I participated in the Spring Fling Mark | 3 weeks | 嗯，这个我目前算不出来。 我手头能用的证据里，只有两段对话摘要：一段是你卖自制烘焙食品（muffins、scones、cookies），另一段是你在 Spring Fling Market 和精品店老板聊批发合作。但两件事各自发生在哪天，证据里没有具体日期，所以相隔几周我没法准确推算。 如果你告诉我两个大致时间点，我可以帮你算。 |
| 45 | gpt4_6dc9b45b | temporal-reasoning | False | tool_call_only | False | False | True | How many months ago did I attend the Seattle International Film Festival? | 4 months ago | 我先查一下原始记录，确认你说的"今天"具体是哪一天。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="recall_memory"> <｜｜DSML｜｜parameter name="query" string="true">user attended Seattle International Film Festiva |
| 46 | gpt4_8279ba02 | temporal-reasoning | False | deterministic_mismatch | False | False | False | How many days ago did I buy a smoker? | 10 days ago. 11 days (including the last day) is also acceptable. | 我这边现有的记忆里没找到你买 smoker 的日期。能看到的只有一条相关的：你之前在找新的 BBQ 酱配方，说自己一直在从零开始做、想改进——但那条没提具体购买时间，所以我算不出“多少天前”。 你要是记得大概多久买的，跟我说个大概时间，我帮你核一下。 |
| 47 | gpt4_93159ced | temporal-reasoning | False | tool_call_only | True | False | True | How long have I been working before I started my current job at NovaTech? | 4 years and 9 months | <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="read_file"> <｜｜DSML｜｜parameter name="file" string="true">/home/jjh/git_work/akashic-agent/.worktrees/memory-governance-eval-v2/my_md/memo |
| 48 | gpt4_d6585ce8 | temporal-reasoning | False | deterministic_mismatch | True | True | False | What is the order of the concerts and musical events I attended in the past two months, starting from the earliest? | The order of the concerts I attended is: 1. Billie Eilish concert at the Wells Fargo Center in Philly, 2. Free outdoor c | 过去两个月里，我能确认的音乐活动有这么几场： - 布鲁克林的一个音乐节（你说刚从那儿回来） - 费城的 Billie Eilish 演唱会 - 一场 Queen 的现场演出（你说刚看完） 另外你还提过最近看了好几场演唱会，但没具体点名是哪几场。 不过这些信息里都没有具体日期，也没交代谁先谁后，所以我没法可靠地按从最早到最晚排出准确顺序。能确定的只有：这几场都 |
| 49 | gpt4_f420262d | temporal-reasoning | False | tool_call_only | True | True | True | What was the airline that I flied with on Valentine's day? | American Airlines | 嗯，这个我得回原文确认一下，摘要里没直接写情人节那段。等我查一下。 <｜｜DSML｜｜tool_calls> <｜｜DSML｜｜invoke name="fetch_messages"> <｜｜DSML｜｜parameter name="source_ref" string="true">gpt4_f420262d_history_0004</｜｜DSML｜ |

## Concrete Message Flow

For each case, the observed flow is:

1. `PublicLongMemoryCase` loads LongMemEval row and creates session-scoped memory items.
2. `public_case_to_eval_case` writes only the current case history into `setup.memory_items`; gold answer stays in expectations/report only.
3. `ComprehensiveOnlineMemoryEngine.retrieve` returns governed P5 evidence IDs and an evidence contract block.
4. AgentLoop sends the user question plus memory context to the provider. The exact provider request payload was not persisted in v2.
5. Provider answer is persisted in answer_debug and session DB as the assistant final message.
6. Public scorer compares answer text against gold/aliases. Tool-call-like text is classified as `tool_call_only`.

## Next Debugging Requirement

- Before rerunning Phase A, add explicit provider request capture for eval-only runs, or enable a sanitized payload snapshot, so future analysis can inspect the exact Chat Completions messages.
- Do not enter Phase B until evidence rendering is changed to expose answer-bearing session content and Phase A gate passes.
