# 灌溉阀门组表单前端对接文档

## 1. 目标

在 `plant-agent` 对话流中支持设备灌溉建议的自定义渲染：

1. Agent 根据地块、土壤湿度、气象和阀门组信息返回灌溉时长表单。
2. 前端把 LLM 文本流中的 `form irrigation-valve-duration` 解析为阀门组卡片。
3. 用户可以选择阀门组并调整灌溉时长。
4. 前端通过正常对话流提交结构化 `form_submit` 消息。
5. 后端生成执行草稿和二次确认文案，但此时不得打开阀门。
6. 用户在后续轮次明确确认后，后端才允许调用 `start_valve_bank`。

本协议的后端事实来源为：

- `custom_skills/agri-operation-workflow/references/irrigation-form.md`
- `custom_skills/agri-operation-workflow/scripts/irrigation_control_payload.py`

## 2. 完整交互流程

```mermaid
flowchart LR
    A[Agent 输出灌溉表单 Syntax] --> B[前端流解析器识别表单]
    B --> C[渲染阀门组与推荐时长]
    C --> D[用户选择阀门并调整时长]
    D --> E[提交 form_submit 用户消息]
    E --> F[后端 prepare-execution]
    F --> G[Assistant 展示二次确认文案]
    G --> H[用户在下一轮明确确认]
    H --> I[后端 build-execution]
    I --> J[依次调用 start_valve_bank]
```

关键边界：

- 前端只负责展示阀门组、编辑时长和提交用户选择。
- 首次表单提交只生成执行草稿，不代表设备控制授权。
- 前端不得直接调用 `start_valve_bank`。
- 最终执行必须发生在 Assistant 展示确认内容后的下一次用户明确确认。

## 3. LLM 输出协议

Agent 返回以下专用 Syntax，不使用 JSON 包裹，也不直接返回 SSE 事件：

```text
form irrigation-valve-duration
title 灌溉时长确认
autoOpen false
plot_name "东区3号地块"
average_soil_moisture 25
reason "玉米拔节期地块偏干，未来三天无明显降雨"
data
  - valve_bank_id "31"
    valve_bank_title "东区滴灌阀组A"
    duration_minutes 20
    selected true
  - valve_bank_id "32"
    valve_bank_title "东区滴灌阀组B"
    duration_minutes 20
    selected true
```

字段规则：

| 字段 | 类型 | 可编辑 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 否 | 卡片标题 |
| `autoOpen` | boolean | 否 | 默认 `false`，消息内展示摘要卡片，不自动打开编辑弹窗 |
| `plot_name` | string | 否 | 地块名称，只作为判断依据展示 |
| `average_soil_moisture` | number | 否 | 多个土壤湿度传感器的平均湿度 |
| `reason` | string | 否 | 结合地块、作物、土壤湿度和天气得出的灌溉原因 |
| `valve_bank_id` | string | 否 | 阀门组ID，必须保持十进制字符串 |
| `valve_bank_title` | string | 否 | 阀门组名称 |
| `duration_minutes` | positive integer | 是 | 推荐或用户调整后的灌溉分钟数 |
| `selected` | boolean | 是 | 是否执行该阀门组 |

以下字段不能出现在可见 Syntax 或用户提交中：

- `cid`
- `plot_id`
- `plot_device_ids`
- `pending_irrigation_draft`
- `pending_execution_draft`
- `sensor_analysis`
- `run_status`
- token 或其他系统参数

## 4. 前端标准化数据结构

前端解析 Syntax 后，标准化为独立的 `form-panel` 联合类型，不复用农资表单的 `goodsList`：

```ts
export interface IrrigationValveBankFormItem {
  valve_bank_id: string
  valve_bank_title: string
  duration_minutes: number
  selected: boolean
}

export interface IrrigationValveDurationFormBlock {
  kind: 'form-panel'
  tag: 'irrigation_valve_duration_confirm'
  formType: 'irrigation-valve-duration'
  title?: string
  autoOpen?: boolean
  loading?: boolean
  plot_name: string
  average_soil_moisture: number
  reason: string
  valveBanks: IrrigationValveBankFormItem[]
}
```

`valve_bank_id` 可能来自 int64，必须在 Syntax 解析、Vue 状态、历史消息和提交消息中始终保留为字符串，禁止调用 `Number()`。

