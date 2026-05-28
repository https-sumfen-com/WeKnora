# get_weather 字段提取与预警规则

重点不是罗列气象数字，而是**判断预警等级并给出农事建议**。

---

## 一、实时天气（不传 days 或 days=0）

来源：`payload.now`

### 有效字段

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

**跳过**：`icon`、`wind360`、`pressure`、`fxLink`、`refer`

### 实时天气预警阈值

触发任一阈值时必须生成 recommendation。

| 指标 | 阈值 | 预警级别 | 农事影响 |
|---|---|---|---|
| `windScale` | ≥ 5 级 | 橙色 | 暂停喷药、喷灌，防药液飘移 |
| `windScale` | ≥ 7 级 | 红色 | 停止所有田间机械作业 |
| `temp` | ≤ 5°C | 橙色 | 幼苗/萌发期关注冻害，推迟精密播种 |
| `temp` | ≥ 35°C | 橙色 | 避免正午田间作业，注意热害 |
| `humidity` | ≤ 30% | 黄色 | 干旱风险：优先安排灌溉，监测墒情 |
| `humidity` | ≥ 85% | 黄色 | 高湿风险：关注真菌病害，避免高湿期喷雾 |
| `precip` | ≥ 10mm | 橙色 | 大雨：暂停田间作业，检查排水 |
| `precip` | ≥ 25mm | 红色 | 暴雨：停止所有作业，关注防涝 |
| `temp - feelsLike` | ≥ 8°C | 黄色 | 风寒明显，田间人员注意保暖 |

### 组合判断

- `windScale ≥ 5` + `humidity ≤ 30%` → 喷灌效果差，建议推迟至风速降低
- `temp ≤ 5°C` + `humidity ≥ 85%` → 霜冻+高湿，病害和冻害双风险
- `precip > 0` + `cloud ≥ 90%` → 持续阴雨，关注排水和病害

### 无实时预警时

输出天气快照 metric + 一句 Markdown："当前气象条件（风力{windScale}级，温度{temp}°C，湿度{humidity}%）适宜田间作业。" 不要生成空 recommendation。

---

## 二、7天预报（days=7）

来源：`payload.days[]`，每项为一天的预报记录。

### 有效字段

| 字段 | 含义 | 单位 |
|---|---|---|
| `fxDate` | 预报日期 | YYYY-MM-DD |
| `tempMax` | 最高气温 | °C |
| `tempMin` | 最低气温 | °C |
| `textDay` | 白天天气描述 | — |
| `textNight` | 夜间天气描述 | — |
| `windScaleDay` | 白天风力等级 | 级 |
| `windDirDay` | 白天风向 | — |
| `humidity` | 相对湿度 | % |
| `precip` | 预计降水量 | mm |
| `uvIndex` | 紫外线指数 | — |

**跳过**：`icon`、`wind360`、`fxLink`、`refer`、`pressure`、`sunrise`、`sunset`（除非用户明确关注日出日落）

### 预报预警阈值

扫描 `days[]` 全部日期，命中以下条件的日期需在 recommendation 中标注：

| 指标 | 阈值 | 预警级别 | 农事影响 |
|---|---|---|---|
| `windScaleDay` | ≥ 5 级 | 橙色 | 该日暂停喷药喷灌 |
| `windScaleDay` | ≥ 7 级 | 红色 | 该日停止田间机械作业 |
| `tempMin` | ≤ 5°C | 橙色 | 夜间冻害风险，关注幼苗保护 |
| `tempMax` | ≥ 35°C | 橙色 | 高温热害，避免正午作业 |
| `precip` | ≥ 10mm | 橙色 | 大雨，暂停田间作业，检查排水 |
| `precip` | ≥ 25mm | 红色 | 暴雨，停止所有作业 |
| `humidity` | ≥ 85% | 黄色 | 高湿，关注真菌病害 |

### 作业窗口判断

从 `days[]` 中找出**无预警的连续日期**作为推荐作业窗口：
- 推荐条件：`windScaleDay ≤ 4` + `precip < 5mm` + `5°C < tempMin` + `tempMax < 35°C`
- 若连续 3 天以上满足条件 → 在 recommendation 中标注"推荐作业窗口：{fxDate} 至 {fxDate}"
- 若全部 7 天均有预警 → 说明"未来一周内无适宜大田作业窗口"

### 无预报预警时

输出预报 table + 一句 Markdown："未来7天气象条件整体正常，无明显农事风险。"

---

## 三、`days` 参数选择规则

| 用户意图 | days 参数 |
|---|---|
| 当前天气、今天天气、现在多少度、现在适合打药吗 | 不传（仅 now） |
| 未来天气、明天天气、这周天气、几天后、预报 | `days=7` |
| 未来天气预警分析、作业窗口安排、近期风险 | `days=7` |
