# LongMemEval Phase A v5 PASS Case LLM Judge 审阅

## 总览

- 审阅对象：`pass.md` 中 28 条 PASS case。
- 总体结论：大多数 PASS 是合理的，模型答案确实命中 gold 且与证据一致。
- 明显问题：第 4 条 `852ce960` 是 **false positive**，模型虽然包含 `$400,000`，但最终倾向 `$350,000`，不能算正确。
- 边界问题：第 5 条 `a2f3aa27` 的 gold 把 “close to 1300” 简化成 `1300`，模型按证据谨慎回答。这个 PASS 不宜当作严格语义正确，更像 gold / case 设计本身不够精确。
- 评测风险：当前 strict / normalized 主要靠 gold 子串命中；对于 PASS case，子串命中通常有效，但遇到“列出多个候选值、否定、犹豫、最终答案反向”的情况会产生 false positive。

---

## 1. `0f05491a` - knowledge-update

问题是：**How many stars do I need to reach the gold level on my Starbucks Rewards app?**

证据里有两次更新：2023-07-11 用户纠正为 **125 stars**；2023-07-30 用户再次纠正为 **120 stars**。后者是最新记忆。

gold answer 是：`120`。

模型输出说：7 月 11 日是 125 stars，7 月 30 日又更新为 **120 stars**，所以最新值应信 120 stars。

这个答案正确：它没有只抓旧值，而是识别了 knowledge-update 的时间顺序，并把最新修正作为答案。

scorer 用 exact 子串命中 `120`，这里判 PASS 是合理的。

结论：**合理 PASS。**

---

## 2. `1cea1afa` - knowledge-update

问题是：**How many Instagram followers do I currently have?**

证据里用户先在 2023-05-21 说达到 **500 followers**，后来在 2023-05-25 说现在是 **600 followers**。提问时间是 2023-06-08。

gold answer 是：`600`。

模型输出说：记录里最新里程碑是 2023-05-25 的 **600 followers**，但无法实时确认 2023-06-08 当天的当前粉丝数。

这个答案语义上正确。它给出了 benchmark 需要的长期记忆答案 `600`，同时对 “currently” 做了合理的实时性 caveat。

scorer 因 exact 子串命中 `600` 判 PASS，这里合理。

结论：**合理 PASS。**

---

## 3. `830ce83f` - knowledge-update

问题是：**Where did Rachel move to after her recent relocation?**

证据里 Rachel 先搬到 **Chicago**，后来用户又说 Rachel **moved back to the suburbs again**。问题问 recent relocation，因此应取最新搬迁结果。

gold answer 是：`the suburbs`。

模型输出说 Rachel first moved to Chicago，later moved back to **the suburbs**，具体 suburb 未说明。

这个答案正确：既处理了旧信息，也指出了最新状态。

scorer exact 子串命中 `the suburbs`，判 PASS 合理。

结论：**合理 PASS。**

---

## 4. `852ce960` - knowledge-update

问题是：**What was the amount I was pre-approved for when I got my mortgage from Wells Fargo?**

证据里有冲突：2023-08-11 用户说 Wells Fargo 预批 **$350,000**；2023-11-30 用户回忆 “remember when I got pre-approved for **$400,000** from Wells Fargo?”。

gold answer 是：`$400,000`。

模型输出列出了两个数字：`$350,000` 和 `$400,000`。但它的最后主结论是：如果按时间顺序算最初的预批，那是 **$350,000**。

这个答案不能算完全正确。虽然它包含了 gold 的 `$400,000`，但并没有把 `$400,000` 作为回答；相反，它把最终可执行答案落到了 `$350,000`，与 gold 不一致。

判分原因是 scorer 的子串匹配问题：只要答案里出现 `$400,000` 就 exact pass，没有理解模型最终立场。

结论：**这是 false positive。模型输出不应算 PASS。**

---

## 5. `a2f3aa27` - knowledge-update

问题是：**How many followers do I have on Instagram now?**

证据里用户在 2023-05-28 先说有 **1250 followers**，稍后又说自己 **close to 1300 now**。注意原文不是已经精确达到 1300，而是接近 1300。

