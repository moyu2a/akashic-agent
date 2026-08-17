# LongMemEval Phase A v7 LLM Judge 审阅

## 总览

- 审阅对象：`v7_pass.md` 的 28 条静态 PASS，以及 `v7_falied.md` 的 22 条静态 FAILED。注意本地文件名是 `v7_falied.md`，不是 `v7_failed.md`。
- v7 的证据治理整体比旧版更清晰：每条 case 都给了 `allowed_evidence`、`used_memory_ids`、render token 和诊断字段。
- 主要评测问题仍然在 deterministic scorer：它对自然语言等价、缩写、中文回答英文问题、abstention 改写、长 gold answer 的鲁棒性不足。
- PASS 中仍有明显问题：`852ce960` 是 **false positive**，模型最终主结论是 `$350,000`，但 gold 是 `$400,000`。
- PASS 中还有边界项：`a2f3aa27` 的证据是 “close to 1300”，模型也没有精确断言当前就是 1300。
- FAILED 中多数是 **false negative**：模型答案事实正确，但没有原样匹配 gold，或回答语言与 question language 不一致。
- 真正比较像模型错误的是 `gpt4_1d80365e`：模型没有给出 gold 接受的 2 days / 3 days，而是说无法确定。

---

## Part A: v7 PASS Cases

## 1. `0f05491a` - knowledge-update

问题是：**How many stars do I need to reach the gold level on my Starbucks Rewards app?**

证据里先有 2023-07-11 的 **125 stars**，后有 2023-07-30 的最新纠正 **120 stars**。

gold answer 是：`120`。

模型输出：需要 **120 stars**，并说明这是用户上次纠正后的数字。

这个答案正确，时间更新也处理对了。

结论：**合理 PASS。**

---

## 2. `1cea1afa` - knowledge-update

问题是：**How many Instagram followers do I currently have?**

证据里 2023-05-21 是 **500 followers**，2023-05-25 是 **600 followers**。提问日期是 2023-06-08。

gold answer 是：`600`。

模型输出：不能实时确认今天的当前粉丝数，但最新记录是 2023-05-25 的 **600 followers**。

这个答案事实正确，而且对 “currently” 的实时性做了合理保留。`final_stance_review_needed=True` 是合理提示，但不构成模型错误。

结论：**合理 PASS。**

---

## 3. `830ce83f` - knowledge-update

问题是：**Where did Rachel move to after her recent relocation?**

证据里 Rachel 先搬到 Chicago，后来又 **moved back to the suburbs again**。

gold answer 是：`the suburbs`。

模型输出：Rachel 最近搬回了 **the suburbs**，Chicago 是更早的信息。

这个答案正确。

结论：**合理 PASS。**

---

## 4. `852ce960` - knowledge-update

问题是：**What was the amount I was pre-approved for when I got my mortgage from Wells Fargo?**

证据里有两个冲突数字：2023-08-11 用户明确说从 Wells Fargo 预批 **$350,000**；2023-11-30 用户又回忆 “pre-approved for **$400,000** from Wells Fargo”。

gold answer 是：`$400,000`。

模型输出虽然提到了 `$400,000`，但最终主结论是：`$350,000` figure from the original conversation is the one I'd treat as the actual pre-approval amount。

这个答案不能算正确。它包含 gold 字符串，但最终答案和 gold 相反。

判错/判对原因：scorer 只做子串命中，没有判断 final stance。v7 已经打了 `final_stance_review_needed=True`，这个诊断是对的，但 strict pass 仍然放过了。

结论：**false positive。模型不应算 PASS。**

---

## 5. `a2f3aa27` - knowledge-update

问题是：**How many followers do I have on Instagram now?**

证据里用户先说 **1250 followers**，稍后说 **close to 1300 now**。原文不是精确说已经达到 1300。

gold answer 是：`1300`。

模型输出：最新记录是 1250，后来接近 1300；无法确认 2023-06-03 的 exact count，best guess around 1300。

