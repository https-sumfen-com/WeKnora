# get_plot_device_list 参数与字段提取规则

查询指定地块的传感器设备列表及实时读数。工具成功时直接返回数组；输出结构化结果时，必须保留本文列出的全部字段。

## 请求参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `cid` | 是 | 企业 ID，必须为正整数 |
| `plot_id` | 是 | 地块 ID，必须为正整数 |
| `page` | 否 | 页码；只传正整数，未指定时省略 |
| `limit` | 否 | 每页数量；只传正整数，未指定时省略 |
| `name` | 否 | 设备名称筛选值；服务端会去除首尾空格 |
| `token` | 否 | 会话中的上游访问令牌；没有时省略，禁止编造 |
| `entity_id` | 否 | 实体 ID；没有时省略 |
| `entity_info_id` | 否 | 实体信息 ID；没有时省略 |

`cid`、`plot_id`、`page`、`limit` 支持 JSON 整数或整数字符串。服务端固定查询 `device_type="sensor"` 并请求 `get_device_data=1`，这两个字段不是工具入参。

最小调用：

```json
{
  "cid": 2007,
  "plot_id": 123
}
```

缺少有效 `cid` 或 `plot_id` 时返回参数错误，不得把错误解释为空设备列表。

## 返回结构

```text
payload[]
├── id                       # 地块设备关联 ID（plot_device_id）
├── name                     # 地块设备显示名称
├── device_type              # 设备大类，例如 sensor
└── device
    ├── id                   # 设备 ID；不同于外层 id
    ├── name                 # 设备名称
    └── device_data[]
        ├── key              # 遥测字段编码
        ├── name             # 遥测字段名称
        ├── value            # 实时读数，类型按上游原值保留
        └── field_unit       # 单位；可能为空字符串
```

## 完整字段示例

```json
[
  {
    "device": {
      "device_data": [
        {
          "field_unit": "",
          "key": "trsd",
          "name": "土壤湿度",
          "value": 23
        },
        {
          "field_unit": "",
          "key": "trwd",
          "name": "土壤温度",
          "value": 22
        },
        {
          "field_unit": "",
          "key": "STEM",
          "name": "土壤温度v2",
          "value": 26
        },
        {
          "field_unit": "",
          "key": "SHUM",
          "name": "土壤湿度v2",
          "value": 27
        }
      ],
      "id": 424,
      "name": "水肥传感器01"
    },
    "device_type": "sensor",
    "id": 16,
    "name": "水肥传感器01"
  }
]
```

## 输出规则

- 每个设备项都输出 `id`、`name`、`device_type`、`device.id`、`device.name` 和完整的 `device.device_data[]`。
- 每条遥测都输出 `key`、`name`、`value`、`field_unit`；`field_unit=""` 时保留空字符串，不猜测单位。
- 即使遥测名称相近，也按不同 `key` 保留为独立读数，例如 `trwd` 与 `STEM`。
- 查询关联阀门组时，把外层 `id`（示例 `16`）作为 `get_valve_bank_by_device.plot_device_id`；不得传嵌套 `device.id`（示例 `424`）。
- 返回空数组时说明“未查询到该地块的传感器设备”，不要生成虚构设备或读数。
