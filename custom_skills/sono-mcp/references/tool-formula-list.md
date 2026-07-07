# get_formula_list 字段提取规则

配方列表用于给用户选择农资配方。配方本身不保存农事记录；用户选定配方后，才可把配方内 `goods` 明细作为 `add_farming_record.goodsList` 的来源。

## 返回结构

上游返回数组：

```json
[
  {
    "id": 1171,
    "name": "排风2",
    "goods": [
      {
        "id": 6335,
        "num": "3.0000",
        "stock_goods": {
          "id": 1,
          "name": "50%硫酸钾",
          "price": "3.73",
          "type": "化肥",
          "unit": "公斤"
        }
      }
    ]
  }
]
```

## 字段含义

| 字段 | 含义 | 使用规则 |
|---|---|---|
| `id` | 配方 ID | 展示为可选配方 ID |
| `name` | 配方名称 | 展示首选名称 |
| `goods[].id` | 配方明细 ID | 回填 `goodsList` 时保留 |
| `goods[].num` | 配方用量 | 可作为本次用量来源，单位取 `stock_goods.unit` |
| `goods[].stock_goods` | 农资商品档案 | 为空时不要补造农资名称、类型、价格、单位 |
| `goods[].stock_goods.id` | 农资商品 ID | 回填 `goodsList` 时保留 |
| `goods[].stock_goods.name` | 农资名称 | 展示农资明细首选名称 |
| `goods[].stock_goods.price` | 农资价格 | 有值才展示 |
| `goods[].stock_goods.type` | 农资类型 | 如"化肥" |
| `goods[].stock_goods.unit` | 单位 | 如"公斤" |

## 回答规则

- 用户选择配方时，列出配方名称、配方 ID，以及每个有 `stock_goods` 的农资名称、用量、单位、价格。
- `stock_goods=null` 的明细只展示明细 ID 和 `num`，并说明农资档案缺失；不要猜名称或单位。
- 用户问"有哪些配方"时，只列配方摘要，不自动保存农事记录。
- 用户明确选择某个配方用于新增农事记录时，才把该配方的 `goods` 明细带入 `add_farming_record.goodsList`。
- 空数组时说明"未查询到可用配方"。
