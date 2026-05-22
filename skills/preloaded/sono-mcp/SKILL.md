---
name: call-mcp-tools
description: "Use when the server-side Agent must precisely choose and call currently registered service-support MCP tools: get_plot_info, get_weather, get_summary_base, or get_plot_device_info."
---

# 服务端 Agent 精确调用本服务 MCP 工具

本 skill 用于指导服务端 Agent 根据用户意图，准确选择并调用 `service-support` 当前已注册的 MCP 工具。

目标：少调用、准调用、不猜参数、不把空结果当错误。

## 当前可调用工具

当前 MCP 服务注册以下工具：

- `get_plot_info`
- `get_weather`
- `get_summary_base`
- `get_plot_device_info`

不要调用以下工具：

- `get_data_list`
- `get_data_detail`

这两个 data 工具的逻辑代码仍存在，但在 `internal/server/mcp/server.go` 中注册被注释，当前不会出现在 MCP 工具列表中。除非服务端重新启用注册并重新核对实现，否则 Agent 不应选择或调用它们。

## 核心原则

- 只调用当前已注册工具：`get_plot_info`、`get_weather`、`get_summary_base`、`get_plot_device_info`。
- 不要直接拼接内部 HTTP、JSON-RPC、gRPC 请求，除非用户明确要求调试底层接口。
- 不要猜测 `plot_id`、`device_id`、`dept_id`、`base_id`、企业身份、用户身份或 token。
- 能从服务端上下文、会话上下文、网关上下文获得的参数，不要要求用户重复提供。
- 用户意图不清晰或缺少关键业务对象时，先追问，不要盲目调用工具。
- MCP 返回 `isError=false` 且文本为空时，表示默认数据或空结果，不是异常。
- 有数据时基于返回 JSON 的 `payload` 简洁回答；不要原样倾倒大段 JSON。
- 真实错误时避免暴露 token、内部 URL、内部配置等敏感信息。

## 数值参数规则

所有工具的数字字段使用 `FlexibleInt64` 解码：

- 可传 JSON 数字：`123`
- 可传整数字符串：`"123"`
- `null`、空字符串或缺省会按 `0` 或“不存在”处理
- 非整数字符串会导致参数错误：`必须是整数`

不要把自然语言中的序号、排名、页码臆断为结构化 ID。

## 参数来源优先级

参数按以下优先级提取：

1. 服务端 Agent 上下文、会话上下文、网关上下文。
2. 当前业务页面或上层路由传入的结构化参数。
3. 用户本轮输入中的显式参数。
4. 历史对话中仍然明确有效的参数。

常见上下文字段示例：

```json
{
  "cid": 2007,
  "token": "optional-token",
  "user": {
    "id": 158,
    "dept_id": 1549,
    "entity_id": 1,
    "entity_info_id": 99
  }
}
```

字段映射：

- 四个已注册工具都使用 `cid` 作为企业标识。
- `get_summary_base` 使用 `dept_id` 表示部门 ID，使用 `base_id` 表示基地 ID。
- `get_plot_device_info` 使用 `device_id` 表示设备 ID；访问上游时映射为 `id`，会把 `entity_info_id` 映射为上游 `enterpriseId`，并固定传 `getDeviceData=1` 获取设备数据。
- `token`、`entity_id`、`entity_info_id` 可传入工具参数；当前 land JSON-RPC 请求体实际使用查询所需的 `cid`、`plot_id`、`keyword`、`dept_id`、`base_id`、`id`、`entity_info_id`。
- LLM 系统参数中 `dept_id=-1` 表示没有可用部门；`dept_id=0` 表示全部门权限。

## 工具选择规则

### 选择 `get_plot_info`

当用户要查询地块、田块、农田、种植地块等基础信息时调用。

典型意图：

- 查询某个地块信息
- 查看地块面积、名称、位置、作物等基础资料
- “这个地块是什么情况”
- “帮我看一下 plot_id 为 X 的地块”
- “查询东区地块信息”

调用规则：

- 已有 `plot_id` 时优先传 `plot_id`。
- 没有 `plot_id`，但用户给出明确地块名称、区域名称、田块名称时，传 `keyword`。
- 同时有 `plot_id` 和明确名称时可以都传，`plot_id` 用于精确匹配，`keyword` 作为辅助条件。
- 用户问天气时不要先调用 `get_plot_info`，应直接选择 `get_weather`。
- 用户问设备详情时不要先调用 `get_plot_info`，应直接选择 `get_plot_device_info`。
- 如果无法确定地块对象，先追问地块名称或地块 ID。

