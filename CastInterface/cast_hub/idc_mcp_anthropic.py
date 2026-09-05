"""IDC cohort search via Anthropic Messages API MCP connector."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cast_hub")

IDC_MCP_SERVER_NAME = "idc"
MCP_BETA = "mcp-client-2025-11-20"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_IDC_MCP_URL = "https://api.imaging.datacommons.cancer.gov/mcp"

SYSTEM_PROMPT = """You help users query the Imaging Data Commons (IDC) using IDC MCP tools.
Ground filter values with list_attributes / get_attribute_values when unsure.
Prefer build_cohort for attribute filters; use run_sql only when cohort filters are insufficient.
After you have results, your final reply must be ONLY a JSON object (no markdown fences) with:
- series: array of series or study records. Prefer one object per series with these
  IDC field names when available from tool output:
  SeriesInstanceUID, StudyInstanceUID, PatientID, collection_id, Modality,
  SeriesDescription, series_aws_url, crdc_series_uuid, aws_bucket, instanceCount,
  series_size_MB. Do not rename these keys. Copy values verbatim from MCP tool
  results — do not drop SeriesInstanceUID, StudyInstanceUID, series_aws_url, or
  crdc_series_uuid. If only studies are known, still include StudyInstanceUID on
  each object so the client can expand to series via the IDC REST manifest.
- sql: optional SQL string if run_sql was used
- citation: optional citation text
Include at most {max_rows} series in the series array.
"""


def anthropic_configured() -> bool:
    return bool(str(os.getenv("ANTHROPIC_API_KEY") or "").strip())


def env_anthropic_model() -> str:
    raw = os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
    return str(raw or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def env_idc_mcp_upstream_url() -> str:
    raw = os.getenv("CAST_HUB_IDC_MCP_UPSTREAM_URL", DEFAULT_IDC_MCP_URL)
    return str(raw or DEFAULT_IDC_MCP_URL).strip().rstrip("/")


def _parse_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    raw = str(text or "").strip()
    if not raw:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    if raw.startswith("{") and raw.endswith("}"):
        try:
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            payload = json.loads(raw[start : end + 1])
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _coerce_series_payload(data: Any) -> List[Dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    series = data.get("series")
    if isinstance(series, list):
        return [row for row in series if isinstance(row, dict)]
    rows = data.get("rows")
    columns = data.get("columns")
    if not isinstance(rows, list) or not isinstance(columns, list):
        return []
    col_names: List[str] = []
    for col in columns:
        if isinstance(col, dict):
            col_names.append(str(col.get("name") or ""))
        else:
            col_names.append(str(col or ""))
    out: List[Dict[str, Any]] = []
    for row in rows:
        record: Dict[str, Any] = {}
        if isinstance(row, list):
            for idx, name in enumerate(col_names):
                if name and idx < len(row):
                    record[name] = row[idx]
        elif isinstance(row, dict):
            record.update(row)
        if record:
            out.append(record)
    return out


_LAUNCH_FIELD_KEYS = (
    "SeriesInstanceUID",
    "seriesInstanceUID",
    "series_uid",
    "series_aws_url",
    "seriesAwsUrl",
    "aws_url",
    "awsUrl",
    "seriesUrl",
    "series_url",
    "crdc_series_uuid",
    "crdcSeriesUuid",
    "crdc_uuid",
    "crdcUuid",
)


def _row_has_launch_fields(row: Dict[str, Any]) -> bool:
    for key in _LAUNCH_FIELD_KEYS:
        value = row.get(key)
        if value is not None and str(value).strip():
            return True
    return False


def _count_launchable_series(rows: List[Dict[str, Any]]) -> int:
    return sum(1 for row in rows if _row_has_launch_fields(row))


def _select_series_payload(
    tool_series: List[Dict[str, Any]],
    text_series: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Prefer MCP tool rows with launch fields over thin Anthropic summary JSON."""
    tool_ok = _count_launchable_series(tool_series)
    text_ok = _count_launchable_series(text_series)
    if tool_ok and tool_ok >= text_ok:
        return tool_series
    if text_ok:
        return text_series
    return tool_series or text_series


