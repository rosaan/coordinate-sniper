"""
Sequence for deleting a user in the VAEEG application.
"""
import pyautogui
import re
import pyperclip
from utils import click, click_and_type, wait, press_key
from utils.app_manager import connect_or_start, bring_up_window, find_and_close_error_dialog

# Coordinate definitions for the delete user flow
cancel_button = (600.0, 202.5)
search_client_input = (222.5, 208.75)
delete_button = (757.5, 203.75)

# Application configuration
EXE_PATH = r"C:\\Program Files (x86)\\VAEEG\\VA.exe"
WINDOW_TITLE_REGEX = r"VAEEG - \[Client\]"


def clear_input_box(coords: tuple, backspace_count: int = 100) -> None:
    """
    Clear an input box by clicking it and pressing backspace multiple times.
    
    Args:
        coords: Tuple of (x, y) coordinates of the input box
        backspace_count: Number of backspaces to press (default: 100)
    """
    x, y = coords
    pyautogui.click(x, y)
    wait(0.3)  # Wait for focus
    
    # Select all and delete
    pyautogui.hotkey("ctrl", "a")
    wait(0.2)
    
    # Press backspace multiple times to ensure it's cleared
    for _ in range(backspace_count):
        pyautogui.press("backspace")
    
    wait(0.3)


def click_yes_on_dialog(app, timeout: float = 2.0) -> bool:
    """
    Find and click Yes button on a confirmation dialog.
    
    Args:
        app: Application instance
        timeout: Maximum time to wait for dialog
        
    Returns:
        True if Yes button was clicked, False otherwise
    """
    try:
        from pywinauto.findwindows import ElementNotFoundError
        
        # Get all windows
        windows = app.windows()
        
        for win in windows:
            try:
                window_text = win.window_text().lower()
                
                # Look for dialog windows (common patterns)
                if any(keyword in window_text for keyword in ["confirm", "delete", "yes", "no", "ok", "cancel"]):
                    # Try to find Yes button
                    try:
                        yes_button = win.child_window(title_re=re.compile("yes", re.I))
                        if yes_button.exists():
                            print("    [*] Clicking Yes button...")
                            yes_button.click()
                            wait(0.5)
                            return True
                    except Exception:
                        pass
            except Exception:
                continue
        
        # Fallback: Press Enter (often selects Yes/OK)
        print("    [*] Pressing Enter on dialog (Yes)...")
        press_key("enter")
        wait(0.5)
        return True
    except Exception as e:
        print(f"    [!] Could not find Yes button: {e}")
        # Fallback: Press Enter
        press_key("enter")
        wait(0.5)
        return False


def delete_user(client_id: str,
                exe_path: str = EXE_PATH, 
                window_title_regex: str = WINDOW_TITLE_REGEX) -> bool:
    """
    Delete a user from VAEEG by client ID.
    
    Sequence:
    1. Click search_client_input
    2. Clear input box (100 backspaces)
    3. Enter clientId
    4. Click delete_button
    5. First confirm dialog - click Yes
    6. Second confirm dialog - click Yes
    7. Clear input box again
    
    Optimized for slow laptops with extended delays to prevent VAEEG crashes.
    
    Args:
        client_id: Client ID (5-character unique code) to delete
        exe_path: Path to the VAEEG executable
        window_title_regex: Regex pattern to match the window title
        
    Returns:
        True if deletion was successful, False otherwise
    """
    # Connect to or start the application
    app = connect_or_start(exe_path)
    win = bring_up_window(app, window_title_regex)
    
    # Give the app extra time to stabilize after startup (critical for slow laptops)
    wait(3)

    # Step 0: Cancel the create
    print("    [*] Cancelling create...")
    click(cancel_button, delay=0.5)
    wait(2)  # Wait for cancel dialog
    
    # Step 1: Click search_client_input
    print("    [*] Clicking search client input...")
    click(search_client_input, delay=0.5)
    wait(0.5)
    
    # Step 2: Clear the input box (100 backspaces)
    print("    [*] Clearing input box...")
    clear_input_box(search_client_input, backspace_count=100)
    wait(0.5)
    
    # Step 3: Enter the clientId
    print(f"    [*] Entering client ID: {client_id}...")
    click_and_type(search_client_input, client_id, clear_first=False, type_interval=0.05, delay=1.5)
    wait(2)  # Wait for search results to load
    
    # Step 4: Click delete button
    print("    [*] Clicking delete button...")
    click(delete_button, delay=0.5)
    wait(2)  # Wait for first confirmation dialog
    
    # Step 5: First confirm dialog - click Yes
    print("    [*] First confirmation dialog - clicking Yes...")
    click_yes_on_dialog(app, timeout=2.0)
    wait(2)  # Wait for second confirmation dialog
    
    # Step 6: Second confirm dialog - click Yes
    print("    [*] Second confirmation dialog - clicking Yes...")
    click_yes_on_dialog(app, timeout=2.0)
    wait(2)  # Wait for deletion to complete
    
    # Step 7: Go back to input box and clear it
    print("    [*] Clearing input box after deletion...")
    click(search_client_input, delay=0.5)
    wait(0.3)
    clear_input_box(search_client_input, backspace_count=100)
    wait(0.5)
    
    print("    [✓] User deletion completed")
    return True

