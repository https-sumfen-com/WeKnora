# 新增、编辑农事计划 MCP 调用与字段规则

适用于 `add_work_task`、`update_work_task`。两个工具都由服务端调用 service-agri JSON-RPC；Agent 只调用 MCP 工具，不直接请求上游，也不自行构造 JSON-RPC envelope。

## 目录

- [1. 工具选择](#1-工具选择)
- [2. JSON-RPC 映射](#2-json-rpc-映射)
- [3. 新增计划](#3-新增计划)
- [4. 更新计划](#4-更新计划)
- [5. 计划字段](#5-计划字段)
- [6. matter_list 与农资配方](#6-matter_list-与农资配方)
- [7. MCP 参数示例](#7-mcp-参数示例)
- [8. 返回处理](#8-返回处理)

## 1. 工具选择

| 用户意图 | MCP 工具 | 写入数据 |
|---|---|---|
| 新增、创建、保存一条未来计划 | `add_work_task` | 是 |
| 修改、调整、更新一条已有计划 | `update_work_task` | 是 |

- “农事记录”表示已经发生的作业，用 `add_farming_record`；“农事计划”表示未来安排，使用本文件的两个工具。
- 只有用户明确授权对应写操作时才能调用；查询计划使用 `get_work_task_list`，并加载 `tool-work-task-list.md`。
- 新增与更新不得互换：`add_work_task` 会移除所有 `id`，`update_work_task` 必须传真实计划 `id`。

## 2. JSON-RPC 映射

服务端负责构造 JSON-RPC 2.0 的 `jsonrpc`、`id`、`method` 和 `params`。Agent 只提供 MCP 参数。

| MCP 工具 | 上游 method | 上游 params |
|---|---|---|
| `add_work_task` | `/agri/updateWorkTask` | `[cid, plan_payload]`，强制删除 `plan_payload.id` |
| `update_work_task` | `/agri/updateWorkTask` | `[cid, plan_payload]`，`plan_payload.id` 必填 |

控制字段处理：

- `cid` 作为 JSON-RPC 第一个位置参数，不放入 `plan_payload`。
- `token`、`entity_info_id` 不放入 `plan_payload`。
- `entity_id > 0` 时由服务端放入 `plan_payload.entity_id`；不要在自定义 payload 中覆盖。
- 业务字段先按 MCP schema 解码，再合并到 `plan_payload`。额外字段只有在来源明确且上游契约确实需要时才传，不得编造。
- JSON-RPC `error` 会转换为 MCP `isError=true`；成功结果直接返回业务 JSON，不包含 `action`、`source` 外层包装。

## 3. 新增计划

### 调用条件

服务端硬性校验：

- `cid`：正整数。
- `name`：去除首尾空格后非空。
- `start_time`：非空日期字符串。

按当前业务表单语义，执行新增前还应确认：

1. 已选择基地。
2. 已确定结束日期，且不早于开始日期。
3. 已至少选择一个地块。
4. 已选择一个农事类型。
5. 已至少选择一个执行人。

提醒时间、作业组、农资和配方不是业务必填项。

### 新增纪律

- 只有用户明确要求新增、创建、保存或提交计划时调用。
- 禁止传 `id`。即使输入包含 `id`，MCP 解码层和 JSON-RPC 客户端也会删除它。
- `plot_id`、`work_user` 从数组去重后转成英文逗号分隔字符串。
- `end_time` 不得早于 `start_time`；服务端当前只校验必填字段，Agent 必须在调用前完成日期关系校验。
- `matter_list` 当前业务表单通常只包含一个农事类型；没有农资或配方时仍传 `goods_list: []`。

## 4. 更新计划

### 调用条件

服务端硬性校验：

- `cid`：正整数。
- `id`：正整数农事计划 ID。
- `name`：非空；即使只修改其他字段，也必须使用已知的原计划名称或用户明确提供的新名称，不得猜测。

### 部分更新语义

- 只传用户明确要求修改的可选字段。
- 省略字段表示保持上游原值。
- 显式空字符串或空数组会被保留，表示用户明确清空。例如 `end_time: ""`、`matter_list: []`。
- 修改日期时确保 `end_time >= start_time`；只修改其他字段时可省略日期。
- `id` 必须来自计划列表、当前计划上下文或用户明确选择，不得使用 `plot_id`、`matter_id`、农事记录 ID 代替。
- 用户没有明确修改授权时不得调用；调用失败后不自动改用 `add_work_task`。

## 5. 计划字段

### MCP schema 字段

| 字段 | 类型 | 使用规则 |
|---|---|---|
| `cid` | `number \| integer-string` | 必填企业 ID；服务端作为 JSON-RPC 独立位置参数 |
| `token` | `string` | 可选鉴权上下文；不进入计划业务 payload |
| `entity_id` | `number \| integer-string` | 可选；正整数时写入业务 payload |
| `entity_info_id` | `number \| integer-string` | 可选上下文；不进入计划业务 payload |
| `id` | `number \| integer-string` | 仅更新必填；新增禁止传入 |
| `name` | `string` | 新增、更新均必填；去除首尾空格 |
| `start_time` | `string` | 新增必填、更新可选；使用确定日期 |
| `end_time` | `string` | 可选；不得早于开始日期；更新时空字符串表示清空 |
| `remind_time` | `string` | 可选提醒日期；明确清空时可传空字符串 |
| `work_user` | `number \| string` | 执行人 ID；多选时去重后用英文逗号连接 |
| `plot_id` | `number \| string` | 新增/更新可传单个或英文逗号分隔地块 ID |
| `matter_list` | `array` | 农事类型、农资和配方；更新时空数组表示清空 |
| `remark` | `string` | 可选备注 |
| `cycle_type` | `string` | 可选周期类型；只传上游已知值 |
| `base_id` | `number \| integer-string` | 可选基地 ID；正整数时进入业务 payload |
| `user_id` / `dept_id` | `number \| integer-string` | 可选用户/部门上下文；只传真实值 |
| `tgzn_user_id` / `tgzn_dept_id` / `tgzn_entity_id` | `number \| integer-string` | 可选业务身份字段；只传真实值 |

### 兼容业务字段

当前服务会保留 MCP 输入中的额外业务字段，但它们不是核心 `WorkTaskFields`：

| 字段 | 类型 | 使用规则 |
|---|---|---|
| `work_team_id` | `number \| string \| null` | 可选作业组 ID；未选择时仅在上游明确接受 `null` 时传入 |
| `is_end` | `number` | 新增页面语义固定为 `0`；更新时只传用户明确要求的真实状态 |

`type`、`relation_type` 不属于当前已知业务字段；除非 MCP schema 或上游契约明确要求，否则不要加入。

## 6. `matter_list` 与农资配方

`matter_list` 元素：

| 字段 | 类型 | 规则 |
|---|---|---|
| `matter_id` | `number \| string` | 必填农事类型 ID，不根据名称猜 ID |
| `goods_list` | `array` | 农资和配方明细；没有时传 `[]` |

### 普通农资

普通农资 `is_formula=0`：

| 字段 | 类型 | 规则 |
|---|---|---|
| `goods_id` | `number \| string` | 农资 ID；优先使用库存农资 ID |
| `goods_name` | `string` | 农资名称 |
| `stock_goods_id` | `number \| string` | 库存农资 ID |
| `is_formula` | `number` | 固定 `0` |
| `num` | `number` | 总计划用量：每亩用量 × 所选地块总亩数 |
| `dosage` | `number` | 每亩用量换算值：每亩千克数 × `1000` |
| `price` | `number` | 单价；无有效价格时为 `0` |
| `total_price` | `string` | `num × price`，保留四位小数 |
| `plot_cost_price` | `string` | 每亩成本，保留四位小数；面积为 `0` 时为 `0.0000` |
| `unit` | `string` | 当前页面语义固定为 `KG` |

### 配方

配方顶层 `is_formula=1`：

| 字段 | 类型 | 规则 |
|---|---|---|
| `goods_id` | `number \| string` | 配方 ID |
| `goods_name` | `string` | 配方名称 |
| `is_formula` | `number` | 固定 `1` |
| `num` | `number` | 当前页面语义固定为 `1` |
| `total_price` | `string` | 所有组成农资总价之和，保留四位小数 |
| `goods` | `array` | 配方组成农资列表 |

配方组成农资：

| 字段 | 类型 | 规则 |
|---|---|---|
| `goods_id` | `number \| string` | 组成农资 ID |
| `goods_name` | `string` | 组成农资名称 |
| `stock_goods_id` | `number \| string` | 库存农资 ID；没有时为空字符串 |
| `price` | `number` | 单价；无有效价格时为 `0` |
| `unit` | `string` | 没有时为空字符串 |
| `num` | `number` | 用量；无有效值时为 `0` |
| `total_price` | `string` | `price × num`，保留四位小数 |

所有 ID、面积、用量和价格必须来自上下文、用户选择或真实计算结果，不得猜测。不要把库存余量直接当作计划用量。

## 7. MCP 参数示例

### 新增

```json
{
  "cid": 2007,
  "entity_id": 1,
  "name": "8 月水稻施肥计划",
  "start_time": "2026-08-10",
  "end_time": "2026-08-12",
  "remind_time": "2026-08-09",
  "base_id": 75,
  "work_team_id": 21,
  "work_user": "101,102",
  "plot_id": "301,302",
  "matter_list": [
    {
      "matter_id": 51,
      "goods_list": [
        {
          "goods_id": 801,
          "goods_name": "复合肥",
          "stock_goods_id": 801,
          "is_formula": 0,
          "num": 15,
          "dosage": 1500,
          "price": 3.2,
          "total_price": "48.0000",
          "plot_cost_price": "4.8000",
          "unit": "KG"
        }
      ]
    }
  ],
  "is_end": 0
}
```

### 更新

```json
{
  "cid": 2007,
  "id": 18,
  "name": "8 月水稻施肥计划（调整）",
  "start_time": "2026-08-11",
  "end_time": "2026-08-13",
  "remark": "根据降雨预报顺延一天"
}
```

## 8. 返回处理

- `add_work_task`、`update_work_task` 通常返回保存后的计划对象。只有存在明确计划 `id` 或保存后对象时，才确认新增/更新成功。
- 新增结果优先展示计划 ID、名称、日期、地块和执行人。
- 更新结果只说明真实返回或用户明确要求修改的内容，不声称省略字段已改变。
- `isError=true` 时说明操作失败，不暴露 endpoint、JSON-RPC method、token 或内部错误堆栈，不自动重试，也不改调另一个写入工具。
- MCP 成功但内容为空时说明请求已处理但没有可确认结果，不得声称写入成功。
