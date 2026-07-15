# -*- coding: utf-8 -*-
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "irrigation_control_payload.py"


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


class IrrigationControlPayloadTests(unittest.TestCase):
    def test_analyze_sensors_uses_first_exact_shum_per_device(self):
        result = run_script("analyze-sensors", {"devices": [
            {"id": 16, "name": "传感器A", "device": {"device_data": [
                {"key": "trsd", "value": 99},
                {"key": "SHUM", "value": 20},
                {"key": "SHUM", "value": 80},
            ]}},
            {"id": "21", "name": "传感器B", "device": {"device_data": [
                {"key": "shum", "value": 90},
                {"key": "SHUM", "value": "30.5"},
            ]}},
            {"id": 22, "name": "无效传感器", "device": {"device_data": [
                {"key": "SHUM", "value": "not-a-number"},
            ]}},
        ]})

        self.assertTrue(result["ok"])
        self.assertTrue(result["has_valid_shum"])
        self.assertEqual(result["average_soil_moisture"], 25.25)
        self.assertIsInstance(result["plot_device_ids"], str)
        self.assertEqual(result["plot_device_ids"], "16,21")
        self.assertEqual(result["plot_device_id_values"], [16, 21])
        self.assertNotIn("plot_device_ids_csv", result)
        self.assertEqual([row["value"] for row in result["sensor_readings"]], [20, 30.5])

    def test_analyze_sensors_returns_no_control_input_without_valid_shum(self):
        result = run_script("analyze-sensors", {"devices": [
            {"id": 16, "device": {"device_data": [
                {"key": "SHUM", "value": None},
                {"key": "SHUM", "value": True},
                {"key": "SHUM", "value": "NaN"},
            ]}},
        ]})
        self.assertTrue(result["ok"])
        self.assertFalse(result["has_valid_shum"])
        self.assertIsNone(result["average_soil_moisture"])
        self.assertEqual(result["plot_device_ids"], "")
        self.assertEqual(result["plot_device_id_values"], [])
        self.assertNotIn("plot_device_ids_csv", result)
        for forbidden in (
            "pending_irrigation_draft",
            "pending_execution_draft",
            "start_valve_bank_args",
        ):
            self.assertNotIn(forbidden, result)

    def test_analyze_sensors_rejects_duplicate_outer_device_id(self):
        result = run_script("analyze-sensors", {"devices": [
            {"id": 16, "device": {"device_data": [
                {"key": "SHUM", "value": 20},
            ]}},
            {"id": "16", "device": {"device_data": [
                {"key": "SHUM", "value": 30},
            ]}},
        ]})

        self.assertFalse(result["ok"])
        self.assertFalse(result["has_valid_shum"])
        self.assertIn("duplicate plot_device_id: 16", result["errors"])
        for forbidden in (
            "plot_device_ids",
            "plot_device_id_values",
            "pending_irrigation_draft",
            "pending_execution_draft",
            "start_valve_bank_args",
        ):
            self.assertNotIn(forbidden, result)

    def test_analyze_sensors_rejects_non_finite_aggregate(self):
        result = run_script("analyze-sensors", {"devices": [
            {"id": 16, "device": {"device_data": [
                {"key": "SHUM", "value": 1e308},
            ]}},
            {"id": 21, "device": {"device_data": [
                {"key": "SHUM", "value": 1e308},
            ]}},
        ]})

        self.assertFalse(result["ok"])
        self.assertFalse(result["has_valid_shum"])
        self.assertIn("average_soil_moisture must be finite", result["errors"])
        for forbidden in (
            "plot_device_ids",
            "plot_device_id_values",
            "pending_irrigation_draft",
            "pending_execution_draft",
            "start_valve_bank_args",
        ):
            self.assertNotIn(forbidden, result)

    def test_analyze_sensors_accepts_single_large_finite_value(self):
        result = run_script("analyze-sensors", {"devices": [
            {"id": 16, "device": {"device_data": [
                {"key": "SHUM", "value": 1e308},
            ]}},
        ]})

        self.assertTrue(result["ok"])
        self.assertTrue(result["has_valid_shum"])
        self.assertEqual(float(result["average_soil_moisture"]), 1e308)
        self.assertEqual(result["plot_device_ids"], "16")
        self.assertEqual(result["plot_device_id_values"], [16])

    def test_ids_above_js_safe_integer_preserve_exact_precision_end_to_end(self):
        sensor_id = 9007199254740993
        cid = 9007199254740995
        plot_id = 9007199254740997
        valve_id = 9007199254740999

        sensor_analysis = run_script("analyze-sensors", {"devices": [
            {"id": sensor_id, "name": "高位设备ID", "device": {"device_data": [
                {"key": "SHUM", "value": 20},
            ]}},
        ]})
        self.assertEqual(sensor_analysis["plot_device_id_values"], [sensor_id])
        self.assertEqual(sensor_analysis["plot_device_ids"], str(sensor_id))

        panel = run_script("build-panel", {
            "cid": str(cid),
            "plot_id": plot_id,
            "plot_name": "高位ID地块",
            "sensor_analysis": sensor_analysis,
            "irrigation_needed": True,
            "reason": "验证整数精度",
            "recommended_duration_minutes": 20,
            "valve_banks": [
                {"id": str(valve_id), "run_status": "0", "title": "高位ID阀门组"},
            ],
        })
        self.assertTrue(panel["ok"])
        pending = panel["pending_irrigation_draft"]
        self.assertEqual(pending["cid"], cid)
        self.assertEqual(pending["plot_id"], plot_id)
        self.assertEqual(pending["valve_banks"][0]["id"], valve_id)

        prepared = run_script("prepare-execution", {
            "pending_irrigation_draft": pending,
            "submitted_form": {
                "type": "form_submit",
                "formType": "irrigation-valve-duration",
                "tag": "irrigation_valve_duration_confirm",
                "valveBanks": [{
                    "valve_bank_id": valve_id,
                    "duration_minutes": 15,
                    "selected": True,
                }],
            },
        })
        self.assertTrue(prepared["ok"])
        execution = run_script("build-execution", {
            "pending_execution_draft": prepared["pending_execution_draft"],
            "execution_confirmed": True,
            "draft_was_shown_to_user": True,
            "confirmation_source": "user_confirmed_irrigation_execution_draft",
            "confirmed_draft_fingerprint": prepared["draft_fingerprint"],
        })
        self.assertTrue(execution["ok"])
        self.assertEqual(execution["start_valve_bank_args"], [{
            "cid": cid,
            "id": valve_id,
            "auto_off_minutes": 15,
        }])

    def _panel_payload(self):
        sensor_analysis = run_script("analyze-sensors", {"devices": [
            {"id": 16, "name": "传感器A", "device": {"device_data": [
                {"key": "SHUM", "value": 20},
            ]}},
            {"id": 21, "name": "传感器B", "device": {"device_data": [
                {"key": "SHUM", "value": 30.5},
            ]}},
        ]})
        return {
            "cid": 2007,
            "plot_id": 130,
            "plot_name": "示例地块",
            "sensor_analysis": sensor_analysis,
            "irrigation_needed": True,
            "reason": "土壤湿度偏低且近期无明显降雨",
            "recommended_duration_minutes": 20,
            "valve_banks": [
                {"id": 31, "run_status": "0", "title": "阀门组A"},
                {"id": 32, "run_status": "0", "title": "阀门组B"},
            ],
        }

    def test_build_panel_returns_irrigation_syntax_and_internal_draft(self):
        result = run_script("build-panel", self._panel_payload())
        self.assertTrue(result["ok"])
        self.assertIn("form irrigation-valve-duration", result["form_syntax"])
        self.assertIn("average_soil_moisture 25.25", result["form_syntax"])
        self.assertIn("valve_bank_id 31", result["form_syntax"])
        pending = result["pending_irrigation_draft"]
        self.assertEqual(len(pending["valve_banks"]), 2)
        self.assertEqual(pending["average_soil_moisture"], 25.25)
        self.assertEqual(pending["sensor_analysis"], self._panel_payload()["sensor_analysis"])

    def test_build_panel_rejects_missing_or_tampered_sensor_analysis(self):
        base = self._panel_payload()
        cases = {}

        missing = copy.deepcopy(base)
        missing.pop("sensor_analysis")
        cases["missing"] = missing

        bad_average = copy.deepcopy(base)
        bad_average["sensor_analysis"]["average_soil_moisture"] = 99
        cases["average"] = bad_average

        duplicate_reading = copy.deepcopy(base)
        duplicate_reading["sensor_analysis"]["sensor_readings"].append(
            copy.deepcopy(duplicate_reading["sensor_analysis"]["sensor_readings"][0])
        )
        cases["duplicate"] = duplicate_reading

        bad_ids = copy.deepcopy(base)
        bad_ids["sensor_analysis"]["plot_device_ids"] = "16, 21"
        cases["ids"] = bad_ids

        bad_id_values = copy.deepcopy(base)
        bad_id_values["sensor_analysis"]["plot_device_id_values"] = [16, 999]
        cases["id_values"] = bad_id_values

        invalid_gate = copy.deepcopy(base)
        invalid_gate["sensor_analysis"]["has_valid_shum"] = False
        cases["has_valid_shum"] = invalid_gate

        for name, payload in cases.items():
            with self.subTest(name=name):
                # Legacy bare input is present to prove the panel must validate
                # sensor_analysis instead of trusting this value.
                payload["average_soil_moisture"] = 25.25
                result = run_script("build-panel", payload)
                self.assertFalse(result["ok"])
                for forbidden in (
                    "form_syntax",
                    "pending_irrigation_draft",
                    "pending_execution_draft",
                    "start_valve_bank_args",
                ):
                    self.assertNotIn(forbidden, result)

    def test_build_panel_requires_explicit_irrigation_needed_gate(self):
        for gate_value in (None, False):
            with self.subTest(gate_value=gate_value):
                payload = self._panel_payload()
                if gate_value is None:
                    payload.pop("irrigation_needed")
                else:
                    payload["irrigation_needed"] = gate_value

                result = run_script("build-panel", payload)

                self.assertFalse(result["ok"])
                for forbidden in (
                    "form_syntax",
                    "pending_irrigation_draft",
                    "pending_execution_draft",
                    "start_valve_bank_args",
                ):
                    self.assertNotIn(forbidden, result)

    def test_build_panel_empty_valves_falls_back_to_farming_operation(self):
        payload = self._panel_payload()
        payload["valve_banks"] = []
        result = run_script("build-panel", payload)
        self.assertFalse(result["ok"])
        self.assertTrue(result["fallback_to_farming_operation"])
        for forbidden in (
            "form_syntax",
            "pending_irrigation_draft",
            "pending_execution_draft",
            "start_valve_bank_args",
        ):
            self.assertNotIn(forbidden, result)

    def test_prepare_execution_rejects_unknown_valve_id(self):
        panel = run_script("build-panel", self._panel_payload())
        result = run_script("prepare-execution", {
            "pending_irrigation_draft": panel["pending_irrigation_draft"],
            "submitted_form": {
                "type": "form_submit",
                "formType": "irrigation-valve-duration",
                "tag": "irrigation_valve_duration_confirm",
                "valveBanks": [{
                    "valve_bank_id": 999,
                    "duration_minutes": 20,
                    "selected": True,
                }],
            },
        })
        self.assertFalse(result["ok"])
        self.assertIn("unknown valve_bank_id: 999", result["errors"])
        self.assertNotIn("start_valve_bank_args", result)

    def test_prepare_execution_rejects_omitted_pending_valve_id(self):
        panel = run_script("build-panel", self._panel_payload())
        result = run_script("prepare-execution", {
            "pending_irrigation_draft": panel["pending_irrigation_draft"],
            "submitted_form": {
                "type": "form_submit",
                "formType": "irrigation-valve-duration",
                "tag": "irrigation_valve_duration_confirm",
                "valveBanks": [
                    {"valve_bank_id": 31, "duration_minutes": 20, "selected": True},
                ],
            },
        })

        self.assertFalse(result["ok"])
        self.assertIn(
            "submitted valve IDs must exactly match pending valve IDs",
            result["errors"],
        )
        self.assertNotIn("pending_execution_draft", result)
        self.assertNotIn("start_valve_bank_args", result)

    def test_form_submit_only_prepares_draft_and_later_confirmation_builds_args(self):
        panel = run_script("build-panel", self._panel_payload())
        prepared = run_script("prepare-execution", {
            "pending_irrigation_draft": panel["pending_irrigation_draft"],
            "submitted_form": {
                "type": "form_submit",
                "formType": "irrigation-valve-duration",
                "tag": "irrigation_valve_duration_confirm",
                "valveBanks": [
                    {"valve_bank_id": 32, "duration_minutes": 25, "selected": True},
                    {"valve_bank_id": 31, "duration_minutes": 15, "selected": True},
                ],
            },
        })
        self.assertTrue(prepared["ok"])
        self.assertTrue(prepared["requires_execution_confirmation"])
        self.assertEqual(len(prepared["draft_fingerprint"]), 64)
        self.assertEqual(
            prepared["pending_execution_draft"]["draft_fingerprint"],
            prepared["draft_fingerprint"],
        )
        self.assertNotIn("start_valve_bank_args", prepared)

        blocked = run_script("build-execution", {
            "pending_execution_draft": prepared["pending_execution_draft"],
            "execution_confirmed": True,
        })
        self.assertFalse(blocked["ok"])
        self.assertTrue(blocked["requires_execution_confirmation"])

        execution = run_script("build-execution", {
            "pending_execution_draft": prepared["pending_execution_draft"],
            "execution_confirmed": True,
            "draft_was_shown_to_user": True,
            "confirmation_source": "user_confirmed_irrigation_execution_draft",
            "confirmed_draft_fingerprint": prepared["draft_fingerprint"],
        })
        self.assertTrue(execution["ok"])
        self.assertEqual(execution["start_valve_bank_args"], [
            {"cid": 2007, "id": 32, "auto_off_minutes": 25},
            {"cid": 2007, "id": 31, "auto_off_minutes": 15},
        ])

    def _prepared_execution(self):
        panel_payload = self._panel_payload()
        # Keeps the regression focused on draft binding against the old panel
        # implementation, which required this now-untrusted field.
        panel_payload["average_soil_moisture"] = 25.25
        panel = run_script("build-panel", panel_payload)
        return run_script("prepare-execution", {
            "pending_irrigation_draft": panel["pending_irrigation_draft"],
            "submitted_form": {
                "type": "form_submit",
                "formType": "irrigation-valve-duration",
                "tag": "irrigation_valve_duration_confirm",
                "valveBanks": [
                    {"valve_bank_id": 31, "duration_minutes": 15, "selected": True},
                    {"valve_bank_id": 32, "duration_minutes": 25, "selected": True},
                ],
            },
        })

    def test_build_execution_requires_confirmed_draft_fingerprint(self):
        prepared = self._prepared_execution()
        result = run_script("build-execution", {
            "pending_execution_draft": prepared["pending_execution_draft"],
            "execution_confirmed": True,
            "draft_was_shown_to_user": True,
            "confirmation_source": "user_confirmed_irrigation_execution_draft",
        })

        self.assertFalse(result["ok"])
        self.assertTrue(result["requires_execution_confirmation"])
        self.assertNotIn("start_valve_bank_args", result)

    def test_build_execution_rejects_tampered_pending_draft(self):
        prepared = self._prepared_execution()
        fingerprint = prepared.get("draft_fingerprint")
        mutations = {
            "bank_id": lambda draft: draft["valve_banks"][0].__setitem__("id", 999),
            "duration": lambda draft: draft["valve_banks"][0].__setitem__("duration_minutes", 99),
        }

        for name, mutate in mutations.items():
            with self.subTest(name=name):
                draft = copy.deepcopy(prepared["pending_execution_draft"])
                mutate(draft)
                result = run_script("build-execution", {
                    "pending_execution_draft": draft,
                    "execution_confirmed": True,
                    "draft_was_shown_to_user": True,
                    "confirmation_source": "user_confirmed_irrigation_execution_draft",
                    "confirmed_draft_fingerprint": fingerprint,
                })

                self.assertFalse(result["ok"])
                self.assertTrue(result["requires_execution_confirmation"])
                self.assertNotIn("start_valve_bank_args", result)

    def test_skill_documents_batch_valve_lookup_and_separate_execution_turn(self):
        skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        irrigation_text = (SKILL_DIR / "references" / "irrigation-control.md").read_text(encoding="utf-8")
        form_text = (SKILL_DIR / "references" / "irrigation-form.md").read_text(encoding="utf-8")

        for required in (
            'key == "SHUM"',
            "Call get_valve_bank_by_device exactly once",
            "plot_device_ids",
            "comma-separated string",
        ):
            self.assertIn(required, irrigation_text)

        for required in (
            "form irrigation-valve-duration",
            "irrigation_valve_duration_confirm",
            "user_confirmed_irrigation_execution_draft",
        ):
            self.assertIn(required, form_text)

        self.assertIn(
            "Never call `start_valve_bank` in the same assistant turn that receives the irrigation form submit",
            skill_text,
        )

    def test_sono_mcp_contract_uses_batch_string_and_list_response(self):
        repo = SKILL_DIR.parents[1]
        sono_skill = (repo / "custom_skills" / "sono-mcp" / "SKILL.md").read_text(encoding="utf-8")
        valve_ref = (repo / "custom_skills" / "sono-mcp" / "references" / "tool-valve-bank-by-device.md").read_text(encoding="utf-8")
        plot_devices_ref = (repo / "custom_skills" / "sono-mcp" / "references" / "tool-plot-device-list.md").read_text(encoding="utf-8")

        self.assertIn("plot_device_ids", sono_skill)
        self.assertIn('"plot_device_ids": "16,21,35"', valve_ref)
        self.assertIn("payload[]", valve_ref)
        self.assertIn("服务端已去重", valve_ref)
        self.assertNotIn('"plot_device_id": 16', valve_ref)
        self.assertIn("plot_device_ids", plot_devices_ref)

    def test_valve_control_references_select_id_from_batch_payload_item(self):
        repo = SKILL_DIR.parents[1]
        sono_skill = (repo / "custom_skills" / "sono-mcp" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertGreaterEqual(
            sono_skill.count("所选 `get_valve_bank_by_device.payload[].id`"),
            3,
        )
        refs = repo / "custom_skills" / "sono-mcp" / "references"
        for name in ("tool-start-valve-bank.md", "tool-stop-valve-bank.md"):
            with self.subTest(name=name):
                text = (refs / name).read_text(encoding="utf-8")
                self.assertIn("get_valve_bank_by_device.payload[].id", text)
                self.assertNotIn("get_valve_bank_by_device.id", text)

    def test_sono_mcp_documents_coordinated_irrigation_exception(self):
        repo = SKILL_DIR.parents[1]
        sono_skill = (repo / "custom_skills" / "sono-mcp" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("普通请求仍然单工具优先", sono_skill)
        self.assertIn("device-assisted irrigation workflow", sono_skill)
        for tool_name in (
            "get_plot_device_list",
            "get_plot_info",
            "get_weather",
            "get_valve_bank_by_device",
        ):
            self.assertIn(tool_name, sono_skill)
        self.assertIn("仍禁止扫描或无目的调用", sono_skill)

    def test_skill_has_branch_specific_checklists_and_complete_form_rows(self):
        skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        form_text = (SKILL_DIR / "references" / "irrigation-form.md").read_text(encoding="utf-8")

        farm_heading = "### Farming-record branch checklist"
        irrigation_heading = "### Device-irrigation branch checklist"
        self.assertIn(farm_heading, skill_text)
        self.assertIn(irrigation_heading, skill_text)
        farm_start = skill_text.index(farm_heading)
        irrigation_start = skill_text.index(irrigation_heading)
        farm_checklist = skill_text[farm_start:irrigation_start]
        irrigation_checklist = skill_text[irrigation_start:]
        self.assertIn("matter_id", farm_checklist)
        self.assertIn("add_farming_record", farm_checklist)
        for farming_only_term in (
            "matter_id",
            "get_agri_input_list",
            "goodsList",
            "add_farming_record",
        ):
            self.assertNotIn(farming_only_term, irrigation_checklist)

        self.assertIn(
            "The submit must contain every candidate `valve_bank_id` from the trusted pending draft exactly once.",
            form_text,
        )
        self.assertIn(
            "Use `selected: false` to cancel execution; deleting a row does not cancel it.",
            form_text,
        )


if __name__ == "__main__":
    unittest.main()
