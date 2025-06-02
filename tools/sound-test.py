import ctypes
import numpy as np
import sounddevice as sd
import time

# --- ctypes Definitions for Windows Core Audio API ---

# Basic COM types
ULONG = ctypes.c_ulong
LONG = ctypes.c_long
DWORD = ctypes.c_ulong
USHORT = ctypes.c_ushort
WORD = ctypes.c_ushort
UINT = ctypes.c_uint
LPVOID = ctypes.c_void_p
LPCWSTR = ctypes.c_wchar_p
HANDLE = LPVOID
HRESULT = LONG
BOOL = ctypes.c_int # Windows BOOL is int

# GUID structure
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ULONG),
        ("Data2", USHORT),
        ("Data3", USHORT),
        ("Data4", ctypes.c_ubyte * 8)
    ]
    def __init__(self, l, w1, w2, b1, b2, b3, b4, b5, b6, b7, b8):
        self.Data1 = l
        self.Data2 = w1
        self.Data3 = w2
        self.Data4[0] = b1; self.Data4[1] = b2; self.Data4[2] = b3; self.Data4[3] = b4
        self.Data4[4] = b5; self.Data4[5] = b6; self.Data4[6] = b7; self.Data4[7] = b8
        super().__init__()
    def __repr__(self):
        return f"GUID({self.Data1:#010x}, {self.Data2:#06x}, {self.Data3:#06x}, ...)"

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
    def __del__(self):
        if hasattr(self, '_needs_clear') and self._needs_clear:
            try: PropVariantClear(ctypes.byref(self))
            except NameError: pass

# Constants
CLSCTX_ALL = 0x1 | 0x4 | 0x10 # CLSCTX_INPROC_SERVER | CLSCTX_LOCAL_SERVER | CLSCTX_REMOTE_SERVER
STGM_READ = 0x0
COINIT_APARTMENTTHREADED = 0x2
COINIT_MULTITHREADED = 0x0 # This is 0, which was the issue with RPC_E_CHANGED_MODE if used

eConsole, eMultimedia, eCommunications = 0, 1, 2 # ERole
eRender, eCapture = 0, 1 # EDataFlow

S_OK = 0
S_FALSE = 1
RPC_E_CHANGED_MODE = 0x80010106 # HRESULT for this error

# GUIDs
CLSID_MMDeviceEnumerator = GUID(0xBCDE0395, 0xE52F, 0x467C, 0x8E, 0x3D, 0xC4, 0x57, 0x92, 0x91, 0x69, 0x2E)
IID_IMMDeviceEnumerator = GUID(0xA95664D2, 0x9614, 0x4F35, 0xA7, 0x46, 0xDE, 0x8D, 0xB6, 0x36, 0x17, 0xE6)
IID_IMMDevice = GUID(0xD666063F, 0x1587, 0x4E43, 0x81, 0xF1, 0xB9, 0x48, 0xE8, 0x07, 0x36, 0x3F)
IID_IPropertyStore = GUID(0x886d8eeb, 0x8cf2, 0x4446, 0x8d, 0x02, 0xcd, 0xba, 0x1d, 0xbd, 0xcf, 0x99)
PKEY_Device_FriendlyName = PROPERTYKEY(
    GUID(0xa45c254e, 0xdf1c, 0x4efd, 0x80, 0x20, 0x67, 0xd1, 0x46, 0xa8, 0x50, 0xe0), 2
)
VT_LPWSTR = 31

# VTable structures
class IUnknownVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", ctypes.WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(GUID), ctypes.POINTER(LPVOID))),
        ("AddRef", ctypes.WINFUNCTYPE(ULONG, LPVOID)),
        ("Release", ctypes.WINFUNCTYPE(ULONG, LPVOID)),
    ]
class IMMDeviceVtbl(IUnknownVtbl):
    _fields_ = [
        ("Activate", ctypes.WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(GUID), DWORD, LPVOID, ctypes.POINTER(LPVOID))),
        ("OpenPropertyStore", ctypes.WINFUNCTYPE(HRESULT, LPVOID, DWORD, ctypes.POINTER(LPVOID))),
        ("GetId", ctypes.WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(LPCWSTR))),
        ("GetState", ctypes.WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(DWORD))),
    ]
class IMMDeviceEnumeratorVtbl(IUnknownVtbl):
    _fields_ = [
        ("EnumAudioEndpoints", ctypes.WINFUNCTYPE(HRESULT, LPVOID, ctypes.c_int, DWORD, ctypes.POINTER(LPVOID))),
        ("GetDefaultAudioEndpoint", ctypes.WINFUNCTYPE(HRESULT, LPVOID, ctypes.c_int, ctypes.c_int, ctypes.POINTER(LPVOID))),
        ("GetDevice", ctypes.WINFUNCTYPE(HRESULT, LPVOID, LPCWSTR, ctypes.POINTER(LPVOID))),
        ("RegisterEndpointNotificationCallback", ctypes.WINFUNCTYPE(HRESULT, LPVOID, LPVOID)),
        ("UnregisterEndpointNotificationCallback", ctypes.WINFUNCTYPE(HRESULT, LPVOID, LPVOID)),
    ]
