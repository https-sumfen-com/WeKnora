# Evidence-Backed Usage Recommendation

Read this reference when a recommended farming operation uses agricultural materials.

## Goal

The material confirmation panel should contain a recommended total material quantity `num` when a reasonable per-mu rate and `record_draft.area` are known. `dosage` is computed as `num / area * 1000`.

Use `num: 0` and `dosage: 0` only when no reliable per-mu rate can be found or area is unavailable.

## Evidence Priority

Use this order to derive the internal per-mu rate:

1. SONO-MCP returned recommendation fields or text that explicitly gives an area rate.
2. User-provided crop, stage, target, severity, soil, area, or material rate.
3. Knowledge-base or technical-standard content read for the crop/stage/problem/material category.
4. The model's own agronomic experience, when stronger sources do not provide a rate.
5. If none of the above supports a reasonable rate, use `num: 0` and let the user edit it.

Model experience is allowed only for the internal per-mu rate. It must not be used to invent material IDs, inventory, price, unit, area, or upstream business facts.

## Conversion

When `record_draft.area` is known:

```text
num    = per_mu_rate * area
dosage = num / area * 1000
```

When area is unknown, do not invent area and do not compute `dosage`; keep `num: 0` and `dosage: 0` until area is available or the frontend/user confirms total `num`.

## Required Behavior

- For 施肥/追肥/补肥, try to produce a per-mu fertilizer usage recommendation.
- For 用药/植保/病虫害防治/除草, try to produce a per-mu pesticide/herbicide usage recommendation when the material label or knowledge source provides an area rate.
- For operations that usually do not use materials, keep `goodsList: []` unless the user or MCP evidence names a material.
- If evidence or model agronomic experience gives a range, choose a conservative midpoint or context-appropriate value when it fits the current crop/stage/problem.

## What Not To Use As Rate Or Quantity

Never copy these into the internal per-mu rate, frontend `num`, or computed `dosage`:

- inventory balance `num`
- package specification
- product `number21921` style specification
- price
- material concentration
- product name numbers such as `50%`

## Submit Boundary

The final `add_farming_record.goodsList` does not include `mu_usage`. It includes compact frontend-confirmed fields only: `goods_name`, `stock_goods_id`, `is_formula`, `num`, `price`, `unit`, and computed `dosage`.
