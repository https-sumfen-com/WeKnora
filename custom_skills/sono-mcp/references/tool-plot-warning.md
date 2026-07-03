# get_plot_warning 字段提取规则

地块预警聚焦**预警等级 + 风险类型 + 发生时间 + 影响地块 + 处置建议**，不要展示内部记录字段。

## Payload 结构

上游通常返回预警列表，也可能返回带列表字段的对象。按以下结构兼容处理：

```
payload
├── []                         # 预警数组
└── list / data / records / rows# 预警数组候选字段

warning item
├── id
├── plot_id / plotId
├── plot_name / plotName / plot.name
├── warning_type / type / category
├── warning_level / level / grade
├── title / name
├── content / message / description
├── start_date / startDate / warning_time / created_at
├── end_date / endDate
├── status
└── suggestion / advice / handle_suggestion
```

## 必须提取的字段

| 关注维度 | 字段路径候选 | 空值处理 |
|---|---|---|
| 地块 | `plot_name`、`plotName`、`plot.name`、`plot_id`、`plotId` | 名称优先，ID 兜底 |
| 预警标题 | `title`、`name`、`warning_type`、`type`、`category` | 全空则写"地块预警" |
| 预警等级 | `warning_level`、`level`、`grade`、`severity` | 保留原始等级词；数字按下方规则解释 |
| 预警内容 | `content`、`message`、`description`、`reason` | 只摘摘要点，不输出长原文 |
| 时间 | `warning_time`、`start_date`、`startDate`、`created_at`、`end_date`、`endDate` | 全空则不展示时间 |
| 状态 | `status`、`state`、`is_handled` | 有明确处理状态时展示 |
| 建议 | `suggestion`、`advice`、`handle_suggestion`、`recommendation` | 最多 3 条 |

## 等级解释

优先使用上游给出的中文等级。若只返回数字，可按保守规则解释：

| 数字 | 预警等级 |
|---|---|
| `1` | 低风险 |
| `2` | 中风险 |
| `3` | 高风险 |
| `4` 或更高 | 严重风险 |

不能确定数字含义时，写作"等级：{原值}"，不要强行映射颜色。

## 风险类型处理

- 气象类：降雨、大风、低温、高温、干旱、高湿等，建议结合时间窗口安排作业避让。
- 病虫害类：病害、虫害、草害等，建议现场核查并按植保方案处理。
- 设备/传感类：传感异常、数据缺失、设备离线等，建议检查设备供电、网络和传感器。
- 生长类：长势异常、缺苗、倒伏、营养不足等，建议核查地块实际情况并安排农事处理。

## 空值与排序规则

- `payload = null`、`{}`、`[]` 或列表为空 → 说明"未查询到相关预警"。
- 值为 `null`、`""`、`"0"`、`"0000-00-00"`、`"0000-00-00 00:00:00"` → 跳过。
- 多条预警按等级从高到低、时间从近到远摘要；最多展示 5 条，更多时说明剩余数量。
- 不要展示内部 ID、坐标、边界、图片 URL、`tgzn_*`、处理日志明细。

## 输出格式建议

1. 先说明查询地块和预警数量。
2. 有高风险或严重风险时优先放在第一条。
3. 每条预警包含：等级、类型/标题、时间、简短内容、建议。
4. 无预警时只说"未查询到相关预警"，不要生成泛化风险提醒。
