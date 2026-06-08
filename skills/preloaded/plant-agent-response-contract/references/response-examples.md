# 返回示例与自检

示例中的数值表示“已由 SONO-MCP 返回”的数据形态；实际输出必须替换为当前任务真实读取的数据。

示例为了展示组合效果，常把多个片段放在同一个批量 payload 中。实际运行时默认可以按片段流式输出：chart card 就绪后先输出 chart，风险建议就绪后再输出 recommendation，最后按需输出 quick-reply。不要因为示例是批量 JSON，就等待所有片段齐全后一次性 answer。

## 局部 card + recommendation + quick-reply 示例

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": [
    {
      "kind": "card",
      "card": {
        "type": "metric",
        "cardId": "metric_plot_b07_soil_snapshot",
        "data": {
          "title": "B-07 墒情快照",
          "items": [
            { "label": "土壤墒情", "value": 15.2, "unit": "%" },
            { "label": "近7天有效降雨", "value": 0, "unit": "mm" }
          ],
          "sourceSummary": "数据来自当前地块墒情快照和近7天降雨统计。"
        }
      }
    },
    {
      "kind": "card",
      "card": {
        "type": "recommendation",
        "cardId": "rec_plot_b07_soil_attention",
        "data": {
          "title": "B-07 今日关注建议",
          "items": [
            {
              "title": "优先核查灌溉条件",
              "priority": "high",
              "reason": "当前土壤墒情为 15.2%，近7天有效降雨为 0mm，存在水分不足风险。",
              "action": "确认灌溉设备在线状态并安排补水窗口"
            }
          ]
        }
      }
    },
    {
      "kind": "quick-reply",
      "prompts": [
        { "label": "看趋势", "fillText": "用图表展示 B-07 近 14 天墒情趋势" },
        { "label": "生成报告", "fillText": "生成 B-07 地块墒情风险报告" }
      ]
    }
  ],
  "focusEntities": [
    { "kind": "plot", "id": "plot-b07", "name": "B-07 地块" }
  ]
}
```

## 天气趋势 chart + recommendation + quick-reply 示例

用户问“天气趋势”“未来7天天气走势”且已有 `payload.days[]` 时，生成局部 `chart` card，不生成 `report`。

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": [
    {
      "kind": "card",
      "card": {
        "type": "chart",
        "cardId": "chart_weather_7d_trend",
        "data": {
          "title": "未来7天气温与降水趋势",
          "chartType": "line-bar",
          "option": {
            "title": { "text": "未来7天气温与降水趋势" },
            "tooltip": { "trigger": "axis" },
            "legend": { "data": ["最高温", "最低温", "降水"] },
            "xAxis": { "type": "category", "data": ["6/8", "6/9", "6/10", "6/11", "6/12", "6/13", "6/14"] },
            "yAxis": [
              { "type": "value", "name": "温度", "axisLabel": { "formatter": "{value}°C" } },
              { "type": "value", "name": "降水", "axisLabel": { "formatter": "{value}mm" } }
            ],
            "series": [
              { "type": "line", "name": "最高温", "data": [19, 21, 23, 23, 20, 21, 23] },
              { "type": "line", "name": "最低温", "data": [7, 10, 10, 11, 7, 10, 11] },
              {
                "type": "bar",
                "name": "降水",
                "yAxisIndex": 1,
                "data": [2.4, 0, 0, 0, 0, 18.9, 0],
                "markPoint": { "data": [{ "name": "强降水", "coord": ["6/13", 18.9], "value": 18.9 }] }
              }
            ]
          },
          "sourceSummary": "数据来自 get_weather.days，展示未来7天最高温、最低温和降水趋势。"
        }
      }
    },
    {
      "kind": "card",
      "card": {
        "type": "recommendation",
        "cardId": "rec_weather_7d_work_window",
        "data": {
          "title": "天气风险与作业窗口",
          "items": [
            {
              "title": "6月13日强降水，暂停田间作业",
              "priority": "high",
              "reason": "6月13日预计降水 18.9mm，超过 10mm 农事风险阈值。",
              "action": "6月12日前检查排水沟渠，6月13日暂停喷药、追肥和机械下田"
            },
            {
              "title": "6月9日至12日适合作业",
              "priority": "low",
              "reason": "6月9日至12日无明显降水，风力处于 1-4 级范围。",
              "action": "优先安排喷药、追肥、播种收尾或设备巡检"
            }
          ]
        }
      }
    },
    {
      "kind": "quick-reply",
      "prompts": [
        { "label": "结合墒情", "fillText": "结合地块墒情分析未来7天作业窗口" },
        { "label": "查看作业计划", "fillText": "根据未来7天天气安排农事作业计划" }
      ]
    }
  ]
}
```