gold answer 是：`1300`。

模型输出说：最后记录是 5 月 28 日用户说自己 **快 1300**，但无法实时确认现在具体多少。

这个答案是证据忠实的，但不等于严格回答 `1300`。如果评测目标要求抽取 gold，那么模型没有明确断言 “你现在有 1300 followers”；如果评测目标要求忠实记忆，它反而比 gold 更严谨。

scorer 因为答案里出现 `1300` 而 exact pass，但这是一个边界 PASS：它不是标准的语义命中，而是 gold 过度简化 + 子串命中共同造成的。

结论：**边界 case。更合理标注是 partial / case-gold questionable，不建议当作干净 PASS。**

---

## 6. `2e6d26dc` - multi-session

问题是：**How many babies were born to friends and family members in the last few months?**

证据里有四组出生信息：aunt 的 twins **Ava and Lily** 是 2 个；cousin Rachel 的 baby boy **Max** 是 1 个；college friend David 的 baby boy **Jasper** 是 1 个；Mike and Emma 的 baby girl **Charlotte** 是 1 个。

合计是：2 + 1 + 1 + 1 = **5**。

gold answer 是：`5`。

模型输出列出了 Ava、Lily、Max、Jasper、Charlotte，并给出 **5 babies**。

这个答案正确。虽然模型列表编号只有 4 项，但第一项是 twins，所以总数没错。

scorer exact 子串命中 `5`，判 PASS 合理。

结论：**合理 PASS。**

---

## 7. `60472f9c` - multi-session

问题是：**How many projects have I been working on simultaneously, excluding my thesis?**

证据里用户提到 Master's thesis 之外，还有 **Data Mining group project** 和 **Database Systems group project**。

gold answer 是：`2`。

模型输出说：除了 thesis，同时忙 **2 个项目**，分别是 Data Mining 和 Database Systems。

这个答案完全正确。

scorer exact 子串命中 `2`，判 PASS 合理。

结论：**合理 PASS。**

---

## 8. `61f8c8f8` - multi-session

问题是：**How much faster did I finish the 5K run compared to my previous year's time?**

证据里用户说去年 5K 用时 **45 minutes**，最近完成 5K 用时 **35 minutes**。

计算是：45 - 35 = **10 minutes**。

gold answer 是：`10 minutes`。

模型输出说：You finished **10 minutes faster** — 45 minutes last year to 35 minutes recently.

这个答案完全正确：证据、计算、单位都对。

scorer exact 子串命中 `10 minutes`，判 PASS 合理。

结论：**合理 PASS。**

---

## 9. `88432d0a` - multi-session

问题是：**How many times did I bake something in the past two weeks?**

证据里有 4 次烘焙相关事件：周二 sourdough bread recipe；上周末 chocolate cake；上周四 cookies；上周六 whole wheat baguette。

gold answer 是：`4`。

模型输出先明确说过去两周有 **4 次**，并列出四条。后面又补充说如果严格看日期和是否同一天，可能是 3 到 4 次。

主答案是正确的。后面的 caveat 有点多余，但没有推翻 “4 次” 这个回答；同一天烤两样东西也仍然可以算两次烘焙活动。

scorer exact 子串命中 `4`，判 PASS 基本合理。

结论：**合理 PASS，但答案带了不必要的模糊化说明。**

---

## 10. `8e91e7d9` - multi-session

问题是：**What is the total number of siblings I have?**

证据里用户说自己有 **a brother**，也说自己来自有 **3 sisters** 的家庭。

合计是：1 brother + 3 sisters = **4 siblings**。

gold answer 是：`4`。

模型输出说你总共有 **4 siblings**：1 brother and 3 sisters。

这个答案完全正确。

scorer exact 子串命中 `4`，判 PASS 合理。

结论：**合理 PASS。**

---

## 11. `a3332713` - multi-session

问题是：**What is the total amount I spent on gifts for my coworker and brother?**

证据里用户给 coworker 买 baby clothes and toys，花了 **$100**；给 brother 买 graduation gift card，也花了 **$100**。

合计是：$100 + $100 = **$200**。