def _block_type(block: Any) -> str:
    if isinstance(block, dict):
        return str(block.get("type") or "")
    return str(getattr(block, "type", "") or "")


def _block_get(block: Any, key: str, default=None):
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


def _extract_search_result(response: Any) -> Dict[str, Any]:
    tool_series: List[Dict[str, Any]] = []
    text_series: List[Dict[str, Any]] = []
    sql = ""
    citation = ""
    text_parts: List[str] = []
    tool_names: List[str] = []

    for block in _block_get(response, "content", []) or []:
        block_type = _block_type(block)
        if block_type == "mcp_tool_use":
            name = _block_get(block, "name")
            if name:
                tool_names.append(str(name))
            continue
        if block_type == "mcp_tool_result":
            for part in _block_get(block, "content", []) or []:
                part_text = _block_get(part, "text")
                if not part_text:
                    continue
                try:
                    parsed = json.loads(str(part_text))
                except json.JSONDecodeError:
                    continue
                found = _coerce_series_payload(parsed)
                if found:
                    tool_series = found
                if isinstance(parsed, dict):
                    if parsed.get("sql"):
                        sql = str(parsed["sql"])
                    if parsed.get("citation"):
                        citation = str(parsed["citation"])
            continue
        if block_type == "text":
            text = str(_block_get(block, "text") or "")
            if not text:
                continue
            text_parts.append(text)
            parsed = _parse_json_from_text(text)
            if not parsed:
                continue
            found = _coerce_series_payload(parsed)
            if found:
                text_series = found
            if parsed.get("sql"):
                sql = str(parsed.get("sql") or sql)
            if parsed.get("citation"):
                citation = str(parsed.get("citation") or citation)

    series = _select_series_payload(tool_series, text_series)
    return {
        "series": series,
        "sql": sql,
        "citation": citation,
        "text": "\n".join(text_parts).strip(),
        "toolName": tool_names[-1] if tool_names else "anthropic",
    }


def search_idc_via_anthropic(prompt: str, max_rows: int = 20) -> Dict[str, Any]:
    """Run IDC MCP tools through Anthropic's MCP connector (sync; use to_thread in hub)."""
    api_key = str(os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured on the Cast hub"
        )

    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "anthropic package is not installed on the Cast hub"
        ) from exc

    user_prompt = str(prompt or "").strip()
    if not user_prompt:
        raise ValueError("prompt is required")

    capped_rows = max(1, min(int(max_rows or 20), 100))
    idc_url = env_idc_mcp_upstream_url()
    client = anthropic.Anthropic(api_key=api_key)

    logger.info(
        "idc-mcp anthropic search prompt_len=%d max_rows=%d idc_url=%s",
        len(user_prompt),
        capped_rows,
        idc_url,
    )

    response = client.beta.messages.create(
        model=env_anthropic_model(),
        max_tokens=4096,
        betas=[MCP_BETA],
        system=SYSTEM_PROMPT.format(max_rows=capped_rows),
        messages=[{"role": "user", "content": user_prompt}],
        mcp_servers=[
            {
                "type": "url",
                "url": idc_url,
                "name": IDC_MCP_SERVER_NAME,
            }
        ],
        tools=[
            {
                "type": "mcp_toolset",
                "mcp_server_name": IDC_MCP_SERVER_NAME,
            }
        ],
    )

    result = _extract_search_result(response)
    if capped_rows and len(result["series"]) > capped_rows:
        result["series"] = result["series"][:capped_rows]

    logger.info(
        "idc-mcp anthropic search done series=%d tool=%s",
        len(result["series"]),
        result.get("toolName"),
    )
    return result
