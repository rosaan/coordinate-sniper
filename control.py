import time
import ctypes
from ctypes import wintypes
import win32api
import win32con
import win32gui

user32 = ctypes.windll.user32

# ChildWindowFromPointEx constants
CWP_ALL = 0x0000
CWP_SKIPINVISIBLE = 0x0001
CWP_SKIPDISABLED = 0x0002
CWP_SKIPTRANSPARENT = 0x0004


# structures
class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def get_cursor_pos():
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def get_hwnd_from_point(x, y):
    return user32.WindowFromPoint(POINT(x, y))


def get_class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def get_window_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def get_control_id(hwnd):
    # GetDlgCtrlID is the proper API for "control id" in Win32 dialog children
    cid = user32.GetDlgCtrlID(hwnd)
    return cid


def get_parent(hwnd):
    return user32.GetParent(hwnd)


def screen_to_client(hwnd, x, y):
    """convert screen coords -> client coords for that hwnd"""
    pt = POINT(x, y)
    user32.ScreenToClient(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def child_from_point_ex(hwnd_parent, x_client, y_client):
    """
    Use ChildWindowFromPointEx to try to get the *real* child under (x_client,y_client)
    without accidentally stopping at a big container like TPanel.
    """
    user32.ChildWindowFromPointEx.restype = wintypes.HWND
    user32.ChildWindowFromPointEx.argtypes = [wintypes.HWND, POINT, wintypes.UINT]
    pt = POINT(x_client, y_client)

    # We try progressively "stricter" filters to skip transparent / disabled etc.
    for flags in (
        CWP_ALL,
        CWP_SKIPTRANSPARENT,
        CWP_SKIPTRANSPARENT | CWP_SKIPINVISIBLE,
        CWP_SKIPTRANSPARENT | CWP_SKIPINVISIBLE | CWP_SKIPDISABLED,
    ):
        child = user32.ChildWindowFromPointEx(hwnd_parent, pt, flags)
        if child and child != hwnd_parent:
            return child
    return None


def deep_resolve_hwnd_at_point(x_screen, y_screen):
    """
    Strategy:
    1. Top = WindowFromPoint(screenX, screenY)
    2. Convert to that hwnd's client coords
    3. Ask ChildWindowFromPointEx for the *real* subchild under that point
    4. If found and it's different, try again recursively (to go deeper)
    """
    chain = []
    current = get_hwnd_from_point(x_screen, y_screen)
    if not current:
        return chain

    while current:
        chain.append(current)

        cx, cy = screen_to_client(current, x_screen, y_screen)
        nxt = child_from_point_ex(current, cx, cy)
        if not nxt or nxt == current:
            break

        current = nxt

    return chain  # chain[0] = topmost hwnd, chain[-1] = deepest child we could resolve


def dump_single(hwnd, label=""):
    if not hwnd:
        print(f"[{label}] HWND: None")
        return

    try:
        cls = get_class_name(hwnd)
    except Exception:
        cls = "<err>"

    try:
        txt = get_window_text(hwnd)
    except Exception:
        txt = "<err>"

    try:
        cid = get_control_id(hwnd)
    except Exception:
        cid = "<err>"

    parent_hwnd = get_parent(hwnd)

    print("=" * 60)
    print(f"[{label}] HWND:        {hwnd} (hex {hex(hwnd)})")
    print(f"[{label}] Class Name:  {cls}")
    print(f"[{label}] Window Text: {txt}")
    print(f"[{label}] Control ID:  {cid}")
    print(
        f"[{label}] Parent HWND: {parent_hwnd} (hex {hex(parent_hwnd) if parent_hwnd else None})"
    )

    # Build a suggested pywinauto selector for win32 backend
    # We'll only include fields that look meaningful.
    bits = []
    # cid is often int >= 1 for real controls
    if isinstance(cid, int) and cid > 0:
        bits.append(f"control_id={cid}")
    if cls and cls != "":
        bits.append(f'class_name="{cls}"')
    if txt and txt != "":
        # Strip newlines just to keep it clean
        safe_txt = txt.replace("\r", " ").replace("\n", " ").strip()
        if safe_txt:
            bits.append(f'title="{safe_txt}"')

    if bits:
        print(f"[{label}] Suggested pywinauto selector:")
        print("    win.child_window(" + ", ".join(bits) + ")")
    else:
        print(f"[{label}] Suggested pywinauto selector:")
        print(
            "    # Nothing reliable (custom-painted?). May need TAB / image automation"
        )

    print("=" * 60)


# --- Hotkey (F8) setup ---
HOTKEY_ID = 1
MOD_NOREPEAT = 0x4000
VK_F8 = win32con.VK_F8

if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_NOREPEAT, VK_F8):
    raise RuntimeError("Failed to register F8. Kill other instances and retry.")

print("Deep inspector running.")
print("Instructions:")
print("1. Hover over ANYTHING in that old app (textbox, fake button, etc).")
print("2. Press F8.")
print(
    "3. I'll print BOTH the outer hwnd (like TPanel) and the deepest hwnd under your cursor if any child exists."
)
print("4. Look at Control ID, Class Name, Suggested pywinauto selector.")
print("5. Ctrl+C here to exit.\n")

try:
    msg = wintypes.MSG()
    while True:
        # Check for F8 hotkey message
        if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            if msg.message == win32con.WM_HOTKEY and msg.wParam == HOTKEY_ID:
                x, y = get_cursor_pos()
                chain = deep_resolve_hwnd_at_point(x, y)

                if not chain:
                    print("No HWND under cursor?")
                    continue

                # dump topmost and deepest
                top_hwnd = chain[0]
                deep_hwnd = chain[-1]

                if top_hwnd == deep_hwnd:
                    # only one level, nothing deeper
                    dump_single(top_hwnd, "top/deep")
                else:
                    dump_single(top_hwnd, "topmost")
                    dump_single(deep_hwnd, "deepest")

                print("\n")  # spacer

        time.sleep(0.05)

except KeyboardInterrupt:
    print("Exiting...")
finally:
    user32.UnregisterHotKey(None, HOTKEY_ID)