class IPropertyStoreVtbl(IUnknownVtbl):
    _fields_ = [
        ("GetCount", ctypes.WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(DWORD))),
        ("GetAt", ctypes.WINFUNCTYPE(HRESULT, LPVOID, DWORD, ctypes.POINTER(PROPERTYKEY))),
        ("GetValue", ctypes.WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))),
        ("SetValue", ctypes.WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))),
        ("Commit", ctypes.WINFUNCTYPE(HRESULT, LPVOID)),
    ]

# Helper to create interface pointers (these are the *typed* pointers)
def com_interface_pointer(interface_name, vtable_type):
    class Interface(ctypes.Structure): _fields_ = [("lpVtbl", ctypes.POINTER(vtable_type))]
    Interface.__name__ = interface_name
    return ctypes.POINTER(Interface)

IMMDeviceEnumeratorPtr = com_interface_pointer("IMMDeviceEnumerator", IMMDeviceEnumeratorVtbl)
IMMDevicePtr = com_interface_pointer("IMMDevice", IMMDeviceVtbl)
IPropertyStorePtr = com_interface_pointer("IPropertyStore", IPropertyStoreVtbl)

try:
    ole32 = ctypes.WinDLL('ole32')
    CoInitializeEx = ole32.CoInitializeEx; CoInitializeEx.restype=HRESULT; CoInitializeEx.argtypes=[LPVOID, DWORD]
    CoUninitialize = ole32.CoUninitialize; CoUninitialize.restype=None; CoUninitialize.argtypes=[]
    
    # CoCreateInstance expects LPVOID* (ctypes.POINTER(LPVOID) or ctypes.POINTER(ctypes.c_void_p)) for ppv
    CoCreateInstance = ole32.CoCreateInstance; CoCreateInstance.restype=HRESULT; CoCreateInstance.argtypes=[
        ctypes.POINTER(GUID), LPVOID, DWORD, ctypes.POINTER(GUID), ctypes.POINTER(LPVOID) # THIS IS THE CRITICAL CHANGE IN ARGTYPES
    ]
    
    PropVariantClear = ole32.PropVariantClear; PropVariantClear.restype=HRESULT; PropVariantClear.argtypes=[ctypes.POINTER(PROPVARIANT)]
    
    COM_INITIALIZED_SUCCESSFULLY_FOR_FUNCTION = False # Flag for CoUninitialize
except (OSError, AttributeError) as e:
    print(f"FATAL: Could not load ole32.dll or its functions: {e}")
    CoInitializeEx = CoUninitialize = CoCreateInstance = PropVariantClear = lambda *args: -1 # Dummy error
    COM_INITIALIZED_SUCCESSFULLY_FOR_FUNCTION = False


def get_default_communication_device_name():
    global COM_INITIALIZED_SUCCESSFULLY_FOR_FUNCTION
    COM_INITIALIZED_SUCCESSFULLY_FOR_FUNCTION = False # Reset for each call

    hr = CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    if hr != S_OK and hr != S_FALSE:
        if hr == RPC_E_CHANGED_MODE:
            print(f"CoInitializeEx failed: RPC_E_CHANGED_MODE (0x{hr & 0xFFFFFFFF:08X}). "
                  "COM already initialized with a different threading model.")
        else:
            print(f"CoInitializeEx failed with HRESULT: 0x{hr & 0xFFFFFFFF:08X}")
        return None
    COM_INITIALIZED_SUCCESSFULLY_FOR_FUNCTION = True # Mark that CoUninitialize is needed

    # Declare raw void pointers to receive the COM interface pointers
    device_enumerator_raw = ctypes.c_void_p()
    default_device_raw = ctypes.c_void_p()
    property_store_raw = ctypes.c_void_p()

    # Create IMMDeviceEnumerator instance
    hr_create = CoCreateInstance(ctypes.byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL,
                                 ctypes.byref(IID_IMMDeviceEnumerator), ctypes.byref(device_enumerator_raw))
    if hr_create < 0:
        print(f"CoCreateInstance for IMMDeviceEnumerator failed: 0x{hr_create & 0xFFFFFFFF:08X}")
        CoUninitialize()
        COM_INITIALIZED_SUCCESSFULLY_FOR_FUNCTION = False
        return None
    # Cast the raw pointer to the specific typed pointer
    device_enumerator = ctypes.cast(device_enumerator_raw, IMMDeviceEnumeratorPtr)

    # Get the default communication audio endpoint
    hr_get_default = device_enumerator.contents.lpVtbl.contents.GetDefaultAudioEndpoint(
        device_enumerator, eRender, eCommunications, ctypes.byref(default_device_raw)
    )
    if hr_get_default < 0:
        if hr_get_default == 0x80070490: # ERROR_NOT_FOUND
             print("GetDefaultAudioEndpoint: Default communication device not found.")
        else:
            print(f"GetDefaultAudioEndpoint failed: 0x{hr_get_default & 0xFFFFFFFF:08X}")
        device_enumerator.contents.lpVtbl.contents.Release(device_enumerator)
        CoUninitialize()
        COM_INITIALIZED_SUCCESSFULLY_FOR_FUNCTION = False
        return None
    # Cast the raw pointer to the specific typed pointer
    default_device = ctypes.cast(default_device_raw, IMMDevicePtr)


    # Open the property store for the default device
    hr_open_store = default_device.contents.lpVtbl.contents.OpenPropertyStore(
        default_device, STGM_READ, ctypes.byref(property_store_raw)
    )
    if hr_open_store < 0:
        print(f"IMMDevice::OpenPropertyStore failed: 0x{hr_open_store & 0xFFFFFFFF:08X}")
        default_device.contents.lpVtbl.contents.Release(default_device)
        device_enumerator.contents.lpVtbl.contents.Release(device_enumerator)
        CoUninitialize()
        COM_INITIALIZED_SUCCESSFULLY_FOR_FUNCTION = False
        return None
    # Cast the raw pointer to the specific typed pointer
    property_store = ctypes.cast(property_store_raw, IPropertyStorePtr)

    prop_variant = PROPVARIANT()
    hr_get_value = property_store.contents.lpVtbl.contents.GetValue(
        property_store, ctypes.byref(PKEY_Device_FriendlyName), ctypes.byref(prop_variant)
    )
    device_name = None
    if hr_get_value == S_OK:
        if prop_variant.vt == VT_LPWSTR:
            device_name = prop_variant.union.pwszVal
            prop_variant._needs_clear = True # Mark for clearing by PROPVARIANT.__del__
        else:
            print(f"PKEY_Device_FriendlyName has unexpected variant type: {prop_variant.vt}")
            PropVariantClear(ctypes.byref(prop_variant)) # Still clear it
    else:
        print(f"IPropertyStore::GetValue for FriendlyName failed: 0x{hr_get_value & 0xFFFFFFFF:08X}")

    # Release COM objects in reverse order of acquisition
    property_store.contents.lpVtbl.contents.Release(property_store)
    default_device.contents.lpVtbl.contents.Release(default_device)
    device_enumerator.contents.lpVtbl.contents.Release(device_enumerator)
    
    if COM_INITIALIZED_SUCCESSFULLY_FOR_FUNCTION:
        CoUninitialize()
        COM_INITIALIZED_SUCCESSFULLY_FOR_FUNCTION = False

    return device_name

