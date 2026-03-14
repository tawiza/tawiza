"""Camel AI Tools for analysis and report generation.

Tools for synthesizing data and generating multi-format reports.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from camel.toolkits import FunctionTool
from loguru import logger


def generate_report(
    title: str,
    sections: list[dict[str, Any]],
    output_dir: str = "./outputs/analyses",
    formats: list[str] = None,
) -> dict[str, Any]:
    """Generate a structured report in multiple formats.

    Args:
        title: Report title
        sections: List of section dicts with 'title' and 'content' keys
        output_dir: Directory to save the report
        formats: List of formats to generate ('md', 'json', 'csv')

    Returns:
        Dictionary with:
        - success: Boolean
        - files: List of generated file paths
        - report_dir: Directory containing all files
    """
    # Create output directory with timestamp
    if formats is None:
        formats = ["md"]
    timestamp = datetime.now().strftime("%Y-%m-%d")
    slug = title.lower().replace(" ", "-")[:50]
    report_dir = Path(output_dir) / f"{timestamp}_{slug}"
    report_dir.mkdir(parents=True, exist_ok=True)

    generated_files = []

    # Generate Markdown
    if "md" in formats:
        md_content = f"# {title}\n\n"
        md_content += f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        md_content += "---\n\n"

        for section in sections:
            md_content += f"## {section.get('title', 'Section')}\n\n"
            content = section.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        md_content += (
                            f"- **{item.get('name', 'Item')}**: {item.get('description', '')}\n"
                        )
                    else:
                        md_content += f"- {item}\n"
            else:
                md_content += f"{content}\n"
            md_content += "\n"

        md_file = report_dir / "rapport.md"
        md_file.write_text(md_content, encoding="utf-8")
        generated_files.append(str(md_file))
        logger.info(f"Generated markdown report: {md_file}")

    # Generate JSON
    if "json" in formats:
        json_data = {
            "title": title,
            "date": datetime.now().isoformat(),
            "sections": sections,
        }
        json_file = report_dir / "data.json"
        json_file.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")
        generated_files.append(str(json_file))
        logger.info(f"Generated JSON data: {json_file}")

    # Generate metadata
    metadata = {
        "title": title,
        "generated_at": datetime.now().isoformat(),
        "formats": formats,
        "sections_count": len(sections),
        "files": [str(f) for f in generated_files],
    }
    meta_file = report_dir / "metadata.json"
    meta_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return {
        "success": True,
        "files": generated_files,
        "report_dir": str(report_dir),
        "metadata": metadata,
    }


def export_csv(
    data: list[dict[str, Any]], filename: str, output_dir: str = "./outputs/analyses"
) -> dict[str, Any]:
    """Export data to CSV format.

    Args:
        data: List of dictionaries to export
        filename: Output filename (without extension)
        output_dir: Directory to save the file

    Returns:
        Dictionary with:
        - success: Boolean
        - file_path: Path to generated CSV
        - rows: Number of rows exported
    """
    import csv

    if not data:
        return {"success": False, "error": "No data to export"}

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    csv_file = output_path / f"{filename}.csv"

    # Get all unique keys from data
    all_keys = set()
    for item in data:
        all_keys.update(item.keys())
    headers = sorted(all_keys)

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in data:
            # Flatten nested dicts
            flat_row = {}
            for key in headers:
                value = row.get(key, "")
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                flat_row[key] = value
            writer.writerow(flat_row)

    logger.info(f"Exported {len(data)} rows to CSV: {csv_file}")

    return {
        "success": True,
        "file_path": str(csv_file),
        "rows": len(data),
    }


def analyze_data(data: list[dict[str, Any]], analysis_type: str = "summary") -> dict[str, Any]:
    """Perform basic analysis on structured data.

    Args:
        data: List of dictionaries to analyze
        analysis_type: Type of analysis ('summary', 'distribution', 'top_n')

    Returns:
        Dictionary with analysis results depending on type
    """
    if not data:
        return {"success": False, "error": "No data to analyze"}

    result = {
        "success": True,
        "total_records": len(data),
        "analysis_type": analysis_type,
    }

    if analysis_type == "summary":
        # Basic statistics
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())

        result["fields"] = list(all_keys)
        result["field_coverage"] = {}
        for key in all_keys:
            non_null = sum(1 for item in data if item.get(key) is not None)
            result["field_coverage"][key] = f"{non_null}/{len(data)}"

    elif analysis_type == "distribution":
        # Distribution of categorical fields
        distributions = {}
        for key in data[0].keys() if data else []:
            values = [item.get(key) for item in data if item.get(key)]
            if values and all(isinstance(v, str) for v in values):
                # Count occurrences
                from collections import Counter

                counts = Counter(values)
                distributions[key] = dict(counts.most_common(10))
        result["distributions"] = distributions

    return result


# ============================================================================
# TOOL REGISTRATION
# ============================================================================


def get_analysis_tools() -> list[FunctionTool]:
    """Get all analysis tools as Camel FunctionTools.

    Returns:
        List of FunctionTool instances ready for use with Camel agents
    """
    tools = [
        FunctionTool(generate_report),
        FunctionTool(export_csv),
        FunctionTool(analyze_data),
    ]

    logger.debug(f"Registered {len(tools)} analysis tools for Camel AI")
    return tools


# Convenience exports
ANALYSIS_TOOLS = get_analysis_tools()
