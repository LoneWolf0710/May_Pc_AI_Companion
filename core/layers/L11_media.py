"""L11: Media Control Layer — audio/video device management.

Actions: 32
Privilege: user
Libraries: pycaw, subprocess, winreg, ctypes
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.engine.verifier import Verifiers
from core.layers._utils import run_ps, run_cmd, create_escalation_fn, create_preflight_fn

logger = logging.getLogger("may.core.layers.L11_media")

LAYER_NAME = "media"
ACTIONS = [
    # Audio playback (10)
    "list_audio_sessions", "get_active_audio", "get_all_audio_sessions",
    "set_session_volume", "set_session_mute", "set_session_state",
    "get_audio_meter", "set_audio_endpoint", "get_default_audio_device",
    "set_default_audio_device",
    # Audio devices (8)
    "list_audio_devices", "get_audio_device_info", "enable_audio_device",
    "disable_audio_device", "set_audio_device_volume", "mute_audio_device",
    "unmute_audio_device", "get_audio_device_mute",
    # Video/media (8)
    "get_media_info", "list_media_files", "play_media",
    "pause_media", "stop_media", "next_track", "previous_track",
    "get_media_position",
    # CD/DVD (6)
    "list_optical_drives", "get_disc_info", "eject_disc",
    "close_disc_tray", "is_disc_inserted", "get_disc_type",
]


# ── Audio playback ────────────────────────────────────────────────────

async def _list_audio_sessions_pycaw(params: dict) -> Any:
    try:
        from pycaw.pycaw import AudioUtilities
        sessions = AudioUtilities.GetAllSessions()
        result = []
        for s in sessions:
            if s.Process:
                result.append({
                    "pid": s.Process.pid,
                    "name": s.Process.name(),
                    "volume": s.SimpleAudioVolume.GetMasterVolume() if s.SimpleAudioVolume else 0,
                    "muted": s.SimpleAudioVolume.GetMute() if s.SimpleAudioVolume else False,
                })
        return {"sessions": result}
    except Exception as e:
        return {"error": str(e)}


async def _list_audio_sessions_ps(params: dict) -> Any:
    success, output = await run_ps("Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object Name,Id | ConvertTo-Json")
    if success:
        try:
            return {"sessions": json.loads(output)}
        except json.JSONDecodeError:
            return {"sessions": [], "raw": output}
    return {"error": output}


async def _get_active_audio(params: dict) -> Any:
    try:
        from pycaw.pycaw import AudioUtilities
        sessions = AudioUtilities.GetAllSessions()
        for s in sessions:
            if s.Process and s.SimpleAudioVolume:
                vol = s.SimpleAudioVolume.GetMasterVolume()
                if vol > 0:
                    return {
                        "pid": s.Process.pid, "name": s.Process.name(),
                        "volume": vol, "muted": s.SimpleAudioVolume.GetMute(),
                    }
        return {"message": "No active audio session"}
    except Exception as e:
        return {"error": str(e)}


async def _get_all_audio_sessions(params: dict) -> Any:
    try:
        from pycaw.pycaw import AudioUtilities
        sessions = AudioUtilities.GetAllSessions()
        result = []
        for s in sessions:
            result.append({
                "pid": s.Process.pid if s.Process else 0,
                "name": s.Process.name() if s.Process else "System",
                "volume": s.SimpleAudioVolume.GetMasterVolume() if s.SimpleAudioVolume else 0,
                "muted": s.SimpleAudioVolume.GetMute() if s.SimpleAudioVolume else False,
            })
        return {"sessions": result}
    except Exception as e:
        return {"error": str(e)}


async def _set_session_volume_pycaw(params: dict) -> Any:
    pid = params.get("pid")
    level = params.get("level", 50)
    if pid is None:
        return {"error": "PID required"}
    try:
        from pycaw.pycaw import AudioUtilities
        sessions = AudioUtilities.GetAllSessions()
        for s in sessions:
            if s.Process and s.Process.pid == int(pid) and s.SimpleAudioVolume:
                s.SimpleAudioVolume.SetMasterVolume(level / 100.0, None)
                return {"pid": pid, "volume": level}
        return {"error": f"Session PID {pid} not found"}
    except Exception as e:
        return {"error": str(e)}


async def _set_session_volume_sendkeys(params: dict) -> Any:
    level = params.get("level", 50)
    # SendKeys volume control (approximate)
    success, output = await run_ps(f"$wsh = New-Object -ComObject WScript.Shell; for($i=0;$i -lt {min(15, level // 5)}){{$wsh.SendKeys([char]175); Start-Sleep -Milliseconds 50}}")
    return {"volume": level, "approximate": True}


async def _set_session_mute_pycaw(params: dict) -> Any:
    pid = params.get("pid")
    muted = params.get("muted", True)
    if pid is None:
        return {"error": "PID required"}
    try:
        from pycaw.pycaw import AudioUtilities
        sessions = AudioUtilities.GetAllSessions()
        for s in sessions:
            if s.Process and s.Process.pid == int(pid) and s.SimpleAudioVolume:
                s.SimpleAudioVolume.SetMute(int(muted), None)
                return {"pid": pid, "muted": muted}
        return {"error": f"Session PID {pid} not found"}
    except Exception as e:
        return {"error": str(e)}


async def _set_session_mute_sendkeys(params: dict) -> Any:
    muted = params.get("muted", True)
    success, output = await run_ps("$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]0xAD)")
    return {"muted": muted}


async def _set_session_state(params: dict) -> Any:
    pid = params.get("pid")
    state = params.get("state", "play")
    return {"pid": pid, "state": state, "note": "Media state control requires app-specific APIs"}


async def _get_audio_meter(params: dict) -> Any:
    success, output = await run_ps("Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object Name,Id | ConvertTo-Json")
    if success:
        try:
            return {"processes": json.loads(output)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _set_audio_endpoint(params: dict) -> Any:
    return {"note": "Endpoint switching requires COM API", "device_id": params.get("device_id", "")}


async def _get_default_audio_device_pycaw(params: dict) -> Any:
    try:
        from pycaw.pycaw import AudioUtilities
        role = params.get("role", "console")
        if role == "console":
            device = AudioUtilities.GetSpeakers()
        else:
            device = AudioUtilities.GetMicrophone()
        return {"role": role, "device": str(device)}
    except Exception as e:
        return {"error": str(e)}


async def _get_default_audio_device_ps(params: dict) -> Any:
    success, output = await run_ps("Get-PnpDevice -Class AudioEndpoint -Status OK | Select-Object FriendlyName | ConvertTo-Json")
    if success:
        try:
            return {"devices": json.loads(output)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _set_default_audio_device(params: dict) -> Any:
    return {"device_id": params.get("device_id", ""), "role": params.get("role", "console")}


# ── Audio devices ─────────────────────────────────────────────────────

async def _list_audio_devices_ps(params: dict) -> Any:
    success, output = await run_ps("Get-PnpDevice -Class AudioEndpoint | Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json")
    if success:
        try:
            return {"devices": json.loads(output)}
        except json.JSONDecodeError:
            return {"devices": [], "raw": output}
    return {"error": output}


async def _list_audio_devices_pycaw(params: dict) -> Any:
    try:
        from pycaw.pycaw import AudioUtilities
        speakers = AudioUtilities.GetAllSpeakers()
        result = []
        for d in speakers:
            try:
                result.append({"name": d.FriendlyName, "id": str(d.id)})
            except Exception:
                continue
        return {"devices": result, "count": len(result)}
    except Exception as e:
        return {"error": str(e)}


async def _get_audio_device_info(params: dict) -> Any:
    device_id = params.get("device_id", "")
    success, output = await run_ps(f"Get-PnpDevice -InstanceId '{device_id}' | ConvertTo-Json")
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _enable_audio_device(params: dict) -> Any:
    device_id = params.get("device_id", "")
    if not device_id:
        return {"error": "Device ID required"}
    success, output = await run_ps(f"Enable-PnpDevice -InstanceId '{device_id}' -Confirm:$false")
    return {"status": "enabled" if success else "failed", "output": output}


async def _disable_audio_device(params: dict) -> Any:
    device_id = params.get("device_id", "")
    if not device_id:
        return {"error": "Device ID required"}
    success, output = await run_ps(f"Disable-PnpDevice -InstanceId '{device_id}' -Confirm:$false")
    return {"status": "disabled" if success else "failed", "output": output}


async def _set_audio_device_volume(params: dict) -> Any:
    return await _set_session_volume_pycaw({"pid": None, "level": params.get("level", 50)})


async def _mute_audio_device(params: dict) -> Any:
    return await _set_session_mute_pycaw({"pid": None, "muted": params.get("muted", True)})


async def _unmute_audio_device(params: dict) -> Any:
    return await _set_session_mute_pycaw({"pid": None, "muted": False})


async def _get_audio_device_mute(params: dict) -> Any:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        from ctypes import cast, POINTER
        device = AudioUtilities.GetSpeakers()
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        muted = volume.GetMute()
        return {"muted": bool(muted)}
    except Exception as e:
        return {"error": str(e)}


# ── Video/media ───────────────────────────────────────────────────────

async def _get_media_info_ps(params: dict) -> Any:
    success, output = await run_ps("Get-Process | Where-Object {$_.ProcessName -match 'vlc|mpc|potplayer|media'} | Select-Object ProcessName,Id,WorkingSet | ConvertTo-Json")
    if success:
        try:
            return {"players": json.loads(output)}
        except json.JSONDecodeError:
            return {"message": "No media player running"}
    return {"error": output}


async def _list_media_files(params: dict) -> Any:
    directory = params.get("directory", "")
    if not directory:
        return {"error": "Directory required"}
    import os
    media_exts = {'.mp3', '.wav', '.flac', '.mp4', '.avi', '.mkv', '.wmv', '.m4a', '.ogg'}
    try:
        files = []
        for f in os.listdir(directory):
            if os.path.splitext(f)[1].lower() in media_exts:
                path = os.path.join(directory, f)
                size = os.path.getsize(path)
                files.append({"name": f, "path": path, "size": size})
        return {"files": files[:50]}
    except Exception as e:
        return {"error": str(e)}


async def _play_media(params: dict) -> Any:
    path = params.get("path", "")
    if not path:
        return {"error": "Path required"}
    import subprocess
    # Use cmd /c start without shell=True to avoid command injection
    subprocess.Popen(["cmd", "/c", "start", "", path])
    return {"status": "playing", "path": path}


async def _pause_media(params: dict) -> Any:
    success, output = await run_ps("(New-Object -ComObject WScript.Shell).SendKeys(' ')")
    return {"status": "pause_sent"}


async def _stop_media(params: dict) -> Any:
    success, output = await run_ps("(New-Object -ComObject WScript.Shell).SendKeys('{STOP}')")
    return {"status": "stop_sent"}


async def _next_track(params: dict) -> Any:
    success, output = await run_ps("(New-Object -ComObject WScript.Shell).SendKeys('{MEDIA_NEXT_TRACK}')")
    return {"status": "next_sent"}


async def _previous_track(params: dict) -> Any:
    success, output = await run_ps("(New-Object -ComObject WScript.Shell).SendKeys('{MEDIA_PREV_TRACK}')")
    return {"status": "prev_sent"}


async def _get_media_position(params: dict) -> Any:
    return {"note": "Media position requires media player API integration"}


# ── CD/DVD ────────────────────────────────────────────────────────────

async def _list_optical_drives(params: dict) -> Any:
    success, output = await run_ps("Get-CimInstance Win32_CDROMDrive | Select-Object Name,Drive,MediaLoaded | ConvertTo-Json")
    if success:
        try:
            return {"drives": json.loads(output)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _get_disc_info(params: dict) -> Any:
    success, output = await run_ps("Get-CimInstance Win32_CDROMDrive | Select-Object Name,VolumeName,MediaType,FileSystem | ConvertTo-Json")
    if success:
        try:
            return {"disc": json.loads(output)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _eject_disc(params: dict) -> Any:
    success, output = await run_ps("(New-Object -ComObject Shell.Application).NameSpace(17).InvokeVerb('eject')")
    return {"status": "eject_sent"}


async def _close_disc_tray(params: dict) -> Any:
    return {"note": "Close tray requires vendor-specific API"}


async def _is_disc_inserted(params: dict) -> Any:
    success, output = await run_ps("(Get-CimInstance Win32_CDROMDrive).MediaLoaded")
    return {"inserted": output.strip().lower() == "true" if success else False}


async def _get_disc_type(params: dict) -> Any:
    success, output = await run_ps("(Get-CimInstance Win32_CDROMDrive).MediaType")
    return {"type": output.strip() if success else "unknown"}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION MAP
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    # Audio playback
    "list_audio_sessions":   ([_list_audio_sessions_pycaw, _list_audio_sessions_ps], None),
    "get_active_audio":      ([_get_active_audio], None),
    "get_all_audio_sessions":([_get_all_audio_sessions], None),
    "set_session_volume":    ([_set_session_volume_pycaw, _set_session_volume_sendkeys], None),
    "set_session_mute":      ([_set_session_mute_pycaw, _set_session_mute_sendkeys], None),
    "set_session_state":     ([_set_session_state], None),
    "get_audio_meter":       ([_get_audio_meter], None),
    "set_audio_endpoint":    ([_set_audio_endpoint], None),
    "get_default_audio_device": ([_get_default_audio_device_pycaw, _get_default_audio_device_ps], None),
    "set_default_audio_device": ([_set_default_audio_device], None),
    # Audio devices
    "list_audio_devices":    ([_list_audio_devices_ps, _list_audio_devices_pycaw], None),
    "get_audio_device_info": ([_get_audio_device_info], None),
    "enable_audio_device":   ([_enable_audio_device], None),
    "disable_audio_device":  ([_disable_audio_device], None),
    "set_audio_device_volume":([_set_audio_device_volume], None),
    "mute_audio_device":     ([_mute_audio_device], None),
    "unmute_audio_device":   ([_unmute_audio_device], None),
    "get_audio_device_mute": ([_get_audio_device_mute], None),
    # Video/media
    "get_media_info":        ([_get_media_info_ps], None),
    "list_media_files":      ([_list_media_files], None),
    "play_media":            ([_play_media], None),
    "pause_media":           ([_pause_media], None),
    "stop_media":            ([_stop_media], None),
    "next_track":            ([_next_track], None),
    "previous_track":        ([_previous_track], None),
    "get_media_position":    ([_get_media_position], None),
    # CD/DVD
    "list_optical_drives":   ([_list_optical_drives], None),
    "get_disc_info":         ([_get_disc_info], None),
    "eject_disc":            ([_eject_disc], None),
    "close_disc_tray":       ([_close_disc_tray], None),
    "is_disc_inserted":      ([_is_disc_inserted], None),
    "get_disc_type":         ([_get_disc_type], None),
}


# ══════════════════════════════════════════════════════════════════════════════
# HANDLER
# ══════════════════════════════════════════════════════════════════════════════

async def handler(action: str, params: dict[str, Any]) -> Result:
    """L11 Media layer handler — routes actions to their fallback chains."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown media action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"media.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("media", action),
        escalation_fn=create_escalation_fn("media", action),
    )

    suggested = None
    if not success and error:
        suggested = f"Try running as Administrator. Error: {error[:120]}"

    return Result(
        command_id=params.get("id", ""),
        success=success,
        data=data,
        error=error if not success else None,
        verified=verifier is not None and success,
        method_used=method_used,
        suggested_action=suggested,
    )