def generate_tone(frequency, duration, sample_rate, amplitude=0.5):
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    tone = amplitude * np.sin(2 * np.pi * frequency * t)
    return tone.astype(np.float32)

if __name__ == "__main__":
    tone_frequency = 440; tone_duration = 1.0; sample_rate = 44100
    print(f"Generating a {tone_frequency} Hz tone for {tone_duration} second(s)...")
    audio_data = generate_tone(tone_frequency, tone_duration, sample_rate)

    print("\n--- Playing tone on Default Playback Device (via sounddevice default) ---")
    try:
        default_playback_sd_index = sd.default.device[1]
        device_info = sd.query_devices(default_playback_sd_index)
        print(f"Sounddevice Default Playback Device: '{device_info['name']}' (Index: {default_playback_sd_index})")
        sd.play(audio_data, sample_rate, device=default_playback_sd_index); sd.wait()
        print("Done playing on Sounddevice Default Playback Device.")
    except Exception as e: print(f"Error playing on Sounddevice Default Playback Device: {e}")

    print("\n--- Attempting to play tone on Default COMMUNICATION Device (via ctypes Core Audio) ---")
    comm_device_name_ctypes = get_default_communication_device_name()

    if comm_device_name_ctypes:
        print(f"Windows Default Communication Device (from ctypes): '{comm_device_name_ctypes}'")
        comm_device_sd_index = None
        sd_devices = sd.query_devices()
        for i, dev in enumerate(sd_devices):
            if dev['max_output_channels'] > 0:
                # Exact match
                if dev['name'] == comm_device_name_ctypes:
                    comm_device_sd_index = i; break
                # Partial match (sounddevice name can be truncated/different)
                if comm_device_name_ctypes in dev['name'] or dev['name'] in comm_device_name_ctypes:
                    if comm_device_sd_index is None: # Prefer exact, take first partial
                         print(f"Potential partial match: sd name '{dev['name']}' vs ctypes name '{comm_device_name_ctypes}'")
                         comm_device_sd_index = i 
        
        if comm_device_sd_index is not None:
            device_info = sd.query_devices(comm_device_sd_index)
            print(f"Found corresponding sounddevice output device: '{device_info['name']}' (Index: {comm_device_sd_index})")
            try:
                sd.play(audio_data, sample_rate, device=comm_device_sd_index); sd.wait()
                print("Done playing on Default Communication Device.")
            except Exception as e: print(f"Error playing on comm device '{comm_device_name_ctypes}': {e}")
        else:
            print(f"Could not find a matching sounddevice output device for '{comm_device_name_ctypes}'.")
            print("Available sounddevice output devices:"); [print(f"  {i}: {d['name']}") for i,d in enumerate(sd_devices) if d['max_output_channels']>0]
    else:
        print("Could not retrieve Default Communication Device name using ctypes.")

    print("\nScript finished.")
    input("Press Enter to exit...")