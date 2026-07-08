# Agri Material Usage Syntax Contract

Read this reference before returning recommended materials or handling a submitted material confirmation.

Prefer `scripts/agri_material_payload.py build-panel` to create the frontend-visible Syntax from `get_agri_input_list` rows. Hand-build only when script execution is unavailable. Keep the script-produced `pending_draft` internally; do not include it in the frontend-visible Syntax.

## Assistant Syntax

Return only `form agri-material-usage` Syntax when the user has ordered a farming operation and material confirmation is required.

```text
form agri-material-usage
title 补全信息
autoOpen false
data
  - goods_name 氮磷钾复合肥
    stock_goods_id 7
    is_formula 0
    num 24
    price 3
    unit kg
    dosage 12000
    stock_record_id 7
```

Rules:

- The first line must be `form agri-material-usage`.
- Do not return `schemaVersion`, `blocks`, `kind`, `form-panel`, JSON wrappers, SSE JSON events, or Markdown explanation around the Syntax.
- `title` defaults to `补全信息`.
- `autoOpen` defaults to `false`; set it to `true` only when the panel should open immediately.
- `data` must be present. When MCP returns no valid material candidates, return `data` with no `-` items.
- Each material item starts with `  - goods_name ...`; following fields use four spaces.
- Include only candidates matched to the farming operation type. Do not pass through every inventory row returned by `get_agri_input_list`.
- Do not include plot, address, operation, task, `pending_draft`, `record_draft`, original inventory rows, token, or system parameters in the Syntax.

## Field Lines

Each item should include these fields when available:

```text
  - goods_name 高钾肥
    stock_goods_id 5
    is_formula 0
    num 2.65
    price 12.8
    unit kg
    dosage 1000
    stock_record_id 29
```

Validation:

- `goods_name` must be non-empty.
- `stock_goods_id` must be greater than `0`.
- `num` must be greater than or equal to `0`.
- `price` must be greater than or equal to `0`.
- Default `is_formula` to `0`.
- Default `unit` to `""`; render empty string as `unit ""` if the field is emitted.
- Use `num > 0` when MCP, a knowledge-base/technical-standard source, explicit user conditions, or model agronomic experience support a per-mu recommendation and area is known. Otherwise use `0`.
- `dosage` is computed as `num / area * 1000`; do not copy package specification, stock quantity, inventory balance, or product-name numbers into `dosage`.
- Do not set `num: 0` merely because the user did not type a value; first check whether the recommendation itself has a supported per-mu rate and whether area is known.

## User Submit Message

The frontend confirms by sending a structured user message containing:

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

The submitted `goodsList` is the user's final material decision. It carries total `num`, not per-mu `mu_usage`. It does not include plot, address, operation, task, original inventory rows, or old farming-form fields.

Before creating the record, validate submitted items against the original `get_agri_input_list` rows, then build the compact submit payload as described in `goodslist-submit.md`.