## 企业报告示例

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": [
    {
      "kind": "report",
      "title": "企业经营风险概览",
      "cards": [
        {
          "type": "metric",
          "cardId": "metric_enterprise_overview_20260514",
          "data": {
            "items": [
              { "label": "基地数量", "value": 4, "unit": "个" },
              { "label": "在线设备率", "value": 91.3, "unit": "%" },
              { "label": "高风险地块", "value": 2, "unit": "块" }
            ]
          }
        },
        {
          "type": "chart",
          "cardId": "chart_enterprise_risks_20260514",
          "data": {
            "title": "重点风险强度",
            "chartType": "bar",
            "option": {
              "title": { "text": "重点风险强度" },
              "tooltip": { "trigger": "axis" },
              "xAxis": {
                "type": "category",
                "data": ["东区基地", "B-07 地块"]
              },
              "yAxis": {
                "type": "value",
                "name": "风险等级",
                "min": 0,
                "max": 3
              },
              "series": [
                {
                  "type": "bar",
                  "name": "风险强度",
                  "data": [3, 3],
                  "label": { "show": true, "position": "top" }
                }
              ]
            },
            "sourceSummary": "高风险按 3 分映射，仅用于风险强度可视化；风险事实来自 SONO-MCP 返回的设备离线和地块墒情异常。"
          }
        },
        {
          "type": "recommendation",
          "cardId": "rec_enterprise_actions_20260514",
          "data": {
            "title": "建议动作",
            "items": [
              {
                "id": "check-east-devices",
                "title": "优先排查东区基地离线设备",
                "reason": "SONO-MCP 返回 3 台设备离线，影响东区基地环境监测连续性",
                "priority": "high"
              }
            ]
          }
        }
      ]
    },
    {
      "kind": "quick-reply",
      "prompts": [
        { "label": "查看东区基地", "fillText": "生成东区基地设备运行分析报告" },
        { "label": "查看 B-07", "fillText": "分析 B-07 地块近 14 天墒情变化" }
      ]
    }
  ],
  "focusEntities": []
}
```

## 地块 WOFOST 报告示例

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": [
    {
      "kind": "report",
      "title": "B-07 地块 WOFOST 生长模拟报告",
      "cards": [
        {
          "type": "metric",
          "cardId": "metric_wofost_b07_20260603",
          "data": {
            "items": [
              { "label": "发育阶段 DVS", "value": 1.18 },
              { "label": "最大叶面积指数", "value": 3.42 },
              { "label": "根深", "value": 82.5, "unit": "cm" },
              { "label": "地上总生物量", "value": 6420, "unit": "kg/ha" },
              { "label": "贮藏器官干物质", "value": 2180, "unit": "kg/ha" }
            ]
          }
        },
        {
          "type": "chart",
          "cardId": "chart_wofost_b07_growth_20260603",
          "data": {
            "title": "WOFOST 生育进程与生物量趋势",
            "chartType": "line",
            "option": {
              "title": { "text": "WOFOST 生育进程与生物量趋势" },
              "tooltip": { "trigger": "axis" },
              "legend": { "top": 28 },
              "grid": { "left": 48, "right": 32, "top": 72, "bottom": 36 },
              "dataset": {
                "source": [
                  { "day": "序列1", "DVS": 0.82, "TAGP": 4100, "LAI": 2.7 },
                  { "day": "序列2", "DVS": 1.02, "TAGP": 5280, "LAI": 3.1 },
                  { "day": "序列3", "DVS": 1.18, "TAGP": 6420, "LAI": 3.3 }
                ]
              },
              "xAxis": { "type": "category" },
              "yAxis": [
                { "type": "value", "name": "DVS/LAI" },
                { "type": "value", "name": "TAGP kg/ha" }
              ],
              "series": [
                { "name": "DVS", "type": "line", "encode": { "x": "day", "y": "DVS" } },
                { "name": "LAI", "type": "line", "encode": { "x": "day", "y": "LAI" } },
                { "name": "TAGP", "type": "line", "yAxisIndex": 1, "encode": { "x": "day", "y": "TAGP" } }
              ]
            },
            "sourceSummary": "数据来自 get_wofost_report.csv_content 的有效模型日序列，表示模型模拟结果。"
          }
        },
        {
          "type": "chart",
          "cardId": "chart_wofost_b07_water_20260603",
          "data": {
            "title": "WOFOST 水分平衡",
            "chartType": "bar",
            "option": {
              "title": { "text": "WOFOST 水分平衡" },
              "tooltip": { "trigger": "axis" },
              "xAxis": { "type": "category", "data": ["降雨", "灌溉", "入渗", "渗漏", "蒸腾", "土壤蒸发"] },
              "yAxis": { "type": "value", "name": "mm" },
              "series": [
                { "type": "bar", "name": "水分量", "data": [62, 0, 48, 8, 96, 21] }
              ]
            },
            "sourceSummary": "数据来自 get_wofost_report.terminal_report_json，表示模型期水分平衡模拟。"
          }
        },
        {
          "type": "recommendation",
          "cardId": "rec_wofost_b07_water_20260603",
          "data": {
            "title": "模型建议",
            "items": [
              {
                "title": "模型土壤含水量偏低，建议关注补水",
                "priority": "high",
                "reason": "WOFOST 日序列最后有效 SM=0.18，低于 0.20 风险阈值"
              }
            ]
          }
        }
      ]
    }
  ],
  "focusEntities": [
    { "kind": "plot", "id": "plot-b07", "name": "B-07 地块" }
  ]
}
```

