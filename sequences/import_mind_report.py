"""
Sequence for importing mind report in the VAEEG application.
Exports PDF and uploads to server.
"""
import os
import re
import datetime
from typing import Optional, Tuple, List
from utils import click, click_and_type, wait, enter_save_file_name, save_file
from utils.app_manager import connect_or_start, bring_up_window, close_application

# Coordinate definitions for the import mind report flow
CLIENT_CODE_INPUT = (222.5, 208.75)  # Client code input field coordinates (same as search_client_input)
GRID_CONTROL = None  # Will use pywinauto to find by control_id
PRINT_BUTTON_1 = (1242.5, 227.5)
PRINT_BUTTON_2 = (1527.5, 150)
PRINT_PREVIEW_SAVE = (601.25, 45)

# Application configuration
EXE_PATH = r"C:\\Program Files (x86)\\VAEEG\\VA.exe"
WINDOW_TITLE_REGEX = r"VAEEG - \[Client\]"


def parse_grid_entry(text: str) -> Optional[Tuple[str, str, int]]:
    """
    Parse a grid entry in format: YYYY-MM-DD HH:MM 480/1440/1441
    
    Args:
        text: Grid entry text
        
    Returns:
        Tuple of (date_str, time_str, code) or None if invalid
    """
    # Pattern: YYYY-MM-DD HH:MM 480/1440/1441
    pattern = r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(480|1440|1441)"
    match = re.match(pattern, text.strip())
    if match:
        date_str = match.group(1)
        time_str = match.group(2)
        code = int(match.group(3))
        return (date_str, time_str, code)
    return None


def get_grid_entries(win) -> List[Tuple[str, str, int, int]]:
    """
    Get all entries from the grid control.
    
    Args:
        win: WindowSpecification object containing the grid
        
    Returns:
        List of tuples: (date_str, time_str, code, row_index)
    """
    entries = []
    try:
        # Find the grid control
        grid = win.child_window(control_id=2163448, class_name="TDBGrid")
        
        if not grid.exists():
            print("    [!] Grid control not found")
            return entries
        
        # Method 1: Try to get all row text from grid
        try:
            grid_text = grid.window_text()
            if grid_text:
                # Split by lines and parse each
                lines = grid_text.split('\n')
                for idx, line in enumerate(lines):
                    parsed = parse_grid_entry(line)
                    if parsed:
                        date_str, time_str, code = parsed
                        entries.append((date_str, time_str, code, idx))
                if entries:
                    print(f"    [✓] Found {len(entries)} entries via window_text()")
                    return entries
        except Exception as e:
            print(f"    [*] Method 1 failed: {e}")
        
        # Method 2: Try to get text from grid cells
        try:
            # Try to access grid rows/cells
            # TDBGrid might expose items via item_text() or similar
            for row_idx in range(10):  # Check up to 10 rows
                try:
                    # Try different ways to get cell text
                    cell_text = None
                    
                    # Try item_text if available
                    if hasattr(grid, 'item_text'):
                        cell_text = grid.item_text(row_idx)
                    
                    # Try getting text from first child window (cell)
                    if not cell_text:
                        try:
                            cells = grid.children()
                            if cells and row_idx < len(cells):
                                cell_text = cells[row_idx].window_text()
                        except Exception:
                            pass
                    
                    if cell_text:
                        parsed = parse_grid_entry(cell_text)
                        if parsed:
                            date_str, time_str, code = parsed
                            entries.append((date_str, time_str, code, row_idx))
                except Exception:
                    continue
            
            if entries:
                print(f"    [✓] Found {len(entries)} entries via cell access")
                return entries
        except Exception as e:
            print(f"    [*] Method 2 failed: {e}")
        
        # Method 3: Try to get text from all descendants
        try:
            descendants = grid.descendants()
            for idx, desc in enumerate(descendants):
                try:
                    desc_text = desc.window_text()
                    if desc_text:
                        parsed = parse_grid_entry(desc_text)
                        if parsed:
                            date_str, time_str, code = parsed
                            entries.append((date_str, time_str, code, idx))
                except Exception:
                    continue
            
            if entries:
                print(f"    [✓] Found {len(entries)} entries via descendants")
                return entries
        except Exception as e:
            print(f"    [*] Method 3 failed: {e}")
        
        # If no entries found, return empty list
        # The click function will use fallback method (click first/second rows)
        print("    [!] Could not read grid entries - will use fallback click method")
        
    except Exception as e:
        print(f"    [!] Error reading grid: {e}")
    
    return entries


