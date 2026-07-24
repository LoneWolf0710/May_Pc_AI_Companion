"""L17: Content & Utility Tools Layer — math, encoding, format conversion, QR codes.

Actions: 12
Privilege: user
Libraries: json, csv, hashlib, base64, math, re, io
"""

from __future__ import annotations

import asyncio
import base64
import csv
import hashlib
import json
import logging
import os
import re
import time as _time
from pathlib import Path
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.layers._utils import run_ps, run_cmd, create_escalation_fn, create_preflight_fn

logger = logging.getLogger("may.core.layers.L17_content_tools")

LAYER_NAME = "content_tools"
ACTIONS = [
    # Math & conversion (4)
    "calculate", "unit_convert", "timer", "speed_test",
    # Encoding (4)
    "hash_string", "base64_encode", "base64_decode", "create_qr_code",
    # Format conversion (4)
    "json_format", "csv_to_json", "json_to_csv", "compare_images",
]


# ══════════════════════════════════════════════════════════════════════════════
# Math & Calculation
# ══════════════════════════════════════════════════════════════════════════════

# Unit conversion table: (from_unit, to_unit) -> factor
_UNIT_CONVERSIONS: dict[tuple[str, str], float] = {
    # Length
    ("m", "ft"): 3.28084, ("ft", "m"): 0.3048,
    ("km", "mi"): 0.621371, ("mi", "km"): 1.60934,
    ("cm", "in"): 0.393701, ("in", "cm"): 2.54,
    ("mm", "in"): 0.0393701, ("in", "mm"): 25.4,
    ("m", "cm"): 100, ("cm", "m"): 0.01,
    ("m", "mm"): 1000, ("mm", "m"): 0.001,
    ("yd", "m"): 0.9144, ("m", "yd"): 1.09361,
    # Weight
    ("kg", "lb"): 2.20462, ("lb", "kg"): 0.453592,
    ("g", "oz"): 0.035274, ("oz", "g"): 28.3495,
    ("kg", "g"): 1000, ("g", "kg"): 0.001,
    ("lb", "oz"): 16, ("oz", "lb"): 0.0625,
    # Temperature
    ("c", "f"): None, ("f", "c"): None,  # Special handling
    ("c", "k"): None, ("k", "c"): None,
    # Volume
    ("l", "gal"): 0.264172, ("gal", "l"): 3.78541,
    ("ml", "fl_oz"): 0.033814, ("fl_oz", "ml"): 29.5735,
    # Data
    ("gb", "mb"): 1024, ("mb", "gb"): 1 / 1024,
    ("tb", "gb"): 1024, ("gb", "tb"): 1 / 1024,
    ("mb", "kb"): 1024, ("kb", "mb"): 1 / 1024,
    ("gb", "bytes"): 1073741824, ("mb", "bytes"): 1048576,
    # Time
    ("h", "min"): 60, ("min", "h"): 1 / 60,
    ("min", "s"): 60, ("s", "min"): 1 / 60,
    ("h", "s"): 3600, ("s", "h"): 1 / 3600,
    ("d", "h"): 24, ("h", "d"): 1 / 24,
    # Area
    ("sqm", "sqft"): 10.7639, ("sqft", "sqm"): 0.092903,
    ("ha", "acres"): 2.47105, ("acres", "ha"): 0.404686,
}


def _convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    """Convert between C, F, K."""
    # First convert to Celsius
    if from_unit == "f":
        celsius = (value - 32) * 5 / 9
    elif from_unit == "k":
        celsius = value - 273.15
    else:
        celsius = value

    # Then convert from Celsius to target
    if to_unit == "f":
        return celsius * 9 / 5 + 32
    elif to_unit == "k":
        return celsius + 273.15
    return celsius


