# 天气报告结构（get_weather）

聚焦**预警判断 + 农事影响**，不逐字段罗列气象数值。

预警阈值和字段规则见 `sono-mcp/references/tool-weather.md`。

---

## 一、实时天气报告（payload.now）

### 有预警时

触发条件：`windScale≥5` / `temp≤5` / `temp≥35` / `humidity≤30` / `humidity≥85` / `precip≥10`

#### 卡片顺序（2 张 + quick-reply）

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

### 无预警时

- **metric**（同上快照卡片，无 trend 高亮）
- Markdown 一句：`"当前气象条件（风力{windScale}级，温度{temp}°C，湿度{humidity}%）适宜田间作业。"`
- **quick-reply（1-2 个）**：追问地块长势或作业计划

---

## 二、7天预报报告（payload.days[]）

### 卡片顺序（2-3 张 + quick-reply）

**1. table — 7天天气预报**

- 标题："未来7天天气预报"
- 列：日期 | 天气 | 最高/最低温 | 风力 | 降水(mm) | 湿度(%)
- 触发预警阈值的单元格在 label 后标注 ⚠（如 `"5/3日 ⚠"`）
- 日期格式：M月D日（如"1月15日"）
- 7条全部展示，不截断

**2. recommendation — 未来天气预警与作业建议**

有预警日期时生成：
- 每条对应一类风险（不要每天一条），合并同类预警
- `title`：`"{日期范围}：{预警类型}"`，如"1月16-17日：风力≥5级，暂停喷药喷灌"
- `reason` 引用具体数值，如"1月16日风力5级、1月17日风力6级，超过喷雾安全阈值"
- `priority`：红色预警 → `high`；橙色 → `high`；黄色 → `mid`
- 最多 3 条，按 priority 降序

有推荐作业窗口时追加 1 条 recommendation（priority: `low`）：
- `title`："推荐作业窗口：{fxDate} 至 {fxDate}"
- `reason`：说明该时段满足的条件（风力≤4级、降水<5mm等）

全部 7 天无预警时：
- 跳过 recommendation，Markdown 一句："未来7天气象条件整体正常，无明显农事风险。"

**3. metric（可选）— 最近1天快照**

仅当用户追问"明天天气"时，生成 `days[0]` 的 metric 卡片，字段同实时天气快照，把 `temp` 替换为 `tempMax`/`tempMin`。

**quick-reply（2 个）**
- "查看当前实时天气" → `"查询{地块名称}当前天气"`
- "查看地块作物状态" → `"查看{地块名称}当前作物长势"`

---

## 禁止项

- 不要把 `icon`、`wind360`、`pressure`、`fxLink`、`refer` 放入任何卡片
- 实时报告无预警时不强行生成 recommendation
- 预报报告中不要逐天生成 recommendation，按风险类型合并
- 不要把实时天气报告与地块详情混在同一个 report block；两者同时有数据时分两个独立 report
- 实时报告不推断未来天气；预报报告不使用 `payload.now` 字段