这个答案忠实于证据，但不是一个干净的 `1300` 答案。严格说，gold 把 “close to 1300” 简化成 `1300` 有问题；模型的谨慎回答反而更符合证据。

结论：**边界 PASS / gold questionable。更适合标 partial，而不是干净 PASS。**

---

## 6. `2e6d26dc` - multi-session

问题是：**How many babies were born to friends and family members in the last few months?**

证据包括 aunt 的 twins Ava and Lily、Rachel 的 Max、David 的 Jasper、Mike and Emma 的 Charlotte。

合计是 **5 babies**。

gold answer 是：`5`。

模型输出列出了这 5 个 baby，并给出 **5 babies**。

结论：**合理 PASS。**

---

## 7. `61f8c8f8` - multi-session

问题是：**How much faster did I finish the 5K run compared to my previous year's time?**

证据是去年 45 minutes，最近 35 minutes。

计算是 45 - 35 = **10 minutes**。

模型输出：**10 minutes faster**，并额外给出 22% improvement。

结论：**合理 PASS。**

---

## 8. `88432d0a` - multi-session

问题是：**How many times did I bake something in the past two weeks?**

证据里有 4 次烘焙：sourdough bread、chocolate cake、cookies、whole wheat baguette。

gold answer 是：`4`。

模型输出用中文列出了 4 次，并说明 cake 和 baguette 虽在同一周末但属于两次不同烤制。

事实答案正确，但问题是英文，模型回答中文；诊断字段也标了 `language_mismatch=True`。如果评测把语言合同当硬约束，这条不应是干净 PASS；如果只评事实，则 PASS 合理。

结论：**事实合理 PASS，但有语言合同违规。**

---

## 9. `8e91e7d9` - multi-session

问题是：**What is the total number of siblings I have?**

证据是 1 brother 和 3 sisters，合计 **4 siblings**。

模型输出：4 siblings total。

结论：**合理 PASS。**

---

## 10. `a3332713` - multi-session

问题是：**What is the total amount I spent on gifts for my coworker and brother?**

证据是 coworker gift **$100**，brother gift card **$100**，合计 **$200**。

模型输出给出两笔金额并算出 **$200**。

诊断字段里 `supporting_fact_hit=False`、`literal_gold_hit=False`，但答案本身是正确的。这里是诊断字段漏检，不是模型问题。

结论：**合理 PASS；诊断字段有 false negative。**

---

## 11. `bb7c3b45` - multi-session

问题是：**How much did I save on the Jimmy Choo heels?**

证据是购买价 **$200**，原价 **$500**。

计算是 $500 - $200 = **$300**。

模型输出：saved **$300**。

诊断字段同样没命中 supporting fact，但模型答案正确。

结论：**合理 PASS；诊断字段有漏检。**

---

## 12. `ef9cf60a` - multi-session

问题是：**How much did I spend on gifts for my sister?**

证据是 spa gift card **$100**，Tiffany necklace **$200**，合计 **$300**。

模型输出：about **$300 total**。

诊断字段没命中 supporting fact，但答案正确。

结论：**合理 PASS；诊断字段有漏检。**

---

## 13. `gpt4_2f91af09` - multi-session

问题是：**How many total pieces of writing have I completed since I started writing again three weeks ago?**

证据是 **17 poems**、**5 short stories**、**1 writing challenge piece**。

合计是 **23**。

模型输出：minimum counted total is **23 pieces**，并说明无法确认是否后来又新增。

这个答案正确。caveat 不影响 benchmark 所需答案，只是对不同日期的记录做了保守说明。

结论：**合理 PASS。**

---

## 14. `3249768e` - single-session-assistant

问题是：**five bottles 里第五瓶是什么？**

证据里第五瓶是 **Absinthe**。

模型输出：The fifth bottle was **Absinthe**。

结论：**合理 PASS。**

---

## 15. `3e321797` - single-session-assistant

