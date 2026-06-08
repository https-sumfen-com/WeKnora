# 地块基础快照结构（get_plot_info）

聚焦**基础种植状态 + 当前评级 + 农事建议**，不展示档案字段（地址、坐标、创建人、系统标识）。

地块情况、地块分析、地块报告的重点分析来源是 `get_wofost_report`。`get_plot_info` 只作为基础快照补充，用于名称、面积、当前作物、当前阶段、评级和建议依据；不要用它替代 WOFOST 的作物模型模拟分析。

字段提取规则见 `sono-mcp/references/tool-plot-info.md`。

---

## 卡片顺序（2-4 张）

### 1. metric — 地块生长快照

来源：`plot_crop` + `area`

**null 检查（先做）**：若 `plot_crop` 为 null 或 `plot_crop.crop` 为 null，则 作物/已生长天数/当前阶段/播种日期/预计收获 **全部跳过**；必要时由自然回复补充：`"暂无种植批次数据，以下信息仅供参考。"`

items 按序（值为 `0`、`null`、空字符串、`"0"` 时**跳过该 item**，不能用 "0" 占位）：

| label | value 来源 | unit / 格式 |
|---|---|---|
| 作物 | `plot_crop.crop.name` | 用括号注明批次年份，如"油菜（2026年）" |
| 面积 | `area` | `area_unit`（如"亩"） |
| 已生长天数 | `plot_crop.already_days` | 天 |
| 生长阶段 | `plot_crop.current_crop_model_cycle.name` + `plot_crop.progress` | 如"幼苗期（进度 19%）" |
| 播种日期 | `plot_crop.start_time` | YYYY-MM-DD（为 "0" 或 "0000-00-00" 时跳过） |
| 预计收获 | `plot_crop.end_time` | YYYY-MM-DD |

**禁止在此 metric 卡片中添加任何天气字段**（温度、湿度、风力、降水、当前天气等）。如果用户明确请求的是地块报告，天气应作为同一 `report.cards[]` 中的独立 weather chart 或 recommendation 维度，不要另起第二个 report。

**自然回复补充依据**（若 `current_crop_model_cycle.remark` 含"生长状态"段）：
> 当前阶段说明：{remark 中"生长状态："之后的内容，截取到"注意事项："之前}

### 2. chart — 长势与环境评级

来源：`grade[]`

- 标题："长势与环境评级"
- 图表优先：能把评级映射为有序分值时生成 ECharts `chart`，常见选择为 `radar` 或 `bar`
- 评级映射仅用于可视化：优=3、中=2、低=1；不要把映射分值当作业务原始事实
- 只展示 value 非 `"0"`、非空、非 null 的项
- value 为 `"低"` 的项在图表标签或 `sourceSummary` 中标注风险；如果无法稳定映射评级，再降级为 table
- `grade[]` 全为空 / 全为 "0" → 跳过此卡片，自然回复一句"暂无评级数据。"
- **此卡片是 recommendation 的视觉依据，必须在 recommendation 之前出现**

### 3. chart — 积温积雨同比

来源：`accumulated_tp`

- 标题：`"积温积雨对比（{start_date} 至 {end_date}）"`
- 图表优先：生成 ECharts `chart`，常见选择为分组 `bar`，展示本期 vs 去年同期；变化值可用标签、tooltip 或辅助系列表达
- 指标：积温（°C）/ 有效积温（°C）/ 积雨（mm）
- `analyze` 字段内容可作为自然回复依据（1句话），不进入 block
- `accumulated_tp` 为空或所有字段均为 0 → 跳过此卡片

### 4. recommendation — 农事建议

**必须有事实来源，不能写通用模板建议。**

来源优先级：

1. `current_crop_model_cycle.remark` 中"注意事项："之后的内容 → 基础建议（priority: `low`）
2. `grade[].value = "低"` → 针对性建议（priority: `high`）
3. `accumulated_tp` 积温偏低/积雨偏高异常 → 气象风险提示（priority: `mid`）
4. `iot_device.fault > 0` → 设备故障建议（priority: `mid`）

每条 `items[].reason` 必须引用具体字段值。最多 3 条，按 priority 降序保留。

若以上来源均无数据支撑 → 跳过 recommendation，自然回复一句"暂无农事建议依据。"

---

## quick-reply（2-3 个）

- "查看WOFOST模型报告" → `"生成{name}地块WOFOST作物模型报告"`（上下文有 `cid` 和 `plot_id` 时优先）
- "查看该地块天气预报" → `"查询{name}天气"`
- "查看地块历史农事记录" → `"查询{name}农事作业记录"`
- 如 `iot_device.fault > 0`：追加 "查看故障设备详情" → `"查询该地块设备状态"`

---

## 禁止项

- 坐标、边界、`pathPositions`、`enclosure_img`、`cover` URL
- `tgzn_*`、`sync_id`、`member_id`、`use_id`
- `crop_model_cycle` 全部阶段列表（只用 `current_crop_model_cycle`）
- metric 卡片中出现天气字段（温度、湿度、风力等）
- 值为 `0`、`"0"`、`null`、空字符串的 item **不能**以 "0" 显示，必须跳过
- 土壤 N/P/K/有机质/pH 为空时不生成占位卡片，由自然回复说明即可
