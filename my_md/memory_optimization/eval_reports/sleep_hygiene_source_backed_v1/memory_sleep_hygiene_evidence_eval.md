# 睡眠巩固记忆库卫生评测报告

本报告来自确定性离线 evidence，不修改真实记忆库。

| 指标 | 数值 |
| --- | ---: |
| case 数 | 160 |
| 扫描 active item 数 | 224 |
| evidence row 数 | 200 |
| 重复候选识别率 | 100.0% |
| 过期候选识别率 | 100.0% |
| 低价值候选识别率 | 100.0% |
| 来源覆盖率 | 81.5% |
| proxy 回源成功率 | 36.1963% |
| shadow 估算 token 节省率 | 40.5157% |
| 关键记忆保持率 | 100.0% |
| 关键记忆误伤候选数 | 0 |
| 非预期候选数 | 0 |
| 误伤候选率 | 0.0% |
| 实际应用变更数 | 0 |

说明：当前阶段仍是 shadow / dry-run。重复、过期、低价值和 token 节省均表示候选识别或估算，不表示真实 DB 已经被清理。

## standard / hard / overall

| case_set | case 数 | evaluated item 数 | candidate recall | candidate precision | retained protection | false positive cleanup | safe evidence token saving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| standard | 96 | 96 | 100.0% | 100.0% | 100.0% | 0.0% | 64.574% |
| hard | 64 | 104 | 100.0% | 100.0% | 100.0% | 0.0% | 23.75% |
| overall | 160 | 200 | 100.0% | 100.0% | 100.0% | 0.0% | 40.5157% |

## V3 cleanup / review action metrics

| case_set | cleanup recall | cleanup precision | merge suggestions | review required | safe cleanup token saving |
| --- | ---: | ---: | ---: | ---: | ---: |
| standard | 100.0% | 100.0% | 0 | 0 | 64.574% |
| hard | 100.0% | 100.0% | 8 | 24 | 23.75% |
| overall | 100.0% | 100.0% | 8 | 24 | 40.5157% |

## hard scenario breakdown

| scenario | case 数 | evaluated item 数 | cleanup recall | cleanup precision | merge suggestions | review required | retained protection |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_scope_identical | 8 | 16 | unavailable | unavailable | 0 | 0 | 100.0% |
| missing_source_but_important | 8 | 8 | unavailable | unavailable | 0 | 0 | 100.0% |
| mixed_signal_low_value | 8 | 8 | 100.0% | 100.0% | 0 | 0 | unavailable |
| multi_duplicate_pairwise | 8 | 24 | 100.0% | 100.0% | 0 | 0 | 100.0% |
| near_merge_not_duplicate | 8 | 16 | unavailable | unavailable | 8 | 8 | 100.0% |
| old_high_value | 8 | 8 | unavailable | unavailable | 0 | 0 | 100.0% |
| opposite_preference_conflict | 8 | 16 | unavailable | unavailable | 0 | 16 | 100.0% |
| temporary_but_pinned | 8 | 8 | unavailable | unavailable | 0 | 0 | 100.0% |

## source evidence metrics

| metric | value |
| --- | ---: |
| source fetch mode | session-store |
| source_ref coverage | 81.5% |
| source_ref parse success | 82.2086% |
| source fetch success | 36.1963% |
| source support rate | 18.4049% |
| missing source count | 75 |
| unsupported source count | 29 |
| session ref not fetchable count | 37 |
| malformed source_ref count | 29 |

## source evidence by action

| action | rows | source_ref coverage | parse success | fetch success | support rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| merge_suggestions | 8 | 87.5% | 85.7143% | 42.8571% | 14.2857% |
| retained_rows | 104 | 83.6538% | 81.6092% | 41.3793% | 20.6897% |
| review_required | 24 | 87.5% | 85.7143% | 42.8571% | 19.0476% |
| safe_cleanup_candidates | 96 | 79.1667% | 82.8947% | 30.2632% | 15.7895% |
