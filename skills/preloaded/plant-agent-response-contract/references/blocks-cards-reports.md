# 多 schema 渲染片段规范

本参考定义结构化渲染片段的长期约束。片段自身必须字段完整、类型稳定、可被运行时直接渲染。

## 输出形态

本参考只定义多 schema 渲染片段。结构化片段的常态是 `card` 和 `quick-reply`；`report` 只是把多张 card 组合成一组的模板。用户明确要求卡片、图表、地图、表格、指标面板、可视化、报告，用户询问趋势、走势、变化、对比、分布且已有可图形化数据，或读取到异常、风险、预警、离线、缺口、阈值越界等需要局部高亮的数据，或运行时要求结构化片段时，才使用 `blocks`。SONO-MCP 返回数据本身不要求优先生成 block。

图表类结构化展示使用 `type: "chart"` 卡片，完整规则见 `echarts-options.md`。`data.option` 必须是可直接渲染的纯 JSON ECharts option。`chartType` / `chartRequest` 可用于追溯和校验，但不是最小合法渲染字段。

默认按多 schema 片段流式输出。每个已就绪片段都必须放进带 `schemaVersion` 和 `blocks` 的小 payload；不要为了等待其它 card、recommendation、quick-reply 或自然语言收尾，把所有内容攒成一次性最终回答。

```ts
type RenderFragmentPayload = {
  schemaVersion: 'plant-agent.message.v1'
  blocks: BusinessBlock[]
  focusEntities?: EntityRef[]
}
```

结构化 payload 只承载可渲染内容。Agent 不在 `blocks` 里生成 `text/content` 或推理型 block。

局部结构化展示默认生成 `card`，默认追加 `quick-reply`。只有明确报告意图才使用 `report` 组合模板；成组聚合展示如果没有明确报告要求，输出多张 `card` + `quick-reply`。

禁止输出裸 `BusinessBlock`，例如只输出 `{ "kind": "card", ... }` 是不合规的。即使只输出一张 card，也必须包在 `RenderFragmentPayload.blocks[]` 中。

异常、风险、预警、离线、阈值越界等场景必须生成至少一张 `recommendation` card；`recommendation` 用来承载“为什么值得关注”和“下一步建议”，不要只用 `metric` 或 `chart` 罗列现象。

## 片段合法性门控

每次结构化输出必须是字段完整、可被当前 schema 渲染的 `RenderFragmentPayload` JSON object。不要把“payload 合法”理解成“整段回答必须先组成一个完整大 JSON object”。

- 顶层必须包含 `"schemaVersion": "plant-agent.message.v1"` 和 `"blocks"`。
- `blocks[]` 可以只包含一个已就绪的 `card`、`quick-reply` 或 `report`；不要为了凑齐所有片段而等待。
- 多个 payload 可以按就绪顺序依次输出；每个 payload 都必须自带 `schemaVersion` 和 `blocks`。
- **唯一例外是 `quick-reply`：它必须是最后输出的内容，排在自然语言正文和所有其它片段之后。即使 quick-reply 先就绪，也要压到最后再发；其后不得再输出任何正文或片段。**
- payload 不包代码围栏，不在 JSON 前后追加其它包装。不要把 payload 当 Markdown 代码块展示。
- 不要输出裸 `kind/card/prompts/title/cards` 对象；前端解析入口依赖 `schemaVersion`。
- 所有 key 和 string 必须使用双引号；每个属性必须是 `"key": value`，不能只写 `"key"`。
- 禁止缺值字段：例如 `"value"`、`"top"`、`"smooth"`、`"yAxisIndex"` 后面没有 `: <value>` 时，整包无效。
- 禁止 `undefined`、`NaN`、`Infinity`、函数、`Date` 对象、正则、注释和尾逗号。
- 布尔值必须写成 `true` / `false`；数字必须是 JSON number；字符串不能代替数字。
- 事实值缺失时跳过对应字段、`items[]` 项、`series[]` 项或整张 card；不要输出空 key、空字符串、`null` 或 0 占位。
- 必需字段缺失导致 card 无法成立时，不生成该 card；不要用空 card 表示缺口。
- `null` 只允许用于 ECharts 明确支持的序列断点或 dataset 缺口；metric、recommendation、table 的必需字段不要用 `null`。
- 片段合法性优先级高于信息完整度。片段数据过长或容易写断时，先输出最小可渲染 card，删除可选追溯字段、聚合图表数据，不能输出半截 JSON。