问题是：**tomato juice mixed with lemon juice 要敷多久？**

gold answer 是：`10 minutes`。

模型输出：leave it on for **10 minutes**。

结论：**合理 PASS。**

---

## 16. `51b23612` - single-session-assistant

问题是：**mocked Western culture 的 Soviet cartoon 是什么？**

证据和 gold 都是 **Nu, pogodi!**

模型输出正确。

结论：**合理 PASS。**

---

## 17. `8aef76bc` - single-session-assistant

问题是：**newspaper flower vase 推荐什么 sealant？**

gold answer 是：`Mod Podge or another sealant`。

模型输出：**Mod Podge** or another sealant。

结论：**合理 PASS。**

---

## 18. `e982271f` - single-session-assistant

问题是：**Portland indie music venues 列表最后一个是什么？**

gold answer 是：`Revolution Hall`。

模型输出：last venue was **Revolution Hall**。

结论：**合理 PASS。**

---

## 19. `6f9b354f` - single-session-user

问题是：**What color did I repaint my bedroom walls?**

gold answer 是：`a lighter shade of gray`。

模型输出：A lighter shade of gray。

结论：**合理 PASS。**

---

## 20. `86b68151` - single-session-user

问题是：**Where did I buy my new bookshelf from?**

gold answer 是：`IKEA`。

模型输出：You bought it from IKEA。

结论：**合理 PASS。**

---

## 21. `ad7109d1` - single-session-user

问题是：**What speed is my new internet plan?**

gold answer 是：`500 Mbps`。

模型输出：Your plan is **500 Mbps**。

`missed_salient_context_possible` 不影响这里，因为问题只要具体速度。

结论：**合理 PASS。**

---

## 22. `caf9ead2` - single-session-user

问题是：**How long did it take to move to the new apartment?**

gold answer 是：`5 hours`。

模型输出：Around **5 hours**。

结论：**合理 PASS。**

---

## 23. `a3838d2b` - temporal-reasoning

问题是：**Run for the Cure 之前参加了多少 charity events？**

证据中 Run for the Cure 是 2023-10-15。之前有 Dance for a Cause、Walk for Wildlife、charity golf tournament、Food for Thought charity gala，共 **4** 个；Bike-a-Thon 在 November，不能算。

模型输出正确列出 4 个并排除 Bike-a-Thon。

结论：**合理 PASS。**

---

## 24. `gpt4_2f56ae70` - temporal-reasoning

问题是：**Which streaming service did I start using most recently?**

证据里 Disney+ 是 last month 的 free trial，比 Apple TV+、Netflix、Hulu、Amazon Prime 都更新。

模型输出：**Disney+**。

结论：**合理 PASS。**

---

## 25. `gpt4_4929293a` - temporal-reasoning

问题是：**cousin's wedding 和 Michael's engagement party 哪个先？**

证据是 Michael's engagement party 在 2023-05-06，cousin's wedding 在 2023-06-15。

模型输出：Michael's engagement party happened first。

结论：**合理 PASS。**

---

## 26. `gpt4_61e13b3c` - temporal-reasoning

问题是：**Farmers' Market 最后一次卖 baked goods 到 Spring Fling Market 隔了几周？**

证据是 Farmers' Market 在 2023-02-26，Spring Fling Market 在 2023-03-20。

相差 22 天，即 **3 weeks plus 1 day**，按 gold 是 **3 weeks**。

模型输出：3 weeks plus 1 day，22 days。

虽然诊断字段没命中 literal/supporting fact，但答案正确。

结论：**合理 PASS；诊断字段有漏检。**

---

## 27. `gpt4_93159ced` - temporal-reasoning

问题是：**How long have I been working before I started my current job at NovaTech?**

证据里用户说总共 professionally working **9 years**，在 NovaTech **4 years and 3 months**。

计算是 9 years - 4 years 3 months = **4 years and 9 months**。

模型输出给出 **4 years and 9 months**，并说明 9-year 是 round number。

