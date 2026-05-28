# 天气报告结构（get_weather）

聚焦**预警判断 + 农事影响**，不逐字段罗列气象数值。

预警阈值和字段规则见 `sono-mcp/references/tool-weather.md`。

---

## 有预警时

触发条件：`windScale≥5` / `temp≤5` / `temp≥35` / `humidity≤30` / `humidity≥85` / `precip≥10`

### 卡片顺序（2 张 + quick-reply）

**1. metric — 当前天气快照**

items 按序：

| label | value 来源 | unit |
|---|---|---|
| 天气状况 | `text` | — |
| 温度 | `temp` | °C |
| 体感温度 | `feelsLike` | °C |
| 风力 | `windScale`级 + `windDir` | — |
| 湿度 | `humidity` | % |
| 降水 | `precip` | mm |

- 触发预警的字段加 `trend: "down"`
- 观测时间（`obsTime`）作为 Markdown 补充，不占 item

**2. recommendation — 天气预警与农事建议**

- `title` 直接写预警，如"风力6级：暂停喷药与喷灌作业"
- `reason` 必须引用具体数值，如"当前风速49km/h（6级），超过喷雾安全阈值（≤4级）"
- `priority`：红色预警 → `high`；橙色 → `high`；黄色 → `mid`
- 多个预警按 priority 降序，最多 3 条；同类合并（如风速+低湿同时影响喷灌合并为一条）
- 如有联动地块信息（`plot_type` 喷灌/滴灌），在 `reason` 中补充灌溉方式

**quick-reply（2 个）**
- "查看地块实时长势" → `"查看{地块名称}当前作物状态"`
- "查看基地设备状态" → `"查询该地块所属基地设备在线情况"`

---

## 无预警时

所有指标均在安全范围。

- **metric**（同上快照卡片，无 trend 高亮）
- Markdown 一句：`"当前气象条件（风力{windScale}级，温度{temp}°C，湿度{humidity}%）适宜田间作业。"`
- **quick-reply（1-2 个）**：追问地块长势或作业计划

---

## 禁止项

- 不要把 `icon`、`wind360`、`pressure`、`fxLink`、`refer` 放入任何卡片
- 无预警时不强行生成 recommendation
- 不要推断"未来几天天气"——当前只有实时快照；用户询问未来天气时回复"当前仅支持实时天气，未来预报功能即将上线"
- 不要把天气报告与地块详情混在同一个 report block；两者同时有数据时分两个独立 report
