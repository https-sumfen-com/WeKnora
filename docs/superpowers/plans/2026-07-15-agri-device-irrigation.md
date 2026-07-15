# Agri Device Irrigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `agri-operation-workflow` with MCP-grounded soil-moisture irrigation recommendations, a duration form, a separate confirmation turn, and guarded `start_valve_bank` calls.

**Architecture:** Keep MCP selection and agronomic judgment in `SKILL.md`; add a standalone Python script for exact `SHUM` extraction, batch `plot_device_ids` construction, form payload validation, and the cross-turn execution gate. Synchronize the local `sono-mcp` contract to the new batch valve-bank API without replacing the user's existing uncommitted edits.

**Tech Stack:** Markdown Agent Skills, Python 3 standard library, `unittest`, SONO-MCP tool contracts.

## Global Constraints

- `get_valve_bank_by_device.plot_device_ids` is a comma-separated string such as `"16,21,35"`, not a JSON array.
- The valve-bank API is called once and returns a server-deduplicated list.
- Only exact `key == "SHUM"` telemetry contributes to the average; one value per sensor device.
- The form submit turn never calls or authorizes `start_valve_bank`; a later user turn must confirm the displayed execution draft.
- Missing valid telemetry, insufficient irrigation evidence, or an empty valve-bank list never triggers device control.
- All int64 identifiers crossing JSON, form, trusted-state, or MCP boundaries are canonical decimal strings; this includes `cid`, `plot_id`, plot-device IDs, and valve-bank IDs.
- A direct request with a unique valve-bank ID and duration uses a separate later-turn-confirmed SONO direct-control route and does not require `plot_id` or sensor-assisted discovery.
- Preserve the user's pre-existing changes in `custom_skills/sono-mcp/SKILL.md` and do not stage unrelated files.
- Run Python with `D:\Program Files\uv\global_python\Scripts\python.exe` in this terminal.
- Set `$env:PYTHONUTF8 = '1'` in documented Windows validation commands; the payload scripts also configure UTF-8 stdio so unprefixed `unittest discover` remains reproducible under the default Windows code page.

---

### Task 1: Add RED tests for sensor analysis and batch valve lookup

**Files:**
- Create: `custom_skills/agri-operation-workflow/tests/test_irrigation_control_payload.py`
- Test: `custom_skills/agri-operation-workflow/tests/test_irrigation_control_payload.py`

**Interfaces:**
- Consumes: CLI script path `scripts/irrigation_control_payload.py` and commands `analyze-sensors`, `build-panel`, `prepare-execution`, `build-execution`.
- Produces: executable behavior contract for Task 2 and documentation assertions for Task 3.

- [ ] **Step 1: Create the subprocess test harness and exact-SHUM test**

```python
# -*- coding: utf-8 -*-
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
        self.assertEqual(result["plot_device_ids"], "16,21")
        self.assertEqual(result["plot_device_id_values"], ["16", "21"])
        self.assertEqual([row["value"] for row in result["sensor_readings"]], [20, 30.5])
```

- [ ] **Step 2: Add missing-telemetry and invalid-value tests**

```python
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
```

- [ ] **Step 3: Add form, tamper, and cross-turn confirmation tests**

```python
    def _panel_payload(self):
        return {
            "cid": 2007,
            "plot_id": 130,
            "plot_name": "示例地块",
            "average_soil_moisture": 25.25,
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
        self.assertIn('valve_bank_id "31"', result["form_syntax"])
        self.assertEqual(len(result["pending_irrigation_draft"]["valve_banks"]), 2)

    def test_build_panel_empty_valves_falls_back_to_farming_operation(self):
        payload = self._panel_payload()
        payload["valve_banks"] = []
        result = run_script("build-panel", payload)
        self.assertFalse(result["ok"])
        self.assertTrue(result["fallback_to_farming_operation"])
        self.assertNotIn("form_syntax", result)

    def test_prepare_execution_rejects_unknown_valve_id(self):
        panel = run_script("build-panel", self._panel_payload())
        result = run_script("prepare-execution", {
            "pending_irrigation_draft": panel["pending_irrigation_draft"],
            "submitted_form": {
                "type": "form_submit",
                "formType": "irrigation-valve-duration",
                "tag": "irrigation_valve_duration_confirm",
                "valveBanks": [{
                    "valve_bank_id": "999",
                    "duration_minutes": 20,
                    "selected": True,
                }],
            },
        })
        self.assertFalse(result["ok"])
        self.assertIn("unknown valve_bank_id: 999", result["errors"])
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
                    {"valve_bank_id": "31", "duration_minutes": 15, "selected": True},
                    {"valve_bank_id": "32", "duration_minutes": 25, "selected": True},
                ],
            },
        })
        self.assertTrue(prepared["ok"])
        self.assertTrue(prepared["requires_execution_confirmation"])
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
        })
        self.assertTrue(execution["ok"])
        self.assertEqual(execution["start_valve_bank_args"], [
            {"cid": "2007", "id": "31", "auto_off_minutes": 15},
            {"cid": "2007", "id": "32", "auto_off_minutes": 25},
        ])
```

