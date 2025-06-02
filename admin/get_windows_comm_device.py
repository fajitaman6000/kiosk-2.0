# get_windows_comm_device.py
# This script identifies and prints the name of the Windows Default Communication Output Device
# using the Core Audio API (ctypes). Designed to be called by other scripts.

import sys
import ctypes
from ctypes import wintypes
import traceback

# --- ctypes Definitions for Windows Core Audio API ---

# Basic COM types
ULONG = ctypes.c_ulong
LONG = ctypes.c_long
DWORD = wintypes.DWORD
USHORT = wintypes.USHORT
WORD = wintypes.WORD
UINT = wintypes.UINT
LPVOID = wintypes.LPVOID
LPCWSTR = wintypes.LPCWSTR
HANDLE = wintypes.HANDLE
HRESULT = ctypes.c_long # wintypes.HRESULT is c_long
BOOL = wintypes.BOOL

# GUID structure
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ULONG),
        ("Data2", USHORT),
        ("Data3", USHORT),
        ("Data4", ctypes.c_ubyte * 8)
    ]
    def __init__(self, l, w1, w2, b1, b2, b3, b4, b5, b6, b7, b8):
        self.Data1 = l; self.Data2 = w1; self.Data3 = w2
        self.Data4[0]=b1; self.Data4[1]=b2; self.Data4[2]=b3; self.Data4[3]=b4
        self.Data4[4]=b5; self.Data4[5]=b6; self.Data4[6]=b7; self.Data4[7]=b8
        super().__init__()
    # No __repr__ to keep output clean for parsing

# PROPERTYKEY structure
class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", DWORD)]

# PROPVARIANT structure
class PROPVARIANT_UNION(ctypes.Union):
    _fields_ = [("pwszVal", LPCWSTR), ("lVal", LONG), ("ulVal", ULONG)]

class PROPVARIANT(ctypes.Structure):
    _fields_ = [
        ("vt", WORD), ("wReserved1", WORD), ("wReserved2", WORD), ("wReserved3", WORD),
        ("union", PROPVARIANT_UNION)
    ]
    def __init__(self):
        super().__init__()
        self.vt = 0 # VT_EMPTY
        self._needs_clear = False # Custom flag

    def __del__(self):
        # PropVariantClear needs to be globally available
        if hasattr(self, '_needs_clear') and self._needs_clear and _PropVariantClear_func_local:
            try:
                _PropVariantClear_func_local(ctypes.byref(self))
            except Exception: # Silently ignore errors during interpreter shutdown
                pass # Can happen if ole32.dll is already unloaded

# Constants
CLSCTX_ALL = 0x1 | 0x4 | 0x10 # CLSCTX_INPROC_SERVER | CLSCTX_LOCAL_SERVER | CLSCTX_REMOTE_SERVER
STGM_READ = 0x0
COINIT_APARTMENTTHREADED = 0x2
eConsole, eMultimedia, eCommunications = 0, 1, 2 # ERole
eRender, eCapture = 0, 1 # EDataFlow
S_OK = 0
S_FALSE = 1
RPC_E_CHANGED_MODE = 0x80010106
ERROR_NOT_FOUND = ctypes.c_long(0x80070490).value # HRESULT for "Element not found."

# GUIDs
CLSID_MMDeviceEnumerator = GUID(0xBCDE0395, 0xE52F, 0x467C, 0x8E, 0x3D, 0xC4, 0x57, 0x92, 0x91, 0x69, 0x2E)
IID_IMMDeviceEnumerator = GUID(0xA95664D2, 0x9614, 0x4F35, 0xA7, 0x46, 0xDE, 0x8D, 0xB6, 0x36, 0x17, 0xE6)
IID_IMMDevice = GUID(0xD666063F, 0x1587, 0x4E43, 0x81, 0xF1, 0xB9, 0x48, 0xE8, 0x07, 0x36, 0x3F)
IID_IPropertyStore = GUID(0x886d8eeb, 0x8cf2, 0x4446, 0x8d, 0x02, 0xcd, 0xba, 0x1d, 0xbd, 0xcf, 0x99)
PKEY_Device_FriendlyName = PROPERTYKEY(
    GUID(0xa45c254e, 0xdf1c, 0x4efd, 0x80, 0x20, 0x67, 0xd1, 0x46, 0xa8, 0x50, 0xe0), 2
)
VT_LPWSTR = 31

