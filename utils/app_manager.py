"""
Application management utilities for connecting to and managing application windows.
"""
import os
import time
import re
from pywinauto import Application
from pywinauto.findwindows import ElementNotFoundError
from typing import Optional, List


def connect_or_start(exe_path: str, backend: str = "win32", startup_delay: float = 5.0) -> Application:
    """
    Ensure fresh launch of VAEEG application - closes existing instances if running, then starts fresh.
    Handles login sequence: password entry, login button, and confirmation dialog.
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

    # Always ensure fresh launch - close existing instances first
    print("[+] Ensuring fresh launch - checking for existing instances...")
    for target in (exe_path, exe_name):
        try:
            existing_app = Application(backend=backend)
            existing_app.connect(path=target)
            print(f"[+] Found existing instance, closing it...")
            # Close all windows
            try:
                windows = existing_app.windows()
                for win in windows:
                    try:
                        win.close()
                        time.sleep(0.3)
                    except Exception:
                        pass
            except Exception:
                pass
            # Kill the process
            try:
                existing_app.kill()
                print(f"[+] Closed existing instance")
                time.sleep(2)  # Wait for process to fully close
            except Exception:
                # Fallback: use taskkill
                try:
                    import subprocess
                    subprocess.run(["taskkill", "/F", "/IM", exe_name], 
                                 capture_output=True, timeout=5)
                    print(f"[+] Closed existing instance (via taskkill)")
                    time.sleep(2)
                except Exception:
                    pass
            break
        except Exception:
            pass
    
    # Start fresh instance
    print(f"[+] Starting fresh instance: {exe_path} (this may take a moment on slow systems)...")
    app = Application(backend=backend).start(exe_path)
    # Extended delay for slow laptops to prevent crashes
    time.sleep(startup_delay)
    print(f"[+] Application started, waiting for login screen...")
    time.sleep(3)  # Additional stabilization time
    
    # Handle login sequence
    print("[+] Starting login sequence...")
    import pyautogui
    
    # Step 1: Click password field and enter "1"
    password_coord = (882.5, 582.5)
    print(f"    [*] Clicking password field at {password_coord}...")
    pyautogui.click(password_coord[0], password_coord[1])
    time.sleep(0.5)
    print("    [*] Entering password '1'...")
    pyautogui.typewrite("1", interval=0.1)
    time.sleep(0.5)
    
    # Step 2: Click login button
    login_button_coord = (892.5, 648.75)
    print(f"    [*] Clicking login button at {login_button_coord}...")
    pyautogui.click(login_button_coord[0], login_button_coord[1])
    time.sleep(2)  # Wait for confirm dialog
    
    # Step 3: Wait for "Confirm" dialog and click No
    print("    [*] Waiting for 'Confirm' dialog...")
    confirm_dialog = None
    max_wait = 10
    for attempt in range(max_wait):
        try:
            confirm_dialog = app.window(title_re="Confirm")
            confirm_dialog.wait("exists", timeout=2.0)
            print("    [✓] 'Confirm' dialog found")
            break
        except Exception:
            if attempt < max_wait - 1:
                time.sleep(0.5)
            else:
                print("    [!] 'Confirm' dialog not found, continuing anyway...")
    
    if confirm_dialog:
        print("    [*] Clicking 'No' on Confirm dialog...")
        try:
            # Try to find No button
            no_button = confirm_dialog.child_window(title_re=re.compile("no", re.I))
            if no_button.exists():
                no_button.click()
                time.sleep(0.5)
            else:
                # Fallback: press N key (often selects No)
                confirm_dialog.type_keys("N")
                time.sleep(0.5)
        except Exception:
            # Fallback: press N key
            try:
                confirm_dialog.type_keys("N")
                time.sleep(0.5)
            except Exception:
                print("    [!] Could not click No, trying Escape...")
                confirm_dialog.type_keys("{ESC}")
                time.sleep(0.5)
    
    # Step 4: Wait for main app window "VAEEG - [Client]" to load
    print("    [*] Waiting for main app window 'VAEEG - [Client]' to load...")
    main_window = None
    for attempt in range(20):  # Up to 20 seconds
        try:
            main_window = app.window(title_re="VAEEG - \\[Client\\]")
            main_window.wait("exists", timeout=1.0)
            print("    [✓] Main app window loaded")
            break
        except Exception:
            if attempt < 19:
                time.sleep(1)
            else:
                raise RuntimeError("Main app window 'VAEEG - [Client]' did not appear after login")
    
    print("[+] Login sequence completed, app is ready")
    time.sleep(2)  # Final stabilization
    
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


def find_and_close_error_dialog(app: Application, 
                                error_keywords: List[str] = None,
                                timeout: float = 3.0) -> bool:
    """
    Find and close error dialog popups (like SQL errors, MySQL errors).
    Checks both window title and content text, and also checks for modal dialogs.
    
    Args:
        app: Application instance
        error_keywords: List of keywords to match in dialog title/content (default: common error keywords)
        timeout: Maximum time to wait for dialog (in seconds)
        
    Returns:
        True if error dialog was found and closed, False otherwise
    """
    if error_keywords is None:
        error_keywords = ["error", "sql", "mysql", "exception", "failed", "warning", "server", "gone away"]
    
    try:
        # Wait a bit for dialog to appear (dialogs might take time to show)
        time.sleep(0.5)
        
        # Method 1: Check using pywinauto windows
        windows = app.windows()
        
        for win in windows:
            try:
                # Get window title
                window_title = win.window_text().lower()
                
                # Skip empty windows
                if not window_title:
                    continue
                
                # Try to get window content/body text (for message boxes)
                window_content = ""
                try:
                    # Try to get text from static text controls or labels
                    static_texts = win.descendants(control_type="Static")
                    content_parts = []
                    for static in static_texts:
                        try:
                            text = static.window_text()
                            if text and len(text.strip()) > 0:
                                content_parts.append(text.lower())
                        except Exception:
                            pass
                    window_content = " ".join(content_parts)
                except Exception:
                    pass
                
                # Also try to get text from all child controls
                try:
                    all_texts = []
                    for child in win.descendants():
                        try:
                            child_text = child.window_text()
                            if child_text and len(child_text.strip()) > 0:
                                all_texts.append(child_text.lower())
                        except Exception:
                            pass
                    if all_texts:
                        window_content = " ".join(all_texts)
                except Exception:
                    pass
                
                # Combine title and content for matching
                full_text = (window_title + " " + window_content).lower()
                
                # Check if window title OR content contains error keywords
                if any(keyword.lower() in full_text for keyword in error_keywords):
                    print(f"    [*] Found error dialog: '{win.window_text()}'")
                    if window_content:
                        print(f"    [*] Dialog content: '{window_content[:150]}...'")
                    
                    # Try to find and click OK/Yes/Close button
                    # Common button texts
                    button_texts = ["ok", "yes", "close", "accept", "okay"]
                    
                    for btn_text in button_texts:
                        try:
                            # Try multiple ways to find button
                            # Method 1: By title
                            button = win.child_window(title_re=re.compile(btn_text, re.I))
                            if button.exists():
                                print(f"    [*] Clicking '{btn_text}' button...")
                                button.click()
                                time.sleep(0.5)
                                return True
                        except Exception:
                            try:
                                # Method 2: By control type Button
                                buttons = win.descendants(control_type="Button")
                                for btn in buttons:
                                    try:
                                        btn_text_lower = btn.window_text().lower()
                                        if btn_text in btn_text_lower:
                                            print(f"    [*] Clicking '{btn_text}' button (found by control type)...")
                                            btn.click()
                                            time.sleep(0.5)
                                            return True
                                    except Exception:
                                        continue
                            except Exception:
                                pass
                    
                    # If no button found, try pressing Enter or Escape
                    try:
                        print("    [*] Pressing Enter to close dialog...")
                        win.type_keys("{ENTER}")
                        time.sleep(0.5)
                        return True
                    except Exception:
                        try:
                            print("    [*] Pressing Escape to close dialog...")
                            win.type_keys("{ESC}")
                            time.sleep(0.5)
                            return True
                        except Exception:
                            pass
                    
                    # Last resort: try clicking at common OK button locations
                    try:
                        rect = win.rectangle()
                        # Click near bottom-center (common OK button location)
                        center_x = rect.left + (rect.width() // 2)
                        bottom_y = rect.top + rect.height() - 30
                        import pyautogui
                        pyautogui.click(center_x, bottom_y)
                        time.sleep(0.5)
                        print("    [*] Clicked dialog center-bottom (OK button area)")
                        return True
                    except Exception:
                        pass
            except Exception as e:
                # Continue checking other windows
                continue
        
        # Method 2: Try to find dialogs by checking for modal windows or dialog classes
        # This catches dialogs that might not have been found above
        try:
            import pyautogui
            # Check if there's a dialog-like window by looking for windows with specific classes
            # This is a fallback method
            dialog_classes = ["#32770", "Dialog", "MessageBox"]
            for win in windows:
                try:
                    class_name = win.class_name()
                    if class_name in dialog_classes:
                        window_text = win.window_text().lower()
                        if any(keyword in window_text for keyword in error_keywords):
                            print(f"    [*] Found dialog by class: '{class_name}' - '{win.window_text()}'")
                            # Try to close it
                            try:
                                win.type_keys("{ENTER}")
                                time.sleep(0.5)
                                return True
                            except Exception:
                                import pyautogui
                                rect = win.rectangle()
                                center_x = rect.left + (rect.width() // 2)
                                bottom_y = rect.top + rect.height() - 30
                                pyautogui.click(center_x, bottom_y)
                                time.sleep(0.5)
                                return True
                except Exception:
                    continue
        except Exception:
            pass
        
        return False
    except Exception as e:
        # If any error occurs, assume no dialog found
        return False


def close_application(app: Application, exe_path: str = None) -> None:
    """
    Close the VAEEG application.
    
    Args:
        app: Application instance
        exe_path: Optional path to executable (for fallback kill)
    """
    try:
        print("    [*] Closing VAEEG application...")
        
        # Try to close all windows gracefully
        try:
            windows = app.windows()
            for win in windows:
                try:
                    win.close()
                    time.sleep(0.3)
                except Exception:
                    pass
        except Exception:
            pass
        
        # Try to kill the process
        try:
            app.kill()
            print("    [✓] VAEEG application closed")
            time.sleep(1)  # Give it time to fully close
        except Exception:
            # Fallback: use taskkill if available
            if exe_path:
                import subprocess
                exe_name = os.path.basename(exe_path)
                try:
                    subprocess.run(["taskkill", "/F", "/IM", exe_name], 
                                 capture_output=True, timeout=5)
                    print("    [✓] VAEEG application closed (via taskkill)")
                    time.sleep(1)
                except Exception:
                    print("    [!] Could not close VAEEG application")
    except Exception as e:
        print(f"    [!] Error closing VAEEG: {e}")

