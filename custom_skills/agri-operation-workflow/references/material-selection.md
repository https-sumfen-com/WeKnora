# Operation-Aware Material Selection

Read this reference after `get_agri_input_list` returns and before building the `form-panel.goodsList`.

## Goal

`get_agri_input_list` returns an inventory pool. The panel must show only materials that fit the selected farming operation and current MCP evidence. Do not return the full inventory list as recommended materials.

## Selection Inputs

Use only:

- confirmed operation name and `matter_id` from `get_farming_operation_list`
- MCP evidence that caused the recommendation, such as plot status, weather, warning type, crop stage, or disease/weed/pest risk
- inventory row fields from `get_agri_input_list`, especially `name`, `stock_goods.name`, `stock_goods.type`, `stock_goods.unit`, `price`, and IDs
- explicit user choice

Do not use model knowledge to invent product names, IDs, units, prices, or stock. Model agronomic experience may be used only to recommend the internal per-mu rate that is converted into frontend `num` and `dosage`.

## Filtering Rules

First classify the operation by its real name/category. Then keep only inventory rows that match the operation:

| Operation intent | Candidate inventory match |
| --- | --- |
| 施肥, 追肥, 基肥, 补肥, 营养调控 | `stock_goods.type` or name indicates fertilizer, organic fertilizer, compound fertilizer, nitrogen, phosphorus, potassium, or micronutrient |
| 用药, 植保, 病害防治, 虫害防治 | `stock_goods.type` or name indicates pesticide, fungicide, insecticide, bactericide, or plant protection material |
| 除草, 草害防控 | `stock_goods.type` or name indicates herbicide or weed-control material |
| 播种, 补种 | `stock_goods.type` or name indicates seed or seed-treatment material |
| 灌溉, 排水, 整地, 中耕, 巡田, 采收, 机械作业, 观察复核 | Usually no agricultural material. Return `goodsList: []` unless MCP/user context explicitly names a material |

If the operation name is ambiguous, do not guess. Return `goodsList: []` and let the user add materials in the frontend panel, or ask the user which material category should be used.

## Ranking

When several rows match:

1. Prefer rows whose `stock_goods.type` matches the operation category.
2. Prefer rows whose `stock_goods.name` or `name` matches the MCP evidence or user wording.
3. Prefer rows with nonzero inventory `num` when the field is present.
4. Keep the list short. Return the most relevant candidates, not the full category, unless the user explicitly asks to choose from all matching materials.

## Usage Rules

- For material-related operation recommendations, actively resolve an internal recommended per-mu rate; see `usage-recommendation.md`.
- `build-panel` converts the per-mu rate to frontend total `num` using `record_draft.area`, then computes `dosage = num / area * 1000`.
- If no reasonable usage recommendation or area exists after checking those sources, use `num: 0` and `dosage: 0`.
- Never treat stock balance `num`, package specification, `dosage`, price, material concentration, or product-name numbers as the per-mu rate.
- Keep `is_formula: 0`; `get_formula_list` is not part of this workflow.

## Empty Result

Return `goodsList: []` when:

- the operation normally does not use materials,
- the inventory pool has no confident match,
- only unrelated materials are available,
- required IDs or material names are missing.

An empty list is safer than showing unrelated or all inventory items. The frontend supports manual material addition.