结论：**合理 PASS。**

---

## 28. `gpt4_f420262d` - temporal-reasoning

问题是：**Valentine's day 坐的航空公司是什么？**

证据里 2023-02-14 用户提到 American Airlines LAX to JFK flight delayed by 2 hours。

模型输出：**American Airlines**。

结论：**合理 PASS。**

---

## Part B: v7 FAILED Cases

## 1. `60bf93ed_abs` - abstention

问题是：**How many days did it take for my iPad case to arrive after I bought it?**

证据只涉及 graphics card、Wi-Fi、password manager 等，没有 iPad case 购买或到货信息。

gold answer 是：信息不足，用户没有提到买 iPad case。

模型输出：没有这条信息，没有买 iPad case 或到货记录，所以不能告诉用了几天。

这个答案完全符合 gold 的 abstention intent。

判错原因是 deterministic scorer 没有匹配到 gold 的完整措辞；诊断字段 `abstention_intent_passed=True` 已经说明语义通过。

结论：**false negative。模型没错。**

---

## 2. `88432d0a_abs` - abstention

问题是：**How many times did I bake egg tarts in the past two weeks?**

证据里有 tart crust、whole wheat bread、sourdough、chocolate cake 等，但没有 egg tarts。

gold answer 是：信息不足，用户没有提到 baking egg tarts。

模型输出：没有 egg tarts 记录，并列出已有 baking 记录不包含 egg tarts。

这个答案正确。

判错原因是 abstention 改写没有被 deterministic scorer 接受；`abstention_intent_passed=True`。

结论：**false negative。模型没错。**

---

## 3. `c8090214_abs` - abstention

问题是：**How many days before I bought my iPad did I attend the Holiday Market?**

证据里有 Holiday Market，也有 iPhone / TV 等购物信息，但没有买 iPad 的记录。

gold answer 是：信息不足；提到了 iPhone 13 Pro 和 Holiday Market，但没提到买 iPad。

模型输出：只有 Holiday Market 约在 Black Friday 前一周，没有 iPad 购买日期，因此无法计算天数。

这个答案正确。

结论：**false negative。模型没错。**

---

## 4. `031748ae` - knowledge-update

问题是：**刚开始 Senior Software Engineer 时带多少工程师？现在带多少？**

证据里 2023-05-11 用户纠正说刚开始带 **4 engineers**；2023-10-24 用户说现在 lead a team of **five engineers**。

gold answer 是：刚开始 4，现在 5。

模型输出：When you first started ... **4 engineers**. Now ... **5 engineers**.

这个答案完全正确。

判错原因是模型没有原样复现 gold 的完整句子，属于语义等价但 deterministic mismatch。

结论：**false negative。模型没错。**

---

## 5. `e493bb7c` - knowledge-update

问题是：**Where is the painting 'Ethereal Dreams' by Emma Taylor currently hanging?**

证据里早期是 above living room sofa；2023-10-30 最新更新为 moved above my bed / in bedroom。

gold answer 是：`in my bedroom`。

模型输出：as of latest update, hanging above the bed in your bedroom。

这个答案正确，并且处理了 knowledge-update。

判错原因是 gold 是短语，模型用了更完整自然语言表达。

结论：**false negative。模型没错。**

---

## 6. `60472f9c` - multi-session

问题是：**excluding thesis，同时做几个 projects？**

证据里 thesis 之外有 Data Mining group project 和 Database Systems project。

gold answer 是：`2`。

模型输出：two projects besides the thesis: Data Mining 和 Database Systems。

这个答案正确。

判错原因是 answer 使用 `two` 而不是 `2`，或没有被 normalized scorer 捕捉。

结论：**false negative。模型没错。**

---

## 7. `6456829e` - multi-session

问题是：**How many plants did I initially plant for tomatoes and cucumbers?**

证据里用户最初种了 **5 tomato plants**，还有 **3 cucumber plants**。

gold answer 是：`8`。