gold answer 是：`$200`。

模型输出给出两笔来源并算出 **$200 total**。

这个答案完全正确。

scorer exact 子串命中 `$200`，判 PASS 合理。

结论：**合理 PASS。**

---

## 12. `bb7c3b45` - multi-session

问题是：**How much did I save on the Jimmy Choo heels?**

证据里用户说 Jimmy Choo heels 在 outlet mall 买成 **$200**，后来又说原价 **$500**。

计算是：$500 - $200 = **$300**。

gold answer 是：`$300`。

模型输出说 saved **$300**，并解释原价 $500、购买价 $200。

这个答案完全正确。

scorer exact 子串命中 `$300`，判 PASS 合理。

结论：**合理 PASS。**

---

## 13. `ef9cf60a` - multi-session

问题是：**How much did I spend on gifts for my sister?**

证据里用户提到给 sister 的两件礼物：spa gift card **$100**，Tiffany silver necklace 约 **$200**。

合计是：$100 + $200 = **$300**。

gold answer 是：`$300`。

模型输出列出两笔并给出合计 **$300**。

这个答案完全正确。

scorer exact 子串命中 `$300`，判 PASS 合理。

结论：**合理 PASS。**

---

## 14. `gpt4_2f91af09` - multi-session

问题是：**How many total pieces of writing have I completed since I started writing again three weeks ago, including short stories, poems, and pieces for the writing challenge?**

证据里用户说写了 **17 poems**，又参加 writing challenge 写了 **1** 篇 “The Smell of Old Books”，后来说已经写了 **5 short stories**。

合计是：17 + 1 + 5 = **23**。

gold answer 是：`23`。

模型输出给出 17 poems、5 short stories、1 writing challenge piece，并算出 **23 total**，同时说明前提是 challenge piece 没被包含在 5 short stories 内。

这个答案正确。caveat 合理，因为证据确实来自不同日期和不同类别。

scorer exact 子串命中 `23`，判 PASS 合理。

结论：**合理 PASS。**

---

## 15. `3249768e` - single-session-assistant

问题是：**Can you remind me what the fifth bottle was?**

证据里之前 assistant 推荐 gin-based cocktails 的五瓶：Sweet Vermouth、Dry Vermouth、Campari、Elderflower Liqueur、**Absinthe**。第五瓶就是 Absinthe。

gold answer 是：`Absinthe`。

模型输出说：The fifth bottle was **Absinthe**，并补充完整五瓶列表。

这个答案完全正确。

scorer exact 子串命中 `Absinthe`，判 PASS 合理。

结论：**合理 PASS。**

---

## 16. `3e321797` - single-session-assistant

问题是：**You mentioned applying tomato juice mixed with lemon juice, how long did you say I should leave it on for?**

证据里前一次 natural remedies 回答中，tomato juice mixed with lemon juice 的使用时间是 **10 minutes**。

gold answer 是：`10 minutes`。

模型输出说：**10 minutes**, then rinse off with cold water.

这个答案完全正确。

scorer exact 子串命中 `10 minutes`，判 PASS 合理。

结论：**合理 PASS。**

---

## 17. `51b23612` - single-session-assistant

问题是：**What was that Soviet cartoon you mentioned that mocked Western culture?**

证据里 assistant 曾在 Soviet propaganda 例子中说，popular Soviet cartoon **“Nu, pogodi!”** mocked Western culture and portrayed the Soviet Union as superior。

gold answer 是：`Nu, pogodi!`。

模型输出说：You're thinking of **“Nu, pogodi!”**，并复述了它作为 Soviet propaganda / humor 的上下文。

这个答案完全正确。

scorer exact 子串命中 `Nu, pogodi!`，判 PASS 合理。

结论：**合理 PASS。**

---

## 18. `e982271f` - single-session-assistant

问题是：**What was the name of the last venue you recommended in the list of popular venues in Portland for indie music shows?**

证据里前一次 assistant 给了 Portland indie music venues 的列表，最后一个是 **Revolution Hall**。

gold answer 是：`Revolution Hall`。

模型输出说：之前那串场地名单里，最后一个是 **Revolution Hall**。

