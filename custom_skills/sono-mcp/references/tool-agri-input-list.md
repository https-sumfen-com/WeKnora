# get_agri_input_list 字段提取规则

农资列表用于给用户选择库存农资，通常服务于 `add_farming_record.goodsList`。只展示真实返回的库存、商品、单位和价格，不补造本次用量。

## 返回结构

上游返回数组：

```json
[
  {
    "id": 29,
    "name": "50%硫酸钾",
    "num": "10.00",
    "price": "3.73",
    "stock_goods": {
      "id": 1,
      "name": "50%硫酸钾",
      "price": "3.73",
      "type": "化肥",
      "unit": "公斤"
    }
  }
]
```

## 字段含义

| 字段 | 含义 | 使用规则 |
|---|---|---|
| `id` | 库存记录 ID | 展示为可选项 ID；回填时保留 |
| `name` | 库存记录名称 | 兜底名称；优先展示 `stock_goods.name` |
| `num` | 当前库存余量 | 只作库存展示，不是本次作业用量 |
| `price` | 库存价格/单价 | 有值才展示 |
| `stock_goods.id` | 农资商品 ID | 回填 `goodsList` 时保留 |
| `stock_goods.name` | 农资名称 | 展示首选名称 |
| `stock_goods.type` | 农资类型 | 如"化肥" |
| `stock_goods.unit` | 单位 | 如"公斤" |

## 回答规则

- 用户选择农资时，列出：农资名称、类型、库存数量、单位、价格、库存记录 ID。
- `num` 是库存余量，不是本次作业用量；本次用量必须来自用户输入、表单或配方。
- `stock_goods` 为空时，只展示顶层 `id/name/num/price`，不要补商品类型或单位。
- 用于 `add_farming_record` 时，只把用户明确选择的农资放入 `goodsList`，并保留原始 ID、商品 ID、名称、单位、价格等真实字段。
- 空数组时说明"未查询到可用农资库存"。