## 地块基础快照示例

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": [
    {
      "kind": "report",
      "title": "B-07 地块墒情风险报告",
      "cards": [
        {
          "type": "metric",
          "cardId": "metric_plot_b07_soil_20260514",
          "data": {
            "items": [
              { "label": "当前墒情", "value": 15.2, "unit": "%", "trend": "down" },
              { "label": "阈值差", "value": -2.8, "unit": "%" }
            ]
          }
        },
        {
          "type": "chart",
          "cardId": "chart_plot_b07_soil_14d",
          "data": {
            "title": "B-07 近 14 天墒情趋势",
            "chartType": "line",
            "chartRequest": {
              "title": "B-07 近 14 天墒情趋势",
              "goal": "trend",
              "chartType": "line",
              "dataset": [
                { "day": "05-01", "soilMoisture": 18.2 },
                { "day": "05-02", "soilMoisture": 17.6 }
              ],
              "xField": "day",
              "yField": "soilMoisture",
              "series": [{ "name": "墒情", "field": "soilMoisture" }],
              "reason": "day 是连续日期字段，soilMoisture 是同一地块连续数值，适合用 line 展示趋势。"
            },
            "option": {
              "title": { "text": "B-07 近 14 天墒情趋势" },
              "tooltip": { "trigger": "axis" },
              "legend": { "top": 28 },
              "grid": { "left": 40, "right": 24, "top": 72, "bottom": 36 },
              "dataset": {
                "source": [
                  { "day": "05-01", "soilMoisture": 18.2 },
                  { "day": "05-02", "soilMoisture": 17.6 }
                ]
              },
              "xAxis": { "type": "category" },
              "yAxis": { "type": "value", "name": "墒情（%）" },
              "series": [
                {
                  "name": "墒情",
                  "type": "line",
                  "encode": { "x": "day", "y": "soilMoisture" },
                  "smooth": true
                }
              ]
            },
            "sourceSummary": "数据来自 SONO-MCP 返回的 B-07 地块近 14 天墒情序列。"
          }
        },
        {
          "type": "recommendation",
          "cardId": "rec_plot_b07_irrigation",
          "data": {
            "title": "建议动作",
            "items": [
              {
                "id": "irrigate-b07",
                "title": "优先安排 B-07 滴灌",
                "reason": "当前墒情低于阈值，且近 7 天无有效降雨",
                "priority": "high",
                "targetEntity": { "kind": "plot", "id": "plot-b07", "name": "B-07 地块" }
              }
            ]
          }
        }
      ]
    }
  ],
  "focusEntities": [
    { "kind": "plot", "id": "plot-b07", "name": "B-07 地块" }
  ]
}
```

## 设备详情示例

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": [
    {
      "kind": "card",
      "card": {
        "type": "metric",
        "cardId": "metric_device_weather_001_status",
        "data": {
          "items": [
            { "label": "当前状态", "value": "在线" },
            { "label": "24 小时中断", "value": 25, "unit": "分钟" }
          ]
        }
      }
    }
  ],
  "focusEntities": [
    { "kind": "device", "id": "weather-001", "name": "1 号气象站" }
  ]
}
```

