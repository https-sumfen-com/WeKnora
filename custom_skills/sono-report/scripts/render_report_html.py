# -*- coding: utf-8 -*-
# @Time    : 2026/6/29 12:24
# @Author  : feidu
# @File    : render_report_html.py
"""完整报告的确定性数据注入，防止用户数据终止script。

Render a SONO report HTML file by injecting REPORT_DATA into template.html.

Usage:
  python scripts/render_report_html.py template.html normalized-report-data.json generated-report.html

This script performs deterministic template injection. It does not call MCP and
it does not invent business facts.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPORT_DATA_RE = re.compile(
    r"const\s+REPORT_DATA\s*=\s*/\*\s*__REPORT_DATA__\s*\*/\s*\{[\s\S]*?\n\};",
    re.MULTILINE,
)


def main() -> None:
    """从归一化输入渲染可信模板，失败时不保存HTML。"""
    parser = argparse.ArgumentParser(description="Inject REPORT_DATA into SONO HTML template")
    parser.add_argument("template", help="HTML template path")
    parser.add_argument("report_data", help="Normalized REPORT_DATA JSON path")
    parser.add_argument("output", help="Output HTML path")
    args = parser.parse_args()

    template_path = Path(args.template)
    data_path = Path(args.report_data)
    output_path = Path(args.output)
    if output_path.parent == Path('.'):
        raise SystemExit("Output HTML must be written inside the per-run WORKDIR, not the current skill directory")

    html = template_path.read_text(encoding="utf-8")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("REPORT_DATA must be a JSON object")

    payload = json.dumps(data, ensure_ascii=False, indent=2)
    for char, escaped in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        payload = payload.replace(char, escaped)
    replacement = "const REPORT_DATA = " + payload + ";"
    rendered, count = REPORT_DATA_RE.subn(lambda _: replacement, html, count=1)
    if count != 1:
        raise SystemExit("Template must contain exactly one REPORT_DATA placeholder")
    if not rendered.lstrip().startswith("<!DOCTYPE html>"):
        raise SystemExit("Rendered report must start with <!DOCTYPE html>")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(str(output_path))


if __name__ == "__main__":
    main()
