# get_plot_device_info 字段提取规则

设备报告聚焦**设备状态 + 最新遥测 + 异常预警**，不展示设备类型定义模板和内部系统字段。

## Payload 结构

```
payload
├── id               # 外部关联 ID（入参的逻辑 ID）
├── name             # 设备名称（顶层简短名）
├── device_type      # 设备大类："sensor" / "machine" 等
├── plot             # 关联地块 {id, name}
├── plot_id
├── device_detail    # 主要数据来源（见下）
└── device_group     # 所属分组 {title}

device_detail
├── name             # 设备完整名称（含序列号）
├── deviceType.name  # 设备型号名称，如"气象站"
├── deviceGroup.title# 分组名，如"传感器"
├── is_online        # 0=离线，1=在线
├── last_device_time # 最后通信时间 "YYYY-MM-DD HH:mm:ss"
├── device_data[]    # ★ 已处理的遥测数组，含 name/value/field_unit/is_index/is_open
└── last_device_data # 原始键值对，含 电池电压_null 等隐藏字段
```

## 必须提取的字段

| 关注维度 | 字段路径 |
|---|---|
| 设备型号 | `device_detail.deviceType.name` |
| 设备完整名称 | `device_detail.name` |
| 所属分组 | `device_detail.deviceGroup.title` |
| 关联地块 | `plot.name` + `plot_id` |
| 在线状态 | `device_detail.is_online`（0=离线，1=在线） |
| 最后通信 | `device_detail.last_device_time` |
| 遥测读数 | `device_detail.device_data[]`（见下方提取规则） |
| 电池电压 | `device_detail.last_device_data.电池电压_null`（若存在） |

## 遥测数组提取规则（device_detail.device_data）

- 展示：`is_open=1` 的条目（含 `name`、`value`、`field_unit`）
- 跳过：`is_open=0` 的条目（系统隐藏字段，如瞬时雨量）
- `is_index=1` 的字段为核心指标，报告中优先展示
- 风向字段的 `value` 已经过 `angleToDirection` 处理，直接使用中文方向（如"南"）

## 跳过字段

- `deviceFeatures`、`deviceType.features`、`deviceField` — 字段定义模板，无遥测值
- `last_device_data` 中：`traceId`、`datatime`（时间戳数字）、`纬度_null`、`经度_null`
- 所有 `tgzn_*`、`icon`、`icon_path`、`cover`、图片 URL、EUI、platform
- `device_detail` 内嵌的重复 `device_detail`/`device_data` 结构

## 设备异常预警规则

| 条件 | 优先级 | 建议内容 |
|---|---|---|
| `is_online=0` | high | 设备离线，检查电源、网络连接和固件 |
| `电池电压_null < 3.5V` | mid | 低电量，尽快更换或充电 |
| `last_device_time` 距当前 > 2小时 | mid | 数据上报延迟，检查网络和设备状态 |
| 风速传感器值 > 10 m/s | mid | 结合天气预警逻辑（参考 tool-weather.md） |

无以上异常时不生成 recommendation，Markdown 一句"设备运行正常。"