- [ ] **Step 4: Add skill and SONO-MCP documentation contract tests**

```python
    def test_skill_documents_batch_valve_lookup_and_separate_execution_turn(self):
        skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        irrigation_text = (SKILL_DIR / "references" / "irrigation-control.md").read_text(encoding="utf-8")
        form_text = (SKILL_DIR / "references" / "irrigation-form.md").read_text(encoding="utf-8")
        combined = "\n".join((skill_text, irrigation_text, form_text))
        for required in (
            'key == "SHUM"',
            "plot_device_ids",
            "form irrigation-valve-duration",
            "irrigation_valve_duration_confirm",
            "user_confirmed_irrigation_execution_draft",
            "Never call `start_valve_bank` in the same assistant turn that receives the irrigation form submit",
        ):
            self.assertIn(required, combined)

    def test_sono_mcp_contract_uses_batch_string_and_list_response(self):
        repo = SKILL_DIR.parents[1]
        sono_skill = (repo / "custom_skills" / "sono-mcp" / "SKILL.md").read_text(encoding="utf-8")
        valve_ref = (repo / "custom_skills" / "sono-mcp" / "references" / "tool-valve-bank-by-device.md").read_text(encoding="utf-8")
        plot_devices_ref = (repo / "custom_skills" / "sono-mcp" / "references" / "tool-plot-device-list.md").read_text(encoding="utf-8")
        combined = "\n".join((sono_skill, valve_ref, plot_devices_ref))
        self.assertIn('"plot_device_ids": "16,21,35"', combined)
        self.assertIn("服务端已去重", combined)
        self.assertNotIn('"plot_device_id": 16', combined)
```

- [ ] **Step 5: Run the new test file and verify RED**

Run:

```powershell
$env:PYTHONUTF8 = '1'
& 'D:\Program Files\uv\global_python\Scripts\python.exe' 'custom_skills/agri-operation-workflow/tests/test_irrigation_control_payload.py' -v
```

Expected: FAIL because `scripts/irrigation_control_payload.py`, `references/irrigation-control.md`, and `references/irrigation-form.md` do not exist and the current SONO-MCP detailed contract still uses `plot_device_id`.

---

### Task 2: Implement the deterministic irrigation payload script

**Files:**
- Create: `custom_skills/agri-operation-workflow/scripts/irrigation_control_payload.py`
- Test: `custom_skills/agri-operation-workflow/tests/test_irrigation_control_payload.py`

**Interfaces:**
- Consumes: JSON stdin for `analyze-sensors`, `build-panel`, `prepare-execution`, and `build-execution`.
- Produces: the MCP-ready `plot_device_ids` comma-separated string, internal `plot_device_id_values`, `form_syntax`, `pending_irrigation_draft`, `pending_execution_draft`, and guarded `start_valve_bank_args`.

- [ ] **Step 1: Implement JSON helpers and sensor analysis**

```python
def _finite_number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def analyze_sensors(payload):
    devices = payload.get("devices")
    if not isinstance(devices, list):
        return {"ok": False, "errors": ["devices must be a list"]}
    readings = []
    ids = []
    seen_ids = set()
    for item in devices:
        if not isinstance(item, dict):
            continue
        plot_device_id = _positive_int(item.get("id"))
        if plot_device_id is None:
            continue
        data = item.get("device", {}).get("device_data", [])
        if not isinstance(data, list):
            continue
        value = next((_finite_number(row.get("value")) for row in data
                      if isinstance(row, dict) and row.get("key") == "SHUM"
                      and _finite_number(row.get("value")) is not None), None)
        if value is None:
            continue
        canonical_id = str(plot_device_id)
        readings.append({"plot_device_id": canonical_id,
                         "sensor_name": str(item.get("name") or item.get("device", {}).get("name") or ""),
                         "value": value})
        if canonical_id not in seen_ids:
            seen_ids.add(canonical_id)
            ids.append(canonical_id)
    average = None if not readings else _clean_number(sum(row["value"] for row in readings) / len(readings))
    return {"ok": True, "has_valid_shum": bool(readings),
            "sensor_readings": readings, "average_soil_moisture": average,
            "plot_device_ids": ",".join(map(str, ids)),
            "plot_device_id_values": ids}
```

- [ ] **Step 2: Implement valve-list validation and Syntax generation**

