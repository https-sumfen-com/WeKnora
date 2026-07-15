# 农事设备灌溉工作流设计

## 目标与范围

升级 `custom_skills/agri-operation-workflow`，增加基于土壤湿度传感器、地块信息和天气的灌溉判断、阀门组时长表单、跨轮确认及设备执行流程。

本次同时同步 `custom_skills/sono-mcp` 中 `get_valve_bank_by_device` 的本地契约：参数由单个 `plot_device_id` 改为批量字符串 `plot_device_ids`，返回值由单个对象改为服务端已去重的阀门组列表。保留工作区中已经存在的用户修改，只补齐仍使用旧参数的章节和引用。

本次不修改前端解析器。技能内定义新的 Syntax 与 `form_submit` 合同，供具备相应解析能力的前端消费。

## 边界

- 传感器辅助判断、灌溉推荐、时长表单和确认执行由 `agri-operation-workflow` 负责。
- 实际查询和控制仍由 SONO-MCP 工具负责；本技能不复制 MCP 实现。
- 纯数据转换、表单生成、表单校验和执行授权由独立脚本 `scripts/irrigation_control_payload.py` 负责。
- 用户直接明确要求控制一个已确定的阀门组时，继续遵循 `sono-mcp` 的直接控制合同；传感器辅助推荐流程不得削弱该合同的参数约束和返回处理规则。
- 没有有效遥测、无需灌溉或没有可控制阀门组时，不得调用 `start_valve_bank`。

## 组件

### 技能主流程

`SKILL.md` 增加设备灌溉触发词、流程分支、硬性确认边界和完成检查。主流程负责选择 SONO-MCP 工具、组织灌溉判断证据、保存脚本产生的内部草稿，并根据脚本输出决定是否允许设备控制。

### SONO-MCP 批量阀门合同

`get_valve_bank_by_device` 接收：

```json
{
  "cid": 2007,
  "plot_device_ids": "16,21,35"
}
```

`plot_device_ids` 是由正整数地块设备关联 ID 组成的逗号字符串，不使用 JSON 数组，不包含空格。ID 来自 `get_plot_device_list` 每个设备项最外层 `id`，不能使用嵌套的 `device.id`。调用前按首次出现顺序去重。

接口成功后返回阀门组列表，列表已经由服务端按阀门组去重。每项至少保留 `id`、`run_status` 和 `title`。工作流验证列表内容，但不依赖本地再次去重来修正上游结果。

### 确定性脚本

新增 `scripts/irrigation_control_payload.py`，提供四个子命令：

1. `analyze-sensors`：提取每台设备的一个有效 `SHUM` 值，输出传感器明细、平均湿度、去重后的 `plot_device_ids` 数组及逗号字符串。
2. `build-panel`：验证服务端返回的阀门组列表，结合 Agent 给出的灌溉判断和推荐时长，生成专用 Syntax 及内部 `pending_irrigation_draft`。
3. `prepare-execution`：校验前端提交的阀门组 ID、选择状态和时长，输出用户可见的最终执行草稿及内部 `pending_execution_draft`；此阶段不产生 MCP 控制参数。
4. `build-execution`：仅在后来一轮用户明确确认已展示的执行草稿后，生成逐个调用 `start_valve_bank` 的参数列表。

脚本只做确定性转换和授权门禁，不调用 MCP，不自行判断农艺需求。

## 数据流

### 读取与平均土壤湿度

1. 使用上下文中的 `cid` 和 `plot_id` 调用 `get_plot_device_list`。
2. 对每个设备读取 `item.device.device_data[]`。
3. 只接受 `key == "SHUM"` 的条目，大小写必须精确匹配；忽略 `trsd`、`shum`、空值、布尔值、非数值以及非有限数值。
4. 每台设备最多贡献一个湿度值。若同一设备出现多个有效 `SHUM`，取数组中第一个有效值，避免单台设备因重复字段在总体平均值中获得更高权重。
5. 平均湿度等于所有有效设备湿度值的算术平均值。保留原始传感器明细，并输出用于展示的稳定小数结果。
6. 只把具有有效 `SHUM` 的设备最外层 `id` 纳入 `plot_device_ids`。

若没有有效 `SHUM`，不得自动判断需要灌溉或查询阀门组；转为常规农事建议，并说明缺少有效土壤湿度遥测。

### 灌溉判断

1. 调用 `get_plot_info` 获取作物、面积、生长阶段、水分或地块条件。
2. 调用 `get_weather` 获取当前天气及近期预报；需要判断未来降雨时传 `days=7`。
3. Agent 综合平均 `SHUM`、各传感器差异、作物与生长阶段、地块条件、近期降雨、温度、湿度和风况形成判断。
4. 不设置适用于所有作物的固定湿度阈值。证据优先级为 MCP 实时数据、上下文中的技术标准或知识库、用户明确条件、保守的农艺判断。
5. 无需灌溉时，返回判断依据和监测建议，不生成表单。
6. 需要灌溉时，给出保守的正整数推荐时长。推荐值是可编辑建议，不构成设备控制授权。

### 批量查询阀门组

把 `analyze-sensors` 输出的逗号字符串一次性传给 `get_valve_bank_by_device`：

```json
{
  "cid": 2007,
  "plot_device_ids": "16,21,35"
}
```

