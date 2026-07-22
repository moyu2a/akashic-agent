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
| shadow 估算 token 节省率 | 42.5121% |
| 关键记忆保持率 | 100.0% |
| 关键记忆误伤候选数 | 0 |
| 非预期候选数 | 0 |
| 误伤候选率 | 0.0% |
| 实际应用变更数 | 0 |

说明：当前阶段仍是 shadow / dry-run。重复、过期、低价值和 token 节省均表示候选识别或估算，不表示真实 DB 已经被清理。

## standard / hard / overall

| case_set | case 数 | evaluated item 数 | candidate recall | candidate precision | retained protection | false positive cleanup | safe evidence token saving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| standard | 600 | 600 | 100.0% | 100.0% | 100.0% | 0.0% | 64.0138% |
| hard | 320 | 520 | 100.0% | 100.0% | 100.0% | 0.0% | 23.7952% |
| overall | 920 | 1120 | 100.0% | 100.0% | 100.0% | 0.0% | 42.5121% |

## V3 cleanup / review action metrics

| case_set | cleanup recall | cleanup precision | merge suggestions | review required | safe cleanup token saving |
| --- | ---: | ---: | ---: | ---: | ---: |
| standard | 100.0% | 100.0% | 0 | 0 | 64.0138% |
| hard | 100.0% | 100.0% | 40 | 120 | 23.7952% |
| overall | 100.0% | 100.0% | 40 | 120 | 42.5121% |

## hard scenario breakdown

| scenario | case 数 | evaluated item 数 | cleanup recall | cleanup precision | merge suggestions | review required | retained protection |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_scope_identical | 40 | 80 | unavailable | unavailable | 0 | 0 | 100.0% |
| missing_source_but_important | 40 | 40 | unavailable | unavailable | 0 | 0 | 100.0% |
| mixed_signal_low_value | 40 | 40 | 100.0% | 100.0% | 0 | 0 | unavailable |
| multi_duplicate_pairwise | 40 | 120 | 100.0% | 100.0% | 0 | 0 | 100.0% |
| near_merge_not_duplicate | 40 | 80 | unavailable | unavailable | 40 | 40 | 100.0% |
| old_high_value | 40 | 40 | unavailable | unavailable | 0 | 0 | 100.0% |
| opposite_preference_conflict | 40 | 80 | unavailable | unavailable | 0 | 80 | 100.0% |
| temporary_but_pinned | 40 | 40 | unavailable | unavailable | 0 | 0 | 100.0% |
