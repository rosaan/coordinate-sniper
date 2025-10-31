"""
Application management utilities for connecting to and managing application windows.
"""
import os
import time
from pywinauto import Application
from pywinauto.findwindows import ElementNotFoundError
from typing import Optional


def connect_or_start(exe_path: str, backend: str = "win32", startup_delay: float = 5.0) -> Application:
    """
    Connect to a running application instance or start it if not running.
    Optimized for slow laptops with extended startup delay.
    
    Args:
        exe_path: Full path to the executable
        backend: Pywinauto backend ('win32' or 'uia')
        startup_delay: Delay after starting the application (in seconds) - increased for slow laptops
        
    Returns:
        Application instance
    """
    exe_name = os.path.basename(exe_path)
    app = Application(backend=backend)

    # Try to connect to already running instance
    for target in (exe_path, exe_name):
        try:
            app.connect(path=target)
            print(f"[+] Connected to {target}")
            # Give time for app to stabilize even if already running
            time.sleep(2)
            break
        except Exception:
            pass
    else:
        # Not running -> start it
        print(f"[+] Starting {exe_path} (this may take a moment on slow systems)...")
        app = Application(backend=backend).start(exe_path)
        # Extended delay for slow laptops to prevent crashes
        time.sleep(startup_delay)
        print(f"[+] Application started, waiting for stabilization...")
        time.sleep(3)  # Additional stabilization time

    return app


def get_window_state(win) -> str:
    """
    Get the current state of a window.
    
    Args:
        win: WindowSpecification object
        
    Returns:
        String: 'minimized', 'maximized', 'normal', or 'unknown'
    """
    try:
        if win.is_minimized():
            return 'minimized'
        elif win.is_maximized():
            return 'maximized'
        else:
            return 'normal'
    except Exception:
        # Try alternative method using show state
        try:
            show_state = win.get_show_state()
            if show_state == 2:  # SW_SHOWMINIMIZED
                return 'minimized'
            elif show_state == 3:  # SW_SHOWMAXIMIZED
                return 'maximized'
            else:
                return 'normal'
        except Exception:
            return 'unknown'


def bring_up_window(app: Application, title_regex: str, timeout: float = 10.0, 
                   maximize: bool = True, force_foreground: bool = True,
                   retry_count: int = 3) -> 'WindowSpecification':
    """
    Bring up and focus a window by title regex with comprehensive edge case handling.
    Detects window state, handles minimized/maximized/normal states, and ensures full screen.
    
    Args:
        app: Application instance
        title_regex: Regular expression to match window title
        timeout: Maximum time to wait for window (in seconds)
        maximize: Whether to maximize the window to full screen
        force_foreground: Whether to force window to foreground (bring to front)
        retry_count: Number of retries for window operations
        
    Returns:
        WindowSpecification object
        
    Raises:
        ElementNotFoundError: If window cannot be found within timeout
    """
    # Try to find the window with retries
    win = None
    last_error = None
    
    for attempt in range(retry_count):
        try:
            # Match main window title
            win = app.window(title_re=title_regex)
            # Wait for window to exist and be accessible
            win.wait("exists", timeout=timeout)
            break
        except (ElementNotFoundError, Exception) as e:
            last_error = e
            if attempt < retry_count - 1:
                time.sleep(0.5)
                continue
            else:
                raise ElementNotFoundError(
                    f"Window matching '{title_regex}' not found after {retry_count} attempts. "
                    f"Last error: {last_error}"
                )
    
    if win is None:
        raise ElementNotFoundError(f"Could not find window matching '{title_regex}'")
    
    # Wait for window to be visible and enabled
    try:
        win.wait("visible enabled", timeout=timeout)
    except Exception:
        # If visible/enabled check fails, try to make it visible
        try:
            win.show()
            win.wait("visible", timeout=5.0)
        except Exception as e:
            print(f"[!] Warning: Window visibility check failed: {e}")
    
    # Detect current window state
    state = get_window_state(win)
    print(f"[+] Window state detected: {state}")
    
    # Handle minimized state
    if state == 'minimized':
        try:
            print("[+] Restoring minimized window...")
            win.restore()
            time.sleep(0.3)  # Give it time to restore
            # Verify it's restored
            if win.is_minimized():
                # Try alternative restore method
                win.show()
                win.restore()
                time.sleep(0.3)
        except Exception as e:
            print(f"[!] Warning: Failed to restore window: {e}")
            # Try show() as fallback
            try:
                win.show()
                time.sleep(0.3)
            except Exception:
                pass
    
    # Handle maximized state
    elif state == 'maximized':
        if not maximize:
            # User wants normal size, restore it
            try:
                print("[+] Restoring maximized window to normal size...")
                win.restore()
                time.sleep(0.2)
            except Exception as e:
                print(f"[!] Warning: Failed to restore from maximized: {e}")
    
    # Handle normal state - maximize if requested
    elif state == 'normal':
        if maximize:
            try:
                print("[+] Maximizing window...")
                win.maximize()
                time.sleep(0.3)
                # Verify it's maximized
                if not win.is_maximized():
                    # Try alternative maximize
                    win.set_focus()
                    win.maximize()
                    time.sleep(0.3)
            except Exception as e:
                print(f"[!] Warning: Failed to maximize window: {e}")
                # Try alternative: set window size to screen size
                try:
                    import pyautogui
                    screen_width, screen_height = pyautogui.size()
                    win.move_window(x=0, y=0, width=screen_width, height=screen_height)
                    time.sleep(0.2)
                except Exception:
                    pass
    
    # Force window to foreground (bring to front)
    if force_foreground:
        for attempt in range(retry_count):
            try:
                # Method 1: set_focus
                win.set_focus()
                time.sleep(0.1)
                
                # Method 2: Move to top (z-order)
                win.set_focus()
                win.move_window(x=win.rectangle().left, y=win.rectangle().top)
                time.sleep(0.1)
                
                # Method 3: Verify it's actually focused
                if not win.has_focus():
                    win.set_focus()
                    time.sleep(0.2)
                else:
                    break
            except Exception as e:
                if attempt == retry_count - 1:
                    print(f"[!] Warning: Failed to set focus: {e}")
                else:
                    time.sleep(0.2)
    
    # Final verification and adjustment
    try:
        # Ensure window is visible
        if not win.is_visible():
            win.show()
            time.sleep(0.2)
        
        # Ensure it's enabled
        if not win.is_enabled():
            print("[!] Warning: Window is disabled")
        
        # Final maximize check if requested
        if maximize:
            final_state = get_window_state(win)
            if final_state != 'maximized':
                try:
                    win.maximize()
                    time.sleep(0.2)
                except Exception:
                    pass
        
        # Final focus check
        if force_foreground:
            if not win.has_focus():
                win.set_focus()
                time.sleep(0.1)
    
    except Exception as e:
        print(f"[!] Warning: Final verification failed: {e}")
    
    print(f"[✓] Window is ready (state: {get_window_state(win)})")
    return win