不按传感器循环调用。返回空列表时转入现有常规灌溉农事操作推荐流程，通过 `get_farming_operation_list` 获取真实事项，不创建虚构操作，也不自动新增农事记录。

### 灌溉时长表单

至少返回一个阀门组时，`build-panel` 生成：

```text
form irrigation-valve-duration
title 灌溉时长确认
autoOpen false
plot_name "示例地块"
average_soil_moisture 27
reason "土壤湿度偏低且未来三天无明显降雨"
data
  - valve_bank_id 31
    valve_bank_title "水肥阀门组01"
    duration_minutes 20
    selected true
```

表单只允许调整 `duration_minutes` 和 `selected`。阀门名称、原始运行状态、地块、平均湿度、判断依据和候选阀门列表保存在 `pending_irrigation_draft` 中；后续不得信任前端回传的同名元数据。

前端提交合同：

```json
{
  "type": "form_submit",
  "formType": "irrigation-valve-duration",
  "tag": "irrigation_valve_duration_confirm",
  "sourceMessageId": "assistant-message-id",
  "valveBanks": [
    {
      "valve_bank_id": 31,
      "duration_minutes": 20,
      "selected": true
    }
  ]
}
```

校验规则：阀门组 ID 必须存在于内部候选列表，每个 ID 最多出现一次，时长必须是正整数，至少选择一个阀门组。未知 ID、重复 ID、零时长、负数、布尔值和小数均拒绝。

### 二次确认与执行

表单提交只是对阀门组和时长的首次确认。`prepare-execution` 输出包含地块、平均湿度、判断依据、阀门组名称和最终时长的执行草稿，Agent 展示后结束当前轮次。

只有后来一轮用户明确确认这份已展示草稿时，才调用 `build-execution`，并同时传入：

```json
{
  "execution_confirmed": true,
  "draft_was_shown_to_user": true,
  "confirmation_source": "user_confirmed_irrigation_execution_draft"
}
```

`build-execution` 返回：

```json
{
  "start_valve_bank_args": [
    {
      "cid": 2007,
      "id": 31,
      "auto_off_minutes": 20
    }
  ]
}
```

禁止在推荐轮、表单生成轮或表单提交轮调用 `start_valve_bank`。禁止根据自然语言中的模糊同意自行伪造确认标记。

多个阀门组按脚本返回顺序逐个执行。若某一组返回错误，停止调用后续阀门组；不得自动关闭已经成功启动的阀门组作为补偿。最终结果分别列出已启动、失败和未执行项，只有上游明确确认成功时才描述为启动成功。

## 错误与降级处理

| 条件 | 行为 |
|---|---|
| `cid`、`plot_id` 缺失 | 追问或从受信上下文恢复，不调用工具 |
| 没有设备或没有有效 `SHUM` | 不查询阀门，不自动控制；返回常规建议 |
| 地块或天气信息不足以支持判断 | 说明证据不足，不生成设备控制表单 |
| 阀门接口返回空列表 | 转入常规灌溉农事操作推荐 |
| 阀门列表字段无效 | 拒绝生成表单，不猜测 ID、名称或状态 |
| 表单被篡改或时长无效 | 要求用户重新提交，不生成执行参数 |
| 缺少跨轮确认上下文 | 返回 `requires_execution_confirmation: true`，不得控制设备 |
| 某阀门启动失败 | 停止后续调用，报告部分执行状态 |

## 文件职责

- `custom_skills/agri-operation-workflow/SKILL.md`：流程选择、工具编排、硬性确认边界。
- `custom_skills/agri-operation-workflow/references/irrigation-control.md`：灌溉判断、降级和设备执行合同。
- `custom_skills/agri-operation-workflow/references/irrigation-form.md`：Syntax 与 `form_submit` 字段合同。
- `custom_skills/agri-operation-workflow/scripts/irrigation_control_payload.py`：确定性数据转换和授权门禁。
- `custom_skills/agri-operation-workflow/tests/test_irrigation_control_payload.py`：脚本与技能合同回归测试。
- `custom_skills/agri-operation-workflow/agents/openai.yaml`：补充设备灌溉触发说明。
- `custom_skills/sono-mcp/SKILL.md`：同步批量参数、示例和返回列表说明。
- `custom_skills/sono-mcp/references/tool-valve-bank-by-device.md`：批量请求与列表响应权威引用。
- `custom_skills/sono-mcp/references/tool-plot-device-list.md`：同步批量参数交接说明。

## 测试策略

严格按 RED-GREEN-REFACTOR：

1. 先增加失败测试，证明当前技能不能精确提取 `SHUM`、不能构造批量参数、没有专用表单且没有设备执行二次确认门禁。
2. 覆盖精确键匹配、数值清洗、单设备单权重、平均值、ID 去重和逗号拼接。
3. 覆盖阀门列表校验、Syntax 生成、内部草稿保留及前端篡改拒绝。
4. 覆盖表单提交当轮不得产生控制参数、后来轮明确确认后才产生参数。
5. 覆盖空传感器、空阀门列表、无选择、无效时长和未知阀门 ID。
6. 运行新测试、现有农资脚本测试、两个技能的 `quick_validate.py`，并检查工作区差异没有覆盖用户原有修改。
7. 使用最小上下文的前向场景验证 Agent 能正确选择批量接口、在表单提交后停下并等待第二轮确认。