输出 payload 前逐项自检：

1. 顶层是否包含 `"schemaVersion": "plant-agent.message.v1"` 和 `"blocks"`？
2. `blocks[]` 是否至少包含一个受支持 block？
3. 是否没有输出裸 `{ "kind": ... }`？
4. 每个 `metric.items[]` 是否都有非空 `label` 和合法 `value`。
5. 每个 `chart.data.option` 是否自身也是纯 JSON object。

## 当前允许的 blocks

```ts
type BusinessBlock =
  | { kind: 'card', card: AgentCard }
  | { kind: 'quick-reply', prompts: QuickReplyPrompt[] }
  | { kind: 'report', title: string, cards: AgentCard[] }
```

禁止在 `blocks` 中生成 `text`、`content` 或 `reasoning`。推理过程和无法结构化的缺口说明不属于 block 内容。

## Block 规则

### card

用于单张业务卡片。`card` 不能为 `null`；流式占位是运行时内部行为，不是结构化片段内容。

### quick-reply

用于下一步可操作问题。结构化路径默认追加 `quick-reply`，除非用户明确禁止后续追问。`label` 简短，`fillText` 写成可直接发起的追问文本。

```json
{
  "kind": "quick-reply",
  "prompts": [
    { "label": "查看 B-07 趋势", "fillText": "分析 B-07 地块近 14 天墒情变化" }
  ]
}
```

### report

`report` 是 card 的组合模板，只用于用户明确要求生成、查看或输出的企业、基地、地块、设备、农机成组报告。`title` 要短且具体，`cards` 通常 3-7 张，从概览到证据再到建议。

同一明确报告请求默认只有一个主报告范围，也就只生成一个主 `report`：

- 用户明确要求“某地块报告/生成地块报告”时，主范围是该地块；WOFOST、基础快照、评级、积温积雨、未来天气、设备状态、作业窗口、农事建议都是该地块报告的分析维度，必须合并到同一个 `report.cards[]`。
- 用户明确要求“某基地/企业报告”时，基地/企业是主范围；天气、设备、作物结构、投入、风险等作为同一报告内的 cards。
- 只有用户明确要求“分别生成报告/拆开看”，或同时比较多个互不从属对象且放在同一 report 会造成语义混乱时，才允许多个 `report`。

推荐 card 顺序:

```txt
metric -> chart -> chart/map/table -> recommendation -> retrospect/phase-summary
```

不要把无关卡片塞进一个 report；但天气、设备、作业、积温、WOFOST 等如果服务于同一明确报告对象，就不是无关卡片，必须作为不同维度放进同一 report。需要图表时，在相关 `report.cards[]` 中输出 `type: "chart"` 卡片，并用 `data.option` 承载完整 ECharts 配置。

图表优先级高于表格。时间序列、分类对比、占比、分布、多指标对比、风险强度、空间轨迹等数据，优先生成 `chart`；用户询问“趋势/走势/变化/对比/分布”且已有对应数据时，必须生成 `type: "chart"` 卡片。只有需要逐行精确查看、排序、审计、编号、状态清单或字段值大多是文本时，才使用 `table`。

report 组合规则:

- report 只组合同一主对象或同一报告主题下的 cards。
- 不要把章节文本塞进 report。
- report 已承载的指标、建议、来源、缺口，不要重复成额外 block。

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

用于结构化行数据，尤其是需要排序、审计、编号、状态清单、逐行操作或后续交互的列表。简单说明不生成 table。

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

企业和基地信息写在 report 标题或卡片数据里；不要擅自把 `enterprise`、`base` 当作 `focusEntities.kind`，除非运行时已扩展该枚举。

## report 组合模板规范

一个 report 组合模板通常包含:

1. `report`: 3-7 张卡片，顺序为概览、图表证据、空间或明细、建议、复盘。
2. `quick-reply`: 2-4 个后续追问或动作。

报告标题要绑定范围，例如“企业经营风险概览”“东区基地设备运行报告”“B-07 地块墒情风险报告”。不要使用“综合报告”这类空泛标题。

同一主对象明确报告请求的 `blocks` 推荐形态:

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

天气是该地块明确报告请求中的一个维度，应合并为同一 `report.cards[]` 中的天气趋势 chart 或天气风险 recommendation。