### 选择 `get_weather`

当用户要查询天气、气象、降雨、温度、湿度、风力、预报等信息时调用。

典型意图：

- 查询某个地块天气
- 查看今天/未来天气
- 是否下雨、温度多少、湿度多少
- “这个地块适不适合打药/浇水”且明确需要天气信息
- “查询东区地块天气”

调用规则：

- 已有 `plot_id` 时优先传 `plot_id`。
- 没有 `plot_id`，但用户给出明确地块名称、区域名称、田块名称时，传 `keyword`。
- 不要把天气词、时间词、操作词或泛化描述当作 `keyword`，例如“今天”“明天”“下雨”“适合打药”不是地块关键词。
- 如果已有可用 `plot_id` 或 `keyword`，直接调用 `get_weather`，不要先查地块详情。
- 如果无法确定地块对象，先追问地块名称或地块 ID。

### 选择 `get_summary_base`

当用户要查询基地汇总、基地统计、基地看板、基地概览、部门下基地汇总列表时调用。

典型意图：

- 查询基地汇总列表
- 查看某个部门下的基地汇总
- 查看某个基地所在部门的汇总数据
- “基地总体情况/基地看板数据/基地统计”

调用规则：

- 有当前用户部门时可传 `dept_id`。
- 用户指定基地或上下文有基地 ID 时可传 `base_id`。
- `dept_id=0` 表示全部门权限；没有 `base_id` 时可直接传给工具。
- `dept_id=-1` 表示没有可用部门；除非已有 `base_id` 或业务上下文明确允许空结果，否则先追问部门或基地。
- 如果没有可用 `dept_id` 或 `base_id`，工具会返回空成功；Agent 应根据业务场景决定是直接调用还是先追问。

### 选择 `get_plot_device_info`

当用户要根据设备 ID 查询地块设备信息、设备详情、设备数据、设备所属地块或设备分组信息时调用。

典型意图：

- 查询 device_id 为 X 的设备信息
- 查看某个设备详情/设备数据
- “这个设备是什么情况”且上下文已有 `device_id`
- 查看设备关联的地块、设备状态、设备分组等信息

调用规则：

- 必须有明确 `device_id`，来自上下文或用户输入。
- 不要把地块 ID、基地 ID、列表序号、页码误当作 `device_id`。
- 没有 `device_id` 时先追问设备 ID，不要用地块工具替代。
- 查询上游时需要 `cid > 0`；缺少企业 ID 时先从上下文补齐，补不齐再追问或说明无法查询。

## 工具参数格式

### `get_plot_info`

