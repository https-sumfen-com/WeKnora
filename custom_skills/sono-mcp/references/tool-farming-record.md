# add_farming_record 字段提取规则

`add_farming_record` 是写操作，用于新增/保存/提交农事记录。只有用户明确要求保存或提交时才调用；用户只是咨询、选择农资/配方/事项时不要调用。

## 返回结构

上游成功后通常返回完整农事记录对象。只要返回对象里有有效 `id`，就按保存成功处理。

```json
{
  "id": 64913,
  "address": "内蒙古自治区呼伦贝尔市额尔古纳市三河回族乡",
  "area": 140,
  "area_unit": "亩",
  "base_id": 71,
  "matter_id": 143,
  "operate_time": "2026-07-07 00:00",
  "plot_id": 19142,
  "plot": {
    "id": 19142,
    "name": "机耕队63号地水浇地",
    "area": 877,
    "area_unit": "亩",
    "base_id": 71
  },
  "plot_crop_id": 13281,
  "plotCrop": {
    "id": 13281,
    "name": "机耕队63号地水浇地 - 龙辐06-K508",
    "no": "PC25032615504624",
    "start_time": "2025-05-01",
    "end_time": "2025-05-01"
  },
  "work_user": 72,
  "tgzn_user_id": 72,
  "tgzn_dept_id": 1163,
  "tgzn_entity_id": 1
}
```

## 字段含义

| 字段 | 含义 | 使用规则 |
|---|---|---|
| `id` | 新增农事记录 ID | 成功回答中优先展示 |
| `plot.name` / `plot_id` | 作业地块 | 展示地块名，必要时带 ID |
| `plotCrop.name` / `plot_crop_id` | 关联种植批次 | 有值才展示 |
| `matter_id` | 农事事项 ID | 无事项名称时只展示 ID |
| `operate_time` | 作业时间 | 优先展示 |
| `area` / `area_unit` | 本次作业面积 | 有值才展示 |
| `address` | 作业地址 | 有值才展示 |
| `work_user` | 作业人 ID | 用户需要追溯时展示 |
| `tgzn_*` | 网关/同步字段 | 默认不展示 |

## 回答规则

- 成功时用一句话确认已保存，并给出农事记录 ID。
- 摘要地块、种植批次、事项 ID、作业时间、作业面积和地址。
- 返回没有 `goodsList` 时，不要编造农资明细。
- `plotCrop` 只取批次名、批次 ID、批次号、种植起止时间；不要输出完整档案。
- 跳过 `fid=0`、`crop_cycle=""`、`crop_cycle_id=0`、空值、`tgzn_*`、`yield_*`、`trace_no`、创建/更新时间等内部字段。
- 空 payload 时说明"已提交，但未返回记录详情"。
