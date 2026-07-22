# 睡眠巩固记忆库卫生评测报告

本报告来自确定性离线 evidence，不修改真实记忆库。

| 指标 | 数值 |
| --- | ---: |
| case 数 | 920 |
| 扫描 active item 数 | 1270 |
| evidence row 数 | 1120 |
| 重复候选识别率 | 100.0% |
| 过期候选识别率 | 100.0% |
| 低价值候选识别率 | 100.0% |
| 来源覆盖率 | 89.2857% |
| proxy 回源成功率 | 100.0% |
| shadow 估算 token 节省率 | 46.8599% |
| 关键记忆保持率 | 92.7273% |
| 关键记忆误伤候选数 | 40 |
| 非预期候选数 | 40 |
| 误伤候选率 | 7.2727% |
| 实际应用变更数 | 0 |

说明：当前阶段仍是 shadow / dry-run。重复、过期、低价值和 token 节省均表示候选识别或估算，不表示真实 DB 已经被清理。

## standard / hard / overall

| case_set | case 数 | evaluated item 数 | candidate recall | candidate precision | retained protection | false positive cleanup | safe evidence token saving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| standard | 600 | 600 | 100.0% | 100.0% | 100.0% | 0.0% | 64.0138% |
| hard | 320 | 520 | 100.0% | 75.0% | 90.0% | 10.0% | unsafe |
| overall | 920 | 1120 | 100.0% | 93.4426% | 92.7273% | 7.2727% | unsafe |
