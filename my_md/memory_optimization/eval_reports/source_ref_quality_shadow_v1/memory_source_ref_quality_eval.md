# Source Ref Quality Shadow Report

本报告只评估 shadow normalized_source_ref，不修改真实 memory_items.source_ref。

数据语境：synthetic controlled fixture；这不是线上真实提升结论。

| metric | before | after | delta points |
| --- | ---: | ---: | ---: |
| message_level_rate | 33.3333% | 83.3333% | 50.0% |
| parse_success_rate | 66.6667% | 100.0% | 33.3333% |
| fetch_success_rate | 33.3333% | 83.3333% | 50.0% |
| support_rate | 16.6667% | 66.6667% | 50.0% |
| source_backed_eligible_rate | 16.6667% | 66.6667% | 50.0% |

| count | value |
| --- | ---: |
| candidate_count | 6 |
| source_backed_eligible_count_before | 1 |
| source_backed_eligible_count_after | 4 |
| malformed_source_ref_count_before | 1 |
| malformed_source_ref_count_after | 0 |
