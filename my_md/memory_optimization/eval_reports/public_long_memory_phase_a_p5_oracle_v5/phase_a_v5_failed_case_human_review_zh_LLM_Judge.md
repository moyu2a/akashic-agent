# 1.假错误

1. 输入问题
   用户问：
   How many days did it take for my iPad case to arrive after I bought it?
   标准答案是：
   The information provided is not enough. You did not mention buying an iPad case.
   也就是说，正确做法不是算天数，而是识别：历史里没有提到 iPad case，只能拒答。
2. 召回阶段
   三路召回找到了相关历史，但相关的是：
   用户提到新 laptop backpack，到货日期是 1/20
   后面又提到 backpack 是 1/15 从 Amazon 买的
   还有显卡、Wi-Fi、password manager 等信息
   关键点：召回证据里有“买了某个东西并到货”的结构，但那个东西是 laptop backpack，不是 iPad case。
3. 治理后证据
   结构化证据把 60bf93ed_abs_history_0001 和 0002 放进了 allowed evidence。没有 forbidden boundary，也没有 insufficient fallback。
   这说明系统认为有足够证据进入模型，但这些证据其实只能支持“没有 iPad case 记录”，不能支持计算 iPad case 到货天数。
4. 模型实际回答
   模型输出是：
   I don't have any record of an iPad case purchase or delivery in my available memory, so I can't tell you how many days it took to arrive.
   这在语义上是正确的：它没有误把 backpack 当成 iPad case，也没有硬算 1/15 -> 1/20 = 5 days。
5. 为什么被判错
   出错点在 strict scorer，不是模型事实错误。
   strict passed：False
   strict method：deterministic_mismatch
   secondary passed：True
   secondary method：abstention_intent
   strict scorer 是确定性字符串匹配或近似包含逻辑。标准答案说的是：
   The information provided is not enough. You did not mention buying an iPad case.
   模型说的是：
   I don't have any record of an iPad case purchase or delivery...
   两者语义等价，都是“没有足够信息/没有 iPad case 购买记录”，但字符串没有命中 gold，所以 strict 判失败。
   所以这个 case 的结论是：模型回答没错，评测 strict 口径太硬导致假阴性。secondary scorer 捕捉到了拒答意图，因此判通过。

# 2.假错误 意思相对

第二个 case 88432d0a_abs 也是一个 abstention / 应该拒答 的例子。
它问的是：
How many times did I bake egg tarts in the past two weeks?
也就是：过去两周我烤了几次蛋挞？
gold answer 是：
The information provided is not enough. You did not mention baking egg tarts.
也就是说，标准答案认为：历史材料不足，因为用户没有提到烤过 egg tarts。
材料里实际有什么：
用户做过 / 提到过 chocolate cake，给妹妹生日派对做的巧克力蛋糕。
用户讨论过 fruit tart / strawberry tart，但这是计划做草莓挞或讨论水果挞，不是 egg tart。
用户做过或讨论过 whole wheat bread / focaccia / sourdough bread / Italian bread。
有很多烘焙相关上下文，但没有“baked egg tarts”。
模型输出是：
Based on the available memory, there's no record of you baking egg tarts in the past two weeks... The closest thing I can find is a strawberry tart... but no egg tarts.
这其实是正确的。它没有把 strawberry tart 错当成 egg tart，而是明确指出“没有 egg tarts 记录”。
所以它为什么出错？
和第一个 case 一样，不是模型答错，而是 strict scorer 没认出来语义等价。
strict passed：False
secondary passed：True
secondary method：abstention_intent
strict 要命中 gold 的固定表达：“information not enough / did not mention baking egg tarts”。模型用了另一种表达：“no record of you baking egg tarts”。语义一致，但字符串不一致，所以 strict 判错；secondary 识别到了拒答意图，因此判对。
这个 case 的归因也应该是：合理拒答，deterministic scorer false negative。



# 3.第三个 case c8090214_abs 问的是：

