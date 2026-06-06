# Block、Card、Report 规范

本参考定义 Agent 应输出的长期约束。后端可以做兼容适配和校验，但 Agent 不依赖后端修复正常输出。

## 输出形态

通用内容使用顶层 Markdown，结构化业务展示使用 `blocks`。当 SONO-MCP 已返回企业、基地、地块、设备、农机数据，且用户意图是分析、详情、建议、报告或结构化输出时，`blocks` 是主输出，Markdown 只能做极短摘要或缺口说明。

图表类结构化展示使用 `type: "chart"` 卡片，完整规则见 `echarts-options.md`。`data.option` 必须是可直接渲染的纯 JSON ECharts option。`chartType` / `chartRequest` 可用于追溯和校验，但不是最小合法渲染字段。

```ts
type AgentOutput = {
  schemaVersion: 'plant-agent.message.v1'
  markdown: string
  blocks?: BusinessBlock[]
  focusEntities?: EntityRef[]
}
```

如果当前接口仍需要旧格式，由后端 adapter 把 `markdown` 适配到兼容字段；Agent 不在 `blocks` 里生成正文或推理 block。

MCP 成功后的分析/报告类回答不得 Markdown-only。必须至少包含一个 `report` 或 `card` block，除非用户明确要求纯文字解释。

最终提交时输出完整 payload 本身，不要把 payload 内的 report/card 改写成自然语言 Markdown 后提交。

## JSON 合法性门控

最终输出必须是一个可被 `JSON.parse()` 解析的完整 JSON object。Agent 不依赖后端修复半截或不合法 JSON。

- 只输出一个 JSON object，不包 Markdown 代码围栏，不在 JSON 前后追加自然语言。
- 所有 key 和 string 必须使用双引号；每个属性必须是 `"key": value`，不能只写 `"key"`。
- 禁止缺值字段：例如 `"value"`、`"top"`、`"smooth"`、`"yAxisIndex"` 后面没有 `: <value>` 时，整包无效。
- 禁止 `undefined`、`NaN`、`Infinity`、函数、`Date` 对象、正则、注释和尾逗号。
- 布尔值必须写成 `true` / `false`；数字必须是 JSON number；字符串不能代替数字。
- 事实值缺失时跳过对应字段、`items[]` 项、`series[]` 项或整张 card；不要输出空 key、空字符串、`null` 或 0 占位。
- 必需字段缺失导致 card 无法成立时，不生成该 card，在顶层 `markdown` 用一句话说明数据缺口。
- `null` 只允许用于 ECharts 明确支持的序列断点或 dataset 缺口；metric、recommendation、table 的必需字段不要用 `null`。
- JSON 合法性优先级高于信息完整度。payload 过长或容易写断时，减少 report/card 数量、删除可选追溯字段、聚合图表数据，不能提交半截 JSON。

提交前逐项自检：

1. 顶层是否包含 `"schemaVersion": "plant-agent.message.v1"` 和 `"markdown"`。
2. 如果包含 `blocks`，每个 block/card 是否字段完整且类型受支持。
3. 每个 `metric.items[]` 是否都有非空 `label` 和合法 `value`。
4. 每个 `chart.data.option` 是否自身也是纯 JSON object。
5. 将最终文本整体交给 `JSON.parse()` 是否能成功。

## 当前允许的 blocks

```ts
type BusinessBlock =
  | { kind: 'card', card: AgentCard }
  | { kind: 'report', title: string, cards: AgentCard[] }
  | { kind: 'quick-reply', prompts: QuickReplyPrompt[] }
```

禁止在 `blocks` 中生成 `text` 或 `reasoning`。普通正文、分析过程、数据来源、缺口说明全部写进 Markdown。

## Block 规则

### card

用于单张业务卡片。最终输出中 `card` 不能为 `null`；流式占位是前端/后端内部行为，不是 Agent 最终输出。

### report

用于企业、基地、地块、设备、农机的成组分析或报告。`title` 要短且具体，`cards` 通常 3-7 张，从概览到证据再到建议。

同一用户问题默认只有一个主分析范围，也就只生成一个主 `report`：

- 用户问“某地块情况/综合分析/生成报告”时，主范围是该地块；WOFOST、基础快照、评级、积温积雨、未来天气、设备状态、作业窗口、农事建议都是该地块报告的分析维度，必须合并到同一个 `report.cards[]`。
- 用户问“某基地/企业综合分析”时，基地/企业是主范围；天气、设备、作物结构、投入、风险等作为同一报告内的 cards。
- 只有用户明确要求“分别生成报告/拆开看”，或同时比较多个互不从属对象且放在同一 report 会造成语义混乱时，才允许多个 `report`。
- `quick-reply` 可以独立作为第二个 block；它不是一份报告。

推荐顺序:

```txt
metric -> chart -> chart/map/table -> recommendation -> retrospect/phase-summary
```

不要把无关卡片塞进一个 report；但天气、设备、作业、积温、WOFOST 等如果服务于同一主对象的综合分析，就不是无关卡片，必须作为不同维度放进同一 report。需要图表时，在相关 `report.cards[]` 中输出 `type: "chart"` 卡片，并用 `data.option` 承载完整 ECharts 配置。

图表优先级高于表格。时间序列、分类对比、占比、分布、多指标对比、风险强度、空间轨迹等数据，优先生成 `chart`；只有需要逐行精确查看、排序、审计、编号、状态清单或字段值大多是文本时，才使用 `table`。

报告前 Markdown 规则:

- 最多 1-2 句总览，或只写必要数据缺口。
- 不要在 report 前写完整的“地块分析总览”“核心依据”“农事建议”“详细分析报告”等章节。
- report 已承载的指标、建议、来源、缺口，不要在 Markdown 中重复。
- 如果 report 能表达清楚，`markdown` 可以为空字符串或一句话摘要。