```json
{
  "plot_id": 123,
  "keyword": "东区地块",
  "cid": 2007,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

行为：

- `plot_id > 0` 或 `keyword` 非空时，会尝试查询上游。
- 查询上游时必须有 `cid > 0`；否则返回 `INVALID_REQUEST`，消息为“企业 ID 不能为空”。
- `plot_id <= 0` 且 `keyword` 为空时返回默认空成功：`action=plot_info`、`source=default`、`payload={}`、文本为空、`isError=false`。
- 上游 JSON-RPC 方法为 `/agri/getPlotInfo`，请求参数映射为 `companyId=cid`、`id=plot_id`、`keyword=trim(keyword)`。

### `get_weather`

```json
{
  "plot_id": 123,
  "keyword": "东区地块",
  "cid": 2007,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

行为：

- `plot_id > 0` 或 `keyword` 非空时，会尝试查询上游。
- 查询上游时必须有 `cid > 0`；否则返回 `INVALID_REQUEST`，消息为“企业 ID 不能为空”。
- `plot_id <= 0` 且 `keyword` 为空时返回默认空成功：`action=weather`、`source=default`、`payload={}`、文本为空、`isError=false`。
- 上游 JSON-RPC 方法为 `/agri/getPlotWeather`，请求参数映射为 `companyId=cid`、`id=plot_id`、`keyword=trim(keyword)`。

### `get_summary_base`

推荐使用 snake_case 参数：

```json
{
  "cid": 2007,
  "dept_id": 1549,
  "base_id": 88,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

兼容字段：

- `deptId` 可作为 `dept_id` 的兼容别名。
- `baseId` 可作为 `base_id` 的兼容别名。
- 如果 snake_case 和 camelCase 同时存在，优先使用 snake_case。
- 不要使用 `department_id` 或 `departmentId`。

行为：

- `cid <= 0` 时返回默认空成功：`action=summary_base`、`source=default`、`payload=[]`、文本为空、`isError=false`。
- `dept_id` 缺省、`null`、空字符串或小于 `0` 时视为未提供。
- `dept_id=0` 是有效过滤条件，表示全部门权限。
- `base_id` 缺省、`null`、空字符串或小于等于 `0` 时视为未提供。
- 同时提供 `base_id > 0` 和 `dept_id=0` 时，服务会忽略 `dept_id`，只按 `base_id` 查询。
- `cid > 0` 但没有有效 `dept_id` 且没有有效 `base_id` 时返回默认空成功。
- 有有效过滤条件时会查询上游；上游 JSON-RPC 方法为 `/agri/getSummaryBase`。
- 上游参数是位置参数：`[cid, {"dept_id": ..., "base_id": ...}]`，过滤对象只包含实际生效字段。

### `get_plot_device_info`

```json
{
  "device_id": 456,
  "cid": 2007,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 99
}
```

行为：

- `device_id > 0` 时，会尝试查询上游。
- 查询上游时必须有 `cid > 0`；否则返回 `INVALID_REQUEST`，消息为“企业 ID 不能为空”。
- `device_id <= 0` 时返回默认空成功：`action=plot_device_info`、`source=default`、`payload={}`、文本为空、`isError=false`。
- 上游 JSON-RPC 方法为 `/agri/getPlotDeviceInfo`。
- 上游请求参数映射为 `companyId=cid`、`id=device_id`、`enterpriseId=entity_info_id`、`getDeviceData=1`。
- `entity_info_id <= 0` 时不会发送 `enterpriseId`，但仍会按 `device_id` 查询。

## 不要调用工具的情况

以下情况不要调用 MCP 工具：

- 用户只是闲聊、打招呼、表达感谢。
- 用户询问工具能力、接口说明、参数格式，只需要解释。
- 用户请求总结、改写、翻译、推理等不依赖业务数据的任务。
- 缺少关键业务对象，且无法从服务端上下文补齐。
- 多个工具都可能匹配，但无法判断用户真正想查什么。
- 用户要查标准业务数据列表或详情；当前 `get_data_list`、`get_data_detail` 未注册，不能调用。

处理方式：简短追问需要的关键参数，或说明当前工具不支持该类查询。

## 调用顺序策略

### 单工具优先

能用一个工具回答时，只调用一个工具。

示例：

- “查一下 123 地块天气” → `get_weather`
- “查一下 123 地块信息” → `get_plot_info`
- “查询东区地块信息” → `get_plot_info`，参数 `keyword="东区地块"`
- “查询东区地块天气” → `get_weather`，参数 `keyword="东区地块"`
- “查询基地汇总” → `get_summary_base`
- “查询 device_id 456 的设备信息” → `get_plot_device_info`

### 不要默认联动

- 查地块信息时，不要自动查天气或设备。
- 查天气时，不要自动查地块信息。
- 查设备信息时，不要自动查地块信息或天气。
- 查基地汇总时，不要自动查地块信息、天气或设备。
- 当前没有 data 工具可调用时，不要尝试用地块、天气、基地汇总、设备工具替代业务数据列表/详情查询。

## 返回结果处理

处理 MCP 工具结果时按以下顺序判断：

1. `isError=true`：真实工具错误。可以说明服务暂不可用、参数不足或上游异常；不要暴露敏感内部信息。
2. `isError=false` 且文本为空：默认数据或空结果。回答“未查询到相关数据”或“当前参数未查询到数据”。
3. `isError=false` 且文本非空：文本为 JSON，解析后优先基于 `payload` 回答用户问题。

不要把以下情况当作异常：

- `get_plot_info` 空文本。
- `get_weather` 空文本。
- `get_summary_base` 空文本或空列表。
- `get_plot_device_info` 空文本。
- `source=default` 且 `payload` 为空对象或空数组。

## 输出给用户的方式

- 有数据：简洁总结关键字段，不要原样倾倒大段 JSON。
- 空结果：说明未查询到数据，不要展示内部错误。
- 参数不足：只追问最关键的缺失字段。
- 真实错误：说明服务暂不可用或调用失败，避免暴露敏感配置、token、内部 URL。

推荐话术：

- 空结果：`未查询到相关数据。`
- 参数不足：`当前信息不足以确定要查询的对象，请补充地块名称、地块 ID、设备 ID、部门 ID 或基地 ID。`
- 当前工具不支持：`当前 MCP 服务未注册该类查询工具，暂时无法直接查询。`
- 真实错误：`工具调用失败，可能是配置或上游服务异常，请稍后重试。`