How many days before I bought my iPad did I attend the Holiday Market?
意思是：我在买 iPad 之前多少天参加了 Holiday Market？
标准答案是：
The information provided is not enough. You mentioned getting the iPhone 13 Pro and attending the market, but you did not mention buying an iPad.
材料里有两类相关信息：
用户提到自己在 Black Friday 从 Best Buy 以 $800 折扣价买了 iPhone 13 Pro。
用户提到自己在 Black Friday 前一周 去了 local mall 的 annual Holiday Market。
但没有提到买过 iPad。
所以正确逻辑是：可以知道 Holiday Market 大概发生在 Black Friday 前一周，也可以知道用户买过 iPhone 13 Pro，但问题问的是 iPad。没有 iPad 购买日期，因此不能计算天数。
模型输出是：
I can't calculate that from memory — the available records don't include when you bought your iPad...
它还补充说：已有记录显示 Holiday Market 大约在 Black Friday 前一周，如果告诉我 iPad purchase date，就能计算。
这个回答在事实上是对的。它没有把 iPhone 13 Pro 错当成 iPad，也没有硬算日期差。
但它被判：
strict passed：False
secondary passed：False
secondary method：semantic_review_needed
为什么 secondary 也没过？因为它不像前两个 case 那样被 secondary 直接识别成 abstention_intent。可能原因是模型回答里加了较多补充信息，比如 Holiday Market 的相对时间、mid-to-late November、如果告诉我日期可以计算，这让判分器没有简单归入“拒答意图通过”，而是标成需要人工语义审核。
我的判断：这个 case 也更像是假阴性，不是模型错误。
模型回答与 gold 语义一致：都指出缺少 iPad 购买信息，无法计算。测评只是没把这种带解释的拒答识别为通过。

# 第四个 case 031748ae 是 knowledge-update 类型，问题是：

How many engineers do I lead when I just started my new role as Senior Software Engineer? How many engineers do I lead now?
也就是要回答两个时间点：
刚开始 Senior Software Engineer 新角色时带几个工程师？
现在带几个工程师？
材料里有两段关键历史：
2023/05/11：用户澄清说，刚开始这个 Senior Software Engineer 新角色时，自己带 4 engineers。
2023/10/24：用户后来又说，现在自己带 5 engineers。
gold answer 是：
When you just started your new role as Senior Software Engineer, you led 4 engineers. Now, you lead 5 engineers.
模型输出的 normalized 内容是：
Based on the records, when you first started as Senior Software Engineer, you led 4 engineers (May 2023). Now you lead 5 engineers (as of October 2023).
所以从语义上看，模型答对了：它正确保留了旧事实“刚开始是 4”，也正确使用了新事实“现在是 5”。这正是 knowledge-update 类题想测的能力：不是简单用新信息覆盖全部，而是按时间维度区分“then”和“now”。
为什么被判错？
还是 strict/secondary 判分问题：
strict passed：False
secondary passed：False
secondary method：semantic_review_needed
supporting_fact_hit：True
strict 没过，是因为模型加了 Based on the records、May 2023、as of October 2023 这些解释，导致字符串和 gold 不完全一致。secondary 也没有直接判通过，而是标成需要人工审核。
所以这个 case 不是系统没处理 knowledge update，而是 答案正确但判分器没有接受等价表达。归因可以写成：supported_but_deterministic_mismatch / semantic_review_needed，人工应判通过。



# 第五个 case e493bb7c 也是 knowledge-update，问题是：

Where is the painting 'Ethereal Dreams' by Emma Taylor currently hanging?
gold answer 是：
in my bedroom
历史里有两个版本：
旧信息，2023/07/11：用户说 "Ethereal Dreams" 在 living room sofa 上方，也就是客厅沙发上方。
新信息，2023/10/30：用户说自己最近把 "Ethereal Dreams" by Emma Taylor 移到了 bedroom，具体是 above my bed。
模型输出是：
Based on the latest record... the "Ethereal Dreams" painting by Emma Taylor is currently hanging above your bed... Earlier (July) it was above the living room sofa, but that was before the move.
这其实回答得很好：它不仅用了最新信息，还明确区分了旧位置和当前位置。
为什么被判错？
strict passed：False
secondary passed：False
literal_gold_hit：True
supporting_fact_hit：True
secondary method：semantic_review_needed
这里甚至 literal_gold_hit=True，因为模型回答里包含了 bedroom 相关信息。但 gold 是非常短的 in my bedroom，模型回答是更具体的 above your bed，并补充了旧位置。strict 仍然没有接受整个答案。
所以这个 case 也是 测评假阴性。模型并没有错，甚至比 gold 更精确：above your bed 是 in my bedroom 的具体位置。更合理的人工判定应该是通过。
归因可以写：答案语义正确，正确处理了 knowledge update；deterministic scorer 因答案过具体/附带解释而误判。



# 第六个 case `6456829e` 是 **multi-session** 类型，问题是：

```
How many plants did I initially plant for tomatoes and cucumbers?
```

gold answer 是：

```
8
```

它需要跨两个会话合并信息：

- **2023/05/20** 的番茄会话：用户说 `I planted 5 tomato plants initially`
- **2023/05/26** 的黄瓜会话：用户说 `I've got 3 plants`