# VTable function types (common)
WINFUNCTYPE = ctypes.WINFUNCTYPE
_QueryInterface_Type = WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(GUID), ctypes.POINTER(LPVOID))
_AddRef_Type = WINFUNCTYPE(ULONG, LPVOID)
_Release_Type = WINFUNCTYPE(ULONG, LPVOID)

# VTable structures (Corrected to include all methods)
class IMMDeviceVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", _QueryInterface_Type),
        ("AddRef", _AddRef_Type),
        ("Release", _Release_Type),
        ("Activate", WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(GUID), DWORD, LPVOID, ctypes.POINTER(LPVOID))),
        ("OpenPropertyStore", WINFUNCTYPE(HRESULT, LPVOID, DWORD, ctypes.POINTER(LPVOID))),
        ("GetId", WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(LPCWSTR))),
        ("GetState", WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(DWORD))),
    ]

class IMMDeviceEnumeratorVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", _QueryInterface_Type),
        ("AddRef", _AddRef_Type),
        ("Release", _Release_Type),
        ("EnumAudioEndpoints", WINFUNCTYPE(HRESULT, LPVOID, ctypes.c_int, DWORD, ctypes.POINTER(LPVOID))),
        ("GetDefaultAudioEndpoint", WINFUNCTYPE(HRESULT, LPVOID, ctypes.c_int, ctypes.c_int, ctypes.POINTER(LPVOID))),
        ("GetDevice", WINFUNCTYPE(HRESULT, LPVOID, LPCWSTR, ctypes.POINTER(LPVOID))),
        ("RegisterEndpointNotificationCallback", WINFUNCTYPE(HRESULT, LPVOID, LPVOID)),
        ("UnregisterEndpointNotificationCallback", WINFUNCTYPE(HRESULT, LPVOID, LPVOID)),
    ]

class IPropertyStoreVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", _QueryInterface_Type),
        ("AddRef", _AddRef_Type),
        ("Release", _Release_Type),
        ("GetCount", WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(DWORD))),
        ("GetAt", WINFUNCTYPE(HRESULT, LPVOID, DWORD, ctypes.POINTER(PROPERTYKEY))),
        ("GetValue", WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))),
        ("SetValue", WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))),
        ("Commit", WINFUNCTYPE(HRESULT, LPVOID)),
    ]

# Helper to create interface pointers
def com_interface_pointer(interface_name, vtable_type):
    class Interface(ctypes.Structure): _fields_ = [("lpVtbl", ctypes.POINTER(vtable_type))]
    Interface.__name__ = interface_name
    return ctypes.POINTER(Interface)

IMMDeviceEnumeratorPtr = com_interface_pointer("IMMDeviceEnumerator", IMMDeviceEnumeratorVtbl)
IMMDevicePtr = com_interface_pointer("IMMDevice", IMMDeviceVtbl)
IPropertyStorePtr = com_interface_pointer("IPropertyStore", IPropertyStoreVtbl)

# Load ole32.dll functions
_CoInitializeEx_func = None
_CoUninitialize_func = None
_CoCreateInstance_func = None
_PropVariantClear_func_local = None # Using a unique name to avoid conflict with `PROPVARIANT.__del__`

try:
    ole32 = ctypes.WinDLL('ole32')
    _CoInitializeEx_func = ole32.CoInitializeEx
    _CoInitializeEx_func.restype = HRESULT
    _CoInitializeEx_func.argtypes = [LPVOID, DWORD]

    _CoUninitialize_func = ole32.CoUninitialize
    _CoUninitialize_func.restype = None
    _CoUninitialize_func.argtypes = []

    _CoCreateInstance_func = ole32.CoCreateInstance
    _CoCreateInstance_func.restype = HRESULT
    _CoCreateInstance_func.argtypes = [ctypes.POINTER(GUID), LPVOID, DWORD, ctypes.POINTER(GUID), ctypes.POINTER(LPVOID)]

    _PropVariantClear_func_local = ole32.PropVariantClear
    _PropVariantClear_func_local.restype = HRESULT
    _PropVariantClear_func_local.argtypes = [ctypes.POINTER(PROPVARIANT)]

except (OSError, AttributeError) as e:
    sys.stderr.write(f"ERROR: Could not load ole32.dll or its functions: {e}\n")
    # Exit with an error code, indicating failure to load COM components
    sys.exit(1)