Implement `_validated_valve_banks()` to reject non-lists, invalid/duplicate IDs, blank titles, and missing `run_status`. Implement `build_panel()` to require positive `cid`, positive `plot_id`, finite average humidity, non-empty reason, positive integer duration, and at least one valid valve. Render quoted strings with `json.dumps(value, ensure_ascii=False)` and return `fallback_to_farming_operation: true` for an empty list.

```python
def build_panel(payload):
    banks, errors = _validated_valve_banks(payload.get("valve_banks"))
    if payload.get("valve_banks") == []:
        return {"ok": False, "errors": ["no valve banks returned"],
                "fallback_to_farming_operation": True}
    cid = _positive_int(payload.get("cid"))
    plot_id = _positive_int(payload.get("plot_id"))
    average = _finite_number(payload.get("average_soil_moisture"))
    reason = str(payload.get("reason") or "").strip()
    duration = _positive_int(payload.get("recommended_duration_minutes"))
    if cid is None:
        errors.append("cid must be a positive integer")
    if plot_id is None:
        errors.append("plot_id must be a positive integer")
    if average is None:
        errors.append("average_soil_moisture must be finite")
    if not reason:
        errors.append("reason is required")
    if duration is None:
        errors.append("recommended_duration_minutes must be a positive integer")
    if errors:
        return {"ok": False, "errors": errors}
    pending = {
        "cid": cid, "plot_id": plot_id,
        "plot_name": str(payload.get("plot_name") or "").strip(),
        "average_soil_moisture": average, "reason": reason,
        "valve_banks": [{**bank, "recommended_duration_minutes": duration}
                        for bank in banks],
    }
    syntax = _render_form_syntax(pending)
    return {"ok": True, "form_syntax": syntax,
            "pending_irrigation_draft": pending}
```

- [ ] **Step 3: Implement form validation and execution preparation**

`prepare_execution()` must require the exact form triple, reject unknown and duplicate IDs, reject non-boolean `selected`, reject non-positive/non-integer durations, require at least one selected bank, recover titles only from `pending_irrigation_draft`, and return no MCP arguments. It must carry and bind `plot_name`, `average_soil_moisture`, `reason`, valve IDs/titles, and final durations in its trusted draft, fingerprint, and confirmation text.

```python
return {
    "ok": True,
    "requires_execution_confirmation": True,
    "confirmation_text": confirmation_text,
    "execution_draft": execution_draft,
    "pending_execution_draft": execution_draft,
}
```

- [ ] **Step 4: Implement the separate-turn execution gate**

```python
def build_execution(payload):
    confirmed = (
        payload.get("execution_confirmed") is True
        and payload.get("draft_was_shown_to_user") is True
        and payload.get("confirmation_source") == "user_confirmed_irrigation_execution_draft"
    )
    if not confirmed:
        return {"ok": False,
                "errors": ["irrigation execution requires a separate confirmation after the draft is shown"],
                "requires_execution_confirmation": True}
    draft = payload.get("pending_execution_draft")
    if not isinstance(draft, dict):
        return {"ok": False, "errors": ["pending_execution_draft is required"]}
    cid = _positive_int(draft.get("cid"))
    selected = draft.get("valve_banks")
    if cid is None or not isinstance(selected, list) or not selected:
        return {"ok": False, "errors": ["pending execution draft is invalid"]}
    args = []
    for bank in selected:
        bank_id = _positive_int(bank.get("id")) if isinstance(bank, dict) else None
        duration = _positive_int(bank.get("duration_minutes")) if isinstance(bank, dict) else None
        if bank_id is None or duration is None:
            return {"ok": False, "errors": ["pending execution valve is invalid"]}
        args.append({"cid": str(cid), "id": str(bank_id),
                     "auto_off_minutes": duration})
    return {"ok": True, "start_valve_bank_args": args}
```

- [ ] **Step 5: Add the four-command CLI and run tests GREEN**

```python
COMMANDS = {
    "analyze-sensors": analyze_sensors,
    "build-panel": build_panel,
    "prepare-execution": prepare_execution,
    "build-execution": build_execution,
}
```

Run the Task 1 command. Expected: script behavior tests pass; documentation tests may remain RED until Task 3.

---

### Task 3: Document the device workflow and synchronize SONO-MCP

**Files:**
- Modify: `custom_skills/agri-operation-workflow/SKILL.md`
- Create: `custom_skills/agri-operation-workflow/references/irrigation-control.md`
- Create: `custom_skills/agri-operation-workflow/references/irrigation-form.md`
- Modify: `custom_skills/agri-operation-workflow/agents/openai.yaml`
- Modify: `custom_skills/sono-mcp/SKILL.md`
- Modify: `custom_skills/sono-mcp/references/tool-valve-bank-by-device.md`
- Modify: `custom_skills/sono-mcp/references/tool-plot-device-list.md`
- Test: `custom_skills/agri-operation-workflow/tests/test_irrigation_control_payload.py`