所以总数是：

```
5 + 3 = 8
```

模型输出的 normalized 内容是：

```
tomatoes 5 plants initially; cucumbers 3 plants; both were producing plenty
```

也就是说模型其实给出了分解答案：番茄 5 株，黄瓜 3 株。虽然没有直接写最终合计 `8`，但信息足以推出 8。

这里的判分结果是：

- strict passed：`False`
- secondary passed：`False`
- literal_gold_hit：`True`
- supporting_fact_hit：`True`
- failure_attribution：`supported_but_deterministic_mismatch`

这个 case 比前几个稍微不同：模型事实没有错，但**没有按照 gold 的最简输出形式直接回答总数 `8`**。如果问题问 “How many plants”，理想回答应该明确说：

```
8 plants total: 5 tomato plants and 3 cucumber plants.
```

模型只列了 `5` 和 `3`，没有显式合计，所以 deterministic scorer 没过。人工看可以认为语义上接近正确，但如果评测标准要求最终数值，这个 case 可以算“回答格式不够直接”，不是召回或证据错误。

我的判断：**证据和推理都到位，模型答案半对偏可接受；严格来说缺少显式总数 8，导致测评失败。**



# 第七个 case `b3c15d39` 是 **multi-session + 时间差计算**。

问题是：

```
How many days did it take for me to receive the new remote shutter release after I ordered it?
```

gold answer 是：

```
5 days. 6 days (including the last day) is also acceptable.
```

材料里有两个关键会话：

- 一个会话里用户说：新的 remote shutter release **arrived on February 10th**。
- 另一个会话里用户说：自己在 **February 5th** 发现旧的丢了，于是在线订购了新的 remote shutter release。

所以需要跨会话合并：

```
February 5 -> February 10 = 5 days
```

如果按包含首尾日期的口径，也可以说 6 days。

模型输出是：

```
5 days — you ordered it online on February 5th, and it arrived on February 10th.
```

这就是 gold 的第一个可接受答案，完全正确。

但判分结果：

- strict passed：`False`
- secondary passed：`False`
- secondary method：`semantic_review_needed`
- supporting_fact_hit：`True`

这里很明显是测评误判。模型答案开头就是 `5 days`，而 gold 也允许 `5 days`。失败大概率来自 deterministic normalized matching 没有处理好 gold 中的“5 days. 6 days ... also acceptable”这种多可接受答案格式，或者 contains 逻辑要求整段 gold 被包含。

这个 case 应该人工判通过。它不是召回错，也不是回答错，而是 **gold 多答案格式 + strict scorer 过硬导致假阴性**



# 第八个 case `gpt4_7fce9456` 是典型 **multi-session 汇总题**。

问题是：

```
How many properties did I view before making an offer on the townhouse in the Brookside neighborhood?
```

gold answer 说：用户在 Brookside townhouse 出价前看过 **4 个房产**，并列出原因：

1. Oakwood 的 3-bedroom bungalow，厨房需要严重翻修。
2. Cedar Creek 的房产，超出预算。
3. downtown 的 1-bedroom condo，高速公路噪音无法接受。
4. 2-bedroom condo，出价被更高报价击败。

材料分布在多个会话里：

- **Jan 22**：看了 Oakwood 的 3-bedroom bungalow，但厨房需要 serious renovation。
- **Feb 1**：看了 Cedar Creek 的房产，但 out of budget。
- **Feb 10**：看了 downtown 1-bedroom condo，但 highway noise 是 deal-breaker。
- **Feb 15**：看了 2-bedroom condo，后来 **Feb 17** offer 被 higher bid 拒绝。
- **Feb 25**：对 Brookside 的 3-bedroom townhouse 出价。

模型输出的 normalized 内容是：

```
you viewed 4 properties... Oakwood bungalow... Cedar Creek... downtown 1-bedroom condo... 2-bedroom condo...
```

也就是说，它答出了数量 `4`，也列出了四个房产和对应原因，基本和 gold 完全一致。

为什么被判错？

- strict passed：`False`
- secondary passed：`False`
- secondary method：`semantic_review_needed`
- supporting_fact_hit：`True`

这个 case 很明显又是 **字符串/表达不匹配导致的假阴性**。模型说的是 “Based on what's recorded... possible you looked at more that we never discussed”，比 gold 多了一个谨慎限定；另外顺序、措辞不同，比如 “highway noise was a dealbreaker” vs “noise from the highway was a deal-breaker”。语义是一样的，但 deterministic scorer 没吃进去。

所以这个 case 应该人工判通过：**跨会话召回正确、汇总正确、答案也正确，只是 strict/secondary 没理解等价表达。**



