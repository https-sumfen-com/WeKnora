# get_valve_bank_by_device 参数与字段提取规则

根据一个或多个地块设备关联 ID 查询阀门组。工具成功时直接返回阀门组列表；输出结构化结果时，必须保留本文列出的全部字段。

## 请求参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `cid` | 是 | 企业 ID，必须为正整数 |
| `plot_device_ids` | 是 | 逗号分隔的地块设备关联 ID 字符串；每项必须为正整数，取 `get_plot_device_list` 列表项最外层 `id` |
| `token` | 否 | 会话中的上游访问令牌；没有时省略，禁止编造 |
| `entity_id` | 否 | 实体 ID；没有时省略 |
| `entity_info_id` | 否 | 实体信息 ID；没有时省略 |

`cid`、`entity_id`、`entity_info_id` 支持 JSON 整数或整数字符串。`plot_device_ids` 必须是 JSON 字符串，例如单个 ID 传 `"16"`，多个 ID 传 `"16,17"`。

最小调用：

```json
{
  "cid": 2007,
  "plot_device_ids": "16,17"
}
```

缺少有效 `cid` 或 `plot_device_ids`，或其中任一 ID 不是正整数时返回参数错误，不得把错误解释为“未关联阀门组”。

## 返回结构

```text
payload[]
├── id                       # 阀门组 ID，可用于启动/停止阀门组
├── run_status               # 上游运行状态码，按字符串原值保留
├── title                    # 阀门组名称
└── devices[]                # 阀门组关联的地块设备明细
    ├── id                   # 阀门组与地块设备的关联记录 ID
    ├── tag                  # 关联标签，例如 fertigation、dual_way_valve
    ├── water_outlet         # 出水口名称
    └── device
        ├── id               # 地块设备关联 ID，可作为 plot_device_ids 中的一项
        ├── device_id        # 物理设备 ID
        ├── device_type      # 设备类型
        └── name             # 设备名称
```

## 完整字段示例

```json
[
  {
    "devices": [
      {
        "device": {
          "device_id": 423,
          "device_type": "sensor",
          "id": 15,
          "name": "测试水肥"
        },
        "id": 46,
        "tag": "fertigation",
        "water_outlet": "阀8"
      },
      {
        "device": {
          "device_id": 423,
          "device_type": "sensor",
          "id": 15,
          "name": "测试水肥"
        },
        "id": 47,
        "tag": "fertigation",
        "water_outlet": "阀7"
      }
    ],
    "id": 31,
    "run_status": "1",
    "title": "水肥阀门组01（不要修改）"
  },
  {
    "devices": [
      {
        "device": {
          "device_id": 403,
          "device_type": "sensor",
          "id": 10,
          "name": "双路"
        },
        "id": 52,
        "tag": "dual_way_valve",
        "water_outlet": "阀1"
      }
    ],
    "id": 36,
    "run_status": "0",
    "title": "测试流程"
  }
]
```

## 输出规则

- 每个阀门组项始终输出 `id`、`run_status`、`title`、完整的 `devices[]`，不得省略已有字段。
- 每个 `devices[]` 项完整保留关联记录 `id`、`tag`、`water_outlet` 以及 `device.id`、`device.device_id`、`device.device_type`、`device.name`。
- `run_status` 是字符串状态码；当前未提供状态码语义映射，保留上游原值，不自行推断“开启”或“关闭”。
- 列表项最外层 `id` 才是阀门组 ID；用户明确要求控制该阀门组时，可作为 `start_valve_bank.id` 或 `stop_valve_bank.id`。不得误用 `devices[].id`、`devices[].device.id` 或 `devices[].device.device_id`。
- `devices[].device.id` 是地块设备关联 ID，可作为后续 `plot_device_ids` 的一项；`devices[].device.device_id` 是物理设备 ID，两者不得混用。
- 返回空数组时说明“未查询到这些地块设备关联的阀门组”，不要生成虚构状态。
