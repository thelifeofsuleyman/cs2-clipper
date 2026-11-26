"""Read the current Windows playback endpoint without opening an audio stream."""
import ctypes
import sys
from uuid import UUID


def default_playback_endpoint() -> str | None:
    if sys.platform != "win32":
        return None
    from ctypes import byref, c_int, c_long, c_void_p, POINTER, WINFUNCTYPE

    ole = ctypes.WinDLL("ole32")
    ole.CoInitializeEx.argtypes = (c_void_p, ctypes.c_ulong)
    ole.CoInitializeEx.restype = c_long
    ole.CoCreateInstance.argtypes = (c_void_p, c_void_p, ctypes.c_ulong, c_void_p, POINTER(c_void_p))
    ole.CoCreateInstance.restype = c_long
    ole.CoTaskMemFree.argtypes = (c_void_p,)
    ole.CoTaskMemFree.restype = None

    def method(interface, slot, result, *parameters):
        table = ctypes.cast(interface, POINTER(POINTER(c_void_p))).contents
        return WINFUNCTYPE(result, c_void_p, *parameters)(table[slot])

    status = ole.CoInitializeEx(None, 0)
    if status < 0 and status != -2147417850:  # An existing apartment is also usable.
        return None
    class_id = ctypes.create_string_buffer(UUID("bcde0395-e52f-467c-8e3d-c4579291692e").bytes_le)
    interface_id = ctypes.create_string_buffer(UUID("a95664d2-9614-4f35-a746-de8db63617e6").bytes_le)
    enumerator, endpoint, endpoint_id = c_void_p(), c_void_p(), c_void_p()
    try:
        if ole.CoCreateInstance(class_id, None, 1, interface_id, byref(enumerator)) < 0:
            return None
        get_default = method(enumerator, 4, c_long, c_int, c_int, POINTER(c_void_p))
        if get_default(enumerator, 0, 0, byref(endpoint)) < 0:  # eRender, eConsole
            return None
        get_id = method(endpoint, 5, c_long, POINTER(c_void_p))
        if get_id(endpoint, byref(endpoint_id)) < 0 or not endpoint_id:
            return None
        return ctypes.wstring_at(endpoint_id)
    finally:
        if endpoint_id:
            ole.CoTaskMemFree(endpoint_id)
        for interface in (endpoint, enumerator):
            if interface:
                method(interface, 2, ctypes.c_ulong)(interface)  # IUnknown::Release
        if status >= 0:
            ole.CoUninitialize()
