# 农资确认面板后端对接实施文档

## 目标

后端在 AI 判断需要用户确认农资时，返回固定 `form-panel` 消息块。前端识别后自动弹出补全面板，并在用户确认后把最终 `goodsList` 回传给后端继续处理。

## AI 返回消息块

固定使用：

```json
{
  "kind": "form-panel",
  "tag": "agri_material_usage_confirm",
  "title": "补全信息",
  "formType": "agri-material-usage",
  "autoOpen": true,
  "goodsList": []
}
```

## 流式 SSE 返回格式

推荐后端按现有 report block 模式返回：

```txt
data: {"op":"block-start","blockIndex":2,"kind":"form-panel","tag":"agri_material_usage_confirm","title":"补全信息","formType":"agri-material-usage","autoOpen":true}
data: {"op":"form-panel-payload","blockIndex":2,"goodsList":[{"goods_name":"高钾肥","stock_goods_id":5,"stock_record_id":5,"is_formula":0,"mu_usage":1,"price":12.8,"unit":"","dosage":1000}]}
data: {"op":"block-end","blockIndex":2}
```

规则：

- `kind` 固定 `form-panel`
- `tag` 固定 `agri_material_usage_confirm`
- `formType` 固定 `agri-material-usage`
- `goodsList` 必须一次性返回完整数组
- 没有推荐农资时传 `goodsList: []`
- `blockIndex` 和同条消息内其他 block 不冲突

## 非流式 JSON 返回格式

如果通过 `answer` 文本返回结构化 JSON：

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": [
    {
      "kind": "text",
      "markdown": "我先推荐了农资，请确认用量。"
    },
    {
      "kind": "form-panel",
      "tag": "agri_material_usage_confirm",
      "title": "补全信息",
      "formType": "agri-material-usage",
      "autoOpen": true,
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
  ]
}
```

## goodsList 字段

```ts
interface AgriMaterialUsageGoods {
  goods_name: string
  stock_goods_id: number
  stock_record_id?: number
  is_formula?: number
  mu_usage: number
  price: number
  unit?: string
  dosage?: number
}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `goods_name` | 是 | 农资名称 |
| `stock_goods_id` | 是 | 农资商品 ID |
| `stock_record_id` | 否 | 库存记录 ID，对应库存列表的 `id` |
| `is_formula` | 否 | 是否配方农资，默认 `0` |
| `mu_usage` | 是 | 亩用量，用户可修改 |
| `price` | 是 | 单价 |
| `unit` | 否 | 单位，默认空字符串 |
| `dosage` | 否 | 规格/剂量字段 |

## 用户确认后的回传

前端确认后会发送一条用户消息，文本内包含 JSON：

```json
{
  "type": "form_submit",
  "formType": "agri-material-usage",
  "tag": "agri_material_usage_confirm",
  "sourceMessageId": "assistant-message-id",
  "goodsList": [
    {
      "goods_name": "高钾肥",
      "stock_goods_id": 5,
      "stock_record_id": 5,
      "is_formula": 0,
      "mu_usage": 1.5,
      "price": 12.8,
      "unit": "",
      "dosage": 1000
    }
  ]
}
```

后端处理规则：

- 识别 `type === "form_submit"`
- 识别 `formType === "agri-material-usage"`
- 识别 `tag === "agri_material_usage_confirm"`
- 读取 `goodsList` 作为用户最终确认结果
- 不依赖旧农事表单里的地块、地址、事项字段

## 推荐后端校验

- `goodsList` 必须是数组
- `goods_name` 非空
- `stock_goods_id > 0`
- `mu_usage >= 0`
- `price >= 0`
- 缺失 `is_formula` 时按 `0` 处理
- 缺失 `unit` 时按空字符串处理

## 前端已支持

- 流式 `form-panel` block
- `form-panel-payload`
- 非流式 `schemaVersion` JSON
- 历史消息恢复
- 自动弹窗
- 用户新增、删除、修改用量
- 确认后结构化回传 `goodsList`