模型输出：You initially planted **5 tomato plants** and **3 cucumber plants**。

虽然模型没有显式写出总和 `8`，但它给出了组成项 5 和 3，足以回答问题。更理想答案会补一句 “8 total”，但这不应算事实错误。

结论：**false negative / 可接受答案。**

---

## 8. `b3c15d39` - multi-session

问题是：**remote shutter release 从下单到收到用了几天？**

证据里下单是 2023-02-05，到货是 2023-02-10。

差值是 **5 days**；如果首尾都算可以是 6 days。

gold answer 是：`5 days. 6 days (including the last day) is also acceptable.`

模型输出：**5 days**，ordered on February 5th and arrived on February 10th。

这个答案完全正确。

判错原因是 gold 包含两个可接受形式，模型只给了其中一个，deterministic scorer 没处理。

结论：**false negative。模型没错。**

---

## 9. `gpt4_7fce9456` - multi-session

问题是：**Brookside townhouse offer 前看了多少 properties，以及没 offer 的原因？**

证据里共有 4 套：Oakwood bungalow 厨房需大修、Cedar Creek 超预算、1-bedroom condo 高速噪音、2-bedroom condo 被更高报价击败；之后才是 Brookside townhouse。

gold answer 是完整英文描述这 4 套和原因。

模型输出用中文列出 4 套及原因，事实内容基本与 gold 一致。

问题是：用户问题是英文，模型回答中文，诊断字段有 `language_mismatch=True` 和 `mixed_language_mismatch=True`。

如果只评事实，这是 false negative；如果把 response language contract 当硬门槛，FAILED 是合理的。

结论：**事实 false negative，但语言合同违规；建议单独拆分 factual score 和 language score。**

---

## 10. `ceb54acb` - single-session-assistant

问题是：**除了 sexual compulsions，还建议过哪四个替代表达？**

gold answer 是：sexual fixations、problematic sexual behaviors、sexual impulsivity、compulsive sexuality。

模型输出列出了这四个，并附解释。

这个答案完全正确。

判错原因是 long gold + 自然语言解释导致 deterministic mismatch。

结论：**false negative。模型没错。**

---

## 11. `0a34ad58` - single-session-preference

问题是：**Tokyo 出行焦虑，有什么 tips？**

gold 的重点不是单一事实，而是偏好：应该结合用户已有准备，如 Suica card 和 TripIt app，给个性化 Tokyo transit 建议，避免泛泛而谈。

模型输出明显使用了 Suica、Shinjuku、Tsukiji route、Google Maps、rush hour、taxis 等上下文。它没有明确提到 TripIt，但整体不是泛泛建议，而是围绕用户已有行程与 Suica 给建议。

因此模型至少大部分满足 preference gold。若 TripIt 是硬要求，则只能算 partial；若 gold 中 “such as” 是示例，答案应算正确。

结论：**更像 false negative / partial positive；不是模型明显错误。**

---

## 12. `54026fce` - single-session-preference

问题是：**如何和同事保持连接？**

gold 的重点：承认远程工作中想要社交互动，结合之前 virtual coffee breaks、team collaboration 等上下文，给非泛泛建议。

模型输出直接围绕用户喜欢的 **virtual coffee break** 展开，并强调低压力、opt-in、小组、无固定会议负担。

这个答案符合偏好型 gold 的核心要求。

判错原因是 preference gold 太长、deterministic scorer 无法语义匹配。

结论：**false negative。模型没错。**

---

## 13. `a89d7624` - single-session-preference

问题是：**Denver trip 有什么建议？**

gold 的重点：结合用户之前 Denver 音乐经历、The Killers / Brandon Flowers、live music 偏好，建议音乐场景相关活动，避免普通旅游推荐。

模型输出：明确说 Denver again、你上次喜欢那里的 music scene，并推荐 Red Rocks、Ogden Theatre、Bluebird Theater、Fillmore、Larimer Lounge 等音乐地点。

