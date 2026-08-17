# LongMemEval Phase A v5 Failed Case Deep Dive

## Summary

- failed strict cases: `22/50`
- strict pass: `28/50 = 56.0%`
- secondary pass: `30/50 = 60.0%`
- language mismatch among all cases: `8/50`
- all failed records include paths to provider request, answer debug, and structured evidence snapshots.

## Failure Table

| source_id | category | strict_method | secondary | lang | support | attribution | model_answer |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| 60bf93ed_abs | abstention | deterministic_mismatch | abstention_intent | en->en | True | abstention_intent_passed_deterministic_fail, semantic_review_needed, supported_but_deterministic_mismatch | I don't have any record of an iPad case purchase or delivery in my available memory, so I can't tell you how many days it took to arrive. Th |
| 88432d0a_abs | abstention | deterministic_mismatch | abstention_intent | en->en | True | abstention_intent_passed_deterministic_fail, semantic_review_needed, supported_but_deterministic_mismatch | Based on the available memory, there's no record of you baking egg tarts in the past two weeks (May 15–29, 2023). The closest thing I can fi |
| c8090214_abs | abstention | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | I can't calculate that from memory — the available records don't include when you bought your iPad. What I do have: you attended the Holiday |
| 031748ae | knowledge-update | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | Based on the records:  - When you first started as Senior Software Engineer, you led **4 engineers** (May 2023). - Now you lead **5 engineer |
| e493bb7c | knowledge-update | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | Based on the latest record from our conversation (2023-10-30), the "Ethereal Dreams" painting by Emma Taylor is currently hanging **above yo |
| 6456829e | multi-session | deterministic_mismatch | deterministic_mismatch | en->en | True | supported_but_deterministic_mismatch | Based on what you told me earlier:  - Tomatoes: **5 plants** initially - Cucumbers: **3 plants**  Both were producing plenty, by the sound o |
| b3c15d39 | multi-session | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | 5 days — you ordered it online on February 5th, and it arrived on February 10th. |
| gpt4_7fce9456 | multi-session | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | Based on what's recorded, you viewed 4 properties before making the offer on the Brookside townhouse (which was on Feb 25):  1. Oakwood 3-be |
| 8aef76bc | single-session-assistant | deterministic_mismatch | deterministic_mismatch | en->zh | True | language_mismatch_scorer_false_negative_possible, supported_but_deterministic_mismatch | 是 Mod Podge，或者任何其他密封剂——当时说的是用来封住报纸花瓶、让它防水。 |
| ceb54acb | single-session-assistant | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | 还记得，当时除了 "sexual compulsions"，另外四个选项是：  1. Sexual fixations 2. Problematic sexual behaviors 3. Sexual impulsivity 4. Compulsive sexuality  都 |
| 0a34ad58 | single-session-preference | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | Don't worry too much—Tokyo's transit system is big, but it's also one of the easiest to navigate once you get the rhythm. A few things that  |
| 54026fce | single-session-preference | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | Based on what we talked about before, here are a few ways that could help you stay connected:  - **Virtual coffee breaks** — you seemed to l |
| a89d7624 | single-session-preference | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | Based on what we talked about before, Denver is definitely worth a music-focused trip. Since you loved the scene there, here's what I'd put  |
| 4100d0a0 | single-session-user | deterministic_mismatch | deterministic_mismatch | en->en | True | supported_but_deterministic_mismatch | Based on what you told me in our conversation, your ethnicity is Irish and Italian — you mentioned your mixed ethnicity has shaped your upbr |
| 6f9b354f | single-session-user | deterministic_mismatch | deterministic_mismatch | en->zh | True | language_mismatch_scorer_false_negative_possible, supported_but_deterministic_mismatch | 你重新刷的是**浅灰色**——你自己说"lighter shade of gray"，刷完觉得房间亮堂多了。 |
| f4f1d8a4 | single-session-user | deterministic_mismatch | deterministic_mismatch | en->en | True | supported_but_deterministic_mismatch | Your sister — you mentioned she gave you the new stand mixer as a birthday gift last month. |
| 0bc8ad93 | temporal-reasoning | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | Two months ago from now lands around mid-January. In the record from 2023/01/11, you mentioned a lecture at the History Museum about ancient |
| eac54add | temporal-reasoning | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | Four weeks ago you told me you'd just signed a contract with your first freelance client — that was the big milestone. On March 1 you mentio |
| gpt4_1d80365e | temporal-reasoning | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | Based on what's in my memory, you started your solo camping trip to Yosemite on May 15 (you mentioned that day that you were "just starting" |
| gpt4_8279ba02 | temporal-reasoning | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | 10 days ago — you said "I just got a smoker today" in our conversation on 2023-03-15, and today is 2023-03-25. |
| gpt4_93159ced | temporal-reasoning | deterministic_mismatch | deterministic_mismatch | en->zh | True | language_mismatch_scorer_false_negative_possible, supported_but_deterministic_mismatch | 准确说没有一条记录直接告诉你这个数字，但根据你说的两件事可以算出来：你从事专业工作共 9 年，而在 NovaTech 已经约 4 年 3 个月。  所以加入 NovaTech 之前，你大概工作了 **4 年 9 个月** 左右。这是基于这两条信息的推算，不是你的原话直接给出的数字 |
| gpt4_d6585ce8 | temporal-reasoning | deterministic_mismatch | semantic_review_needed | en->en | True | semantic_review_needed, supported_but_deterministic_mismatch | Here's the chronological order of concerts and music events you attended in the past two months, earliest first:  1. **Billie Eilish** — Wel |

