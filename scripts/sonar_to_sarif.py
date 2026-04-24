# Copyright (c) 2026 John Carter. All rights reserved.
"""Convert SonarCloud issues JSON to SARIF 2.1.0 for GitHub Security tab upload.

Usage:
    python scripts/sonar_to_sarif.py <issues.json> <output.sarif>

The issues.json must be the response body from:
    GET https://sonarcloud.io/api/issues/search?projectKeys=<key>&resolved=false&ps=500
"""

from __future__ import annotations

import json
import sys

_SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
)

_SEVERITY_MAP: dict[str, str] = {
    "BLOCKER": "error",
    "CRITICAL": "error",
    "MAJOR": "warning",
    "MINOR": "note",
    "INFO": "note",
}


def convert(issues_data: dict[str, object], project_key: str) -> dict[str, object]:
    """Convert a SonarCloud issues API response to a SARIF 2.1.0 document."""
    rules: dict[str, dict[str, object]] = {}
    results: list[dict[str, object]] = []

    for issue in issues_data.get("issues", []):  # type: ignore[union-attr]
        rule_id: str = issue.get("rule", "unknown")  # type: ignore[assignment]
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": str(issue.get("message", rule_id))},
            }

        component: str = str(issue.get("component", ""))
        prefix = f"{project_key}:"
        if component.startswith(prefix):
            component = component[len(prefix) :]

        line: int = int(issue.get("line", 1) or 1)

        results.append(
            {
                "ruleId": rule_id,
                "level": _SEVERITY_MAP.get(str(issue.get("severity", "MAJOR")), "warning"),
                "message": {"text": str(issue.get("message", ""))},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": component,
                                "uriBaseId": "%SRCROOT%",
                            },
                            "region": {"startLine": line},
                        }
                    }
                ],
            }
        )

    return {
        "$schema": _SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "SonarCloud",
                        "informationUri": "https://sonarcloud.io",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <issues.json> <output.sarif>", file=sys.stderr)
        sys.exit(1)

    issues_path, sarif_path = sys.argv[1], sys.argv[2]

    with open(issues_path) as f:
        issues_data: dict[str, object] = json.load(f)

    # Infer project key from the first issue's component, e.g. "org_repo:src/..."
    project_key = "warlordofmars_hive"
    issues_list = issues_data.get("issues", [])
    if issues_list:
        first_component: str = str(issues_list[0].get("component", ""))  # type: ignore[union-attr]
        if ":" in first_component:
            project_key = first_component.split(":")[0]

    sarif = convert(issues_data, project_key)

    with open(sarif_path, "w") as f:
        json.dump(sarif, f, indent=2)

    n = len(sarif["runs"][0]["results"])  # type: ignore[index]
    print(f"Wrote {n} SonarCloud issues to {sarif_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