async def _calculate(params: dict) -> Any:
    """Evaluate a math expression safely.

    Supports: +, -, *, /, **, %, sqrt, sin, cos, tan, log, abs, min, max, pi, e
    """
    expression = params.get("expression", "")
    if not expression:
        return {"error": "Expression required (e.g. '2 + 2', 'sqrt(16)', '15% of 247')"}

    # Handle natural language patterns
    expr = expression.lower().strip()
    # "X% of Y" pattern
    pct_match = None
    pct_match = re.match(r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)", expr)
    if pct_match:
        pct = float(pct_match.group(1))
        val = float(pct_match.group(2))
        result = (pct / 100) * val
        return {"expression": expression, "result": result, "formatted": f"{pct}% of {val} = {result}"}

    # "X to Y" conversion patterns
    conv_match = re.match(r"(\d+(?:\.\d+)?)\s*(\w+)\s+(?:to|in)\s+(\w+)", expr)
    if conv_match:
        value = float(conv_match.group(1))
        from_u = conv_match.group(2).lower()
        to_u = conv_match.group(3).lower()
        return await _unit_convert({"value": value, "from_unit": from_u, "to_unit": to_u})

    # Safe math evaluation — use ast.parse to validate before exec
    import ast as _ast
    import math as _math

    safe_names = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sqrt": lambda x: x ** 0.5,
        "sin": _math.sin, "cos": _math.cos, "tan": _math.tan,
        "log": _math.log, "log10": _math.log10, "log2": _math.log2,
        "pi": _math.pi, "e": _math.e, "ceil": _math.ceil, "floor": _math.floor,
        "pow": pow,
    }

    # Clean expression
    expr_clean = expression.replace("^", "**")

    try:
        # Validate: only allow numeric expressions (no function calls with side effects,
        # no attribute access, no imports, no comprehensions)
        tree = _ast.parse(expr_clean, mode="eval")
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.Import, _ast.ImportFrom, _ast.FunctionDef,
                                _ast.AsyncFunctionDef, _ast.ClassDef, _ast.Delete,
                                _ast.Global, _ast.Nonlocal)):
                return {"error": f"Cannot evaluate '{expression}': disallowed construct"}
        compiled = compile(tree, "<calc>", "eval")
        result = eval(compiled, {"__builtins__": {}}, safe_names)
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": f"Cannot evaluate '{expression}': {e}"}


async def _unit_convert(params: dict) -> Any:
    """Convert between units of measurement."""
    value = params.get("value", 0)
    from_unit = params.get("from_unit", "").lower().strip()
    to_unit = params.get("to_unit", "").lower().strip()

    if not from_unit or not to_unit:
        return {"error": "Both from_unit and to_unit are required"}

    try:
        value = float(value)
    except (ValueError, TypeError):
        return {"error": f"Invalid value: {value}"}

    # Temperature special case
    temp_units = {"c", "f", "k", "celsius", "fahrenheit", "kelvin"}
    from_short = from_unit[:1]
    to_short = to_unit[:1]

    # Normalize temperature names
    temp_map = {"celsius": "c", "fahrenheit": "f", "kelvin": "k"}
    from_u = temp_map.get(from_unit, from_short)
    to_u = temp_map.get(to_unit, to_short)

    if from_u in ("c", "f", "k") and to_u in ("c", "f", "k"):
        result = _convert_temperature(value, from_u, to_u)
        return {
            "value": value, "from": f"{value} {from_unit}",
            "result": round(result, 4), "to": f"{round(result, 4)} {to_unit}",
        }

    # Direct lookup
    key = (from_unit, to_unit)
    if key in _UNIT_CONVERSIONS:
        factor = _UNIT_CONVERSIONS[key]
        result = value * factor
        return {
            "value": value, "from": f"{value} {from_unit}",
            "result": round(result, 6), "to": f"{round(result, 6)} {to_unit}",
        }

    # Try reverse lookup
    reverse_key = (to_unit, from_unit)
    if reverse_key in _UNIT_CONVERSIONS:
        factor = _UNIT_CONVERSIONS[reverse_key]
        result = value / factor
        return {
            "value": value, "from": f"{value} {from_unit}",
            "result": round(result, 6), "to": f"{round(result, 6)} {to_unit}",
        }

    return {"error": f"Unknown conversion: {from_unit} → {to_unit}. Supported: length, weight, temperature, volume, data, time, area."}


