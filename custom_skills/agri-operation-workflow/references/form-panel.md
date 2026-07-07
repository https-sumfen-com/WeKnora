# Agri Material Form Panel Contract

Read this reference before returning the material confirmation panel or handling a submitted panel.

Prefer `scripts/agri_material_payload.py build-panel` to create this block from `get_agri_input_list` rows. Hand-build only when script execution is unavailable. Keep the script-produced `pending_draft` internally; do not include it in the frontend block.

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
- For material-related recommendations, include a recommended total `num` when there is MCP, knowledge-base, technical-standard, user-condition, or model agronomic basis for a per-mu rate and known area.
- Do not include plot, address, operation, task, or old farming-form fields in this block.
- Do not include `pending_draft`, `record_draft`, original inventory rows, token, or system parameters in this block. Those are internal state for `build-submit`.

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

`schemaVersion` is only the frontend structured-message marker for this farming-operation workflow.

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
  num: number
  price: number
  unit?: string
  dosage?: number
}
```

Validation:

- `goods_name` must be non-empty.
- `stock_goods_id` must be greater than `0`.
- `num` must be greater than or equal to `0`.
- `price` must be greater than or equal to `0`.
- Default `is_formula` to `0`.
- Default `unit` to `""`.
- Use `num > 0` when MCP, a knowledge-base/technical-standard source, explicit user conditions, or model agronomic experience support a per-mu recommendation and area is known. Otherwise use `0`.
- `dosage` is computed as `num / area * 1000`; do not copy package specification, stock quantity, inventory balance, or product-name numbers into `dosage`.
- Do not set `num: 0` merely because the user did not type a value; first check whether the recommendation itself has a supported per-mu rate and whether area is known.

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

The submitted `goodsList` is the user's final material decision. It carries total `num`, not per-mu `mu_usage`. It does not include plot, address, operation, task, or old farming-form fields.

It does not include original inventory rows. Before creating the record, validate submitted items against the original `get_agri_input_list` rows, then build the compact submit payload as described in `goodslist-submit.md`.
