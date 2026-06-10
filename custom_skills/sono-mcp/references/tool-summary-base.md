# get_summary_base 字段提取规则

## 响应结构

```
response[0]
├── department_id        # 0=企业管理员，>0=基地管理员
├── id
└── summary
    ├── base_ids[]       # 包含的基地 ID 列表
    ├── batch_id         # 当前批次 ID
    ├── generated_at     # 数据生成时间
    │
    ├── index_v2                   # 企业 KPI（基地数、面积、水浇地、成本）
    ├── crop_statistics[]          # 作物种植统计（name/area/count_num）
    ├── batch[]                    # 历年产量（name="2024年-甜菜", value=吨）
    ├── batch_contrast_count[]     # 当年 vs 上年投入/产出对比
    │
    ├── wisdom_base
    │   ├── plot                   # 地块面积/数量汇总
    │   ├── plot_type[]            # 地块类型（旱地/喷灌/滴灌）
    │   ├── plant_structure[]      # 作物种植结构（同 crop_statistics）
    │   └── sowing_progress[]      # 播种进度（name/value%）
    │
    ├── wisdom_machine
    │   ├── machine_summary        # 农机汇总（total/work_area/work_time/avg_oil）
    │   ├── machine_type[]         # 农机型号分布
    │   ├── machine_task[]         # 近12月任务量（月度）
    │   └── machine_oil[]          # 近12月油耗（月度）
    │
    ├── wisdom_irrigation
    │   └── device
    │       ├── summary            # {abnormal_count, online_count, total}
    │       ├── status[]           # [{name:"在线",value:N},{name:"离线",value:N}]
    │       └── type[]             # 设备类型分布
    │
    ├── base_soil_preparation_year_count  # 整地年限地块数分布
    ├── base_stock_type_count[]           # 物资库存统计
    │
    ├── weather                    # 实时天气（同 get_weather payload.now）
    └── weather_7days              # 7天预报；weather_7days.daily[] 为预报数组
```

## 角色判断

| `department_id` | 角色 | 关注重点 |
|---|---|---|
| `0` | 企业管理员 | 全企业效益、多作物种植情况、历年产量、整体风险 |
| `> 0` 或按 `base_id` 查 | 基地管理员 | 本基地运营、地块作业、设备状态、作业建议 |

## 企业管理员（department_id=0）字段映射

| 卡片 | 来源路径 | 字段 |
|---|---|---|
| KPI 概览 | `index_v2` | `base_count`、`plot_area`+`plot_area_rate`、`water_area`+`water_area_rate` |
| KPI 概览 | `wisdom_base.plot` | `plot_count`+`plot_count_rate` |
| KPI 概览 | `wisdom_machine.machine_summary` | `total`（台数）、`work_area`（作业面积） |
| 作物结构 | `crop_statistics[]` | `name`、`area`（亩） |
| 地块类型 | `wisdom_base.plot_type[]` | `name`、`value`（亩） |
| 历年产量 | `batch[]` | `name`（"年份-作物"格式）、`value`（产量，吨） |
| 当年投入 | `batch_contrast_count[0].count[]` | `stock_type_name`、`area`、`avg`、`total` |
| 上年对比 | `batch_contrast_count[1].count[]` | `种子`/`化肥`/`农药` total + `水浇地单产`/`旱地单产` avg |
| 设备风险 | `wisdom_irrigation.device.summary` | `abnormal_count`、`online_count`、`total` |
| 播种进度 | `wisdom_base.sowing_progress[]` | `name`、`value`（% 进度） |
| 实时天气 | `weather.now` | 同 tool-weather.md 实时字段 |
| 7天预报 | `weather_7days.daily[]` | 同 tool-weather.md 预报字段 |

## 基地管理员（department_id>0）字段映射

| 卡片 | 来源路径 | 字段 |
|---|---|---|
| KPI 概览 | `wisdom_base.plot` | `plot_count`、`area`、`water_area`+`water_area_rate` |
| KPI 概览 | `wisdom_machine.machine_summary` | `total`、`work_area` |
| 作物结构 | `wisdom_base.plant_structure[]` | `name`、`value`（亩） |
| 地块类型 | `wisdom_base.plot_type[]` | `name`、`value` |
| 农机设备 | `wisdom_machine.machine_summary` + `wisdom_irrigation.device.summary` | 各类汇总数 |
| 播种进度 | `wisdom_base.sowing_progress[]` | `name`、`value` |
| 天气预警 | `weather.now` | 同实时字段 |
| 7天预报 | `weather_7days.daily[]` | 同预报字段 |

## batch 历年产量解析

`batch[].name` 格式：`"2024年-甜菜"`；`value` 单位为吨。只取 `value > 0` 的条目，按年份分组，每个作物一条系列。

## batch_contrast_count 投入对比解析

- `[0]` = 当前批次（`batch_info.title`，如"2026年"）：本年已投入物资
- `[1]` = 上一批次（`batch_info.title`，如"2025年"）：上年完整投入 + 最终单产

常用 `stock_type_id` 对照：

| id | 名称 | 批次 |
|---|---|---|
| `13` | 常规肥料 | 当年 |
| `10` | 微肥 | 当年 |
| `9` | 调节剂 | 当年 |
| `8` | 杀虫剂 | 当年 |
| `7` | 杀菌拌种剂 | 当年 |
| `6` | 除草剂 | 当年 |
| `14` | 小麦种子 | 当年 |
| `15` | 油菜种子 | 当年 |
| `"plot_type_water"` | 水浇地单产（kg/亩） | 当年/上年 |
| `"plot_type_dry"` | 旱地单产（kg/亩） | 当年/上年 |
| `3` | 化肥 | 上年 |
| `4` | 农药 | 上年 |
| `5` | 种子 | 上年 |
| `"cost_price_*"` | 各类成本（元/亩） | 上年 |

## 空值跳过规则

- `index_v2.total_cost = 0` → 不展示总成本 item
- `index_v2.machine_count = 0` / `device_count = 0` → 改用 `wisdom_machine` / `wisdom_irrigation` 字段
- `batch[].value = 0` → 跳过（无产量记录）
- `batch_contrast_count[x].count[].total = 0` → 跳过该投入行
- `wisdom_base.sowing_progress[].value = 0` → 说明"播种进度暂无记录"，不展示为 0%
- `wisdom_machine.machine_task[]` / `machine_oil[]` 全为 0 → 跳过月度趋势图
- 天气：`icon`、`wind360`、`pressure`、`fxLink`、`refer` → 跳过

## 禁止展示

- `base_soil_preparation_year_count`（仅用户主动问整地年限时展示）
- `base_stock_type_count[]`（内部库存字段）
- 坐标、边界、`tgzn_*`、内部 ID