它没有点名 Brandon Flowers，但确实抓住了 live music 这个核心偏好，不是泛泛旅游建议。

结论：**false negative / 接近正确；如果强制要求提 Brandon Flowers，则 partial。**

---

## 14. `4100d0a0` - single-session-user

问题是：**What is my ethnicity?**

证据里用户说 mixed ethnicity - **Irish and Italian**。

gold answer 是：`A mix of Irish and Italian`。

模型输出：mixed Irish and Italian ethnicity。

这个答案完全正确。

判错原因是措辞不同，没有原样命中 gold。

结论：**false negative。模型没错。**

---

## 15. `f4f1d8a4` - single-session-user

问题是：**Who gave me a new stand mixer as a birthday gift?**

证据里用户说 new stand mixer 是 birthday gift from **my sister**。

gold answer 是：`my sister`。

模型输出：Your sister gave you the stand mixer。

这个答案完全正确。

判错原因不合理；诊断里甚至 `literal_gold_hit=True`，但 strict 仍 failed，说明 scorer 管线存在不一致。

结论：**false negative。模型没错。**

---

## 16. `0bc8ad93` - temporal-reasoning

问题是：**两个月前提到 visiting a museum，是不是和朋友一起？**

提问时间是 2023-03-11。两个月前对应 2023-01 左右。证据里 2023-01-11 是 History Museum lecture，没有提到 friend；2022-10-22 的 Science Museum 才是和 chemistry professor friend。

gold answer 是：No, you did not visit with a friend.

模型输出：two-months-ago mention 没有 friend；friend 是更早的 Science Museum。

这个答案正确，且时间区分做得很好。

结论：**false negative。模型没错。**

---

## 17. `b46e15ee` - temporal-reasoning

问题是：**What charity event did I participate in a month ago?**

提问时间是 2023-04-18。证据里 2023-03-19 用户参加 **Walk for Hunger**。

gold answer 是：`the 'Walk for Hunger' charity event`。

模型输出中文回答：参加的是 **Walk for Hunger** 慈善活动，3 月 19 日和同事走 5 公里为当地食物银行筹款。

事实完全正确，但回答语言不符合英文问题。

结论：**事实 false negative；语言合同违规。**

---

## 18. `eac54add` - temporal-reasoning

问题是：**four weeks ago 提到的重要 business milestone 是什么？**

提问时间是 2023-03-28，四周前约是 2023-03-01。证据里用户说刚和第一个 freelance client 签了 contract。

gold answer 是：I signed a contract with my first client.

模型输出：signing your first freelance client contract，并给出 2023-03-01 证据。

这个答案正确。

结论：**false negative。模型没错。**

---

## 19. `gpt4_1d80365e` - temporal-reasoning

问题是：**How many days did I spend on my solo camping trip to Yosemite National Park?**

证据里用户在 2023-05-15 说今天刚开始 solo camping trip，2023-05-17 说今天刚回来。

gold answer 是：`2 days. 3 days (including the last day) is also acceptable.`

模型输出却说：只能确认旅行在这两条记录之间结束，但具体待了多少天，记忆里没有明确数字，说不准。

这个答案没有给出 gold 可接受的 **2 days** 或 **3 days including the last day**。虽然它没有编造，但作为 benchmark 答案是未完成。

结论：**合理 FAILED。模型过度保守，算错/漏答。**

---

## 20. `gpt4_6dc9b45b` - temporal-reasoning

问题是：**How many months ago did I attend the Seattle International Film Festival?**

提问时间是 2021-10-02。证据里用户在 2021-06-01 说当天参加 SIFF。

从 2021-06-01 到 2021-10-02 约 **4 months ago**。

gold answer 是：`4 months ago`。

模型输出中文回答：大概 4 个月前，并给出日期计算。

事实完全正确，但英文问题用了中文回答；诊断字段也标了 language mismatch。

结论：**事实 false negative；语言合同违规。**

---

## 21. `gpt4_8279ba02` - temporal-reasoning