## Root Cause Buckets

| bucket | cases | interpretation |
| --- | ---: | --- |
| semantic_or_rubric_needed | 16 | 答案表达合理但不等于 gold 字符串，偏好题、长答案、列表题需要 rubric/semantic judge。 |
| supported_but_deterministic_mismatch | 3 | 证据命中但 strict contains 未命中，主要是格式、推理表达、单位/日期/列表差异。 |
| language_residual | 3 | 仍有少量 evidence/history 语言锚定导致英文问题中文回答；provider request 中无隐藏语言强制，需要继续增强回答后检或模型约束。 |

## Per-Case Paths

### 60bf93ed_abs
- category: `abstention`
- question: How many days did it take for my iPad case to arrive after I bought it?
- gold: The information provided is not enough. You did not mention buying an iPad case.
- answer: I don't have any record of an iPad case purchase or delivery in my available memory, so I can't tell you how many days it took to arrive. That one's not in our history.
- strict: `deterministic_mismatch`
- secondary: `abstention_intent`
- attribution: `abstention_intent_passed_deterministic_fail, semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0000-chain_tri_governed_answer_contract-baseline-60bf93ed_abs.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0000-chain_tri_governed_answer_contract-baseline-60bf93ed_abs.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0000-chain_tri_governed_answer_contract-baseline-60bf93ed_abs.json`

### 88432d0a_abs
- category: `abstention`
- question: How many times did I bake egg tarts in the past two weeks?
- gold: The information provided is not enough. You did not mention baking egg tarts.
- answer: Based on the available memory, there's no record of you baking egg tarts in the past two weeks (May 15–29, 2023). The closest thing I can find is a **strawberry tart** you mentioned on May 22, along with bread baking and a chocolate cake — but no egg tarts.
- strict: `deterministic_mismatch`
- secondary: `abstention_intent`
- attribution: `abstention_intent_passed_deterministic_fail, semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0001-chain_tri_governed_answer_contract-baseline-88432d0a_abs.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0001-chain_tri_governed_answer_contract-baseline-88432d0a_abs.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0001-chain_tri_governed_answer_contract-baseline-88432d0a_abs.json`