def find_and_click_grid_entries(win, entries: List[Tuple[str, str, int, int]]) -> bool:
    """
    Find and click the latest entry and the 480 version entry in the grid.
    Usually the first or second row contains the entries we need.
    
    Args:
        win: WindowSpecification object
        entries: List of parsed grid entries (may be empty if reading failed)
        
    Returns:
        True if entries were clicked, False otherwise
    """
    try:
        grid = win.child_window(control_id=2163448, class_name="TDBGrid")
        
        if not grid.exists():
            print("    [!] Grid control not found for clicking")
            return False
        
        rect = grid.rectangle()
        import pyautogui
        
        if entries:
            # We have parsed entries - click based on data
            # Sort entries by date and time (latest first)
            sorted_entries = sorted(entries, key=lambda x: (x[0], x[1]), reverse=True)
            
            # Find latest entry
            latest_entry = sorted_entries[0] if sorted_entries else None
            
            # Find 480 version entry (prefer latest 480, otherwise first 480 found)
            code_480_entry = None
            for entry in sorted_entries:
                if entry[2] == 480:
                    code_480_entry = entry
                    break
            
            if latest_entry:
                print(f"    [*] Clicking latest entry: {latest_entry[0]} {latest_entry[1]} {latest_entry[2]}")
                try:
                    # Calculate row positions
                    row_height = max(rect.height() // max(len(entries), 1), 20)  # Minimum 20px per row
                    row_index = latest_entry[3]
                    click_y = rect.top + (row_index * row_height) + (row_height // 2)
                    click_x = rect.left + (rect.width() // 2)
                    
                    # Click latest entry
                    pyautogui.click(click_x, click_y)
                    wait(0.5)
                    
                    # If latest is already 480, we're done
                    if latest_entry[2] == 480:
                        print("    [✓] Latest entry is 480 version - clicked")
                        return True
                    
                    # If we need to click 480 separately and it's different from latest
                    if code_480_entry and code_480_entry != latest_entry:
                        print(f"    [*] Clicking 480 version entry: {code_480_entry[0]} {code_480_entry[1]} {code_480_entry[2]}")
                        row_index_480 = code_480_entry[3]
                        click_y_480 = rect.top + (row_index_480 * row_height) + (row_height // 2)
                        pyautogui.click(click_x, click_y_480)
                        wait(0.5)
                        print("    [✓] Both entries clicked")
                    else:
                        print("    [✓] Latest entry clicked (480 version not found separately)")
                    
                    return True
                except Exception as e:
                    print(f"    [!] Error clicking by row index: {e}, using fallback")
        
        # Fallback: Click first and second rows (user said "usually first or second top")
        print("    [*] Using fallback: clicking first and second rows...")
        try:
            # Estimate row height (usually around 20-25px for grid rows)
            row_height = 25
            click_x = rect.left + (rect.width() // 2)
            
            # Click first row (latest entry, usually)
            click_y1 = rect.top + row_height // 2
            pyautogui.click(click_x, click_y1)
            wait(0.5)
            print("    [✓] Clicked first row")
            
            # Click second row (might be 480 version or another entry)
            click_y2 = rect.top + row_height + (row_height // 2)
            pyautogui.click(click_x, click_y2)
            wait(0.5)
            print("    [✓] Clicked second row")
            
            print("    [✓] Grid entries clicked (fallback method)")
            return True
            
        except Exception as e:
            print(f"    [!] Fallback click failed: {e}")
            return False
    
    except Exception as e:
        print(f"    [!] Error finding grid for clicking: {e}")
        return False


def wait_for_window(app, title_regex: str, timeout: float = 30.0) -> bool:
    """
    Wait for a window with specific title to appear.
    
    Args:
        app: Application instance
        title_regex: Regex pattern to match window title
        timeout: Maximum time to wait (in seconds)
        
    Returns:
        True if window appeared, False otherwise
    """
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            window = app.window(title_re=title_regex)
            if window.exists():
                # Wait for it to be visible and enabled
                window.wait("visible enabled", timeout=2.0)
                print(f"    [✓] Window '{title_regex}' appeared")
                return True
        except Exception:
            pass
        
        wait(0.5)
    
    print(f"    [!] Window '{title_regex}' did not appear within {timeout}s")
    return False


def wait_for_print_preview_ready(app, timeout: float = 60.0) -> bool:
    """
    Wait for Print Preview window to load completely and maximize.
    This window is very slow, so we wait for it to be maximized.
    
    Args:
        app: Application instance
        timeout: Maximum time to wait (in seconds)
        
    Returns:
        True if window is ready and maximized, False otherwise
    """
    import time
    start_time = time.time()
    
    # Wait for window to appear
    if not wait_for_window(app, "Print Preview", timeout=timeout):
        return False
    
    try:
        preview_window = app.window(title_re="Print Preview")
        
        # Wait for window to be maximized (indicates it's fully loaded)
        print("    [*] Waiting for Print Preview to maximize (indicates full load)...")
        max_wait = timeout - (time.time() - start_time)
        
        while time.time() - start_time < timeout:
            try:
                # Check if window is maximized
                if preview_window.is_maximized():
                    print("    [✓] Print Preview is maximized - ready")
                    wait(2.0)  # Extra wait to ensure fully ready
                    return True
                
                # Try to maximize it if not already
                try:
                    preview_window.maximize()
                    wait(1.0)
                    if preview_window.is_maximized():
                        print("    [✓] Print Preview maximized - ready")
                        wait(2.0)  # Extra wait
                        return True
                except Exception:
                    pass
                
            except Exception:
                pass
            
            wait(1.0)
        
        # If we get here, window exists but didn't maximize - still proceed
        print("    [!] Print Preview window exists but may not be fully loaded")
        wait(3.0)  # Extra wait anyway
        return True
        
    except Exception as e:
        print(f"    [!] Error waiting for Print Preview: {e}")
        return False


def check_window_not_responding(app, window_title: str) -> bool:
    """
    Check if a window is in "Not responding" state.
    
    Args:
        app: Application instance
        window_title: Window title to check
        
    Returns:
        True if window is responding, False if not responding
    """
    try:
        window = app.window(title_re=window_title)
        if not window.exists():
            return False
        
        # Try to interact with window - if it responds, it's OK
        try:
            window.set_focus()
            return True
        except Exception:
            return False
            
    except Exception:
        return False


def get_save_path(client_code: str) -> str:
    """
    Generate the save path for the PDF file.
    
    Args:
        client_code: Client code
        
    Returns:
        Full path to save the file
    """
    # Get %USERPROFILE% environment variable
    user_profile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    
    # Create directory if it doesn't exist
    save_dir = os.path.join(user_profile, "scripts", "coordinate-sniper", "files")
    os.makedirs(save_dir, exist_ok=True)
    
    # Generate filename: {client_code}_{date}_{time}.pdf
    now = datetime.datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H%M%S")
    filename = f"{client_code}_{date_str}_{time_str}.pdf"
    
    return os.path.join(save_dir, filename)


def verify_file_exists(file_path: str, timeout: float = 10.0) -> bool:
    """
    Verify that a file exists at the specified path.
    
    Args:
        file_path: Path to the file
        timeout: Maximum time to wait for file to appear (in seconds)
        
    Returns:
        True if file exists, False otherwise
    """
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            print(f"    [✓] File verified: {file_path}")
            return True
        wait(0.5)
    
    print(f"    [!] File not found or empty: {file_path}")
    return False


def import_mind_report(client_code: str,
                       exe_path: str = EXE_PATH,
                       window_title_regex: str = WINDOW_TITLE_REGEX) -> Optional[str]:
    """
    Import mind report for a client code, export as PDF, and return file path.
    
    Sequence:
    1. Click client code input (control_id=3015944, class_name="TRzEdit")
    2. Type the client code
    3. Find text in grid (control_id=2163448, class_name="TDBGrid")
    4. Click latest entry and 480 version entry
    5. Click print button at (1242.5, 227.5)
    6. Wait for "Print options" window
    7. Click button at (1527.5, 150)
    8. Wait for "Print Preview" window (slow, wait for maximize)
    9. Click save button at (601.25, 45)
    10. Save file to %USERPROFILE%\\scripts\\coordinate-sniper\\files\\{client_code}_{date}_{time}.pdf
    11. Verify file exists
    12. Close VAEEG
    
    Args:
        client_code: Client code (5-character unique code)
        exe_path: Path to the VAEEG executable
        window_title_regex: Regex pattern to match the window title
        
    Returns:
        Path to the saved PDF file, or None if failed
        
    Raises:
        RuntimeError: With detailed error message including step that failed
    """
    app = None
    error_step = None
    error_context = {}
    
    try:
        # Initialize application
        try:
            print(f"    [*] Connecting to VAEEG application...")
            app = connect_or_start(exe_path)
            win = bring_up_window(app, window_title_regex)
            error_step = "app_initialization"
            error_context["step"] = "Connecting to VAEEG application"
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_APP_INIT: Failed to connect to VAEEG application: {str(e)}. "
                f"Client code: {client_code}, Exe path: {exe_path}"
            )
        
        # Give the app time to stabilize
        wait(1)
        
        # Ensure main window is focused
        try:
            win.set_focus()
            win.wait("visible enabled", timeout=3.0)
            wait(0.5)
        except Exception as e:
            print(f"    [!] Warning: Could not focus window: {e}")
        
        # Step 1: Click client code input field (using coordinates)
        error_step = "client_code_input_click"
        error_context["step"] = "Clicking client code input field"
        print("    [*] Clicking client code input field...")
        try:
            click(CLIENT_CODE_INPUT, delay=0.5)
            print("    [✓] Client code input field clicked")
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_INPUT_CLICK: Failed to click client code input field at {CLIENT_CODE_INPUT}: {str(e)}. "
                f"Client code: {client_code}"
            )
        
        # Step 2: Type the client code
        error_step = "client_code_type"
        error_context["step"] = f"Typing client code: {client_code}"
        print(f"    [*] Typing client code: {client_code}...")
        try:
            click_and_type(CLIENT_CODE_INPUT, client_code, clear_first=True, type_interval=0.02, delay=1.0)
            wait(1.0)  # Wait for grid to update
            print("    [✓] Client code entered")
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_INPUT_TYPE: Failed to type client code '{client_code}': {str(e)}"
            )
        
        # Step 3: Find entries in grid
        error_step = "grid_read"
        error_context["step"] = "Reading grid entries"
        print("    [*] Reading grid entries...")
        try:
            entries = get_grid_entries(win)
            
            if not entries:
                raise RuntimeError(
                    f"MIND_REPORT_ERROR_GRID_EMPTY: No entries found in grid after entering client code '{client_code}'. "
                    f"Grid may be empty or grid reading failed."
                )
            
            print(f"    [*] Found {len(entries)} entries in grid")
            for entry in entries:
                print(f"        - {entry[0]} {entry[1]} {entry[2]}")
        except RuntimeError:
            raise  # Re-raise RuntimeError as-is
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_GRID_READ: Failed to read grid entries: {str(e)}. "
                f"Client code: {client_code}"
            )
        
        # Step 4: Click latest entry and 480 version
        error_step = "grid_click"
        error_context["step"] = "Clicking grid entries"
        print("    [*] Clicking grid entries...")
        try:
            if not find_and_click_grid_entries(win, entries):
                raise RuntimeError(
                    f"MIND_REPORT_ERROR_GRID_CLICK: Failed to click grid entries. "
                    f"Client code: {client_code}, Found {len(entries)} entries"
                )
        except RuntimeError:
            raise  # Re-raise RuntimeError as-is
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_GRID_CLICK: Error clicking grid entries: {str(e)}. "
                f"Client code: {client_code}"
            )
        
        wait(0.5)
        
        # Step 5: Click print button at (1242.5, 227.5)
        error_step = "print_button_1"
        error_context["step"] = "Clicking first print button"
        print("    [*] Clicking print button (first)...")
        try:
            click(PRINT_BUTTON_1, delay=0.5)
            wait(2.0)  # Wait for Print options window
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_PRINT_BUTTON_1: Failed to click first print button at {PRINT_BUTTON_1}: {str(e)}. "
                f"Client code: {client_code}"
            )
        
        # Step 6: Wait for "Print options" window
        error_step = "print_options_wait"
        error_context["step"] = "Waiting for Print options window"
        print("    [*] Waiting for 'Print options' window...")
        try:
            if not wait_for_window(app, "Print options", timeout=10.0):
                raise RuntimeError(
                    f"MIND_REPORT_ERROR_PRINT_OPTIONS_TIMEOUT: Print options window did not appear within 10 seconds. "
                    f"Client code: {client_code}"
                )
        except RuntimeError:
            raise  # Re-raise RuntimeError as-is
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_PRINT_OPTIONS: Error waiting for Print options window: {str(e)}. "
                f"Client code: {client_code}"
            )
        
        # Check if window is responding
        try:
            if not check_window_not_responding(app, "Print options"):
                print("    [!] Warning: Print options window may not be responding")
                # Try to focus it anyway
                try:
                    print_window = app.window(title_re="Print options")
                    print_window.set_focus()
                    wait(1.0)
                except Exception:
                    pass
        except Exception as e:
            print(f"    [!] Warning: Could not verify Print options window responsiveness: {e}")
        
        # Step 7: Click button at (1527.5, 150)
        error_step = "print_button_2"
        error_context["step"] = "Clicking second print button"
        print("    [*] Clicking print button (second)...")
        try:
            click(PRINT_BUTTON_2, delay=0.5)
            wait(2.0)  # Wait for Print Preview window
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_PRINT_BUTTON_2: Failed to click second print button at {PRINT_BUTTON_2}: {str(e)}. "
                f"Client code: {client_code}"
            )
        
        # Step 8: Wait for "Print Preview" window (very slow)
        error_step = "print_preview_wait"
        error_context["step"] = "Waiting for Print Preview window"
        print("    [*] Waiting for 'Print Preview' window (this may take a while)...")
        try:
            if not wait_for_print_preview_ready(app, timeout=60.0):
                raise RuntimeError(
                    f"MIND_REPORT_ERROR_PRINT_PREVIEW_TIMEOUT: Print Preview window did not appear or load properly within 60 seconds. "
                    f"This window is very slow. Client code: {client_code}"
                )
        except RuntimeError:
            raise  # Re-raise RuntimeError as-is
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_PRINT_PREVIEW: Error waiting for Print Preview window: {str(e)}. "
                f"Client code: {client_code}"
            )
        
        # Step 9: Click save button at (601.25, 45)
        error_step = "save_button_click"
        error_context["step"] = "Clicking save button in Print Preview"
        print("    [*] Clicking save button in Print Preview...")
        try:
            click(PRINT_PREVIEW_SAVE, delay=0.5)
            wait(2.0)  # Wait for save dialog
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_SAVE_BUTTON: Failed to click save button at {PRINT_PREVIEW_SAVE}: {str(e)}. "
                f"Client code: {client_code}"
            )
        
        # Step 10: Wait for save dialog and enter filename
        error_step = "save_dialog_wait"
        error_context["step"] = "Waiting for save dialog"
        print("    [*] Waiting for save dialog...")
        try:
            if not wait_for_window(app, "Save Print Output As", timeout=10.0):
                raise RuntimeError(
                    f"MIND_REPORT_ERROR_SAVE_DIALOG_TIMEOUT: Save dialog 'Save Print Output As' did not appear within 10 seconds. "
                    f"Client code: {client_code}"
                )
        except RuntimeError:
            raise  # Re-raise RuntimeError as-is
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_SAVE_DIALOG: Error waiting for save dialog: {str(e)}. "
                f"Client code: {client_code}"
            )
        
        # Generate save path
        error_step = "file_save"
        error_context["step"] = "Saving file"
        try:
            save_path = get_save_path(client_code)
            save_dir = os.path.dirname(save_path)
            save_filename = os.path.basename(save_path)
            
            print(f"    [*] Saving file to: {save_path}")
            
            # Navigate to save directory if needed (save dialog might open in different location)
            wait(1.0)
            enter_save_file_name(save_path, clear_first=True, delay=0.5)
            wait(1.0)
            
            # Click Save button
            print("    [*] Clicking Save button...")
            save_file(click_save_button=True, use_enter=True, delay=2.0)
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_FILE_SAVE: Failed to save file: {str(e)}. "
                f"Client code: {client_code}, Save path: {save_path if 'save_path' in locals() else 'unknown'}"
            )
        
        # Step 11: Verify file exists
        error_step = "file_verify"
        error_context["step"] = "Verifying file was saved"
        print("    [*] Verifying file was saved...")
        try:
            if not verify_file_exists(save_path, timeout=10.0):
                raise RuntimeError(
                    f"MIND_REPORT_ERROR_FILE_VERIFY: File was not saved or is empty: {save_path}. "
                    f"Client code: {client_code}"
                )
        except RuntimeError:
            raise  # Re-raise RuntimeError as-is
        except Exception as e:
            raise RuntimeError(
                f"MIND_REPORT_ERROR_FILE_VERIFY: Error verifying file: {str(e)}. "
                f"Client code: {client_code}, Save path: {save_path if 'save_path' in locals() else 'unknown'}"
            )
        
        print(f"    [✓] File saved successfully: {save_path}")
        return save_path
        
    except RuntimeError as e:
        # RuntimeError already has formatted message - re-raise
        error_msg = str(e)
        print(f"    [✗] Error during import mind report: {error_msg}")
        import traceback
        # Include traceback in error message for debugging
        tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        print(f"    [*] Traceback:\n{tb_str}")
        raise RuntimeError(f"{error_msg}\nTraceback:\n{tb_str}")
    except Exception as e:
        # Unexpected exception - format with context
        error_msg = (
            f"MIND_REPORT_ERROR_UNEXPECTED: Unexpected error during mind report import: {str(e)}. "
            f"Client code: {client_code}, Error step: {error_step or 'unknown'}, "
            f"Error context: {error_context}"
        )
        print(f"    [✗] {error_msg}")
        import traceback
        tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        print(f"    [*] Traceback:\n{tb_str}")
        raise RuntimeError(f"{error_msg}\nTraceback:\n{tb_str}")
    finally:
        # Step 12: Always close VAEEG application
        if app:
            try:
                print("    [*] Closing VAEEG application...")
                close_application(app, exe_path)
            except Exception as close_error:
                print(f"    [!] Warning: Error closing VAEEG application: {close_error}")
                # Don't raise - we want to report the original error, not the close error

