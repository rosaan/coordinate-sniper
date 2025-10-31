import time
import ctypes
from ctypes import wintypes
import win32con
import win32api

user32 = ctypes.windll.user32

adjustment = 1.25

# hotkeys
HOTKEY_CAPTURE = 1  # F8
HOTKEY_RENAME = 2  # F9
MOD_NOREPEAT = 0x4000
VK_F8 = win32con.VK_F8
VK_F9 = win32con.VK_F9

if not user32.RegisterHotKey(None, HOTKEY_CAPTURE, MOD_NOREPEAT, VK_F8):
    raise RuntimeError("Failed to register F8")
if not user32.RegisterHotKey(None, HOTKEY_RENAME, MOD_NOREPEAT, VK_F9):
    raise RuntimeError("Failed to register F9")


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def get_cursor_pos():
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


current_label = "POS"  # default label

print("=== Coordinate Grabber ===")
print("F8  = capture coord for current label")
print("F9  = change label")
print("Ctrl+C = exit\n")
print(f"Current label: {current_label}")

try:
    msg = wintypes.MSG()
    while True:
        if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            # F8 pressed -> capture position
            if msg.message == win32con.WM_HOTKEY and msg.wParam == HOTKEY_CAPTURE:
                x, y = get_cursor_pos()
                print(f"{current_label} = ({x * adjustment}, {y * adjustment})")
            # F9 pressed -> rename label
            if msg.message == win32con.WM_HOTKEY and msg.wParam == HOTKEY_RENAME:
                new_label = input(
                    "Enter new label name (e.g. CLIENT_ID, GEN_BTN, CODE_FIELD): "
                ).strip()
                if new_label:
                    current_label = new_label
                    print(f"[+] Current label set to: {current_label}")
        time.sleep(0.05)
except KeyboardInterrupt:
    print("Exiting...")
finally:
    user32.UnregisterHotKey(None, HOTKEY_CAPTURE)
    user32.UnregisterHotKey(None, HOTKEY_RENAME)
