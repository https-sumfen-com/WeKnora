# get_valve_bank_by_device 参数与字段提取规则

根据一批地块设备关联 ID 查询阀门组。工具成功时返回服务端已去重的阀门组列表；输出结构化结果时，必须保留本文列出的全部字段。

## 请求参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `cid` | 是 | 企业 ID，必须为正整数 |
| `plot_device_ids` | 是 | 逗号分隔的地块设备关联 ID 字符串，例如 `"16,21,35"`；各 ID 取 `get_plot_device_list` 列表项最外层 `id` |
| `token` | 否 | 会话中的上游访问令牌；没有时省略，禁止编造 |
| `entity_id` | 否 | 实体 ID；没有时省略 |
| `entity_info_id` | 否 | 实体信息 ID；没有时省略 |

`cid`、`entity_id`、`entity_info_id` 支持 JSON 整数或整数字符串。`plot_device_ids` 本身必须是逗号字符串，不是 JSON 数组或数字。

最小调用：

```json
{
  "cid": 2007,
  "plot_device_ids": "16,21,35"
}
```

同一批 ID 只调用一次。缺少有效 `cid`，或 `plot_device_ids` 为空、包含空片段/非正整数时返回参数错误，不得把错误解释为“未关联阀门组”。

## 返回结构

```text
payload[]
├── id           # 阀门组 ID
├── run_status   # 上游运行状态码，按字符串原值保留
└── title        # 阀门组名称
```

## 完整字段示例

```json
[
  {
    "id": 31,
    "run_status": "0",
    "title": "水肥阀门组01（不要修改）"
  },
  {
    "id": 32,
    "run_status": "0",
    "title": "水肥阀门组02（不要修改）"
  }
]
```

## 输出规则

- `payload[]` 是服务端已去重列表；不得按输入设备 ID 再复制阀门组，也不得自行改变服务端顺序。
- 每个列表项始终输出 `id`、`run_status`、`title`，不得省略任一字段。
- `run_status` 是字符串状态码；当前未提供状态码语义映射，保留上游原值，不自行推断“开启”或“关闭”。
- `id` 是阀门组 ID，不是输入的地块设备关联 ID；用户明确要求控制该阀门组时，可作为 `start_valve_bank.id` 或 `stop_valve_bank.id`。
- 返回空数组、`null` 或空文本时说明“未查询到这些地块设备关联的阀门组”，不要生成虚构状态。