### c8090214_abs
- category: `abstention`
- question: How many days before I bought my iPad did I attend the Holiday Market?
- gold: The information provided is not enough. You mentioned getting the iPhone 13 Pro and attending the market, but you did not mention buying an iPad.
- answer: I can't calculate that from memory — the available records don't include when you bought your iPad. What I do have: you attended the Holiday Market about a week before Black Friday, which would put it around mid-to-late November in the 2022 holiday season. If you tell me the iPad purchase date, I can work out the exact number of days.
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0002-chain_tri_governed_answer_contract-baseline-c8090214_abs.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0002-chain_tri_governed_answer_contract-baseline-c8090214_abs.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0002-chain_tri_governed_answer_contract-baseline-c8090214_abs.json`

### 031748ae
- category: `knowledge-update`
- question: How many engineers do I lead when I just started my new role as Senior Software Engineer? How many engineers do I lead now?
- gold: When you just started your new role as Senior Software Engineer, you led 4 engineers. Now, you lead 5 engineers
- answer: Based on the records:  - When you first started as Senior Software Engineer, you led **4 engineers** (May 2023). - Now you lead **5 engineers** (as of October 2023).
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0003-chain_tri_governed_answer_contract-baseline-031748ae.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0003-chain_tri_governed_answer_contract-baseline-031748ae.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0003-chain_tri_governed_answer_contract-baseline-031748ae.json`

### e493bb7c
- category: `knowledge-update`
- question: Where is the painting 'Ethereal Dreams' by Emma Taylor currently hanging?
- gold: in my bedroom
- answer: Based on the latest record from our conversation (2023-10-30), the "Ethereal Dreams" painting by Emma Taylor is currently hanging **above your bed** — you mentioned you'd recently moved it there. Earlier (July) it was above the living room sofa, but that was before the move.
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0009-chain_tri_governed_answer_contract-baseline-e493bb7c.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0009-chain_tri_governed_answer_contract-baseline-e493bb7c.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0009-chain_tri_governed_answer_contract-baseline-e493bb7c.json`

### 6456829e
- category: `multi-session`
- question: How many plants did I initially plant for tomatoes and cucumbers?
- gold: 8
- answer: Based on what you told me earlier:  - Tomatoes: **5 plants** initially - Cucumbers: **3 plants**  Both were producing plenty, by the sound of it.
- strict: `deterministic_mismatch`
- secondary: `deterministic_mismatch`
- attribution: `supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0013-chain_tri_governed_answer_contract-baseline-6456829e.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0013-chain_tri_governed_answer_contract-baseline-6456829e.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0013-chain_tri_governed_answer_contract-baseline-6456829e.json`

### b3c15d39
- category: `multi-session`
- question: How many days did it take for me to receive the new remote shutter release after I ordered it?
- gold: 5 days. 6 days (including the last day) is also acceptable.
- answer: 5 days — you ordered it online on February 5th, and it arrived on February 10th.
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0017-chain_tri_governed_answer_contract-baseline-b3c15d39.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0017-chain_tri_governed_answer_contract-baseline-b3c15d39.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0017-chain_tri_governed_answer_contract-baseline-b3c15d39.json`