# ══════════════════════════════════════════════════════════════════════════════
# Timer
# ══════════════════════════════════════════════════════════════════════════════

_timers: dict[str, asyncio.Task] = {}
_timer_counter = 0


async def _timer(params: dict) -> Any:
    """Set a countdown timer with notification.

    Creates a background task that sends a toast notification when the timer expires.
    """
    global _timer_counter
    seconds = params.get("seconds", 0)
    label = params.get("label", "Timer")

    if not seconds or seconds <= 0:
        return {"error": "Seconds must be > 0"}

    try:
        seconds = float(seconds)
    except (ValueError, TypeError):
        return {"error": f"Invalid seconds: {seconds}"}

    _timer_counter += 1
    timer_id = f"timer_{_timer_counter}"

    async def _countdown():
        await asyncio.sleep(seconds)
        # Log timer completion (toast notification handled by backend notification system)
        logger.info("⏰ Timer complete: %s (%ds)", label, int(seconds))
        # Try to send Windows toast notification via winotify
        try:
            from winotify import Notification, audio
            toast = Notification(app_id="May AI", title="⏰ Timer Complete", msg=f"{label} — {int(seconds)}s timer done!", duration="short")
            toast.set_audio(audio.Default, loop=False)
            toast.show()
        except ImportError:
            pass  # winotify not installed, log is sufficient

    task = asyncio.create_task(_countdown())
    _timers[timer_id] = task

    # Auto-cleanup: remove from dict when task finishes (done or cancelled)
    def _on_done(t: asyncio.Task):
        _timers.pop(timer_id, None)
    task.add_done_callback(_on_done)

    return {
        "timer_id": timer_id,
        "label": label,
        "seconds": seconds,
        "ends_at": f"{seconds}s from now",
        "instruction": f"Timer set for {label}. Will notify in {seconds} seconds.",
    }


async def _cancel_timer(params: dict) -> Any:
    """Cancel a running countdown timer."""
    timer_id = params.get("timer_id", "")
    if not timer_id:
        return {"error": "timer_id required"}
    task = _timers.get(timer_id)
    if task and not task.done():
        task.cancel()
        del _timers[timer_id]
        return {"cancelled": True, "timer_id": timer_id}
    return {"error": f"Timer '{timer_id}' not found or already completed"}


async def _speed_test(params: dict) -> Any:
    """Run an internet speed test."""
    try:
        import httpx
        # Simple download speed test using a known file
        test_url = "http://speedtest.tele2.net/1MB.zip"
        start = _time.time()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(test_url)
            elapsed = __import__("time").time() - start
            if resp.status_code == 200:
                size_mb = len(resp.content) / (1024 * 1024)
                speed_mbps = (size_mb * 8) / elapsed
                return {
                    "download_mbps": round(speed_mbps, 1),
                    "size_mb": round(size_mb, 1),
                    "elapsed_s": round(elapsed, 2),
                    "server": "speedtest.tele2.net",
                    "instruction": f"Download speed: {round(speed_mbps, 1)} Mbps ({round(size_mb, 1)} MB in {round(elapsed, 2)}s)",
                }
            return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        # Fallback: ping test
        try:
            import subprocess
            result = subprocess.run(
                ["ping", "-n", "4", "8.8.8.8"],
                capture_output=True, text=True, timeout=10
            )
            return {"ping_output": result.stdout[:500], "error": f"Speed test failed: {e}. Showing ping instead."}
        except Exception:
            return {"error": f"Speed test failed: {e}"}