## 缺数据示例

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": [
    {
      "kind": "card",
      "card": {
        "type": "metric",
        "cardId": "metric_machinery_m12_status",
        "data": {
          "items": [
            { "label": "当前状态", "value": "在线" }
          ]
        }
      }
    }
  ],
  "focusEntities": [
    { "kind": "machinery", "id": "machinery-m12", "name": "M-12 农机" }
  ]
}
```

## 反例

### blocks 里放 text/content 片段

```json
{ "kind": "text", "content": "今日重点：B-07 地块需要灌溉。" }
```

错误。`text/content` 不是允许的 BusinessBlock，不属于可渲染业务片段。

### blocks 里放推理说明

```json
{ "kind": "reasoning", "text": "先读取地块墒情，再判断风险。" }
```

错误。`reasoning` 不是允许的 BusinessBlock，业务级分析过程不进入可渲染片段。

### 明确结构化或异常数据场景 blocks 为空

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": []
}
```

错误。用户明确要求报告、卡片、图表、可视化，询问趋势、走势、变化、对比、分布且已有可图形化数据，或数据存在异常、风险、预警、离线、缺口、阈值越界等需要局部高亮时，应生成对应 `report`、`card` 或 `quick-reply` block。

### report 空壳或塞入非片段内容

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": [
    { "kind": "report", "title": "B-07 墒情风险报告", "cards": [] }
  ]
}
```

错误。report 是 card 组合模板，`cards` 必须由有效 card 组成，不能提交空壳 report 或非片段内容。

### 编造数据

```json
{ "label": "土壤墒情", "value": 15.2, "unit": "%" }
```

如果 SONO-MCP/API/工具/用户事实没有提供 `15.2`，就是错误。

### 单位写进 value

```json
{ "label": "土壤墒情", "value": "15.2%" }
```

错误。使用 `value: 15.2` 和 `unit: "%"`。

### 未支持的聚焦对象

```json
{ "kind": "base", "id": "base-east", "name": "东区基地" }
```

错误，除非运行时已经扩展 `focusEntities.kind`。企业和基地作为分析范围写入 report 标题或卡片数据。

### chart 缺少 option

```json
{
  "type": "chart",
  "cardId": "chart_plot_b07_soil_14d",
  "data": {
    "title": "B-07 近 14 天墒情",
    "variant": "line",
    "xAxis": ["05-01", "05-02"],
    "series": [{ "name": "墒情", "data": [18.2, 17.6] }]
  }
}
```

错误。`chart` 卡片必须输出完整纯 JSON `data.option`。只给 `variant/xAxis/series` 不能作为合规输出。

### ECharts option 包含函数

```json
{
  "tooltip": {
    "formatter": "(params) => params[0].value + '%'"
  }
}
```

错误。`option` 必须是纯 JSON，不写函数字段；需要格式化时使用 ECharts 字符串模板或默认格式。

### 字段缺值导致 JSON 断裂

```text
{
  "label": "面积",
  "value",
  "unit": "亩"
}
```

```text
{
  "legend": { "top" },
  "series": [
    { "type": "line", "smooth", "yAxisIndex", "data": [4, 5] }
  ]
}
```

错误。任何 key 都必须有 `: value`。缺少面积、布局值、布尔值或轴索引时，删除该字段或跳过对应 item/card；不要留下半截 JSON。

### 同一地块综合分析拆成多份报告

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": [
    {
      "kind": "report",
      "title": "B-07 · 地块综合分析",
      "cards": [
        { "type": "metric", "cardId": "metric_b07_snapshot", "data": { "title": "地块生长快照", "items": [{ "label": "作物", "value": "玉米" }] } }
      ]
    },
    {
      "kind": "report",
      "title": "B-07 · 未来天气",
      "cards": [
        { "type": "chart", "cardId": "chart_b07_weather_7d", "data": { "title": "未来7天天气预报", "option": { "xAxis": { "type": "category", "data": ["6/6", "6/7"] }, "yAxis": { "type": "value" }, "series": [{ "type": "line", "name": "最高温", "data": [22, 24] }] } } }
      ]
    }
  ]
}
```