### gpt4_7fce9456
- category: `multi-session`
- question: How many properties did I view before making an offer on the townhouse in the Brookside neighborhood?
- gold: I viewed four properties before making an offer on the townhouse in the Brookside neighborhood. The reasons I didn't make an offer on them were: the kitchen of the bungalow needed serious renovation, the property in Cedar Creek was out of my budget, the noise from the highway was a deal-breaker for the 1-bedroom condo, and my offer on the 2-bedroom condo was rejected due to a higher bid.
- answer: Based on what's recorded, you viewed 4 properties before making the offer on the Brookside townhouse (which was on Feb 25):  1. Oakwood 3-bedroom bungalow — viewed Jan 22 2. A property in Cedar Creek — viewed Feb 1 (out of your budget) 3. Downtown 1-bedroom condo — viewed Feb 10 (highway noise was a deal-breaker) 4. 2-bedroom condo — viewed Feb 15 (offer rejected Feb 17 due to a higher bid)  That's just what's documented in our conversations, though — it's possible you looked at more that we nev
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0021-chain_tri_governed_answer_contract-baseline-gpt4_7fce9456.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0021-chain_tri_governed_answer_contract-baseline-gpt4_7fce9456.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0021-chain_tri_governed_answer_contract-baseline-gpt4_7fce9456.json`

### 8aef76bc
- category: `single-session-assistant`
- question: I'm going back to our previous conversation about DIY home decor projects using recycled materials. Can you remind me what sealant you recommended for the newspaper flower vase?
- gold: Mod Podge or another sealant
- answer: 是 Mod Podge，或者任何其他密封剂——当时说的是用来封住报纸花瓶、让它防水。
- strict: `deterministic_mismatch`
- secondary: `deterministic_mismatch`
- attribution: `language_mismatch_scorer_false_negative_possible, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0025-chain_tri_governed_answer_contract-baseline-8aef76bc.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0025-chain_tri_governed_answer_contract-baseline-8aef76bc.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0025-chain_tri_governed_answer_contract-baseline-8aef76bc.json`

### ceb54acb
- category: `single-session-assistant`
- question: In our previous chat, you suggested 'sexual compulsions' and a few other options for alternative terms for certain behaviors. Can you remind me what the other four options were?
- gold: I suggested 'sexual fixations', 'problematic sexual behaviors', 'sexual impulsivity', and 'compulsive sexuality'.
- answer: 还记得，当时除了 "sexual compulsions"，另外四个选项是：  1. Sexual fixations 2. Problematic sexual behaviors 3. Sexual impulsivity 4. Compulsive sexuality  都是围绕"难以控制的性行为模式"找的替代说法。
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0026-chain_tri_governed_answer_contract-baseline-ceb54acb.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0026-chain_tri_governed_answer_contract-baseline-ceb54acb.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0026-chain_tri_governed_answer_contract-baseline-ceb54acb.json`

### 0a34ad58
- category: `single-session-preference`
- question: I’m a bit anxious about getting around Tokyo. Do you have any helpful tips?
- gold: The user would prefer responses that utilize their existing resources, such as their Suica card and TripIt app, to provide personalized tips for navigating Tokyo's public transportation. They might not prefer general tips or recommendations that do not take into account their prior preparations.
- answer: Don't worry too much—Tokyo's transit system is big, but it's also one of the easiest to navigate once you get the rhythm. A few things that will genuinely help:  **Just use your Suica for everything** You already have one, which is the biggest hurdle cleared. Tap it on the reader at the ticket gate when you enter and when you exit a station, and it handles the fare automatically. It works across JR lines and the Tokyo Metro, so you don't need to figure out different tickets.  **Follow the signs,
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0028-chain_tri_governed_answer_contract-baseline-0a34ad58.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0028-chain_tri_governed_answer_contract-baseline-0a34ad58.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0028-chain_tri_governed_answer_contract-baseline-0a34ad58.json`

### 54026fce
- category: `single-session-preference`
- question: I've been thinking about ways to stay connected with my colleagues. Any suggestions?
- gold: The user would prefer responses that acknowledge their desire for social interaction and collaboration while working remotely, utilizing their previous experiences with company initiatives and team collaborations. They might prefer suggestions of virtual team-building activities, regular check-ins, or joining interest-based groups within the company. The user may not prefer generic suggestions that do not take into account their specific work situation or previous attempts at staying connected with colleagues.
- answer: Based on what we talked about before, here are a few ways that could help you stay connected:  - **Virtual coffee breaks** — you seemed to like this one. A short, no-agenda video call for casual chat works surprisingly well. - **Light team activities** — trivia, an online game, even a shared playlist can give people a reason to hang out beyond work tasks. - **Casual social channels** — a Slack or Teams channel for non-work talk, where people can share what they're up to. - **Interest groups** — 
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0029-chain_tri_governed_answer_contract-baseline-54026fce.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0029-chain_tri_governed_answer_contract-baseline-54026fce.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0029-chain_tri_governed_answer_contract-baseline-54026fce.json`

