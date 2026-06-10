# get_wofost_report 字段提取规则

WOFOST 报告聚焦**作物模型模拟结果 + 生育进程 + 水分/养分平衡 + 报告链接**，不要原样倾倒 `csv_content` 明细。

## 响应结构

```
payload
├── id
├── plot_id / plot_no
├── report_date          # 报告日期
├── report_no            # 报告编号
├── daily_report_pdf     # PDF 报告链接
├── daily_report_csv     # CSV 明细链接
├── json_file            # 可为空
├── csv_content[]        # JSON 数组：逐日模型明细
├── summary_report_json  # JSON 对象：生长/产量摘要
└── terminal_report_json # JSON 对象：水分平衡摘要
```

`csv_content`、`summary_report_json`、`terminal_report_json` 是 JSON 字段：按数组/对象解析后提取，不要当作普通字符串输出。

## 必须提取的字段

| 关注维度 | 字段路径 | 说明 |
|---|---|---|
| 报告信息 | `report_date`、`report_no`、`plot_id`、`plot_no` | 报告日期、编号、地块标识 |
| 下载链接 | `daily_report_pdf`、`daily_report_csv` | 用户需要报告/明细时给链接；`json_file` 为空则跳过 |
| 生育日期 | `summary_report_json.DOS`、`DOE`、`DOA`、`DOM`、`DOH`、`DOV` | 播种、出苗、开花、成熟、收获等关键日期；null 跳过 |
| 生育进程 | `summary_report_json.DVS`、`LAIMAX`、`RD` | 发育阶段、最大叶面积指数、根深 |
| 生物量/产量 | `summary_report_json.TAGP`、`TWLV`、`TWRT`、`TWSO`、`TWST` | 地上总生物量、叶/根/贮藏器官/茎累计干物质 |
| 养分 | `summary_report_json.NamountSO`、`NuptakeTotal` | 贮藏器官氮量、总氮吸收 |
| 水分平衡 | `terminal_report_json.RAINT`、`TOTIRR`、`TOTINF`、`PERCT`、`WTRAT`、`EVST`、`EVWT`、`LOSST`、`TSR` | 降雨、灌溉、入渗、渗漏、蒸腾、蒸发、损失/径流 |
| 日序列趋势 | `csv_content[]` 中的 `DVS`、`LAI`、`TAGP`、`WSO`、`SM`、`TRA`、`RD`、`NuptakeTotal` | 只提取最后有效值、最大/最小值或趋势；不要逐行展示 |

## WOFOST 常用字段含义

| 字段 | 含义 | 解读要点 |
|---|---|---|
| `DVS` | 作物发育阶段 | 约 `0`=出苗，`1`=开花，`2`=成熟；`1~2` 表示开花后至成熟期 |
| `LAI` / `LAIMAX` | 叶面积指数 / 最大叶面积指数 | 反映冠层发育；优先展示 `LAIMAX` 和当前/最后有效 `LAI` |
| `TAGP` | 地上部总生物量 | 用于概括模型估算总生长量 |
| `WLV`/`TWLV` | 叶干物质 / 累计叶干物质 | 与叶片生长相关 |
| `WRT`/`TWRT` | 根干物质 / 累计根干物质 | 与根系发育相关 |
| `WSO`/`TWSO` | 贮藏器官干物质 / 累计贮藏器官干物质 | 可作为产量形成关注指标 |
| `WST`/`TWST` | 茎干物质 / 累计茎干物质 | 与茎秆生长相关 |
| `RD` | 根深 | 反映根系下扎深度 |
| `SM` | 土壤含水量 | 用于判断水分胁迫趋势 |
| `TRA` / `WTRAT` | 日蒸腾 / 总蒸腾 | 作物耗水强度 |
| `EVS` / `EVST` | 日土壤蒸发 / 总土壤蒸发 | 裸土或冠层下土壤蒸发 |
| `NuptakeTotal` | 总氮吸收 | 反映氮素累积吸收 |

## 空值与数值处理

- 字符串 `"NaN"`、实际 `NaN`、null、空字符串：一律视为空值，跳过，不输出为“NaN”。
- 数字字符串（如 `"14.27"`）按数字解析；输出时保留合理精度，避免长小数原样展示。
- `csv_content[]` 早期记录可能大量为 `"NaN"`：只从有效值中提取趋势和最后有效值。
- 若 `csv_content[]` 没有日期字段，不要臆造日期；可称为“第 N 条/模型日序列最后有效记录”。
- `json_file` 为空时跳过；PDF/CSV 链接为空时不生成下载项。

## 生育阶段解读

按 `summary_report_json.DVS` 或日序列最后有效 `DVS` 简要判断：

| DVS 范围 | 阶段描述 |
|---|---|
| `< 0` | 播种后、出苗前 |
| `0 <= DVS < 1` | 出苗后至开花前，营养生长期 |
| `1 <= DVS < 2` | 开花后至成熟前，产量形成/灌浆期 |
| `>= 2` | 成熟或接近模型终止阶段 |

优先结合 `DOS`、`DOE`、`DOA`、`DOM`、`DOH`、`DOV` 给出日期解释；缺失日期不要补猜。

## 水分与农事建议规则

建议必须来源于报告字段，最多 3 条，按风险优先级输出。

| 条件 | 优先级 | 建议内容 |
|---|---|---|
| `csv_content` 最后有效 `SM < 0.20` | high | 土壤含水量偏低，建议结合天气与灌溉条件安排补水 |
| `0.20 <= SM < 0.25` | mid | 土壤含水量偏低，继续监测墒情 |
| `terminal_report_json.TOTIRR = 0` 且 `WTRAT` 明显大于 `RAINT` | mid | 模型期主要依赖降雨，关注后续灌溉安排 |
| `terminal_report_json.PERCT > 0` 且降雨/入渗较高 | low | 有渗漏消耗，关注水肥淋失风险 |
| `summary_report_json.DVS >= 1` 且 `TWSO` 持续增加 | low | 处于产量形成阶段，关注水分和养分供应稳定性 |

若无明显风险，输出一句：`模型结果未显示明显水分或生长异常，建议按当前生育阶段继续跟踪。`

## 输出格式建议

1. 先用 1 句说明报告日期、地块和当前模型阶段。
2. 用 3~5 个关键指标概括：`DVS`、`LAIMAX`、`TAGP`、`TWSO`、`RD`、`NuptakeTotal`。
3. 单独概括水分平衡：降雨、灌溉、入渗、蒸腾、蒸发。
4. 有 PDF/CSV 链接时，用 Markdown 链接给出，不要展开长 URL。
5. 仅当用户要求“明细/逐日数据”时，才从 `csv_content[]` 生成摘要表；仍不要全量输出。

## 禁止展示

- 不要原样输出完整 `csv_content[]`。
- 不要展示 token、内部 URL、内部配置。
- 不要把 `plot_no`、`report_no` 解释成业务名称。
- 不要用 `NaN`、0 或空值生成占位指标。
- 不要把模型预测值表述为已经实际发生的测产结果；应称为“模型模拟/预测”。
