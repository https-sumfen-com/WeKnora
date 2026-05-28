# get_summary_base 字段提取与角色识别

payload 字段量极大，必须按用户角色定向提取，不要平铺所有字段。

## 角色判断

| 角色 | 判断条件 |
|---|---|
| 企业管理员 | `dept_id=0` 或上下文无 `dept_id`/`base_id` |
| 基地管理员 | `dept_id > 0` 或 `base_id > 0` |
| 无法判断 | 按企业管理员处理，Markdown 首句提示"如需查看特定基地请指定基地名称" |

用户问题明确指向某个基地名称时，从 `summary.base` 列表匹配 `id`，切换为基地管理员视角。

## 企业管理员（dept_id=0）

关注全企业效益、整体种植布局、多基地横向对比。

| 关注维度 | 字段路径 |
|---|---|
| 企业 KPI | `payload[0].summary.index_v2`（base_count、plot_area、water_area、water_area_rate） |
| 作物种植结构 | `payload[0].summary.crop_statistics`（各作物 name、area、count_num） |
| 历史产量趋势 | `payload[0].summary.batch`（年份-作物 name/value，2020-2025） |
| 当年投入与单产 | `payload[0].summary.batch_contrast_count`（当年 vs 上年：种子/肥药亩均、水浇地/旱地单产） |
| 各基地规模 | `payload[0].summary.base`（name、total_area、machine_num、people_num） |
| 各基地农机作业 | `payload[0].summary.wisdom_machine.machine_summary`（各基地 total/work_area/work_time/avg_oil） |
| 设备异常风险 | `payload[0].summary.wisdom_irrigation.device`（各基地 abnormal_count/online_count/total） |
| 各基地种植结构 | `payload[0].summary.wisdom_base.plant_structure`（各基地 key → 作物面积数组） |
| 播种进度 | `payload[0].summary.wisdom_base.sowing_progress`（各基地各作物进度值） |

**不要提取**：单基地设备遥测明细、地图坐标轨迹、`weather_7days` 逐日数据。

## 基地管理员（dept_id>0 或 base_id>0）

定位方式：用 `tgzn_dept_id`（=dept_id）或 `id`（=base_id）在 `wisdom_*`、`weather` 字典中作为 key。

| 关注维度 | 字段路径（以 base_id 为 key） |
|---|---|
| 本基地地块概况 | `wisdom_base.plot[base_id]`（plot_count、area、water_area、water_area_rate） |
| 作物种植结构 | `wisdom_base.plant_structure[base_id]`（各作物面积） |
| 地块类型分布 | `wisdom_base.plot_type[base_id]`（旱地/喷灌地块/滴灌地块面积） |
| 播种进度 | `wisdom_base.sowing_progress[base_id]`（各作物进度值） |
| 农机作业汇总 | `wisdom_machine.machine_summary[base_id]`（total/work_area/work_time/avg_oil） |
| 设备状态 | `wisdom_irrigation.device[base_id]`（total/online_count/abnormal_count） |
| 当前天气 | `weather[base_id].now`（temp/text/windScale/windDir/humidity） |
| 7天天气 | `weather_7days[base_id]`（如存在，用于作业安排建议） |

**不要提取**：其他基地的数据、企业历史产量趋势（除非用户主动追问对比）。