## 5. LLM 流解析与内部事件

外部 Agent 只输出 Syntax。前端的 `structured-message.ts` 在接收文本流时识别：

```text
form irrigation-valve-duration
```

解析完成后，可在前端内部归一化成以下流事件：

```text
data: {"op":"block-start","blockIndex":2,"kind":"form-panel","tag":"irrigation_valve_duration_confirm","title":"灌溉时长确认","formType":"irrigation-valve-duration","autoOpen":false}
data: {"op":"form-panel-payload","blockIndex":2,"formType":"irrigation-valve-duration","plot_name":"东区3号地块","average_soil_moisture":25,"reason":"玉米拔节期地块偏干，未来三天无明显降雨","valveBanks":[{"valve_bank_id":"31","valve_bank_title":"东区滴灌阀组A","duration_minutes":20,"selected":true}]}
data: {"op":"block-end","blockIndex":2}
```

建议把 `form-panel-payload` 定义为可判别联合类型：

```ts
type FormPanelPayloadChunk =
  | {
      op: 'form-panel-payload'
      blockIndex: number
      formType: 'agri-material-usage'
      goodsList: AgriMaterialUsageGoods[]
    }
  | {
      op: 'form-panel-payload'
      blockIndex: number
      formType: 'irrigation-valve-duration'
      plot_name: string
      average_soil_moisture: number
      reason: string
      valveBanks: IrrigationValveBankFormItem[]
    }
```

不要把两个表单统一成没有类型约束的 `unknown[]`。

## 6. 阀门组卡片与编辑面板

### 6.1 消息内摘要卡片

消息内卡片展示：

- 地块名称
- 平均土壤湿度
- 灌溉判断原因
- 阀门组名称和ID
- 当前选择状态
- 每个阀门组的推荐灌溉时长

操作按钮：

- `调整灌溉时长`：打开完整编辑面板。
- `按推荐灌溉`：不修改数据，使用推荐值走同一个首次提交流程。

### 6.2 编辑面板

建议新增独立组件：

```text
IrrigationValveDurationFormPanel.vue
```

只允许修改：

- `selected`
- `duration_minutes`

不允许修改：

- `valve_bank_id`
- `valve_bank_title`
- 地块、湿度和灌溉原因

取消或关闭面板不得发送消息，也不得改变原始 Assistant 消息中的表单内容。

## 7. 首次提交协议

用户点击 `确认` 或 `按推荐灌溉` 后，前端构造以下消息：

```json
{
  "type": "form_submit",
  "formType": "irrigation-valve-duration",
  "tag": "irrigation_valve_duration_confirm",
  "sourceMessageId": "assistant-message-id",
  "valveBanks": [
    {
      "valve_bank_id": "31",
      "duration_minutes": 18,
      "selected": true
    },
    {
      "valve_bank_id": "32",
      "duration_minutes": 20,
      "selected": false
    }
  ]
}
```

提交内容只保留用户可以决定的字段，不提交阀门组名称、地块、湿度、原因、状态或后端草稿。

### 7.1 前端提交前校验

- `valveBanks` 必须包含原始候选阀门组的全部项目。
- 每个原始 `valve_bank_id` 必须且只能出现一次。
- 不允许新增、删除、遗漏或重复阀门组ID。
- 未选择的行不能删除，必须提交 `selected: false`。
- `selected` 必须是 JSON boolean。
- 每行 `duration_minutes` 都必须是正整数，包括 `selected: false` 的行。
- 至少保留一个 `selected: true` 的阀门组。
- `valve_bank_id` 必须是规范的正十进制字符串。

### 7.2 发送方式

沿用现有农资表单的对话提交机制，不新增前端直连阀门的 REST 请求：

```ts
const payload = {
  type: 'form_submit',
  formType: 'irrigation-valve-duration',
  tag: 'irrigation_valve_duration_confirm',
  sourceMessageId,
  valveBanks: editedValveBanks.map(item => ({
    valve_bank_id: item.valve_bank_id,
    duration_minutes: item.duration_minutes,
    selected: item.selected,
  })),
}

const selectedCount = payload.valveBanks.filter(item => item.selected).length
const userText = [
  `已提交灌溉方案，共选择 ${selectedCount} 个阀门组。`,
  '',
  '```json',
  JSON.stringify(payload, null, 2),
  '```',
].join('\n')