问题是：**How many days ago did I buy a smoker?**

提问日期是 2023-03-25。证据里用户在 2023-03-15 说：I just got a smoker today。

从 2023-03-15 到 2023-03-25 是 **10 days ago**；若首尾都算，可以说 11 days including the last day。

gold answer 是：`10 days ago. 11 days (including the last day) is also acceptable.`

模型输出中文回答：2023 年 3 月 15 日说刚收到烟熏炉，今天是 3 月 25 日，所以是 **10 天前**。

事实完全正确。唯一问题是英文问题中文回答；另外 “got a smoker” 和 “buy a smoker” 的差异已被 gold 接受，不构成模型错误。

结论：**事实 false negative；语言合同违规。**

---

## 22. `gpt4_d6585ce8` - temporal-reasoning

问题是：**过去两个月参加的 concerts / musical events 从早到晚排序？**

证据顺序是：2023-03-18 Billie Eilish at Wells Fargo Center in Philly；2023-03-25 free outdoor concert series in the park；2023-04-01 music festival in Brooklyn；2023-04-08 jazz night at a local bar；2023-04-15 Queen + Adam Lambert at Prudential Center in Newark, NJ。

gold answer 也是这个顺序。

模型输出用中文列出完全相同顺序，并补充具体日期和同伴信息。

事实内容正确，但英文问题中文回答，语言合同违规。

结论：**事实 false negative；语言合同违规。**

---

## 汇总判断

| 来源   | case                                                         | judge 结论                        | 说明                                         |
| ------ | ------------------------------------------------------------ | --------------------------------- | -------------------------------------------- |
| PASS   | `852ce960`                                                   | false positive                    | 包含 `$400,000`，但最终主结论是 `$350,000`   |
| PASS   | `a2f3aa27`                                                   | 边界 / gold questionable          | 证据是 close to 1300，模型也只是 around 1300 |
| PASS   | `88432d0a`                                                   | 事实正确但语言违规                | 英文问题中文答                               |
| PASS   | `a3332713`, `bb7c3b45`, `ef9cf60a`, `gpt4_61e13b3c`          | 合理 PASS                         | 诊断字段漏检 supporting/literal，但答案正确  |
| FAILED | `60bf93ed_abs`, `88432d0a_abs`, `c8090214_abs`               | false negative                    | 正确 abstention，被字符串匹配误伤            |
| FAILED | `031748ae`, `e493bb7c`, `60472f9c`, `6456829e`, `b3c15d39`, `ceb54acb`, `4100d0a0`, `f4f1d8a4`, `0bc8ad93`, `eac54add` | false negative                    | 语义正确，deterministic mismatch             |
| FAILED | `0a34ad58`, `a89d7624`                                       | partial / false negative          | 偏好核心命中，但未覆盖 gold 中所有细节       |
| FAILED | `54026fce`                                                   | false negative                    | 偏好型回答符合核心上下文                     |
| FAILED | `gpt4_7fce9456`, `b46e15ee`, `gpt4_6dc9b45b`, `gpt4_8279ba02`, `gpt4_d6585ce8` | 事实 false negative，语言合同违规 | 内容对，但英文问题中文答                     |
| FAILED | `gpt4_1d80365e`                                              | 合理 FAILED                       | 应答 2 days / 3 days，但模型说无法确定       |

## 对评测的建议

1. PASS 不应只靠 gold 子串命中。需要检查 final stance，尤其是出现多个候选值、冲突、转折词时。
2. FAILED 应区分 factual correctness 和 language contract。中文回答英文问题可以单独扣语言分，但不要混成事实错误。
3. Abstention gold 应用语义规则判定，例如 “no record / can't determine / not enough information” 都应视为等价。
4. 长 gold answer 应拆成 key facts / required slots，而不是要求整句匹配。
5. Preference case 不适合 strict string scorer，应按“是否使用 salient user context、是否避免 generic advice、是否覆盖核心偏好”分项判分。