### a89d7624
- category: `single-session-preference`
- question: I'm planning a trip to Denver soon. Any suggestions on what to do there?
- gold: The user would prefer responses that take into account their previous experience in Denver, specifically their interest in live music and memorable encounter with Brandon Flowers. They might appreciate suggestions that revisit or build upon this experience, such as revisiting the same bar or exploring similar music venues in the area. The user may not prefer general tourist recommendations or activities unrelated to their interest in live music.
- answer: Based on what we talked about before, Denver is definitely worth a music-focused trip. Since you loved the scene there, here's what I'd put on the list:  **Venues:** - Red Rocks Park and Amphitheatre — you've already been, but it's still the crown jewel - The Ogden Theatre — historic, intimate indie/rock/electronic shows - The Bluebird Theater — great atmosphere, diverse lineup - The Fillmore Auditorium — legendary, hosted The Grateful Dead and Jimi Hendrix - Larimer Lounge — smaller and laid-ba
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0030-chain_tri_governed_answer_contract-baseline-a89d7624.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0030-chain_tri_governed_answer_contract-baseline-a89d7624.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0030-chain_tri_governed_answer_contract-baseline-a89d7624.json`

### 4100d0a0
- category: `single-session-user`
- question: What is my ethnicity?
- gold: A mix of Irish and Italian
- answer: Based on what you told me in our conversation, your ethnicity is Irish and Italian — you mentioned your mixed ethnicity has shaped your upbringing.
- strict: `deterministic_mismatch`
- secondary: `deterministic_mismatch`
- attribution: `supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0031-chain_tri_governed_answer_contract-baseline-4100d0a0.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0031-chain_tri_governed_answer_contract-baseline-4100d0a0.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0031-chain_tri_governed_answer_contract-baseline-4100d0a0.json`

### 6f9b354f
- category: `single-session-user`
- question: What color did I repaint my bedroom walls?
- gold: a lighter shade of gray
- answer: 你重新刷的是**浅灰色**——你自己说"lighter shade of gray"，刷完觉得房间亮堂多了。
- strict: `deterministic_mismatch`
- secondary: `deterministic_mismatch`
- attribution: `language_mismatch_scorer_false_negative_possible, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0032-chain_tri_governed_answer_contract-baseline-6f9b354f.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0032-chain_tri_governed_answer_contract-baseline-6f9b354f.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0032-chain_tri_governed_answer_contract-baseline-6f9b354f.json`

### f4f1d8a4
- category: `single-session-user`
- question: Who gave me a new stand mixer as a birthday gift?
- gold: my sister
- answer: Your sister — you mentioned she gave you the new stand mixer as a birthday gift last month.
- strict: `deterministic_mismatch`
- secondary: `deterministic_mismatch`
- attribution: `supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0036-chain_tri_governed_answer_contract-baseline-f4f1d8a4.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0036-chain_tri_governed_answer_contract-baseline-f4f1d8a4.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0036-chain_tri_governed_answer_contract-baseline-f4f1d8a4.json`

### 0bc8ad93
- category: `temporal-reasoning`
- question: I mentioned visiting a museum two months ago. Did I visit with a friend or not?
- gold: No, you did not visit with a friend.
- answer: Two months ago from now lands around mid-January. In the record from 2023/01/11, you mentioned a lecture at the History Museum about ancient civilizations — no friend was mentioned there.  The visit with a friend (the chemistry professor) was the behind-the-scenes Science Museum tour, and that was mentioned back in October 2022, so it's about four-plus months ago, not two.  So: the museum mention from roughly two months ago didn't involve a friend; the friend visit was a separate, earlier memory
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0037-chain_tri_governed_answer_contract-baseline-0bc8ad93.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0037-chain_tri_governed_answer_contract-baseline-0bc8ad93.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0037-chain_tri_governed_answer_contract-baseline-0bc8ad93.json`

