# 推荐农资 Syntax 返回约束

## 适用场景

当后端或模型需要让前端在 `ConversationView` 中流式展示“推荐农资”卡片时，推荐返回 `form agri-material-usage` Syntax。前端会按行解析，已完成的农资条目会立即渲染为 `form-panel` 卡片，效果类似 GPT-Vis Syntax 的流式图表解析。

新链路只返回 Syntax。不要输出 `schemaVersion` JSON、`blocks` JSON、SSE JSON 事件或其他 JSON 外壳。

## 推荐返回格式

```txt
form agri-material-usage
title 补全信息
autoOpen false
data
  - goods_name 氮磷钾复合肥
    stock_goods_id 7
    is_formula 0
    num 0
    price 3
    unit kg
    dosage 0
    stock_record_id 7
  - goods_name 尿素
    stock_goods_id 6
    is_formula 0
    num 0
    price 1.9
    unit kg
    dosage 0
    stock_record_id 6
```

也可以包在代码围栏内：

````txt
```plant-agent
form agri-material-usage
title 补全信息
autoOpen false
data
  - goods_name 水溶肥
    stock_goods_id 4
    num 0
    price 4.8
    unit kg
    dosage 0
    stock_record_id 3
```
````

## 语法规则

- 第一行固定为 `form agri-material-usage`。
- `title` 可选，默认 `补全信息`。
- `autoOpen` 可选，只能是 `true` 或 `false`，默认 `false`。
- `data` 后面每个 `-` 开始一个农资条目。
- 每个字段一行，格式为 `字段名 空格 字段值`。
- 字段值包含空格时用英文双引号包裹，例如 `goods_name "商品 有机肥"`。
- 不输出 Markdown 解释、JSON 外壳或多余注释。
- 流式输出时，尽量按“一个农资条目完整输出后再开始下一个 `-`”的顺序生成。

## 字段约束

| 字段 | 必填 | 类型 | 约束 |
| --- | --- | --- | --- |
| `goods_name` | 是 | string | 非空农资名称 |
| `stock_goods_id` | 是 | number | 大于 0，库存商品 ID |
| `stock_record_id` | 否 | number | 大于 0 时保留，对应库存记录 ID |
| `is_formula` | 否 | number | `0` 或 `1`，缺省按 `0` |
| `num` | 是 | number | 推荐总用量，必须大于等于 0 |
| `price` | 是 | number | 单价，必须大于等于 0 |
| `unit` | 否 | string | 单位，缺省为空字符串 |
| `dosage` | 否 | number | 规格或预设剂量，必须大于等于 0 |

