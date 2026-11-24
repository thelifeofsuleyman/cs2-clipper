"""Executable-name checks using a Windows process snapshot."""

import ctypes
from ctypes import wintypes
from functools import lru_cache


_TH32CS_SNAPPROCESS = 0x00000002
_INVALID_HANDLE = ctypes.c_void_p(-1).value
_ERROR_NO_MORE_FILES = 18


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


@lru_cache(maxsize=1)
def _snapshot_api():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateToolhelp32Snapshot
    create.argtypes = (wintypes.DWORD, wintypes.DWORD)
    create.restype = wintypes.HANDLE
    first, next_process = kernel.Process32FirstW, kernel.Process32NextW
    for read in (first, next_process):
        read.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ProcessEntry))
        read.restype = wintypes.BOOL
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    return create, first, next_process, close


def is_running(executable: str) -> bool:
    """Return whether the executable is present, or raise if the check failed."""
    create, first, next_process, close = _snapshot_api()
    snapshot = create(_TH32CS_SNAPPROCESS, 0)
    if snapshot == _INVALID_HANDLE:
        raise ctypes.WinError(ctypes.get_last_error())

    entry = _ProcessEntry()
    entry.dwSize = ctypes.sizeof(entry)
    name = executable.casefold()
    try:
        found = first(snapshot, ctypes.byref(entry))
        while found:
            if entry.szExeFile.casefold() == name:
                return True
            found = next_process(snapshot, ctypes.byref(entry))
        error = ctypes.get_last_error()
        if error != _ERROR_NO_MORE_FILES:
            raise ctypes.WinError(error)
        return False
    finally:
        close(snapshot)