# 真错误

# 中英混杂类

# 第九个 case `8aef76bc` 是 **single-session-assistant** 类型，问题是：

```
Can you remind me what sealant you recommended for the newspaper flower vase?
```

gold answer 是：

```
Mod Podge or another sealant
```

材料里只有一个相关会话：用户问“用回收材料做 DIY 家居装饰项目”，assistant 给了几个项目。其中 **Newspaper Flower Vase** 这一项写得很明确：

```
Seal the vase with Mod Podge or another sealant to make it water-resistant.
```

所以正确答案就是：**Mod Podge，或者其他密封剂**。

模型实际输出从 normalized answer 看是：

```
是 Mod Podge 或者任何其他密封剂，当时说的是用来封住报纸花瓶，让它防水。
```

事实是对的，证据也命中了：

- `literal_gold_hit=True`
- `supporting_fact_hit=True`

但判分失败：

- strict passed：`False`
- secondary passed：`False`
- language mismatch：`True`
- question_language -> response_language：`en -> zh`

核心问题是：**用户问题是英文，但模型用中文回答了。**

所以这个 case 和前几个不太一样。它不是事实错误，也不是召回错误，而是 **语言遵循错误**：evidence contract 明确要求“用当前用户问题的语言回答”，但模型输出中文。测评失败主要合理，虽然事实内容本身是正确的。



# 第十个 case `ceb54acb` 是 **single-session-assistant** 类型，问题是：

```
In our previous chat, you suggested 'sexual compulsions' and a few other options... what the other four options were?
```

gold answer 是：

```
I suggested 'sexual fixations', 'problematic sexual behaviors', 'sexual impulsivity', and 'compulsive sexuality'.
```

证据里确实有上一轮 assistant 的推荐：

1. Sexual fixations
2. Problematic sexual behaviors
3. Sexual impulsivity
4. Compulsive sexuality

模型 normalized answer 是：

```
还记得当时除了 sexual compulsions 另外 4 个选项是 1 sexual fixations 2 problematic sexual behaviors 3 sexual impulsivity 4 compulsive sexuality...
```

所以事实内容完全正确。

但这里有个有意思的点：文档判定里写 `question_language -> response_language：en -> en`、`language_mismatch=False`，但 normalized answer 明显是中文包着英文术语：

```
还记得当时除了...另外4个选项是...
```

也就是说语言检测可能没把它判成中文，因为核心术语是英文，或者混合文本占比导致误判。严格来说，这个回答也存在轻微语言遵循问题：用户用英文问，理想回答应全英文。

为什么 strict 没过？

- strict passed：`False`
- secondary passed：`False`
- secondary method：`semantic_review_needed`
- supporting_fact_hit：`True`

它没有使用 gold 的原句结构 `I suggested...`，并且中文前后缀导致 normalized 字符串不匹配，所以 deterministic scorer 判错。

我的判断：

- **事实正确**
- **召回正确**
- **答案内容覆盖 gold**
- 但 **输出语言不够干净**，应该用英文回答

如果只看事实，这是测评假阴性；如果把语言规范也算进来，它有一个小问题。更合适的输出应该是：

```c++
The other four options were: sexual fixations, problematic sexual behaviors, sexual impulsivity, and compulsive sexuality.
```

# 



# 第十一个 case `0a34ad58` 是 **single-session-preference** 类型，不是普通事实问答 有迷惑性

用户问题是：

```
I’m a bit anxious about getting around Tokyo. Do you have any helpful tips?
```

gold answer 不是一个标准“应答文本”，而是一个偏好判断：

用户更希望回答能利用 TA 已有准备，比如：

- 已经有 **Suica card**
- 已经下载 **TripIt app**
- 用这些资源给东京公共交通的个性化建议
- 不太希望只给泛泛的通用建议

证据里确实有这些上下文：

- 用户在去 Tsukiji Fish Market 时问过“怎么用刚买的 Suica card 从 Shinjuku 去”。
- 用户说自己下载了 TripIt app 来保持行程有序，但仍然 nervous。
- 多次问东京交通、Narita 到 Shinjuku、路线时间和费用等。

模型输出主要是一些东京交通建议，包含：

- 用 Suica 进出站刷卡
- JR 和 Tokyo Metro 都能用
- 看英文/日文双语标识和线路颜色
- 不确定就问工作人员
- 预留 buffer time
- 累了可以打车
- 穿舒服的鞋

这份回答的问题在于：它**使用了 Suica**，所以抓住了一部分用户偏好；但它**没有提到 TripIt app**，也没有充分围绕用户“已经做过的准备”来组织建议。它更像是“带一点个性化的通用建议”。

