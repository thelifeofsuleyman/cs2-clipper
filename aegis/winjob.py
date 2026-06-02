"""Windows Job Object that kills child processes when the app dies.

Why this exists: the built-in recorder spawns ffmpeg as a child process. On
Windows a child does NOT die when its parent is killed — so a crash, a Task
Manager "End task", or a self-update that exits abruptly would leave ffmpeg
running forever (still recording the screen, still locking the bundled
ffmpeg.exe so an update installer can't replace it).

Assigning ffmpeg to a Job Object created with KILL_ON_JOB_CLOSE means the OS
terminates it the instant our process exits for ANY reason, because closing our
last handle to the job triggers the kill. Pure ctypes — no extra dependency, and
a no-op on non-Windows.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from .log import log

_JobObjectExtendedLimitInformation = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

_job = None
_tried = False


class _BASIC_LIMIT(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
        ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.POINTER(wintypes.ULONG)),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _EXTENDED_LIMIT(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BASIC_LIMIT),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _get_job():
    """Lazily create the kill-on-close job (kept alive for the process lifetime)."""
    global _job, _tried
    if _tried:
        return _job
    _tried = True
    if sys.platform != "win32":
        return None
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = _EXTENDED_LIMIT()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = k32.SetInformationJobObject(
            job, _JobObjectExtendedLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info))
        if not ok:
            return None
        _job = job
        return _job
    except Exception as e:
        log(f"Job object unavailable ({e}); ffmpeg won't be auto-killed on crash")
        return None


def guard(proc) -> None:
    """Tie a subprocess.Popen to the app's lifetime (kill it when we exit)."""
    job = _get_job()
    if not job or sys.platform != "win32":
        return
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.AssignProcessToJobObject(job, int(proc._handle))
    except Exception as e:
        log(f"Could not guard child process: {e}")
