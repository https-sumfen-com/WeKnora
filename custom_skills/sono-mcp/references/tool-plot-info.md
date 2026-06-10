# get_plot_info 字段提取规则

地块报告聚焦**实时生长状态 + 农事建议**，不关注档案字段（地址、经纬度、创建人、同步状态）。

## 必须提取的字段

| 关注维度 | 字段路径 | 说明 |
|---|---|---|
| 地块基础 | `name`、`area`、`area_unit`、`base.name`、`plot_type.name`、`business_type` | 面积、所属基地、地块类型 |
| 当前种植 | `plot_crop.crop.name`、`plot_crop.batch.title`、`plot_crop.start_time`、`plot_crop.end_time` | 作物名、批次、播种/预计收获日期 |
| 生长进度 | `plot_crop.already_days`、`plot_crop.progress`、`plot_crop.current_crop_model_cycle.name` | 已生长天数、阶段进度%、当前阶段名称 |
| 阶段说明 | `plot_crop.current_crop_model_cycle.remark` | 含"生长状态："和"注意事项："两段，格式通常为 `"生长状态：...\n注意事项：..."` |
| 长势评级 | `grade[]`（title + value） | 作物长势、土壤类型、土壤含量、光照条件、水分含量、土壤肥力 |
| 积温积雨 | `accumulated_tp.temp`、`last_temp`、`rainfall`、`last_rainfall`、`valid_temp`、`last_valid_temp`、`start_date`、`end_date`、`analyze` | 含同比文字 |
| 设备状态 | `iot_device.online`、`offline`、`fault`、`long_term_offline` | online>0 或 fault>0 时才展示 |

## 空值跳过规则（重要）

`plot_crop` 为 null 或 `plot_crop.crop` 为 null：
- 作物名、已生长天数、生长阶段、播种日期、预计收获 **全部跳过**，不能用 "0" 占位
- 在 metric 卡片后写 Markdown：`"暂无种植批次数据。"`

字段级跳过（值为 `0`、`"0"`、null、空字符串时，直接跳过该字段，不输出）：
- `plot_crop.start_time` = `"0"` 或 `"0000-00-00"` → 播种日期跳过
- `plot_crop.already_days` = 0 → 已生长天数跳过
- `plot_crop.crop.name` 为空或 null → 作物跳过
- `available_nitrogen`/`available_phosphorus`/`available_potassium`/`organic`/`ph` 均为空 → 整个土壤化验板块跳过
- `plot_crop.target_output = 0` → 不展示目标产量
- `grade[].value` 为 "0" 或空 → 该评级项跳过
- `accumulated_tp` 整体为空或全字段为 0 → 跳过积温积雨卡片

## remark 字段解析方法

`plot_crop.current_crop_model_cycle.remark` 通常格式为：

```
生长状态：{当前阶段的生长描述文字}
注意事项：{农事建议文字}
```

提取规则：
- "生长状态："到"注意事项："之间的文字 → metric 卡片后 Markdown 补充说明
- "注意事项："之后的文字 → recommendation 基础建议（priority: `low`）
- 若 remark 不含上述关键词，整体作为生长状态说明

## 禁止展示的字段

- 坐标、边界、`pathPositions`、`enclosure_img`、`cover` 图片 URL
- `tgzn_*`、`sync_id`、`member_id`、`use_id` 等系统内部字段
- `crop_model_cycle` 全部阶段列表（只用 `current_crop_model_cycle`）
- 土壤化验为空时不生成占位卡片
- **不从 `get_plot_info` 结果中提取天气字段**，天气数据须调用 `get_weather`

## 农事建议生成规则

建议必须来源可追溯，不能写通用模板建议。

1. `current_crop_model_cycle.remark` 中"注意事项："之后的文字 → 当前阶段基础建议（priority: `low`）
2. `grade[].value = "低"` 的项 → 针对性建议（priority: `high`）：
   - 水分含量=低 → 建议尽快安排灌溉，结合 `plot_type.name` 判断灌溉方式（喷灌/滴灌/旱地）
   - 土壤肥力=低 → 建议追施基肥，参考当前阶段养分需求
   - 光照条件=低 → 关注天气预报，必要时推迟化学作业
3. `iot_device.fault > 0` → 建议排查故障设备（priority: `mid`）
4. `accumulated_tp.temp` 低于 `last_temp` 超过 20% → 低温风险提示，关注幼苗保护（priority: `mid`）
5. `accumulated_tp.rainfall` 高于 `last_rainfall` 超过 100% → 渍水风险提示，检查排水（priority: `mid`）

最多 3 条，按 priority 降序保留。每条 `reason` 必须引用具体字段值。