判分结果：

- strict passed：`False`
- secondary passed：`False`
- secondary method：`semantic_review_needed`
- supporting_fact_hit：`True`

这个 case 和前面字符串匹配假阴性不同。这里的 gold 本身是 rubric/偏好描述，不适合 deterministic string scorer。需要人工或 LLM judge 看：模型有没有利用用户偏好。

我的判断：**部分正确，但不算满分。**
模型确实用了 Suica 这个关键信息，但漏掉了 TripIt，也没有特别针对“焦虑”提供更结构化的路线准备策略。更理想的回答应该说：

- 用 Suica 解决车票/换乘支付焦虑
- 把酒店、集合点、车站路线提前放进 TripIt
- 每次出门前保存一条主路线和一条备用路线
- 在 Shinjuku/Narita 等大站预留额外时间
- 迷路时直接问站员，不要硬扛

所以第十一个 case 的错误更像是：**偏好利用不完整 + scorer 不适合评偏好题**。



# 第十二个 case `54026fce` 也是 **single-session-preference**。

问题是：

```
I've been thinking about ways to stay connected with my colleagues. Any suggestions?
```

gold 不是固定答案，而是偏好说明：用户希望回答能结合 TA 的远程工作处境和之前聊过的尝试，例如：

- 用户喜欢在家工作的灵活性，但怀念同事间的社交和 watercooler conversations。
- 用户之前对 **virtual coffee breaks** 感兴趣。
- 回答应建议虚拟团队活动、定期 check-ins、公司内部兴趣小组等。
- 不希望只是泛泛地给社交建议。

证据里有明确上下文：

- 用户之前问过如何和同事社交。
- assistant 推荐过 virtual coffee breaks、online team activities、collaborative projects、Slack/Teams social channels、interest-based groups 等。
- 用户明确说喜欢 virtual coffee breaks，并继续追问如何让团队舒适参与、如何不显得强迫。

模型输出是：

- Based on what we talked about before
- Virtual coffee breaks — you seemed to like this one
- Light team activities
- Casual social channels
- Interest groups
- Recognizing milestones
- 建议先从一两个熟悉的人试起，再扩展到团队

我的判断：**这个回答其实挺好，基本命中了偏好。**

它利用了历史偏好：

- 提到了 “you seemed to like this one”
- 把 virtual coffee breaks 放在第一位
- 建议小范围试点，降低尴尬感
- 提到了 interest groups、team activities、social channels

为什么被判错？

- strict passed：`False`
- secondary passed：`False`
- secondary method：`semantic_review_needed`
- supporting_fact_hit：`True`

原因是 gold 是一段 rubric，而模型输出是实际建议文本。deterministic scorer 没法判断“是否符合偏好”，所以判成不匹配，需要人工或 LLM judge。

这个 case 我会判：**模型回答正确，应人工通过。**
和第十一个不同，第十二个对用户偏好的利用更完整，不只是泛泛建议。它唯一可能欠缺的是没有明确说 “while working remotely”，但内容里的 virtual coffee breaks、Teams/Slack/social channels 已经隐含了远程协作语境。



# 第十三个 case `a89d7624` 是 **single-session-preference**，问题是：

```
I'm planning a trip to Denver soon. Any suggestions on what to do there?
```

gold 不是固定答案，而是偏好说明：用户希望建议能结合之前的 Denver 经历，尤其是：

- 用户喜欢 Denver 的 **live music scene**
- 用户之前在 Denver 看了 **The Killers at Red Rocks**
- 用户还见到了 **Brandon Flowers**
- 所以更希望推荐音乐场馆、音乐节、类似体验，而不是泛泛旅游景点

证据里确实有这些历史：

- 用户说去过 The Killers 在 Red Rocks Amphitheater 的演唱会。
- 用户说见到了 Brandon Flowers。
- 用户说自己喜欢 Denver 的 music scene。
- 之前还问过 Denver 的音乐场馆和音乐节。

模型输出是：

```
Based on what we talked about before, Denver is definitely worth a music-focused trip. Since you loved the scene there, here's what I'd put on the list:
...
Honestly, planning around whichever festival lines up with your dates would be the way to go. You might even catch another band to add to your Brandon Flowers story.
```

normalized answer 里完整包含了：

- Red Rocks Park and Amphitheatre
- The Ogden Theatre
- The Bluebird Theater
- The Fillmore Auditorium
- Larimer Lounge
- Grandoozy
- Denver Folk Festival
- Denver Jazz Festival
- Westword Music Showcase
- Riot Fest Denver
- Twist & Shout Records
- The hi-dive
- The Marquis Theater
- 还提到了 Brandon Flowers story