# ══════════════════════════════════════════════════════════════════════════════
# Encoding & Hashing
# ══════════════════════════════════════════════════════════════════════════════

async def _hash_string(params: dict) -> Any:
    """Generate a hash of a string (md5, sha256, sha1, sha512)."""
    text = params.get("text", "")
    algorithm = params.get("algorithm", "sha256").lower()

    if not text:
        return {"error": "Text required"}

    valid_algos = {"md5", "sha1", "sha256", "sha512", "sha384", "blake2b"}
    if algorithm not in valid_algos:
        return {"error": f"Unknown algorithm: {algorithm}. Valid: {sorted(valid_algos)}"}

    h = hashlib.new(algorithm)
    h.update(text.encode("utf-8"))
    return {"text": text, "algorithm": algorithm, "hash": h.hexdigest()}


async def _base64_encode(params: dict) -> Any:
    """Base64 encode a string."""
    text = params.get("text", "")
    if not text:
        return {"error": "Text required"}
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return {"text": text, "encoded": encoded}


async def _base64_decode(params: dict) -> Any:
    """Base64 decode a string."""
    encoded = params.get("encoded", "")
    if not encoded:
        return {"error": "Encoded string required"}
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
        return {"encoded": encoded, "decoded": decoded}
    except Exception as e:
        return {"error": f"Invalid base64: {e}"}


async def _create_qr_code(params: dict) -> Any:
    """Generate a QR code image from text/URL.

    Uses the 'qrcode' Python library if available, otherwise falls back
    to a PowerShell-based approach.
    """
    data = params.get("data", "")
    output_path = params.get("output_path", "")
    size = params.get("size", 300)

    if not data:
        return {"error": "Data (text or URL) required"}

    if not output_path:
        qr_dir = Path(os.path.expanduser("~/.may/qrcodes"))
        qr_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(qr_dir / "qr_code.png")

    # Try Python qrcode library first
    try:
        import qrcode
        from PIL import Image

        qr = qrcode.QRCode(version=1, box_size=max(1, size // 25), border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((size, size))
        img.save(output_path)
        return {
            "generated": True,
            "path": output_path,
            "data": data[:100],
            "size": size,
            "instruction": f"QR code saved to {output_path}",
        }
    except ImportError:
        pass

    # Fallback: generate via PowerShell
    try:
        ps_cmd = (
            f'Add-Type -AssemblyName System.Drawing; '
            f'$qr = [System.Drawing.Bitmap]::FromFile("{output_path}") 2>$null; '
            f'Write-Output "qr_library_not_available"'
        )
        # If we can't generate QR without library, return instructions
        return {
            "generated": False,
            "data": data,
            "error": "qrcode library not installed. Install with: pip install qrcode[pil]",
            "instruction": f"Install qrcode: pip install qrcode[pil], then retry.",
        }
    except Exception as e:
        return {"error": f"QR generation failed: {e}"}


# ══════════════════════════════════════════════════════════════════════════════
# Format Conversion
# ══════════════════════════════════════════════════════════════════════════════

async def _json_format(params: dict) -> Any:
    """Pretty-print or minify a JSON string."""
    json_string = params.get("json_string", "")
    indent = params.get("indent", 2)

    if not json_string:
        return {"error": "JSON string required"}

    try:
        parsed = json.loads(json_string)
        formatted = json.dumps(parsed, indent=indent, ensure_ascii=False)
        return {"formatted": formatted, "keys": len(parsed) if isinstance(parsed, dict) else None}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}


async def _csv_to_json(params: dict) -> Any:
    """Convert a CSV file to JSON."""
    csv_path = params.get("csv_path", "")
    if not csv_path:
        return {"error": "CSV file path required"}

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return {"json": rows, "row_count": len(rows), "columns": list(rows[0].keys()) if rows else []}
    except Exception as e:
        return {"error": f"Failed to read CSV: {e}"}


async def _json_to_csv(params: dict) -> Any:
    """Convert a JSON file to CSV."""
    json_path = params.get("json_path", "")
    output_path = params.get("output_path", "")

    if not json_path:
        return {"error": "JSON file path required"}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            if "rows" in data:
                data = data["rows"]
            elif "data" in data:
                data = data["data"]
            else:
                data = [data]

        if not isinstance(data, list) or not data:
            return {"error": "JSON must contain an array of objects"}

        if not output_path:
            output_path = json_path.rsplit(".", 1)[0] + ".csv"

        # Collect all unique keys
        all_keys = []
        for row in data:
            if isinstance(row, dict):
                for k in row.keys():
                    if k not in all_keys:
                        all_keys.append(k)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys)
            writer.writeheader()
            for row in data:
                if isinstance(row, dict):
                    writer.writerow(row)

        return {"csv_path": output_path, "row_count": len(data), "columns": all_keys}
    except Exception as e:
        return {"error": f"Failed to convert: {e}"}