### eac54add
- category: `temporal-reasoning`
- question: What was the significant buisiness milestone I mentioned four weeks ago?
- gold: I signed a contract with my first client.
- answer: Four weeks ago you told me you'd just signed a contract with your first freelance client — that was the big milestone. On March 1 you mentioned it while asking for advice on building a solid contract template for future projects.
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0040-chain_tri_governed_answer_contract-baseline-eac54add.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0040-chain_tri_governed_answer_contract-baseline-eac54add.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0040-chain_tri_governed_answer_contract-baseline-eac54add.json`

### gpt4_1d80365e
- category: `temporal-reasoning`
- question: How many days did I spend on my solo camping trip to Yosemite National Park?
- gold: 2 days. 3 days (including the last day) is also acceptable.
- answer: Based on what's in my memory, you started your solo camping trip to Yosemite on May 15 (you mentioned that day that you were "just starting" it), and you got back on May 17 (you said you "just got back" that day). So that's roughly 3 days / 2 nights (May 15–17), though the exact number of days isn't explicitly stated in what I remember.
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0041-chain_tri_governed_answer_contract-baseline-gpt4_1d80365e.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0041-chain_tri_governed_answer_contract-baseline-gpt4_1d80365e.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0041-chain_tri_governed_answer_contract-baseline-gpt4_1d80365e.json`

### gpt4_8279ba02
- category: `temporal-reasoning`
- question: How many days ago did I buy a smoker?
- gold: 10 days ago. 11 days (including the last day) is also acceptable.
- answer: 10 days ago — you said "I just got a smoker today" in our conversation on 2023-03-15, and today is 2023-03-25.
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0046-chain_tri_governed_answer_contract-baseline-gpt4_8279ba02.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0046-chain_tri_governed_answer_contract-baseline-gpt4_8279ba02.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0046-chain_tri_governed_answer_contract-baseline-gpt4_8279ba02.json`

### gpt4_93159ced
- category: `temporal-reasoning`
- question: How long have I been working before I started my current job at NovaTech?
- gold: 4 years and 9 months
- answer: 准确说没有一条记录直接告诉你这个数字，但根据你说的两件事可以算出来：你从事专业工作共 9 年，而在 NovaTech 已经约 4 年 3 个月。  所以加入 NovaTech 之前，你大概工作了 **4 年 9 个月** 左右。这是基于这两条信息的推算，不是你的原话直接给出的数字。
- strict: `deterministic_mismatch`
- secondary: `deterministic_mismatch`
- attribution: `language_mismatch_scorer_false_negative_possible, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0047-chain_tri_governed_answer_contract-baseline-gpt4_93159ced.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0047-chain_tri_governed_answer_contract-baseline-gpt4_93159ced.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0047-chain_tri_governed_answer_contract-baseline-gpt4_93159ced.json`

### gpt4_d6585ce8
- category: `temporal-reasoning`
- question: What is the order of the concerts and musical events I attended in the past two months, starting from the earliest?
- gold: The order of the concerts I attended is: 1. Billie Eilish concert at the Wells Fargo Center in Philly, 2. Free outdoor concert series in the park, 3. Music festival in Brooklyn, 4. Jazz night at a local bar, 5. Queen + Adam Lambert concert at the Prudential Center in Newark, NJ.
- answer: Here's the chronological order of concerts and music events you attended in the past two months, earliest first:  1. **Billie Eilish** — Wells Fargo Center, Philly, with your sister (around 2023-03-18) 2. **Free outdoor concert series in the park** — discovering new local talent (around 2023-03-25) 3. **Music festival in Brooklyn** — with a group of friends, lineup of your favorite indie bands, where you saw Glass Animals live (around 2023-04-01) 4. **Jazz night at a local bar** — intimate live 
- strict: `deterministic_mismatch`
- secondary: `semantic_review_needed`
- attribution: `semantic_review_needed, supported_but_deterministic_mismatch`
- provider_request: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_provider_requests/0048-chain_tri_governed_answer_contract-baseline-gpt4_d6585ce8.json`
- answer_debug: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_answer_debug/0048-chain_tri_governed_answer_contract-baseline-gpt4_d6585ce8.json`
- structured_evidence: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v5/workspace/public_long_memory_structured_evidence/0048-chain_tri_governed_answer_contract-baseline-gpt4_d6585ce8.json`