我的判断：**这个回答是正确的，而且很好地利用了用户偏好。**

它没有给泛泛的 Denver 景点，比如博物馆、公园、市区观光，而是围绕 live music 展开，并且呼应了 Brandon Flowers 的经历。这正是 gold rubric 想要的。

为什么被判错？

- strict passed：`False`
- secondary passed：`False`
- secondary method：`semantic_review_needed`
- supporting_fact_hit：`True`

原因仍然是：gold 是“用户偏好描述/rubric”，模型输出是“实际建议”。确定性 scorer 无法判断建议是否满足 rubric，所以判成 mismatch。

这个 case 应该人工判通过。归因是：**偏好利用正确，scorer 不适合评估 preference-style answer。**



# 第十四个 case `4100d0a0` 是 **single-session-user**，问题是：

```
What is my ethnicity?
```

gold answer 是：

```
A mix of Irish and Italian
```

证据里用户明确说过：

```
my mixed ethnicity - Irish and Italian - has shaped my upbringing
```

所以正确答案就是：Irish and Italian 的混合族裔背景。

模型输出是：

```
Based on what you told me in our conversation, your ethnicity is Irish and Italian — you mentioned your mixed ethnicity has shaped your upbringing.
```

这和 gold 完全等价，只是没有写 “a mix of”。

判分结果：

- strict passed：`False`
- secondary passed：`False`
- supporting_fact_hit：`True`
- failure_attribution：`supported_but_deterministic_mismatch`

这个 case 是非常典型的 **deterministic scorer 假阴性**。

事实、召回、回答都没问题。模型说 “Irish and Italian”，gold 说 “A mix of Irish and Italian”，语义完全一致。应该人工判通过。

# 十五：中英混搭

这个 case 问的是：**“What color did I repaint my bedroom walls?”**
证据里用户明确说过：最近把卧室墙重新刷成了 **“a lighter shade of gray”**，也就是**更浅一点的灰色/浅灰色**。

模型输出是：

> 你重新刷的是**浅灰色**——你自己说 “lighter shade of gray”，刷完觉得房间亮堂多了。

所以从事实层面看，模型是对的：答案命中了 `a lighter shade of gray`，也引用了正确证据。

它被判错的主要原因是：**问题是英文，但模型用中文回答了**。报告里也标了：

- `question_language -> response_language: en -> zh`
- `language_mismatch: True`
- `literal_gold_hit: True`
- `supporting_fact_hit: True`

也就是说，这不是记忆召回错，也不是证据错，而是**输出语言不符合要求 + deterministic scorer 字符串匹配失败**。如果按事实正确性评，这个 case 应该算对；如果测评要求必须英文回答，那它有一个语言格式问题。



# 第 16 个 case 是 **`f4f1d8a4`**。

问题是：**Who gave me a new stand mixer as a birthday gift?**
标准答案是：**my sister**。

证据里用户原话很明确：

> I actually got my new stand mixer as a birthday gift from my sister last month...

模型输出是：

> Your sister — you mentioned she gave you the new stand mixer as a birthday gift last month.

所以这个 case **模型完全答对了**。`your sister` 和 gold 的 `my sister` 在问答语境下是同一个人：用户问“谁送我的”，助手回答“你的姐姐/妹妹”。

被判错原因只是 deterministic scorer 太死板：它把模型完整句子归一化成：

```
yoursisteryoumentionedshegave...
```

而 gold 是：

```
mysister
```

字符串不完全一致，所以判 `False`。报告里也显示：

- `literal_gold_hit: True`
- `supporting_fact_hit: True`
- `language_mismatch: False`
- `failure_attribution: supported_but_deterministic_mismatch`

结论：**这是明显的 scorer false negative，不是模型错误。**



# 第 17 个 case 是 **`0bc8ad93`**，类型是 **temporal-reasoning 时间推理**。

问题是：**“我两个月前提到参观博物馆，那次是和朋友一起去的吗？”**
提问日期是 **2023-03-11**，所以“两个月前”大约指 **2023 年 1 月中旬**。

证据里有几条博物馆相关记忆：

- **2022-10-22**：Science Museum behind-the-scenes tour，是和一位化学教授朋友一起去的。
- **2023-01-11**：History Museum 关于古代文明/Petra 的讲座，没有提到朋友。
- **2023-02-18**：Natural History Museum fossil collection，也没有说和朋友一起。

gold answer 是：**No, you did not visit with a friend.**

模型回答的核心是：

