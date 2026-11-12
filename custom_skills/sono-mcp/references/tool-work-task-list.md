# 农事计划列表 MCP 调用与字段规则

适用于 `get_work_task_list`。该工具由服务端调用 service-agri JSON-RPC；Agent 只调用 MCP 工具，不直接请求上游，也不自行构造 JSON-RPC envelope。

## 目录

- [1. 工具选择](#1-工具选择)
- [2. JSON-RPC 映射](#2-json-rpc-映射)
- [3. 查询参数与窗口](#3-查询参数与窗口)
- [4. 返回字段](#4-返回字段)
- [5. MCP 参数示例](#5-mcp-参数示例)
- [6. 返回处理](#6-返回处理)

## 1. 工具选择

| 用户意图 | MCP 工具 | 写入数据 |
|---|---|---|
| 查询某个地块从指定日期开始 7 天内的计划 | `get_work_task_list` | 否 |

- “农事记录”表示已经发生的作业，用 `add_farming_record`；“农事计划”表示未来安排，列表查询使用本文件的工具。
- 查询意图不得触发新增或更新；查到计划也不代表用户授权修改。
- 用户明确要求新增或编辑计划时，分别使用 `add_work_task`、`update_work_task`，并加载 `tool-work-task-add-update.md`。

## 2. JSON-RPC 映射

服务端负责构造 JSON-RPC 2.0 的 `jsonrpc`、`id`、`method` 和 `params`。Agent 只提供 MCP 参数。

| MCP 工具 | 上游 method | 上游 params |
|---|---|---|
| `get_work_task_list` | `/agri/getWorkTaskList` | `[cid, plot_id, date]` |

- `cid`、`plot_id`、`date` 由服务端依次放入 JSON-RPC 位置参数；Agent 不构造 envelope。
- `token`、`entity_id`、`entity_info_id` 只使用上下文真实值，不进入上述业务位置参数。
- JSON-RPC `error` 会转换为 MCP `isError=true`；成功结果直接返回业务 JSON，不包含 `action`、`source` 外层包装。

## 3. 查询参数与窗口

| 参数 | 必填 | 规则 |
|---|---|---|
| `cid` | 是 | 正整数企业 ID |
| `plot_id` | 是 | 单个正整数地块 ID；不接受逗号分隔多地块 |
| `date` | 否 | 7 天窗口起始日，格式 `YYYY-MM-DD`；省略时从当天开始 |
| `token` / `entity_id` / `entity_info_id` | 否 | 只使用上下文真实值 |

- “今天”可转换为当天日期或省略 `date`；“明天”“下周一”等先转换为确定日期，不原样传入。
- 返回范围是起始日起连续 7 个自然日，并按开始日期、计划 ID 升序排列。
- 跨越窗口的计划也可能返回：计划在窗口前开始、但在窗口内或之后结束时仍属于有效结果。

## 4. 返回字段

| 字段 | 含义 | 回答规则 |
|---|---|---|
| `id` | 农事计划 ID | 保留，后续更新只能使用此值 |
| `name` | 计划名称 | 列表首要字段 |
| `start_time` / `end_time` | 起止日期 | 有值时展示，不扩展范围 |
| `plot_id` / `plot_list` | 地块 ID，以及地块的 `id`、`name`、`area`、`area_unit` | 优先展示真实名称，无名称时展示 ID |
| `work_user` / `work_team_id` | 执行人 ID 和作业组 ID | 不根据 ID 猜姓名或作业组名称 |
| `matter_list` | 农事事项列表 | 元素包含计划事项关联 `id`、农事类型 `matter_id` 和 `goods_list` |
| `progress_count` / `progress_rate` | 完成数、总数和进度百分比 | 优先采用上游返回值，不自行重新计算或修正 |
| `status` / `status_text` / `is_end` | 状态和是否结束 | 三个字段分别按真实值描述，不根据其中一个反推其他字段 |
| `remark` / `remind_time` | 备注和提醒时间 | 非空时展示；`remind_time` 可为 `HH:mm` |

`matter_list[].goods_list` 的农资、配方、用量和成本字段，统一参考[新增、编辑农事计划的 `goods_list` 规则](tool-work-task-add-update.md#6-matter_list-与农资配方)。查询结果由上游直接返回，可能额外包含 `type`、`plan`、`plan_total_num`，并可能将 `price` 等数值表示为字符串；回答时原样理解，不擅自改类型、补字段或反向推算提交参数。

单条计划的实际返回结构如下；工具最外层返回由同类对象组成的数组：

```json
{
  "end_time": "2026-03-19",
  "id": 34922,
  "is_end": 0,
  "matter_list": [
    {
      "goods_list": [
        {
          "dosage": 2,
          "goods_id": 0,
          "goods_name": "生长配方",
          "num": 3,
          "plan": [],
          "plan_total_num": 0,
          "plot_cost_price": 1.11,
          "price": "100",
          "stock_goods_id": 20,
          "total_price": 751.11,
          "type": 1,
          "unit": "组"
        },
        {
          "dosage": 3,
          "goods_id": 0,
          "goods_name": "氯化铵",
          "num": 4,
          "plan": [],
          "plan_total_num": 0,
          "plot_cost_price": 1.11,
          "price": "200",
          "stock_goods_id": 3,
          "total_price": 750.11,
          "type": 1,
          "unit": "组"
        }
      ],
      "id": 53,
      "matter_id": 143
    }
  ],
  "name": "2026-03-19计划",
  "plot_id": "19142",
  "plot_list": [
    {
      "area": 877,
      "area_unit": "亩",
      "id": 19142,
      "name": "机耕队63号地水浇地"
    }
  ],
  "progress_count": {
    "finish_num": 1,
    "progress_rate": 100,
    "total_num": 1
  },
  "progress_rate": 100,
  "remind_time": "05:00",
  "start_time": "2026-03-19",
  "status": 1,
  "status_text": "进行中",
  "work_team_id": 0,
  "work_user": "385"
}
```

空数组表示该地块在目标窗口内没有计划，不是查询失败。

## 5. MCP 参数示例

```json
{
  "cid": 2007,
  "plot_id": 23550,
  "date": "2026-08-10"
}
```

## 6. 返回处理

- 返回值应为计划数组；空数组表示目标 7 天窗口内没有计划。
- 有结果时优先展示计划 ID、名称、日期、地块、执行人和状态；用户需要详情时再展开 `matter_list`。
- `isError=true` 时说明查询失败，不暴露 endpoint、JSON-RPC method、token 或内部错误堆栈，不自动改调其他工具。
- MCP 成功但内容为空时按空结果处理，不声称查询失败。
