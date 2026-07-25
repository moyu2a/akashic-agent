# Source Ref Quality Shadow Report

本报告只评估 shadow normalized_source_ref，不修改真实 memory_items.source_ref。

数据语境：synthetic controlled fixture；这不是线上真实提升结论。

| metric | before | after | delta points |
| --- | ---: | ---: | ---: |
| message_level_rate | 40.0% | 90.0% | 50.0% |
| parse_success_rate | 80.0% | 100.0% | 20.0% |
| fetch_success_rate | 20.0% | 80.0% | 60.0% |
| support_rate | 10.0% | 70.0% | 60.0% |
| source_backed_eligible_rate | 10.0% | 70.0% | 60.0% |

| count | value |
| --- | ---: |
| candidate_count | 200 |
| source_backed_eligible_count_before | 20 |
| source_backed_eligible_count_after | 140 |
| malformed_source_ref_count_before | 20 |
| malformed_source_ref_count_after | 0 |

## Case Set Metrics

| case_set | candidates | before eligible | after eligible | delta points |
| --- | ---: | ---: | ---: | ---: |
| common | 100 | 20.0% | 80.0% | 60.0% |
| hard | 100 | 0.0% | 60.0% | 60.0% |

## Scenario Metrics

| scenario | candidates | before eligible | after eligible | fetch after | support after |
| --- | ---: | ---: | ---: | ---: | ---: |
| already_message_supported | 20 | 100.0% | 100.0% | 100.0% | 100.0% |
| foreign_baseline_replaced | 20 | 0.0% | 100.0% | 100.0% | 100.0% |
| foreign_candidate_filtered | 20 | 0.0% | 0.0% | 0.0% | 0.0% |
| invalid_same_session_baseline | 20 | 0.0% | 100.0% | 100.0% | 100.0% |
| malformed_upgradable | 20 | 0.0% | 100.0% | 100.0% | 100.0% |
| missing_message_id | 20 | 0.0% | 0.0% | 0.0% | 0.0% |
| missing_upgradable | 20 | 0.0% | 100.0% | 100.0% | 100.0% |
| multi_message_supported | 20 | 0.0% | 100.0% | 100.0% | 100.0% |
| session_level_upgradable | 20 | 0.0% | 100.0% | 100.0% | 100.0% |
| unsupported_message_kept | 20 | 0.0% | 0.0% | 100.0% | 0.0% |