> 两个月前对应 1 月中旬；2023-01-11 的 History Museum 讲座没有提到朋友。和朋友一起的是 2022 年 10 月的 Science Museum tour，不是两个月前。所以两个月前那次没有和朋友一起。

这个推理是对的，而且还主动区分了容易混淆的旧记忆：**有朋友的是 10 月那次，不是 1 月那次**。

判错原因还是 scorer 太机械：gold 是短句 `No, you did not visit with a friend.`，模型给了完整推理，没有原样包含 gold，所以 deterministic mismatch；secondary 也标成需要语义审核但默认没过。

结论：**模型没错，这是语义正确但字符串匹配失败的 false negative。**



# 第 18 个 case 是 **`eac54add`**，也是 **temporal-reasoning 时间推理**。

问题是：**“四周前我提到的重大 business milestone 是什么？”**
提问时间是 **2023-03-28**，四周前大约是 **2023-03-01**。

证据里 2023-03-01 用户说：

> I just signed a contract with my first client today...

gold answer 是：

> I signed a contract with my first client.

模型输出是：

> Four weeks ago you told me you'd just signed a contract with your first freelance client — that was the big milestone. On March 1...

这个答案事实完全正确，而且时间推理也正确：3 月 28 往前四周对应 3 月 1，正好命中“签下第一个客户合同”。

判错原因仍然是 deterministic scorer 太死板：gold 是第一人称短句 `I signed a contract with my first client`，模型用了第二人称解释句 `you'd just signed a contract with your first freelance client`，语义等价但字符串不匹配。

结论：**模型没有错，是 scorer false negative；最多只是表达不是 gold 原句，但事实、时间、证据都对。**



# 第 19 个 case 是 **`gpt4_1d80365e`**，还是 **temporal-reasoning 时间推理**。

问题是：**“我在 Yosemite National Park 的 solo camping trip 花了几天？”**
gold answer 是：**2 days；如果把最后一天也算进去，3 days 也可以接受。**

证据里有两个关键时间点：

- **2023-05-15**：用户说 “I just started my solo camping trip to Yosemite National Park today”
- **2023-05-17**：用户说 “I just got back from an amazing solo camping trip to Yosemite National Park today”

所以推理是：从 5 月 15 开始，到 5 月 17 回来。按过夜/完整停留算是 **2 nights / 约 2 days**；按日期包含首尾算是 **3 calendar days**。

模型回答：

> roughly 3 days / 2 nights (May 15–17), though the exact number of days isn't explicitly stated

这和 gold 的接受范围一致。它说了 **3 days / 2 nights**，而 gold 明确说 **3 days including the last day is also acceptable**。

判错原因：gold 是 `2 days. 3 days ... acceptable`，模型没有按 gold 字符串形式输出，而是给了时间推理和“3 days / 2 nights”的自然表达，所以 deterministic scorer 没匹配上，secondary 又标成需要人工语义审查。

结论：**模型是对的；这个 case 也是 scorer false negative。** 模型甚至处理得更稳，因为它说明了“精确 day-count 取决于是否包含最后一天”。



# 第 20 个 case 是 **`gpt4_8279ba02`**，类型还是 **temporal-reasoning 时间推理**。

问题是：**How many days ago did I buy a smoker?**
提问日期是 **2023-03-25**。证据里用户在 **2023-03-15** 说：

> I just got a smoker today...

所以从 3 月 15 到 3 月 25，是 **10 days ago**；如果把首尾日期都算进去，也可以说 **11 days including the last day**。

gold answer 也是：

> 10 days ago. 11 days (including the last day) is also acceptable.

模型输出：

> 10 days ago — you said "I just got a smoker today" in our conversation on 2023-03-15, and today is 2023-03-25.

这个答案完全正确：日期、证据、计算都对。

判错原因仍然是 scorer 的字符串匹配问题。模型没有原样包含 gold 的完整可接受答案格式，而是自然语言解释了计算过程，所以 strict mismatch；secondary 又进入语义审核但没有通过。

结论：**模型没错，这是 false negative。**
这里唯一可以注意的是证据原文是 “got a smoker”，题目说 “buy a smoker”，但 gold 已经认可这条证据，所以不构成模型错误。



# 第 21 个 case 是 **`gpt4_93159ced`**，类型是 **temporal-reasoning 时间推理**。

问题是：**How long have I been working before I started my current job at NovaTech?**
gold answer 是：**4 years and 9 months**。

证据有两条：

- 用户说自己 **professionally working for 9 years**
- 用户又说在 **NovaTech working for about 4 years and 3 months**

所以计算就是：

