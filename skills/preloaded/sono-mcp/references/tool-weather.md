# get_weather 字段提取与预警规则

重点不是罗列气象数字，而是**判断预警等级并给出农事建议**。

## 有效字段（payload.now）

| 字段 | 含义 | 单位 |
|---|---|---|
| `text` | 天气状况描述 | — |
| `temp` | 实时温度 | °C |
| `feelsLike` | 体感温度 | °C |
| `humidity` | 相对湿度 | % |
| `windScale` | 风力等级 | 级 |
| `windDir` | 风向 | — |
| `windSpeed` | 风速 | km/h |
| `precip` | 过去1小时降水量 | mm |
| `dew` | 露点温度 | °C |
| `cloud` | 云量 | % |
| `vis` | 能见度 | km |
| `obsTime` | 观测时间 | ISO8601 |

**跳过**：`icon`（图标码）、`wind360`（角度，用 `windDir`）、`pressure`（气压无农事意义）、`fxLink`、`refer`

## 天气预警阈值

触发任一阈值时必须生成 recommendation。

| 指标 | 阈值 | 预警级别 | 农事影响 |
|---|---|---|---|
| `windScale` | ≥ 5 级 | 橙色 | 暂停喷药、喷灌，防药液飘移或灌溉不均 |
| `windScale` | ≥ 7 级 | 红色 | 停止所有田间机械作业 |
| `temp` | ≤ 5°C | 橙色 | 幼苗/萌发期关注冻害，推迟精密播种 |
| `temp` | ≥ 35°C | 橙色 | 避免正午田间作业，注意热害 |
| `humidity` | ≤ 30% | 黄色 | 干旱风险：旱地优先安排灌溉，监测墒情 |
| `humidity` | ≥ 85% | 黄色 | 高湿风险：关注真菌病害，避免高湿期喷雾 |
| `precip` | ≥ 10mm | 橙色 | 大雨：暂停田间作业，检查排水 |
| `precip` | ≥ 25mm | 红色 | 暴雨：停止所有作业，关注防涝 |
| `temp - feelsLike` | ≥ 8°C | 黄色 | 风寒明显，田间人员注意保暖 |

## 组合判断

多个字段联合触发时取更高级别：

- `windScale ≥ 5` + `humidity ≤ 30%` → 喷灌效果差，建议推迟至风速降低
- `temp ≤ 5°C` + `humidity ≥ 85%` → 霜冻+高湿，病害和冻害双风险
- `precip > 0` + `cloud ≥ 90%` → 持续阴雨，关注排水和病害

## 无预警时

输出天气快照 metric + 一句 Markdown："当前气象条件（风力{windScale}级，温度{temp}°C，湿度{humidity}%）适宜田间作业。" 不要生成空 recommendation。
