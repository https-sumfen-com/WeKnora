# -*- coding: utf-8 -*-
import json
import subprocess
import sys
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "agri_material_payload.py"


def run_script(command, payload):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), command],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"script failed: {proc.stderr}\nstdout={proc.stdout}")
    return json.loads(proc.stdout)


class AgriMaterialPayloadTests(unittest.TestCase):
    def test_build_panel_filters_inventory_by_operation_type(self):
        payload = {
            "operation_name": "中草药开花前追肥",
            "record_draft": {
                "cid": 2007,
                "base_id": 3,
                "plot_id": 130,
                "matter_id": 207,
                "operate_time": "2026-07-07 14:32",
                "area": 2.65,
            },
            "usage_by_stock_record_id": {"29": 1.5},
            "inventory_rows": [
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
                        "unit": "公斤",
                    },
                },
                {
                    "id": 30,
                    "name": "除草剂A",
                    "num": "8.00",
                    "price": "20.00",
                    "stock_goods": {
                        "id": 2,
                        "name": "除草剂A",
                        "price": "20.00",
                        "type": "除草剂",
                        "unit": "升",
                    },
                },
            ],
        }

        result = run_script("build-panel", payload)

        self.assertTrue(result["ok"])
        self.assertEqual(len(result["form_panel"]["goodsList"]), 1)
        item = result["form_panel"]["goodsList"][0]
        self.assertEqual(item["goods_name"], "50%硫酸钾")
        self.assertEqual(item["stock_goods_id"], 1)
        self.assertEqual(item["stock_record_id"], 29)
        self.assertEqual(item["num"], 3.975)
        self.assertEqual(item["dosage"], 1500)
        self.assertEqual(len(result["selected_inventory_rows"]), 1)
        self.assertEqual(result["selected_inventory_rows"][0]["num"], "10.00")
        self.assertEqual(result["pending_draft"]["record_draft"]["matter_id"], 207)
        self.assertEqual(result["pending_draft"]["selected_inventory_rows"][0]["id"], 29)

    def test_build_panel_uses_zero_only_when_no_usage_recommendation_is_supplied(self):
        payload = {
            "operation_name": "追肥",
            "inventory_rows": [
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
                        "unit": "公斤",
                    },
                }
            ],
        }

        result = run_script("build-panel", payload)

        self.assertTrue(result["ok"])
        self.assertEqual(result["form_panel"]["goodsList"][0]["num"], 0)
        self.assertEqual(result["form_panel"]["goodsList"][0]["dosage"], 0)

    def test_build_submit_outputs_compact_frontend_num_contract(self):
        payload = {
            "record_draft": {
                "cid": 2007,
                "base_id": 3,
                "plot_id": 130,
                "matter_id": 207,
                "operate_time": "2026-07-07 14:32",
                "area": 2.65,
                "area_unit": "亩",
            },
            "system_params": {
                "user_id": 73,
                "entity_id": 1,
                "dept_id": 0,
                "token": "do-not-forward",
            },
            "submitted_goodsList": [
                {
                    "goods_name": "50%硫酸钾",
                    "stock_goods_id": 1,
                    "stock_record_id": 29,
                    "is_formula": 0,
                    "num": 2.65,
                    "price": 999,
                    "unit": "公斤",
                }
            ],
            "original_inventory_rows": [
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
                        "unit": "公斤",
                    },
                }
            ],
        }

        result = run_script("build-submit", payload)

        self.assertTrue(result["ok"])
        item = result["goodsList"][0]
        self.assertEqual(
            item,
            {
                "goods_name": "50%硫酸钾",
                "stock_goods_id": 1,
                "is_formula": 0,
                "num": 2.65,
                "price": 999,
                "unit": "公斤",
                "dosage": 1000,
            },
        )
        args = result["add_farming_record_args"]
        self.assertEqual(args["cid"], 2007)
        self.assertEqual(args["base_id"], 3)
        self.assertEqual(args["plot_id"], 130)
        self.assertEqual(args["matter_id"], 207)
        self.assertEqual(args["operate_time"], "2026-07-07 14:32")
        self.assertEqual(args["work_user"], 73)
        self.assertEqual(args["tgzn_user_id"], 73)
        self.assertEqual(args["tgzn_entity_id"], 1)
        self.assertNotIn("token", args)
        self.assertNotIn("tgzn_dept_id", args)
        self.assertEqual(args["goodsList"][0], item)

    def test_build_submit_rejects_missing_record_draft_to_prevent_data_loss(self):
        payload = {
            "submitted_goodsList": [
                {
                    "goods_name": "50%硫酸钾",
                    "stock_goods_id": 1,
                    "stock_record_id": 29,
                    "is_formula": 0,
                    "num": 1.8,
                    "price": 3.73,
                    "unit": "公斤",
                }
            ],
            "original_inventory_rows": [
                {
                    "id": 29,
                    "name": "50%硫酸钾",
                    "num": "10.00",
                    "price": "3.73",
                    "stock_goods": {"id": 1, "name": "50%硫酸钾"},
                }
            ],
        }

        result = run_script("build-submit", payload)

        self.assertFalse(result["ok"])
        self.assertIn("record_draft is required", result["errors"])
        self.assertNotIn("goodsList", result)

    def test_build_submit_preserves_user_confirmed_units_for_real_submit_payload(self):
        payload = {
            "record_draft": {
                "cid": 2014,
                "base_id": 71,
                "plot_id": 19142,
                "matter_id": 143,
                "operate_time": "2026-07-07 00:00",
                "area": 1,
            },
            "system_params": {
                "cid": 2014,
                "cname": "内蒙古科学技术研究院",
                "user_id": 48,
                "dept_id": 0,
                "entity_id": 1,
                "entity_info_id": 0,
                "terminal_id": 1,
                "token": "do-not-forward",
            },
            "submitted_goodsList": [
                {
                    "goods_name": "磷酸二氢钾",
                    "stock_goods_id": 9,
                    "stock_record_id": 9,
                    "is_formula": 0,
                    "num": 0.15,
                    "price": 2.2,
                    "unit": "kg",
                },
                {
                    "goods_name": "水溶肥",
                    "stock_goods_id": 4,
                    "stock_record_id": 3,
                    "is_formula": 0,
                    "num": 0.8,
                    "price": 4.8,
                    "unit": "kg",
                },
            ],
            "original_inventory_rows": [
                {
                    "id": 9,
                    "name": "磷酸二氢钾",
                    "num": "0.0000",
                    "price": "2.2000",
                    "stock_goods": {
                        "id": 9,
                        "name": "磷酸二氢钾",
                        "price": "0.0000",
                        "type": "",
                        "unit": "",
                    },
                },
                {
                    "id": 3,
                    "name": "水溶肥",
                    "num": "0.0000",
                    "price": "4.8000",
                    "stock_goods": {
                        "id": 4,
                        "name": "水溶肥",
                        "price": "4.8000",
                        "type": "",
                        "unit": "",
                    },
                },
            ],
        }

        result = run_script("build-submit", payload)

        self.assertTrue(result["ok"])
        args = result["add_farming_record_args"]
        self.assertEqual(args["work_user"], 48)
        self.assertEqual(args["tgzn_user_id"], 48)
        self.assertEqual(args["tgzn_entity_id"], 1)
        self.assertNotIn("token", args)
        self.assertNotIn("terminal_id", args)
        first = args["goodsList"][0]
        second = args["goodsList"][1]
        self.assertEqual(first["num"], 0.15)
        self.assertEqual(first["price"], 2.2)
        self.assertEqual(first["unit"], "kg")
        self.assertEqual(first["dosage"], 150)
        self.assertEqual(second["num"], 0.8)
        self.assertEqual(second["price"], 4.8)
        self.assertEqual(second["unit"], "kg")
        self.assertEqual(second["dosage"], 800)
        self.assertNotIn("mu_usage", second)
        self.assertNotIn("stock_goods", second)
        self.assertNotIn("inventory_num", second)

    def test_build_submit_fails_when_original_inventory_row_is_missing(self):
        payload = {
            "record_draft": {
                "cid": 2007,
                "base_id": 3,
                "plot_id": 130,
                "matter_id": 207,
                "operate_time": "2026-07-07 14:32",
            },
            "system_params": {"user_id": 73},
            "submitted_goodsList": [
                {
                    "goods_name": "未知肥料",
                    "stock_goods_id": 99,
                    "stock_record_id": 999,
                    "num": 1,
                    "price": 1,
                }
            ],
            "original_inventory_rows": [],
        }

        result = run_script("build-submit", payload)

        self.assertFalse(result["ok"])
        self.assertIn("cannot match original inventory row", result["errors"][0])
        self.assertNotIn("goodsList", result)


if __name__ == "__main__":
    unittest.main()
