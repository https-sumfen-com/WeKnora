# 设备报告结构（get_plot_device_info）

聚焦**在线状态 + 最新遥测读数 + 异常预警**，不展示设备类型定义和内部系统字段。

字段提取规则见 `sono-mcp/references/tool-device-info.md`。

---

## 卡片顺序（2-3 张）

### 前置检查

- `device_detail = null` → 自然回复说明"暂无设备详情数据"，跳过全部卡片，只生成 quick-reply
- 各 item 空值判断：`null`、`""`、`"0"`、`"0000-00-00 00:00:00"` 均视为**无效值**，跳过该 item，不得展示为 "0"

### 1. metric — 设备状态快照

来源：`device_detail`

items 按序（每项先检查空值，无效则跳过）：

| label | value 来源 | 空值/零值处理 |
|---|---|---|
| 设备类型 | `device_detail.deviceType.name` | null/空 → **跳过** |
| 所属地块 | `plot.name` | null/空 → **跳过** |
| 在线状态 | `is_online=1` → "在线"；`=0` → "离线" | null → **跳过**；**禁止展示原始数字 0/1** |
| 最后通信 | `device_detail.last_device_time` | null/"0"/"0000-..." → **跳过** |

如果 `is_online=0`，由自然回复或顶层桥接句标注：`⚠ 设备当前离线，以下为最后上报数据`

### 2. chart — 传感器读数

来源：`device_detail.device_data[]`（只取 `is_open=1` 的条目）

- 标题：`"{deviceType.name}实测数据（{Datatime} 上报）"`
- 图表优先：生成 ECharts `chart` 展示传感器名称与数值，常见选择为 `bar`、`gauge` 或多指标仪表盘式组合
- 单位不一致时不要强行放同一数值轴；可按单位分组生成多个 series/多个坐标轴，或仅展示关键同单位指标
- 排序：`is_index=1` 的行置顶（如温度、湿度、累计雨量），其余按数组顺序
- `is_open=0` 的条目跳过
- 如有 `last_device_data.电池电压_null`，可作为独立 gauge/bar 指标展示，unit "V"
- 数据为空数组 → 跳过此卡片，自然回复说明"暂无遥测数据"
- 仅当传感器值主要是文本状态、无法安全转换为 number，或需要逐行审计时，才降级为 table

### 3. recommendation — 设备异常建议（有异常才生成）

| 条件 | priority | title | reason 模板 |
|---|---|---|---|
| `is_online=0` | high | 设备离线 | "设备 {name} 当前离线（最后通信 {last_device_time}），建议检查电源和网络连接" |
| `电池电压_null < 3.5V` | mid | 电量不足 | "当前电池电压 {value}V，低于3.5V阈值，建议尽快更换" |
| `last_device_time` 距当前 > 2小时 | mid | 数据上报延迟 | "最后通信 {last_device_time}，超过2小时未上报，建议检查网络和设备状态" |

无以上异常时 → 不生成 recommendation，自然回复一句"设备运行正常。"

---

## quick-reply（2 个）

- "查看关联地块状态" → `"查看{plot.name}地块当前状态"`
- "查看基地设备汇总" → `"查询该地块所属基地所有设备状态"`

---

## 禁止项

- 不展示 `deviceFeatures`、`deviceType.features`、`deviceField`（字段定义模板，无遥测值）
- 不展示 `traceId`、时间戳数字 `datatime`、`纬度_null`、`经度_null`
- 不展示 `device_detail` 内嵌的重复 `device_detail`/`device_data` 结构
- 不展示设备 EUI、`icon`、`cover`、`platform` 等内部标识字段
- 不在设备报告中推断作物长势或生成农事建议（设备数据不直接关联作物生长）