**Interfaces:**
- Consumes: Task 2 script commands and current SONO-MCP tool names.
- Produces: discoverable device-irrigation skill instructions and an internally consistent batch valve lookup contract.

- [ ] **Step 1: Extend SKILL.md triggers and script-first contract**

Keep YAML frontmatter to `name` and `description`. Extend the description with `设备操作`, `土壤湿度`, `灌溉判断`, `SHUM`, `irrigation-valve-duration`, and `start_valve_bank`. Add the four script commands and identify script output as authoritative for form and execution payloads.

- [ ] **Step 2: Add the device-assisted workflow phases and hard rules**

Document the exact sequence:

```text
get_plot_device_list -> exact SHUM extraction and average
-> get_plot_info + get_weather -> irrigation decision
-> one get_valve_bank_by_device(plot_device_ids="...")
-> form irrigation-valve-duration -> form submit
-> show execution draft -> later user confirmation
-> start_valve_bank calls in order
```

Include verbatim hard rule:

```markdown
Never call `start_valve_bank` in the same assistant turn that receives the irrigation form submit.
```

Document empty-valve fallback via `get_farming_operation_list`, stop-on-first-error behavior, and no automatic compensating close.

- [ ] **Step 3: Write focused irrigation references**

`irrigation-control.md` owns sensor extraction, agronomic evidence order, batch lookup, fallback, confirmation gate, and partial-execution reporting. `irrigation-form.md` owns exact Syntax fields, the submit JSON, allowed editable fields, and validation rules. Do not duplicate material-form details.

- [ ] **Step 4: Synchronize the SONO-MCP batch contract**

Apply precise patches around the user's current changes:

```markdown
`plot_device_ids` | only `get_valve_bank_by_device`; comma-separated outer IDs such as `"16,21,35"`
```

Update the detailed request example to the batch string, describe `payload[]`, and state that the service returns a deduplicated list. Update `tool-plot-device-list.md` to join valid outer IDs and call the batch tool once. Remove the obsolete example `"plot_device_id": 16` without changing unrelated table formatting.

- [ ] **Step 5: Refresh openai.yaml metadata**

Use quoted strings and keep the required skill token in the prompt:

```yaml
interface:
  display_name: "Agri Operation Workflow"
  short_description: "MCP-backed farming and irrigation control"
  default_prompt: "Use $agri-operation-workflow to recommend MCP-backed farming or irrigation actions, confirm inputs, and safely execute the approved operation."
```

- [ ] **Step 6: Run the new tests GREEN**

Run the Task 1 command. Expected: all irrigation script and documentation contract tests pass.

---

### Task 4: Full verification and forward scenario checks

**Files:**
- Verify: `custom_skills/agri-operation-workflow/`
- Verify: `custom_skills/sono-mcp/`

**Interfaces:**
- Consumes: completed implementation from Tasks 1-3.
- Produces: evidence that old material behavior is preserved and the new workflow is valid.

- [ ] **Step 1: Run all agri-operation workflow tests**

```powershell
$env:PYTHONUTF8 = '1'
& 'D:\Program Files\uv\global_python\Scripts\python.exe' -m unittest discover -s 'custom_skills/agri-operation-workflow/tests' -p 'test_*.py' -v
```

Expected: all existing material tests and new irrigation tests pass with no warnings.

- [ ] **Step 2: Validate both skills**

```powershell
$env:PYTHONUTF8 = '1'
& 'D:\Program Files\uv\global_python\Scripts\python.exe' 'C:\Users\38304\.codex\skills\.system\skill-creator\scripts\quick_validate.py' 'custom_skills/agri-operation-workflow'
& 'D:\Program Files\uv\global_python\Scripts\python.exe' 'C:\Users\38304\.codex\skills\.system\skill-creator\scripts\quick_validate.py' 'custom_skills/sono-mcp'
```

Expected twice: `Skill is valid!`

- [ ] **Step 3: Run direct CLI smoke cases**

Pipe representative JSON into each command and verify that `prepare-execution` has no `start_valve_bank_args`, while `build-execution` only emits them with all three confirmation fields.

- [ ] **Step 4: Forward-test the skill with minimal context**

Ask an independent agent to use the skill for a dry plot with two `SHUM` sensors and two returned valve banks. Success requires one batch `plot_device_ids` call, an irrigation form, no control on form submit, and control only after a later explicit confirmation. Also test an empty valve list and require fallback to a conventional farming-operation recommendation.

- [ ] **Step 5: Inspect the final diff and working tree**

```powershell
git diff --check
git status --short
git diff -- custom_skills/agri-operation-workflow custom_skills/sono-mcp docs/superpowers
```

Expected: no whitespace errors, no generated `__pycache__`, no unrelated file changes, and the user's existing `sono-mcp/SKILL.md` edits remain present.
