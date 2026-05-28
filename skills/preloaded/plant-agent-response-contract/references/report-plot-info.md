# 地块报告结构（get_plot_info）

聚焦**实时生长状态 + 农事建议**，不展示档案字段（地址、坐标、创建人、系统标识）。

字段提取规则见 `sono-mcp/references/tool-plot-info.md`。

---

## 卡片顺序（3-4 张）

### 1. metric — 地块生长快照

来源：`plot_crop` + `area`

items 按序（值为 0 或空则跳过该 item）：

| label | value 来源 | unit |
|---|---|---|
| 作物 | `plot_crop.crop.name` | 用括号注明批次，如"（2026年）" |
| 面积 | `area` | `area_unit` |
| 已生长天数 | `plot_crop.already_days` | 天 |
| 当前阶段 | `plot_crop.current_crop_model_cycle.name` + 进度 | 如"幼苗期（19%）" |
| 播种日期 | `plot_crop.start_time` | YYYY-MM-DD |
| 预计收获 | `plot_crop.end_time` | YYYY-MM-DD |

### 2. table — 长势与环境评级

来源：`grade[]`

- 标题："长势与环境评级"
- 列：评估项 | 评级
- 只展示 value 非 "0" 且非空的项
- value="低" 的行在评估项后加 ⚠（如"水分含量 ⚠"）
- **此卡片是 recommendation 的视觉依据，必须在 recommendation 之前出现**

### 3. table — 积温积雨同比

来源：`accumulated_tp`

- 标题：`"积温积雨对比（{start_date} 至 {end_date}）"`
- 列：指标 | 本期 | 去年同期 | 变化
- 行：积温（°C）/ 有效积温（°C）/ 积雨（mm）
- `analyze` 字段内容作为卡片后的 Markdown 补充（1句话）
- `accumulated_tp` 为空 → 跳过此卡片

### 4. recommendation — 农事建议

**必须有事实来源，不能写通用模板建议。**

来源优先级：

1. `current_crop_model_cycle.remark` 中"注意事项："之后的内容 → 基础建议（priority: `low`）
2. `grade[].value="低"` → 针对性建议（priority: `high`）
3. `accumulated_tp` 积温偏低/积雨偏高异常 → 气象风险提示（priority: `mid`）
4. `iot_device.fault > 0` → 设备故障建议（priority: `mid`）

每条 `items[].reason` 必须引用具体字段值。最多 3 条，按 priority 降序保留。

---

## quick-reply（2-3 个）

- "查看该地块天气预报" → `"查询{name}天气"`
- "查看地块历史农事记录" → `"查询{name}农事作业记录"`
- 如 `iot_device.fault > 0`：追加 "查看故障设备详情" → `"查询该地块设备状态"`

---

## 禁止项

- 坐标、边界、`pathPositions`、`enclosure_img`、`cover` URL
- `tgzn_*`、`sync_id`、`member_id`、`use_id`
- `crop_model_cycle` 全部阶段列表（只用 `current_crop_model_cycle`）
- 土壤 N/P/K/有机质/pH 为空时不生成占位卡片，一行 Markdown 说明即可