inputBarRef.value?.submitWithText(userText)
```

这条消息会作为正常的用户消息进入下一轮 LLM 流。`sourceMessageId` 用于后端恢复对应的可信 `pending_irrigation_draft`。

## 8. 二次确认与设备执行

后端收到首次提交后：

1. 校验三项判别字段和完整阀门组集合。
2. 从可信会话状态或 `sourceMessageId` 恢复 `pending_irrigation_draft`。
3. 调用 `prepare-execution`。
4. 保存 `pending_execution_draft` 和 `draft_fingerprint`。
5. 返回包含地块、平均湿度、灌溉原因、阀门组和最终时长的确认文案。

此时不得调用 `start_valve_bank`。

用户必须在后续轮次明确回复，例如：

```text
确认执行上述灌溉方案
```

前端可以使用普通输入框，也可以在确认文案下提供按钮。按钮的行为只能是通过 `submitWithText` 发送一条新的用户确认消息，不能直接调用设备接口，也不能由前端重新提交或修改执行草稿。

后端收到后续确认后，必须使用：

```text
confirmation_source: user_confirmed_irrigation_execution_draft
```

并校验匹配的 `draft_fingerprint`，之后才允许 `build-execution` 生成 `start_valve_bank_args` 并依次执行阀门组。

## 9. 实时流与历史消息一致性

灌溉表单必须同时支持：

- 当前对话实时流解析。
- 消息结束后的最终内容解析。
- 刷新页面后的历史消息恢复。
- 已提交状态恢复，避免同一表单被重复提交。

如果只修改实时流消费逻辑，刷新页面后表单会退化成原始文本或丢失，因此 `structured-message.ts` 与 `history.ts` 必须使用同一套表单识别和字段校验规则。

## 10. 前端改动位置

目标前端仓库：`E:\SFPRO\MANAGE\tgFrontendPackage\packages\plant-agent`

| 文件 | 改动 |
| --- | --- |
| `src/types/conversation.ts` | 增加 `IrrigationValveDurationFormBlock` 和 `IrrigationValveBankFormItem` |
| `src/types/stream.ts` | 把 `form-panel-payload` 扩展为按 `formType` 判别的联合类型 |
| `src/utils/structured-message.ts` | 增加 `form irrigation-valve-duration` 的分段、流式和最终解析 |
| `src/apis/llm.ts` | 接收包含 `valveBanks` 的 `form-panel-payload` |
| `src/hooks/useStreamConsumer.ts` | 按 `formType` 创建表单 block，移除所有表单都强制转成农资表单的逻辑 |
| `src/store/history.ts` | 增加灌溉表单校验、升级和历史 SSE 恢复 |
| `src/components/conversation/FormPanelTriggerBlock.vue` | 按 `formType` 分发农资表单和灌溉表单摘要 |
| `src/components/conversation/IrrigationValveDurationFormPanel.vue` | 新增阀门组选择和时长编辑面板 |
| `src/components/conversation/ConversationView.vue` | 增加灌溉表单打开、校验和首次提交逻辑 |
| `src/components/conversation/MessageItem.vue` | 识别灌溉 `form_submit`，恢复已提交/禁用状态 |

## 11. 验收标准

- LLM 流中的灌溉 Syntax 不会作为原始文本展示。
- 流式生成过程中不会提前渲染残缺的阀门组表单。
- 表单完成后能展示地块、平均湿度、原因和全部阀门组。
- 用户只能修改选择状态和正整数灌溉时长。
- `valve_bank_id` 在所有前端链路中保持字符串。
- `按推荐灌溉` 和编辑后确认使用完全相同的首次提交协议。
- 未选择的阀门组以 `selected: false` 提交，不会从数组删除。
- 首次提交后只展示后端二次确认内容，不会打开阀门。
- 只有用户在下一轮明确确认，后端才调用 `start_valve_bank`。
- 刷新页面后历史表单仍能正常渲染，且已提交表单不会重复提交。
- 重复ID、未知ID、遗漏行、非整数时长、无选中项都会在提交前被拒绝。