这个答案完全正确。

scorer exact 子串命中 `Revolution Hall`，判 PASS 合理。

结论：**合理 PASS。**

---

## 19. `86b68151` - single-session-user

问题是：**Where did I buy my new bookshelf from?**

证据里用户说：The new bookshelf is from **IKEA**。

gold answer 是：`IKEA`。

模型输出说：From **IKEA**，并说明用户当时提到很满意。

这个答案完全正确。

scorer exact 子串命中 `IKEA`，判 PASS 合理。

结论：**合理 PASS。**

---

## 20. `ad7109d1` - single-session-user

问题是：**What speed is my new internet plan?**

证据里用户说自己 about three weeks ago upgraded to **500 Mbps**，并且 streaming Netflix 明显改善。

gold answer 是：`500 Mbps`。

模型输出说：Your plan is **500 Mbps**，并引用了 about three weeks ago 的升级信息。

这个答案完全正确。

scorer exact 子串命中 `500 Mbps`，判 PASS 合理。

结论：**合理 PASS。**

---

## 21. `caf9ead2` - single-session-user

问题是：**How long did it take to move to the new apartment?**

证据里用户说：it took me and my friends around **5 hours** to move everything into the new apartment。

gold answer 是：`5 hours`。

模型输出说：About **5 hours**，并说明是和朋友把东西搬进新公寓。

这个答案完全正确。

scorer exact 子串命中 `5 hours`，判 PASS 合理。

结论：**合理 PASS。**

---

## 22. `a3838d2b` - temporal-reasoning

问题是：**How many charity events did I participate in before the 'Run for the Cure' event?**

证据里 Run for the Cure 是 **2023-10-15**。在它之前有四个 charity events：**Dance for a Cause**（2023-05-01）、**Walk for Wildlife**（June）、**charity golf tournament**（2023-07-17）、**Food for Thought charity gala**（2023-09-25）。Bike-a-Thon 在 November，发生在 Run for the Cure 之后，不计入。

gold answer 是：`4`。

模型输出列出上述四项，并明确排除 November 的 Bike-a-Thon。

这个答案完全正确：时间排序和排除项都处理对了。

scorer exact 子串命中 `4`，判 PASS 合理。

结论：**合理 PASS。**

---

## 23. `b46e15ee` - temporal-reasoning

问题是：**What charity event did I participate in a month ago?**

提问时间约在 2023-04 中旬，证据里 2023-03-19 用户说当天参加了 **Walk for Hunger** charity event，和同事走了 5 公里为 local food bank 筹款。另一个 24-Hour Bike Ride 在 2023-02 中旬，更早，不符合 “a month ago”。

gold answer 是：`the 'Walk for Hunger' charity event`。

模型输出说：About a month ago, specifically on 2023-03-19, you took part in **“Walk for Hunger”** charity event，并排除了 24-Hour Bike Ride。

这个答案完全正确。

scorer 用 normalized 命中而不是 exact，原因大概率是引号、冠词、大小写或附加说明差异；语义上 PASS 合理。

结论：**合理 PASS。**

---

## 24. `gpt4_2f56ae70` - temporal-reasoning

问题是：**Which streaming service did I start using most recently?**

证据里用户说 Netflix、Hulu、Amazon Prime 已使用 **6 months**；Apple TV+ 用了 **a few months**；Disney+ 是 **free trial last month**。

最近开始使用的是 **Disney+**。

gold answer 是：`Disney+`。

模型输出说 most recent one is **Disney+**，并解释其他服务都更早。

这个答案完全正确。

scorer exact 子串命中 `Disney+`，判 PASS 合理。

结论：**合理 PASS。**

---

## 25. `gpt4_4929293a` - temporal-reasoning

问题是：**Which event happened first, my cousin's wedding or Michael's engagement party?**

证据里 Michael's engagement party 是 **2023-05-06**；cousin's wedding 是 **2023-06-15**。

先发生的是 **Michael's engagement party**。

gold answer 是：`Michael's engagement party`。

模型输出说 Michael's engagement party came first，并给出两个日期。

这个答案完全正确。