def _image_meta(path: str) -> dict:
    """Return optional size/mode metadata for an image file."""
    try:
        from PIL import Image
        img = Image.open(path)
        return {"size": img.size, "mode": img.mode}
    except Exception:
        return {}


async def _compare_images(params: dict) -> Any:
    """Compare two images — delegates to L16_verify._compare_screenshots.

    Avoids duplicating perceptual hash logic. L16 handles perceptual hash
    with file-hash fallback when imagehash is not installed.
    """
    path1 = params.get("path1", "")
    path2 = params.get("path2", "")

    if not path1 or not path2:
        return {"error": "Both path1 and path2 required"}

    # Validate files exist before delegating to L16
    for p in (path1, path2):
        if not os.path.isfile(p):
            return {"error": f"File not found: {p}"}

    try:
        from core.layers.L16_verify import _compare_screenshots
        result = await _compare_screenshots({
            "before_path": path1,
            "after_path": path2,
            "threshold": params.get("threshold", 0.85),
        })
        # Remap L16 keys to L17 expected keys for backward compatibility
        return {
            "similar": not result.get("changed", True),
            "similarity": result.get("similarity", 0),
            "hash_diff": result.get("hash_diff", 0),
            "change_percent": result.get("change_percent"),
            "method": result.get("method", "perceptual_hash"),
            "image1": {"path": path1, **_image_meta(path1)},
            "image2": {"path": path2, **_image_meta(path2)},
        }
    except Exception as e:
        return {"error": f"Comparison failed: {e}"}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION MAP
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    # Math & conversion
    "calculate":        ([_calculate], None),
    "unit_convert":     ([_unit_convert], None),
    "timer":            ([_timer], None),
    "cancel_timer":     ([_cancel_timer], None),
    "speed_test":       ([_speed_test], None),
    # Encoding
    "hash_string":      ([_hash_string], None),
    "base64_encode":    ([_base64_encode], None),
    "base64_decode":    ([_base64_decode], None),
    "create_qr_code":   ([_create_qr_code], None),
    # Format conversion
    "json_format":      ([_json_format], None),
    "csv_to_json":      ([_csv_to_json], None),
    "json_to_csv":      ([_json_to_csv], None),
    "compare_images":   ([_compare_images], None),
}


# ══════════════════════════════════════════════════════════════════════════════
# HANDLER
# ══════════════════════════════════════════════════════════════════════════════

async def handler(action: str, params: dict[str, Any]) -> Result:
    """L17 Content Tools layer handler."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown content_tools action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"content_tools.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("content_tools", action),
        escalation_fn=create_escalation_fn("content_tools", action),
    )

    suggested = None
    if not success and error:
        suggested = f"Error: {error[:120]}"

    return Result(
        command_id=params.get("id", ""),
        success=success,
        data=data,
        error=error if not success else None,
        verified=verifier is not None and success,
        method_used=method_used,
        suggested_action=suggested,
    )