def get_default_communication_device_name():
    """
    Retrieves the friendly name of the default communication output device
    using Windows Core Audio API.
    Returns: string device name if successful, None otherwise.
    """
    
    needs_co_uninitialize = False
    
    hr_init = _CoInitializeEx_func(None, COINIT_APARTMENTTHREADED)
    if hr_init == S_OK:
        needs_co_uninitialize = True
    elif hr_init == S_FALSE:
        # COM already initialized by another thread, potentially okay.
        pass
    elif hr_init == RPC_E_CHANGED_MODE:
        sys.stderr.write(f"WARNING: CoInitializeEx failed: RPC_E_CHANGED_MODE (0x{hr_init & 0xFFFFFFFF:08X}). COM already initialized with a different threading model.\n")
        return None
    else:
        sys.stderr.write(f"ERROR: CoInitializeEx failed with HRESULT: 0x{hr_init & 0xFFFFFFFF:08X}\n")
        return None

    device_enumerator_raw = ctypes.c_void_p()
    default_device_raw = ctypes.c_void_p()
    property_store_raw = ctypes.c_void_p()
    
    device_enumerator = None
    default_device = None
    property_store = None
    device_name_str = None

    try:
        hr = _CoCreateInstance_func(ctypes.byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL,
                               ctypes.byref(IID_IMMDeviceEnumerator), ctypes.byref(device_enumerator_raw))
        if hr < 0:
            sys.stderr.write(f"ERROR: CoCreateInstance for IMMDeviceEnumerator failed: 0x{hr & 0xFFFFFFFF:08X}\n")
            return None
        device_enumerator = ctypes.cast(device_enumerator_raw, IMMDeviceEnumeratorPtr)

        hr = device_enumerator.contents.lpVtbl.contents.GetDefaultAudioEndpoint(
            device_enumerator, eRender, eCommunications, ctypes.byref(default_device_raw)
        )
        if hr < 0:
            if hr == ERROR_NOT_FOUND:
                 sys.stderr.write("INFO: GetDefaultAudioEndpoint: Default communication device not found.\n")
            else:
                sys.stderr.write(f"ERROR: GetDefaultAudioEndpoint failed: 0x{hr & 0xFFFFFFFF:08X}\n")
            return None
        default_device = ctypes.cast(default_device_raw, IMMDevicePtr)

        hr = default_device.contents.lpVtbl.contents.OpenPropertyStore(
            default_device, STGM_READ, ctypes.byref(property_store_raw)
        )
        if hr < 0:
            sys.stderr.write(f"ERROR: IMMDevice::OpenPropertyStore failed: 0x{hr & 0xFFFFFFFF:08X}\n")
            return None
        property_store = ctypes.cast(property_store_raw, IPropertyStorePtr)

        prop_variant = PROPVARIANT()
        hr = property_store.contents.lpVtbl.contents.GetValue(
            property_store, ctypes.byref(PKEY_Device_FriendlyName), ctypes.byref(prop_variant)
        )
        
        if hr == S_OK:
            if prop_variant.vt == VT_LPWSTR:
                device_name_str = ctypes.wstring_at(prop_variant.union.pwszVal)
                prop_variant._needs_clear = True # Mark for clearing by PROPVARIANT.__del__
            else:
                sys.stderr.write(f"ERROR: PKEY_Device_FriendlyName has unexpected variant type: {prop_variant.vt}\n")
                if prop_variant.vt != 0: prop_variant._needs_clear = True # Still clear it if not empty
        else:
            sys.stderr.write(f"ERROR: IPropertyStore::GetValue for FriendlyName failed: 0x{hr & 0xFFFFFFFF:08X}\n")
    except Exception as e:
        sys.stderr.write(f"CRITICAL ERROR in get_default_communication_device_name: {e}\n")
        traceback.print_exc(file=sys.stderr)
        return None
    finally:
        # Release COM objects in reverse order of acquisition
        if property_store: property_store.contents.lpVtbl.contents.Release(property_store)
        if default_device: default_device.contents.lpVtbl.contents.Release(default_device)
        if device_enumerator: device_enumerator.contents.lpVtbl.contents.Release(device_enumerator)
        
        if needs_co_uninitialize:
            _CoUninitialize_func()
    
    return device_name_str

if __name__ == "__main__":
    if sys.platform != 'win32':
        sys.stderr.write("This script is intended for Windows only.\n")
        sys.exit(1)

    device_name = get_default_communication_device_name()
    if device_name:
        sys.stdout.write(device_name + "\n")
        sys.exit(0) # Success
    else:
        sys.stderr.write("Failed to retrieve default communication device name.\n")
        sys.exit(1) # Failure