scorer exact 子串命中 gold，判 PASS 合理。

结论：**合理 PASS。**

---

## 26. `gpt4_61e13b3c` - temporal-reasoning

问题是：**How many weeks passed between the time I sold homemade baked goods at the Farmers' Market for the last time and the time I participated in the Spring Fling Market?**

证据里 Farmers' Market baked goods sale 是 **2023-02-26**；Spring Fling Market 是 **2023-03-20**（3 月 21 日对话里说 yesterday）。

从 2023-02-26 到 2023-03-20 是 22 天，也就是 **3 weeks and 1 day**，按周数回答就是 **3 weeks**。

gold answer 是：`3 weeks`。

模型输出说 About **3 weeks** passed，exactly 3 weeks and 1 day，并列出日期和计算。

这个答案完全正确。

scorer exact 子串命中 `3 weeks`，判 PASS 合理。

结论：**合理 PASS。**

---

## 27. `gpt4_6dc9b45b` - temporal-reasoning

问题是：**How many months ago did I attend the Seattle International Film Festival?**

提问日期是 **2021-10-02**。证据里用户在 **2021-06-01** 说当天刚在 Seattle International Film Festival 看了 “Coda”，并参加 SIFF 一周。

从 2021-06-01 到 2021-10-02 约为 **4 months ago**。

gold answer 是：`4 months ago`。

模型输出说：About **4 months ago**，并给出 2021-06-01 和 2021-10-02 两个日期。

这个答案正确。严格到天数是 4 个月多 1 天，但问题问 months ago，4 months ago 合理。

scorer exact 子串命中 `4 months ago`，判 PASS 合理。

结论：**合理 PASS。**

---

## 28. `gpt4_f420262d` - temporal-reasoning

问题是：**What was the airline that I flied with on Valentine's day?**

Valentine's Day 是 **2023-02-14**。证据里 2023-02-14 用户提到自己还在 recovering from my **American Airlines** flight from LAX to JFK, delayed by 2 hours due to bad weather。

gold answer 是：`American Airlines`。

模型输出说：**American Airlines** — the LAX to JFK flight that was delayed by 2 hours due to bad weather.

这个答案正确：航空公司和辅助细节都与证据一致。

scorer exact 子串命中 `American Airlines`，判 PASS 合理。

结论：**合理 PASS。**

---

## 汇总判断

| case      | judge 结论               | 说明                                           |
| --------- | ------------------------ | ---------------------------------------------- |
| 1         | 合理 PASS                | 最新修正为 120 stars                           |
| 2         | 合理 PASS                | 最新记忆为 600 followers，实时性 caveat 可接受 |
| 3         | 合理 PASS                | 最新搬回 suburbs                               |
| 4         | false positive           | 含 `$400,000` 子串，但最终回答偏向 `$350,000`  |
| 5         | 边界 / gold questionable | 证据是 close to 1300，模型未精确断言 1300      |
| 6-28 其余 | 合理 PASS                | gold、证据、模型主答案基本一致                 |

建议后续 scorer 对 PASS case 增加一个轻量 LLM-judge 或规则过滤：当答案中同时出现多个候选数值、包含 “not / cannot determine / if ... then ... / but ...” 等转折时，不要只靠 gold 子串直接 pass，应检查最终主结论是否真的等于 gold。

## 纳入 50 条总评后的处理

| 类型 | case | 处理结论 |
| --- | --- | --- |
| 明显错误 / PASS false positive | `852ce960` | 计入真实错误。模型文本包含 `$400,000`，但最终主结论偏向 `$350,000`，strict 子串命中不应算通过。 |
| 不清晰 / 边界样本 | `a2f3aa27` | 不计入干净 PASS，也不直接计入真实错误。证据是 `close to 1300`，gold 简化为 `1300`，模型谨慎复述证据本身。 |

与 failed-case LLM judge 合并后，当前 50 条样本的最终口径记录在 `phase_a_v5_comparison.md`：清晰真实通过率约为 `42/50 = 84.0%`，真实错误 `6/50 = 12.0%`，边界/不清晰样本 `2/50 = 4.0%`。