### quick-reply

用于下一步可操作问题。`label` 简短，`fillText` 写成可直接追问的自然语言。

```json
{
  "kind": "quick-reply",
  "prompts": [
    { "label": "查看 B-07 趋势", "fillText": "分析 B-07 地块近 14 天墒情变化" }
  ]
}
```

## 支持的卡片类型

### metric

用于企业、基地或单对象 KPI 快照。

必需: `data.items[]`，每项至少有 `label`、`value`。可选: `unit`、`delta`、`trend`、`icon`。

如果某个指标没有可追溯值，跳过该 item；不要输出 `{ "label": "面积", "value", "unit": "亩" }`、空字符串、`null` 或 0 占位。

```json
{
  "type": "metric",
  "cardId": "metric_soil_b07_20260514",
  "data": {
    "items": [
      { "label": "土壤墒情", "value": 15.2, "unit": "%", "delta": -3.1, "trend": "down" }
    ]
  }
}
```

### chart

用于趋势、分类、对比、占比、分布、关系、流向、空间轨迹或多维指标展示。`data.option` 必须包含完整 ECharts option。

最小合法形态:

```json
{
  "type": "chart",
  "cardId": "chart_custom",
  "data": {
    "title": "自定义图表",
    "option": {
      "xAxis": { "type": "category", "data": ["A", "B"] },
      "yAxis": { "type": "value" },
      "series": [{ "type": "scatter", "name": "样本", "data": [12, 19] }]
    }
  }
}
```

复杂业务图表建议额外提供 `chartType`、`chartRequest`、`sourceSummary`，但最小合法渲染字段只有 `data.option`。完整图表选择和 option 自检规则见 `echarts-options.md`。

### map

只在 SONO-MCP/API 返回坐标、边界、中心点、轨迹或图层时使用。坐标顺序固定为 `[lng, lat]`。

必需: `focus`、`layers`、`center`、`zoom`。

### table

用于结构化行数据，尤其是需要排序、审计、编号、状态清单、逐行操作或后续交互的列表。简单说明优先用 Markdown 表格。

不要用 table 承载可图形化的数据。只要行数据能表达为趋势、对比、占比、分布、强度矩阵或多指标结构，就应先生成 chart；table 最多作为补充明细。

必需: `title`、`columns`、`rows`。`rows` 只放字符串或数字。

### recommendation

用于建议动作。必须同时有事实依据和规则、阈值、模型或工具输出依据。`action` 是前端动作描述，不代表真实业务操作已经执行。

`priority` 只使用 `high`、`mid`、`low`。

**`title` 为必需字段**，不能省略、不能为空字符串。每条 item 也必须有 `reason`（引用具体数值或字段值）。

```json
{
  "type": "recommendation",
  "cardId": "rec_plot22253_20260528",
  "data": {
    "title": "农事建议",
    "items": [
      {
        "title": "水分含量偏低，建议尽快灌溉",
        "priority": "high",
        "reason": "长势评级中水分含量=低，当前处于幼苗期，需保持土壤湿润",
        "action": "安排喷灌作业"
      },
      {
        "title": "当前阶段注意事项",
        "priority": "low",
        "reason": "幼苗期注意事项：及时间苗，保持行距均匀，防止徒长"
      }
    ]
  }
}
```

字段说明：

| 字段 | 必需 | 说明 |
|---|---|---|
| `data.title` | **必需** | 整张卡片的标题，如"农事建议"、"设备异常建议"、"天气预警" |
| `items[].title` | **必需** | 单条建议的标题，不能省略，不能为空 |
| `items[].priority` | **必需** | `high` / `mid` / `low` |
| `items[].reason` | **必需** | 引用具体字段值，不写通用模板语句 |
| `items[].action` | 可选 | 前端动作描述 |

### retrospect

用于历史作业、告警、任务、变化复盘。必须有时间线来源。

### phase-summary

用于生产周期阶段摘要。当前阶段枚举只使用:

```txt
seedling | root-growth | harvest
```

不要在 `phase-summary.phases[].stage` 中使用尚未支持的 `planning`。

## 业务范围与 EntityRef

本 Skill 聚焦:

```txt
enterprise | base | plot | device | machinery
```

企业、基地是分析范围；地块、设备、农机是当前默认可聚焦实体。`focusEntities` 只放可在前端定位的具体对象:

```ts
type EntityKind = 'plot' | 'device' | 'machinery'
```

```json
{ "kind": "plot", "id": "plot-b07", "name": "苏沁 B-07 地块" }
```

企业和基地信息写在 Markdown、report 标题或卡片数据里；不要擅自把 `enterprise`、`base` 当作 `focusEntities.kind`，除非后端和前端已扩展该枚举。

## 报告组织规范

一个生产级报告通常包含:

1. `report`: 3-7 张卡片，顺序为概览、图表证据、空间或明细、建议、复盘。
2. 顶层 Markdown: 可选，最多 1-2 句，用于总览或必要缺口。
3. `quick-reply`: 2-4 个后续追问或动作。

报告标题要绑定范围，例如“企业经营风险概览”“东区基地设备运行报告”“B-07 地块墒情风险报告”。不要使用“综合报告”这类空泛标题。

同一主对象综合分析的 `blocks` 推荐形态:

```txt
[
  report(title="{对象名} · 综合分析", cards=[基础快照, 模型/趋势图, 天气/设备/作业维度, 建议]),
  quick-reply(...)
]
```

不要输出:

```txt
[
  report(title="{地块名} · 地块综合分析", ...),
  report(title="{地块名} · 天气", ...)
]
```

天气是该地块综合分析的一个维度，应合并为同一 `report.cards[]` 中的天气趋势 chart 或天气风险 recommendation。