**9 年 - 4 年 3 个月 = 4 年 9 个月**

模型输出的核心也是：

> 加入 NovaTech 之前，大概工作了 **4 年 9 个月** 左右。

所以事实和推理都是正确的。

它被判错有两个原因：

1. **语言不匹配**：问题是英文，模型用中文回答，报告标了 `en -> zh` 和 `language_mismatch: True`。
2. **字符串匹配失败**：gold 是英文 `4 years and 9 months`，模型输出中文 `4 年 9 个月`，deterministic scorer 没认出来。

结论：**事实上模型答对了，但有语言格式问题。**
如果按 benchmark 要求“同语言回答”，这算一个输出语言错误；如果只看记忆和推理能力，这是正确答案

第 22 个 case 是 **`gpt4_d6585ce8`**，类型是 **temporal-reasoning / chronological ordering**。

问题是：**过去两个月里我参加过的 concerts / musical events，按最早到最晚排序是什么？**
提问日期是 **2023-04-22**。

gold 顺序是：

1. Billie Eilish concert at Wells Fargo Center in Philly
2. Free outdoor concert series in the park
3. Music festival in Brooklyn
4. Jazz night at a local bar
5. Queen + Adam Lambert concert at Prudential Center in Newark, NJ

模型输出的顺序是：

1. **Billie Eilish** — 2023-03-18
2. **Free outdoor concert series in the park** — 2023-03-25
3. **Music festival in Brooklyn** — 2023-04-01
4. **Jazz night at a local bar** — 2023-04-08
5. **Queen with Adam Lambert** — 2023-04-15

这个顺序和 gold **完全一致**，而且模型还补充了地点、同行人、日期依据，都是合理的。

被判错的原因还是 deterministic scorer 太机械：gold 是一句压缩列表，模型是带编号、日期和额外细节的自然语言列表，所以 normalized 字符串不一致。secondary 标了 `semantic_review_needed`，但最后仍然没通过。

结论：**模型答对了，这是 scorer false negative。**
这个 case 不是模型排序错，也不是召回错，而是评分器没有识别“同一列表顺序 + 合理补充信息”的等价答案。

---

# Static/Strict 未通过 Case 的最终复盘结论

结合逐条人工审阅和本文件中的 LLM Judge 审阅，`strict/static failed` 不能直接等价为模型或记忆治理失败。当前 22 条 strict 未通过 case 里，大多数是 scorer false negative：证据召回命中，结构化证据进入模型，模型答案在事实/时间/列表顺序上可被人工判为正确，但 deterministic scorer 因为表达方式、解释性文本、多可接受答案、第一/第二人称转换、或 preference rubric 不是固定字符串而判错。

后续修复只聚焦真正错误，不按 strict failed 全集逐条修：

| 分类 | 代表 case | 结论 | 后续处理 |
| --- | --- | --- | --- |
| 语言遵循问题 | `8aef76bc`, `6f9b354f`, `gpt4_93159ced`; `ceb54acb` 为中英混杂/语言不干净 | 事实基本正确，但英文问题时输出中文或中文包裹英文术语，违反“按当前用户问题语言回答”的全局答案契约。 | 需要全局修复语言诱导、答案契约和必要的 post-check/retry。 |
| 偏好题判断/利用不足 | `0a34ad58` | 使用了部分偏好证据（Suica），但漏掉关键准备信息（TripIt），回答偏通用，没有充分围绕用户已有准备和焦虑场景组织。 | 需要提升偏好类问题的证据利用和答案组织，不做数据集特化。 |
| scorer false negative | `60bf93ed_abs`, `88432d0a_abs`, `c8090214_abs`, `031748ae`, `e493bb7c`, `b3c15d39`, `gpt4_7fce9456`, `54026fce`, `a89d7624`, `4100d0a0`, `f4f1d8a4`, `0bc8ad93`, `eac54add`, `gpt4_1d80365e`, `gpt4_8279ba02`, `gpt4_d6585ce8` 等 | 模型事实正确或人工可接受，失败来自 strict/static 字符串评分过硬。 | 不作为记忆治理链路 bug 修复；仅作为 scorer/rubric 评估改进材料。 |
| 非优先答案形式问题 | `6456829e` | 证据和分解推理正确，输出了 `5` 和 `3`，但没有显式写总数 `8`。 | 不是召回/治理错误；除非单独优化 direct-answer-first 契约，否则不列入本轮真实错误范围。 |

因此，本轮评测后的真实待修问题收敛为两类：**语言问题** 和 **偏好题判断/利用不足**。strict/static 分数继续作为保守下界记录，不能单独作为后续修复目标选择依据。