错误。用户明确要求同一地块报告时，只生成一份主 `report`。天气预报、设备状态、积温积雨、WOFOST 模型、评级和农事建议都应作为同一 `report.cards[]` 中的不同 cards。

## 片段集合自检

- 当前输出是否是一个字段完整的独立片段，或运行时明确要求的批量 payload？
- 如果是批量 payload，是否是可被 `JSON.parse()` 解析的 JSON object，且没有代码围栏或额外包装？
- 是否先读取或接收了 SONO-MCP/API/工具数据？
- 当前是否确实命中明确报告、局部结构化展示意图，或异常/风险数据触发，而不是无片段场景？
- 明确报告意图是否生成了一份主 `report`？天气、设备、作业、WOFOST、评级等维度是否合并到了同一 `report.cards[]`？
- 非报告的局部结构化展示是否只生成 `card` / `quick-reply`，没有误用 `report`？
- `blocks[].kind` 是否只包含 `card`、`report`、`quick-reply`？
- 是否完全避免了 `text` block 和 `reasoning` block？
- card 类型是否只用了当前注册类型？
- `chart` 卡片是否包含纯 JSON `data.option`？复杂图表是否按需补充了 `chartRequest`？
- 用户询问趋势、走势、变化、对比或分布且已有序列/对比数据时，是否生成了 `type: "chart"` card，而不是退回逐行表格？
- 是否不存在 `"value"`、`"top"`、`"smooth"`、`"max"`、`"yAxisIndex"` 等无值 key？缺值数据是否已跳过，或只在缺口有操作价值时转为 recommendation / quick-reply？
- 是否在可视化数据场景优先生成了 `chart`，没有把趋势、对比、占比、分布、多指标对比默认做成 `table`？
- 地块情况/地块分析/地块报告是否把 `get_wofost_report` 作为重点分析来源，而不是只输出 `get_plot_info` 基础快照？
- WOFOST 模型值是否明确表述为“模型模拟/预测”，没有写成实际测产或实测结果？
- 所有数字、坐标、对象 ID、状态、任务结果是否都有来源？
- 数据不足时是否没有生成占位卡片？
- 当前片段集合即使只被严格校验，也仍然可用？
