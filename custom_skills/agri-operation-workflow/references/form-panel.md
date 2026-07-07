# Agri Material Form Panel Contract

Read this reference before returning the material confirmation panel or handling a submitted panel.

## Assistant Block

Return a `form-panel` block when the user has ordered a farming operation and material confirmation is required.

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

Rules:

- `kind` must be `form-panel`.
- `tag` must be `agri_material_usage_confirm`.
- `formType` must be `agri-material-usage`.
- `goodsList` must be a complete array, not a streamed string fragment.
- Use `goodsList: []` when MCP returns no valid material candidates.
- Do not pass through every inventory row returned by `get_agri_input_list`; include only candidates matched to the farming operation type.
- Do not include plot, address, operation, task, or old farming-form fields in this block.

## Non-Streaming Payload

When returning structured JSON in `answer`, use the frontend parser schema marker:

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "blocks": [
    {
      "kind": "text",
      "markdown": "已准备农事记录草稿，请确认本次农资和亩用量。"
    },
    {
      "kind": "form-panel",
      "tag": "agri_material_usage_confirm",
      "title": "补全信息",
      "formType": "agri-material-usage",
      "autoOpen": true,
      "goodsList": []
    }
  ]
}
```

`schemaVersion` is only the frontend structured-message marker. It does not mean this workflow uses `plant-agent-response-contract`.

## Streaming Events

When using SSE chunks, follow the existing block pattern:

```text
data: {"op":"block-start","blockIndex":2,"kind":"form-panel","tag":"agri_material_usage_confirm","title":"补全信息","formType":"agri-material-usage","autoOpen":true}
data: {"op":"form-panel-payload","blockIndex":2,"goodsList":[]}
data: {"op":"block-end","blockIndex":2}
```

Use one `form-panel-payload` per panel and send the full `goodsList` array in that event.

## goodsList Fields

Each item should match:

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

Validation:

- `goods_name` must be non-empty.
- `stock_goods_id` must be greater than `0`.
- `mu_usage` must be greater than or equal to `0`.
- `price` must be greater than or equal to `0`.
- Default `is_formula` to `0`.
- Default `unit` to `""`.
- Only use `mu_usage > 0` when MCP or the user supplied that value. Otherwise use `0`.
- Do not copy `dosage`, package specification, stock quantity, or inventory balance into `mu_usage`.

## User Submit Message

The frontend confirms by sending JSON like:

```json
{
  "type": "form_submit",
  "formType": "agri-material-usage",
  "tag": "agri_material_usage_confirm",
  "sourceMessageId": "assistant-message-id",
  "goodsList": []
}
```

Handle only messages matching all three fields:

- `type === "form_submit"`
- `formType === "agri-material-usage"`
- `tag === "agri_material_usage_confirm"`

The submitted `goodsList` is the user's final material decision. It does not include plot, address, operation, task, or old farming-form fields.
