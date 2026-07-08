# 农资用量确认面板前后端设计文档

> 历史方案文档。新的推荐农资输出必须使用 `docs/agri-material-usage-syntax-contract.md` 中的 `form agri-material-usage` Syntax，不再使用 `schemaVersion` JSON 或 `form-panel` JSON 作为主链路。

## 目标

在 `ConversationView` 中支持由 AI 消息触发的农资用量确认面板。后端通过固定消息块告诉前端“需要用户确认农资”，前端自动弹出面板，默认带入大模型推荐的农资；用户可以修改亩用量、新增农资、删除农资，确认后仅把最终农资列表回传给 AI。

## 非目标

- 不复用旧农事表单的完整提交结构。
- 不在该消息块里传地块、地址、农事事项、任务等旧表单字段。
- 不由前端解析自然语言文案来判断是否弹窗。

## 消息块协议

AI 返回 `form-panel` block。触发标签固定为 `agri_material_usage_confirm`。

```json
{
  "kind": "form-panel",
  "tag": "agri_material_usage_confirm",
  "title": "补全信息",
  "formType": "agri-material-usage",
  "autoOpen": false,
  "goodsList": [
    {
      "goods_name": "高钾肥",
      "stock_goods_id": 5,
      "stock_record_id": 5,
      "is_formula": 0,
      "mu_usage": 1,
      "price": 12.8,
      "unit": "",
      "dosage": 1000
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `kind` | string | 是 | 固定 `form-panel` |
| `tag` | string | 是 | 固定 `agri_material_usage_confirm` |
| `title` | string | 否 | 面板标题，默认 `补全信息` |
| `formType` | string | 是 | 固定 `agri-material-usage` |
| `autoOpen` | boolean | 否 | 是否自动弹出，默认 `false` |
| `goodsList` | array | 是 | AI 推荐好的农资列表 |

`goodsList[]` 字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `goods_name` | string | 是 | 农资名称 |
| `stock_goods_id` | number | 是 | 农资商品 ID |
| `stock_record_id` | number | 否 | 库存记录 ID，对应 `/stock/list` 返回的 `id` |
| `is_formula` | number | 否 | 是否配方农资，默认 `0` |
| `mu_usage` | number | 是 | 亩用量，用户可编辑 |
| `price` | number | 是 | 单价 |
| `unit` | string | 否 | 单位，默认空字符串 |
| `dosage` | number | 否 | 规格/剂量字段，后端有值则传 |

前端展示可计算字段：

- `plot_cost_price = mu_usage * price`
- `total_usage / num / total_price` 暂不强依赖地块面积，当前确认回传只关注 `goodsList` 本身。

## 后端流式返回协议

参考现有 `report` block。推荐返回：

```txt
data: {"op":"block-start","blockIndex":2,"kind":"form-panel","tag":"agri_material_usage_confirm","title":"补全信息","formType":"agri-material-usage","autoOpen":false}
data: {"op":"form-panel-payload","blockIndex":2,"goodsList":[{"goods_name":"高钾肥","stock_goods_id":5,"stock_record_id":5,"is_formula":0,"mu_usage":1,"price":12.8,"unit":"","dosage":1000}]}
data: {"op":"block-end","blockIndex":2}
```

规则：

- `block-start.kind` 固定 `form-panel`。
- `block-start.tag` 固定 `agri_material_usage_confirm`。
- `form-panel-payload.goodsList` 必须是完整数组，不做字符流拼接。
- 同一个 `blockIndex` 只能对应一个 `form-panel`。
- 如果后端不能给出推荐农资，可以传空数组，前端会显示空态并允许用户手动新增。

## 非流式结构化返回协议

如果后端通过 `answer` 文本返回结构化 JSON，格式如下：

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": [
    {
      "kind": "text",
      "markdown": "我先帮你推荐了农资，请确认用量。"
    },
    {
      "kind": "form-panel",
      "tag": "agri_material_usage_confirm",
      "title": "补全信息",
      "formType": "agri-material-usage",
      "autoOpen": false,
      "goodsList": []
    }
  ]
}
```

## 前端行为

### 自动弹出

`ConversationView` 监听最新 assistant 消息：

- 只处理 `message.status === 'done'`。
- 找到 `kind === 'form-panel'`、`tag === 'agri_material_usage_confirm'` 的 block。
- `autoOpen === true` 时自动弹出；默认不自动弹出。
- 同一个 `message.id + blockIndex` 只自动弹一次。
- 历史消息加载时不自动弹，只在面板关闭后保留当前消息触发入口。

### 面板能力

- 默认展示 `goodsList` 卡片。
- `mu_usage` 可编辑。
- 用户可点击 `选择农资` 打开农资选择弹窗。
- 农资选择弹窗：
  - 父分类接口：`/api/agri/inventory/stock/category/list?p_id=0`
  - 子分类接口：`/api/agri/inventory/stock/category/list?p_id=<父分类ID>`
  - 农资列表接口：`/api/agri/inventory/stock/list?category=<子分类ID>&base_id=<lockedBaseInfo.id>&page=<page>&limit=20`
  - 表格字段：标题、价格、库存
  - 支持多选和分页
- 新增农资时从 `/stock/list` 行数据归一化成 `goodsList[]`。
- 删除农资只影响当前面板临时状态。

## 农资接口返回映射

`/api/agri/inventory/stock/list` 行数据映射：

```ts
{
  goods_name: row.name,
  stock_goods_id: row.stock_goods_id,
  stock_record_id: row.id,
  is_formula: row.stock_goods?.formula_id ? 1 : 0,
  mu_usage: 0,
  price: Number(row.price ?? row.stock_goods?.price ?? 0),
  unit: row.stock_goods?.unit || '',
  dosage: Number(row.stock_goods?.number21921 ?? 0)
}
```

## 用户确认回传

确认后前端向 AI 发送结构化文本消息。用户可见文本可以简短显示为“已确认农资用量，共 N 项”，同时消息正文包含结构化 JSON，便于后端解析：

```json
{
  "type": "form_submit",
  "formType": "agri-material-usage",
  "tag": "agri_material_usage_confirm",
  "goodsList": [
    {
      "goods_name": "高钾肥",
      "stock_goods_id": 5,
      "stock_record_id": 5,
      "is_formula": 0,
      "mu_usage": 1,
      "price": 12.8,
      "unit": "",
      "dosage": 1000
    }
  ]
}
```

后端只需要从用户消息中识别 `type=form_submit`、`formType=agri-material-usage`，读取 `goodsList` 继续处理。

## 前端改动范围

- 扩展 `ContentBlock`：新增 `form-panel`。
- 扩展 `StreamChunk`：新增 `form-panel-payload`，并让 `block-start` 支持 `tag/formType/autoOpen`。
- 扩展 `llm.ts asStreamChunk()`：识别 `form-panel-payload`。
- 扩展 `useStreamConsumer()`：创建和填充 `form-panel` block。
- 扩展 `structured-message.ts` 和历史消息解析：允许 `form-panel` block。
- 新增农资 API 封装。
- 新增 `AgriMaterialFormPanel` 组件。
- 在 `ConversationView` 中自动弹出并提交最终 `goodsList`。

## 验收点

- AI 返回 `form-panel` 后，最新消息完成时自动弹出补全面板。
- 推荐农资默认出现在卡片列表中。
- 用户可以修改 `mu_usage`、新增农资、删除农资。
- 确认后发送结构化 `form_submit` 消息。
- 取消或关闭不会提交。
- 历史消息加载不会反复自动弹窗。
