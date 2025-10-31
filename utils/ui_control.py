"""
UI Control utilities for automating GUI interactions.
Provides functions for clicking, typing, waiting, and checking visibility.
"""
import time
import os
import sys
import subprocess
import platform
import pyautogui
import pyperclip
from typing import Tuple, Optional, Callable
# OCR/Tesseract is resource-intensive - only enable if needed
# Set this to False to disable OCR and save resources on slow laptops
OCR_ENABLED = False  # Disabled by default for slow laptops

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


def click(coords: Tuple[float, float], delay: float = 0.05) -> None:
    """
    Click at the specified coordinates.
    
    Args:
        coords: Tuple of (x, y) coordinates
        delay: Delay after clicking (in seconds)
    """
    x, y = coords
    pyautogui.click(x, y)
    if delay > 0:
        time.sleep(delay)


def double_click(coords: Tuple[float, float], delay: float = 0.05) -> None:
    """
    Double-click at the specified coordinates.
    
    Args:
        coords: Tuple of (x, y) coordinates
        delay: Delay after clicking (in seconds)
    """
    x, y = coords
    pyautogui.doubleClick(x, y)
    if delay > 0:
        time.sleep(delay)


def right_click(coords: Tuple[float, float], delay: float = 0.05) -> None:
    """
    Right-click at the specified coordinates.
    
    Args:
        coords: Tuple of (x, y) coordinates
        delay: Delay after clicking (in seconds)
    """
    x, y = coords
    pyautogui.rightClick(x, y)
    if delay > 0:
        time.sleep(delay)


def click_and_type(coords: Tuple[float, float], text: str, clear_first: bool = True, 
                   type_interval: float = 0.02, delay: float = 0.2) -> None:
    """
    Click at coordinates and type text.
    Optimized for faster performance.
    
    Args:
        coords: Tuple of (x, y) coordinates
        text: Text to type
        clear_first: Whether to clear existing text first (Ctrl+A, Backspace)
        type_interval: Delay between keystrokes (in seconds)
        delay: Delay after typing (in seconds)
    """
    x, y = coords
    pyautogui.click(x, y)
    time.sleep(0.1)  # Wait for field focus
    
    if clear_first:
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.05)  # Wait for selection
        pyautogui.press("backspace")
        time.sleep(0.05)  # Wait for clearing
    
    pyautogui.typewrite(text, interval=type_interval)
    if delay > 0:
        time.sleep(delay)


def type_text(text: str, interval: float = 0.02) -> None:
    """
    Type text at current cursor position.
    
    Args:
        text: Text to type
        interval: Delay between keystrokes (in seconds)
    """
    pyautogui.typewrite(text, interval=interval)


def press_key(key: str, presses: int = 1, interval: float = 0.1) -> None:
    """
    Press a key.
    
    Args:
        key: Key to press (e.g., 'enter', 'tab', 'esc')
        presses: Number of times to press the key
        interval: Delay between presses (in seconds)
    """
    pyautogui.press(key, presses=presses, interval=interval)


def hotkey(*keys: str, interval: float = 0.1) -> None:
    """
    Press a combination of keys simultaneously.
    
    Args:
        *keys: Keys to press together (e.g., 'ctrl', 'c')
        interval: Delay after the hotkey (in seconds)
    """
    pyautogui.hotkey(*keys)
    if interval > 0:
        time.sleep(interval)


def wait(seconds: float) -> None:
    """
    Wait for a specified number of seconds.
    
    Args:
        seconds: Number of seconds to wait
    """
    time.sleep(seconds)


def wait_for_pixel_change(coords: Tuple[float, float], 
                         timeout: float = 10.0,
                         check_interval: float = 0.1,
                         initial_color: Optional[Tuple[int, int, int]] = None,
                         min_change_threshold: int = 10) -> bool:
    """
    Wait until pixel color at coordinates changes (useful for detecting UI changes).
    Lightweight alternative to OCR - just checks if pixel color changed.
    
    Args:
        coords: Tuple of (x, y) coordinates to monitor
        timeout: Maximum time to wait (in seconds)
        check_interval: How often to check (in seconds)
        initial_color: Initial RGB color to compare against. If None, uses first sample.
        min_change_threshold: Minimum RGB difference to consider as change
        
    Returns:
        True if pixel changed, False if timeout
    """
    x, y = int(coords[0]), int(coords[1])
    start_time = time.time()
    
    # Get initial color if not provided
    if initial_color is None:
        try:
            screenshot = pyautogui.screenshot()
            initial_color = screenshot.getpixel((x, y))
        except Exception:
            # If we can't get initial color, just wait the timeout
            time.sleep(timeout)
            return False
    
    while time.time() - start_time < timeout:
        try:
            screenshot = pyautogui.screenshot()
            current_color = screenshot.getpixel((x, y))
            
            # Check if color changed significantly
            color_diff = sum(abs(a - b) for a, b in zip(current_color, initial_color))
            if color_diff >= min_change_threshold:
                return True
        except Exception:
            pass
        
        time.sleep(check_interval)
    
    return False


def wait_for_element_ready(coords: Tuple[float, float], 
                          timeout: float = 10.0,
                          check_interval: float = 0.1,
                          stable_duration: float = 0.2) -> bool:
    """
    Wait until element at coordinates appears/is ready by checking pixel stability.
    Checks if pixel color stabilizes (doesn't change for stable_duration).
    Lightweight alternative to OCR - detects when UI element is ready.
    
    Args:
        coords: Tuple of (x, y) coordinates to monitor
        timeout: Maximum time to wait (in seconds)
        check_interval: How often to check (in seconds)
        stable_duration: How long pixel must be stable to consider ready (in seconds)
        
    Returns:
        True if element is ready, False if timeout
    """
    x, y = int(coords[0]), int(coords[1])
    start_time = time.time()
    last_color = None
    color_stable_since = None
    
    while time.time() - start_time < timeout:
        try:
            screenshot = pyautogui.screenshot()
            current_color = screenshot.getpixel((x, y))
            
            if last_color is None:
                last_color = current_color
                color_stable_since = time.time()
            elif current_color == last_color:
                # Color is stable
                if color_stable_since is None:
                    color_stable_since = time.time()
                elif time.time() - color_stable_since >= stable_duration:
                    # Color has been stable long enough
                    return True
            else:
                # Color changed, reset stability timer
                last_color = current_color
                color_stable_since = time.time()
        except Exception:
            pass
        
        time.sleep(check_interval)
    
    return False


def wait_for(condition: Callable[[], bool], timeout: float = 10.0, 
             check_interval: float = 0.2, error_message: Optional[str] = None) -> bool:
    """
    Wait until a condition is met or timeout occurs.
    
    Args:
        condition: Callable that returns True when condition is met
        timeout: Maximum time to wait (in seconds)
        check_interval: How often to check the condition (in seconds)
        error_message: Optional error message to raise on timeout
        
    Returns:
        True if condition was met, False if timeout occurred
        
    Raises:
        TimeoutError: If timeout occurs and error_message is provided
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition():
            return True
        time.sleep(check_interval)
    
    if error_message:
        raise TimeoutError(error_message)
    return False


def is_visible(coords: Tuple[float, float], region: Optional[Tuple[int, int, int, int]] = None,
               confidence: float = 0.8) -> bool:
    """
    Check if something is visible at the specified coordinates.
    This is a placeholder - implement based on your specific needs.
    For image matching, use locate_on_screen instead.
    
    Args:
        coords: Tuple of (x, y) coordinates to check
        region: Optional region (left, top, width, height) to search within
        confidence: Confidence threshold (for image matching)
        
    Returns:
        True if visible, False otherwise
    """
    # This is a simple implementation - you may want to enhance this
    # based on your specific UI automation needs
    try:
        # For now, just check if coordinates are within screen bounds
        screen_width, screen_height = pyautogui.size()
        x, y = coords
        return 0 <= x <= screen_width and 0 <= y <= screen_height
    except Exception:
        return False


def locate_on_screen(image_path: str, confidence: float = 0.8, 
                    region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Tuple[int, int, int, int]]:
    """
    Locate an image on the screen.
    
    Args:
        image_path: Path to the image file to search for
        confidence: Confidence threshold (0.0 to 1.0)
        region: Optional region (left, top, width, height) to search within
        
    Returns:
        Tuple of (left, top, width, height) if found, None otherwise
    """
    try:
        location = pyautogui.locateOnScreen(image_path, confidence=confidence, region=region)
        if location:
            return (location.left, location.top, location.width, location.height)
        return None
    except pyautogui.ImageNotFoundException:
        return None


def click_image(image_path: str, confidence: float = 0.8, 
               region: Optional[Tuple[int, int, int, int]] = None, 
               timeout: float = 5.0) -> bool:
    """
    Find and click an image on the screen.
    
    Args:
        image_path: Path to the image file to search for
        confidence: Confidence threshold (0.0 to 1.0)
        region: Optional region (left, top, width, height) to search within
        timeout: Maximum time to wait for image to appear
        
    Returns:
        True if image was found and clicked, False otherwise
    """
    def find_and_click():
        location = locate_on_screen(image_path, confidence, region)
        if location:
            center_x = location[0] + location[2] // 2
            center_y = location[1] + location[3] // 2
            click((center_x, center_y))
            return True
        return False
    
    return wait_for(find_and_click, timeout=timeout)


def wait_for_clipboard_change(initial_content: Optional[str] = None,
                             timeout: float = 5.0,
                             check_interval: float = 0.1) -> str:
    """
    Wait until clipboard content changes from initial_content (or any change if None).
    Useful for waiting until a copy operation completes.
    
    Args:
        initial_content: Initial clipboard content to compare against. 
                        If None, uses current clipboard as baseline.
        timeout: Maximum time to wait (in seconds)
        check_interval: How often to check clipboard (in seconds)
        
    Returns:
        New clipboard content
        
    Raises:
        TimeoutError: If clipboard doesn't change within timeout
    """
    if initial_content is None:
        initial_content = pyperclip.paste()
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        current_content = pyperclip.paste()
        if current_content != initial_content and current_content.strip():
            return current_content
        time.sleep(check_interval)
    
    raise TimeoutError(f"Clipboard did not change within {timeout} seconds")


def get_clipboard(max_attempts: int = 3) -> str:
    """
    Get the current clipboard contents with retry logic for reliability.
    
    Args:
        max_attempts: Maximum number of attempts to read clipboard
        
    Returns:
        Clipboard text content
    """
    for attempt in range(max_attempts):
        try:
            content = pyperclip.paste()
            # Verify we got something valid
            if content is not None:
                return content
        except Exception as e:
            if attempt < max_attempts - 1:
                time.sleep(0.1)
                continue
            else:
                print(f"    [!] Failed to read clipboard after {max_attempts} attempts: {e}")
    return ""


def set_clipboard(text: str) -> None:
    """
    Set the clipboard contents.
    
    Args:
        text: Text to copy to clipboard
    """
    pyperclip.copy(text)


def scroll(coords: Tuple[float, float], clicks: int = 3, direction: str = 'down') -> None:
    """
    Scroll at the specified coordinates.
    
    Args:
        coords: Tuple of (x, y) coordinates
        clicks: Number of scroll clicks (positive for down, negative for up)
        direction: 'down' or 'up'
    """
    x, y = coords
    scroll_amount = clicks if direction == 'down' else -clicks
    pyautogui.scroll(scroll_amount, x=x, y=y)


def move_mouse(coords: Tuple[float, float], duration: float = 0.5) -> None:
    """
    Move mouse to the specified coordinates.
    
    Args:
        coords: Tuple of (x, y) coordinates
        duration: Time to take for the movement (in seconds)
    """
    x, y = coords
    pyautogui.moveTo(x, y, duration=duration)


def get_mouse_position() -> Tuple[int, int]:
    """
    Get the current mouse position.
    
    Returns:
        Tuple of (x, y) coordinates
    """
    return pyautogui.position()


def find_text_on_screen(text: str, region: Optional[Tuple[int, int, int, int]] = None,
                       case_sensitive: bool = False, exact_match: bool = False) -> bool:
    """
    Check if specified text is visible on the screen using OCR.
    NOTE: OCR is resource-intensive and disabled by default on slow laptops.
    
    Args:
        text: Text to search for
        region: Optional region (left, top, width, height) to search within.
                If None, searches entire screen.
        case_sensitive: Whether the search should be case-sensitive
        exact_match: If True, text must match exactly. If False, checks if text is contained.
        
    Returns:
        True if text is found, False otherwise
        
    Raises:
        ImportError: If pytesseract or PIL are not installed
    """
    if not OCR_ENABLED:
        raise RuntimeError(
            "OCR is disabled to save resources on slow laptops. "
            "Set OCR_ENABLED = True in utils/ui_control.py if you need OCR functionality."
        )
    if not OCR_AVAILABLE:
        raise ImportError(
            "OCR functionality requires pytesseract and Pillow. "
            "Install with: pip install pytesseract pillow"
        )
    
    # Capture screenshot
    if region:
        screenshot = pyautogui.screenshot(region=region)
    else:
        screenshot = pyautogui.screenshot()
    
    # Extract text using OCR
    try:
        extracted_text = pytesseract.image_to_string(screenshot)
    except Exception as e:
        print(f"OCR error: {e}")
        return False
    
    # Prepare text for comparison
    search_text = text if case_sensitive else text.lower()
    screen_text = extracted_text if case_sensitive else extracted_text.lower()
    
    # Check for match
    if exact_match:
        return search_text.strip() == screen_text.strip()
    else:
        return search_text in screen_text


def wait_for_text(text: str, timeout: float = 10.0, 
                 check_interval: float = 0.2,
                 region: Optional[Tuple[int, int, int, int]] = None,
                 case_sensitive: bool = False,
                 exact_match: bool = False,
                 error_message: Optional[str] = None,
                 use_ocr: Optional[bool] = None) -> bool:
    """
    Wait until specified text appears on the screen.
    
    By default, uses OCR if enabled. Can be forced to use OCR or use lightweight checks.
    If OCR is disabled and use_ocr=None, will use a simple time-based wait (not text detection).
    
    Args:
        text: Text to wait for
        timeout: Maximum time to wait (in seconds)
        check_interval: How often to check for the text (in seconds)
        region: Optional region (left, top, width, height) to search within.
                If None, searches entire screen.
        case_sensitive: Whether the search should be case-sensitive
        exact_match: If True, text must match exactly. If False, checks if text is contained.
        error_message: Optional error message to raise on timeout
        use_ocr: If True, force OCR usage. If False, skip OCR and just wait.
                 If None (default), use OCR if enabled, otherwise just wait.
        
    Returns:
        True if text was found (or wait completed if OCR disabled), False if timeout occurred
        
    Raises:
        TimeoutError: If timeout occurs and error_message is provided
        RuntimeError: If OCR is required but disabled
    """
    # Determine if we should use OCR
    should_use_ocr = use_ocr if use_ocr is not None else OCR_ENABLED
    
    if should_use_ocr:
        # Use OCR-based text detection
        if not OCR_AVAILABLE:
            raise ImportError(
                "OCR functionality requires pytesseract and Pillow. "
                "Install with: pip install pytesseract pillow"
            )
        
        def check_text():
            return find_text_on_screen(text, region, case_sensitive, exact_match)
        
        msg = error_message or f"Text '{text}' did not appear within {timeout} seconds"
        return wait_for(check_text, timeout=timeout, check_interval=check_interval, 
                       error_message=msg)
    else:
        # Lightweight mode: just wait for the timeout (no actual text detection)
        # This is useful when OCR is disabled but you still want to wait
        print(f"[*] OCR disabled - waiting {timeout}s (no text detection)")
        time.sleep(timeout)
        return True


def find_text_location(text: str, region: Optional[Tuple[int, int, int, int]] = None,
                      case_sensitive: bool = False) -> Optional[Tuple[int, int, int, int]]:
    """
    Find the location of text on the screen using OCR.
    NOTE: OCR is resource-intensive and disabled by default on slow laptops.
    
    Args:
        text: Text to search for
        region: Optional region (left, top, width, height) to search within.
                If None, searches entire screen.
        case_sensitive: Whether the search should be case-sensitive
        
    Returns:
        Tuple of (left, top, width, height) if found, None otherwise.
        Note: OCR location accuracy may vary.
        
    Raises:
        ImportError: If pytesseract or PIL are not installed
    """
    if not OCR_ENABLED:
        raise RuntimeError(
            "OCR is disabled to save resources on slow laptops. "
            "Set OCR_ENABLED = True in utils/ui_control.py if you need OCR functionality."
        )
    if not OCR_AVAILABLE:
        raise ImportError(
            "OCR functionality requires pytesseract and Pillow. "
            "Install with: pip install pytesseract pillow"
        )
    
    # Capture screenshot
    if region:
        screenshot = pyautogui.screenshot(region=region)
        region_offset_x, region_offset_y = region[0], region[1]
    else:
        screenshot = pyautogui.screenshot()
        region_offset_x, region_offset_y = 0, 0
    
    # Extract text with bounding boxes
    try:
        data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
    except Exception as e:
        print(f"OCR error: {e}")
        return None
    
    # Prepare text for comparison
    search_text = text if case_sensitive else text.lower()
    
    # Search through detected text
    n_boxes = len(data['text'])
    for i in range(n_boxes):
        detected_text = data['text'][i] if case_sensitive else data['text'][i].lower()
        
        # Check if text matches (contains the search text)
        if search_text in detected_text and data['conf'][i] > 0:
            x = data['left'][i] + region_offset_x
            y = data['top'][i] + region_offset_y
            w = data['width'][i]
            h = data['height'][i]
            return (x, y, w, h)
    
    return None


def click_text(text: str, timeout: float = 10.0,
              region: Optional[Tuple[int, int, int, int]] = None,
              case_sensitive: bool = False) -> bool:
    """
    Find and click on text on the screen.
    NOTE: OCR is resource-intensive and disabled by default on slow laptops.
    
    Args:
        text: Text to click on
        timeout: Maximum time to wait for text to appear (in seconds)
        region: Optional region (left, top, width, height) to search within.
                If None, searches entire screen.
        case_sensitive: Whether the search should be case-sensitive
        
    Returns:
        True if text was found and clicked, False otherwise
        
    Raises:
        ImportError: If pytesseract or PIL are not installed
    """
    if not OCR_ENABLED:
        raise RuntimeError(
            "OCR is disabled to save resources on slow laptops. "
            "Set OCR_ENABLED = True in utils/ui_control.py if you need OCR functionality."
        )
    if not OCR_AVAILABLE:
        raise ImportError(
            "OCR functionality requires pytesseract and Pillow. "
            "Install with: pip install pytesseract pillow"
        )
    
    def find_and_click():
        location = find_text_location(text, region, case_sensitive)
        if location:
            # Click at the center of the text bounding box
            center_x = location[0] + location[2] // 2
            center_y = location[1] + location[3] // 2
            click((center_x, center_y))
            return True
        return False
    
    return wait_for(find_and_click, timeout=timeout)


def wait_till_visible(text: str, timeout: float = 10.0, 
                     check_interval: float = 0.2,
                     region: Optional[Tuple[int, int, int, int]] = None,
                     case_sensitive: bool = False,
                     exact_match: bool = False,
                     error_message: Optional[str] = None,
                     return_bool: bool = False) -> Optional[bool]:
    """
    Wait until text is visible on screen. More intuitive name for "wait till I see it".
    By default, returns None (like wait()) and raises TimeoutError on failure.
    
    Args:
        text: Text to wait for
        timeout: Maximum time to wait (in seconds)
        check_interval: How often to check for the text (in seconds)
        region: Optional region (left, top, width, height) to search within.
                If None, searches entire screen.
        case_sensitive: Whether the search should be case-sensitive
        exact_match: If True, text must match exactly. If False, checks if text is contained.
        error_message: Optional error message to raise on timeout.
                      If None, uses default message.
        return_bool: If True, returns bool instead of raising exception.
                    If False (default), returns None on success, raises on timeout.
        
    Returns:
        None if return_bool=False (default), True if text found (return_bool=True),
        False if timeout occurred (return_bool=True)
        
    Raises:
        TimeoutError: If timeout occurs (unless return_bool=True)
        ImportError: If pytesseract or PIL are not installed
        
    Example:
        wait_till_visible("Save Complete")  # Returns None, raises on timeout
        wait_till_visible("Processing...", timeout=30.0)
        found = wait_till_visible("Done", return_bool=True)  # Returns True/False
    """
    msg = error_message or f"Text '{text}' did not appear within {timeout} seconds"
    # Pass use_ocr=None to inherit OCR_ENABLED setting
    result = wait_for_text(text, timeout, check_interval, region, 
                          case_sensitive, exact_match, 
                          error_message=msg if not return_bool else None,
                          use_ocr=None)
    
    if return_bool:
        return result
    # If not return_bool, wait_for_text already raised exception on timeout
    return None


def close_window(use_alt_f4: bool = True, delay: float = 0.2) -> None:
    """
    Close the currently active window.
    
    Args:
        use_alt_f4: If True, uses Alt+F4 to close. If False, uses ESC key.
        delay: Delay after closing (in seconds)
    """
    if use_alt_f4:
        hotkey("alt", "f4", interval=0)
    else:
        press_key("esc", interval=0)
    
    if delay > 0:
        time.sleep(delay)


def wait_till_save_dialog(timeout: float = 10.0, 
                         check_interval: float = 0.2) -> bool:
    """
    Wait until a save dialog appears on screen.
    Looks for common save dialog indicators like "Save As", "File name:", etc.
    
    Args:
        timeout: Maximum time to wait (in seconds)
        check_interval: How often to check for the dialog (in seconds)
        
    Returns:
        True if save dialog appeared, False if timeout occurred
        
    Raises:
        ImportError: If pytesseract or PIL are not installed
    """
    if not OCR_AVAILABLE:
        raise ImportError(
            "OCR functionality requires pytesseract and Pillow. "
            "Install with: pip install pytesseract pillow"
        )
    
    # Common save dialog texts to look for
    save_dialog_indicators = [
        "Save As",
        "Save",
        "File name:",
        "File Name:",
        "Save File",
        "Save to",
    ]
    
    def check_save_dialog():
        for indicator in save_dialog_indicators:
            if find_text_on_screen(indicator, case_sensitive=False):
                return True
        return False
    
    return wait_for(check_save_dialog, timeout=timeout, 
                   check_interval=check_interval,
                   error_message=f"Save dialog did not appear within {timeout} seconds")


def enter_save_file_name(filename: str, clear_first: bool = True,
                        type_interval: float = 0.02, delay: float = 0.1) -> None:
    """
    Enter a filename in the save dialog filename field.
    First navigates to the filename field (usually by clicking or Tab).
    
    Args:
        filename: Name of the file to save (without path, or with full path)
        clear_first: Whether to clear existing text first
        type_interval: Delay between keystrokes (in seconds)
        delay: Delay after typing (in seconds)
    """
    # Try to find and click on filename field by looking for "File name:" label
    # Then press Tab to move to the input field
    if OCR_AVAILABLE:
        try:
            # Look for "File name:" text and try to click near it
            location = find_text_location("File name:", case_sensitive=False)
            if location:
                # Click slightly to the right of the label to get to input field
                click((location[0] + location[2] + 50, location[1] + location[3] // 2), delay=0.1)
            else:
                # Fallback: try to find "File Name:" (different capitalization)
                location = find_text_location("File Name:", case_sensitive=False)
                if location:
                    click((location[0] + location[2] + 50, location[1] + location[3] // 2), delay=0.1)
                else:
                    # If we can't find the label, try Tab to navigate
                    press_key("tab", interval=0.1)
        except Exception:
            # Fallback: use Tab to navigate to filename field
            press_key("tab", interval=0.1)
    else:
        # Fallback: use Tab to navigate to filename field
        press_key("tab", interval=0.1)
    
    time.sleep(0.1)
    
    # Select all and clear if needed
    if clear_first:
        hotkey("ctrl", "a", interval=0.02)
        press_key("backspace", interval=0.02)
    
    # Type the filename
    type_text(filename, interval=type_interval)
    
    if delay > 0:
        time.sleep(delay)


def save_file(click_save_button: bool = True, use_enter: bool = True,
             delay: float = 0.3) -> None:
    """
    Click the Save button in a save dialog or press Enter to confirm save.
    
    Args:
        click_save_button: If True, tries to find and click "Save" button first.
                          Falls back to Enter if not found.
        use_enter: If True, presses Enter to save as fallback or primary method.
                   Works well when Save button is focused or for quick saves.
        delay: Delay after saving (in seconds)
    """
    saved = False
    
    # Try clicking Save button first if requested
    if click_save_button and OCR_AVAILABLE:
        try:
            # Try to find and click "Save" button
            if click_text("Save", timeout=2.0, case_sensitive=False):
                saved = True
        except Exception:
            pass
    
    # Fallback or primary: use Enter key
    if use_enter and not saved:
        press_key("enter", interval=0)
        saved = True
    
    if delay > 0:
        time.sleep(delay)


def retrieve_file(file_path: Optional[str] = None, 
                 from_clipboard: bool = True,
                 wait_for_download: bool = False,
                 download_timeout: float = 30.0) -> Optional[str]:
    """
    Retrieve a file path after saving/downloading.
    Can get path from clipboard or return provided path.
    
    Args:
        file_path: Direct file path to return (if known)
        from_clipboard: If True, gets file path from clipboard
        wait_for_download: If True, waits for download to complete (checks clipboard changes)
        download_timeout: Maximum time to wait for download (in seconds)
        
    Returns:
        File path string if found, None otherwise
    """
    if file_path:
        return file_path
    
    if from_clipboard:
        if wait_for_download:
            # Wait for clipboard to change (indicates download/save completed)
            initial_clipboard = get_clipboard()
            start_time = time.time()
            
            while time.time() - start_time < download_timeout:
                current_clipboard = get_clipboard()
                if current_clipboard != initial_clipboard and current_clipboard.strip():
                    # Check if it looks like a file path
                    if "\\" in current_clipboard or "/" in current_clipboard:
                        return current_clipboard.strip()
                time.sleep(0.2)
            
            # Return current clipboard even if it didn't change much
            clipboard_content = get_clipboard().strip()
            if clipboard_content:
                return clipboard_content
        else:
            # Just get current clipboard
            clipboard_content = get_clipboard().strip()
            if clipboard_content:
                return clipboard_content
    
    return None


def install_pytesseract(install_pillow: bool = True, 
                       check_tesseract_binary: bool = True) -> bool:
    """
    Install pytesseract and Pillow packages, and provide instructions for Tesseract OCR binary.
    
    Args:
        install_pillow: Whether to install Pillow package
        check_tesseract_binary: Whether to check if Tesseract OCR binary is installed
        
    Returns:
        True if packages were installed successfully, False otherwise
        
    Note:
        This function installs the Python packages (pytesseract, Pillow).
        For Windows, you also need to install the Tesseract OCR binary separately:
        1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
        2. Or use Chocolatey: choco install tesseract
        3. Or use winget: winget install UB-Mannheim.TesseractOCR
    """
    packages_to_install = []
    
    # Check if pytesseract is installed
    try:
        import pytesseract
        print("[✓] pytesseract is already installed")
    except ImportError:
        packages_to_install.append("pytesseract")
        print("[!] pytesseract is not installed")
    
    # Check if Pillow is installed
    if install_pillow:
        try:
            from PIL import Image
            print("[✓] Pillow is already installed")
        except ImportError:
            packages_to_install.append("Pillow")
            print("[!] Pillow is not installed")
    
    # Install missing packages
    if packages_to_install:
        print(f"\n[+] Installing packages: {', '.join(packages_to_install)}")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-q"
            ] + packages_to_install)
            print(f"[✓] Successfully installed: {', '.join(packages_to_install)}")
        except subprocess.CalledProcessError as e:
            print(f"[✗] Failed to install packages: {e}")
            return False
    else:
        print("[✓] All required Python packages are installed")
    
    # Check Tesseract OCR binary (especially important on Windows)
    if check_tesseract_binary:
        print("\n[+] Checking for Tesseract OCR binary...")
        is_windows = platform.system() == "Windows"
        
        try:
            import pytesseract
            # Try to get tesseract version
            try:
                version = pytesseract.get_tesseract_version()
                print(f"[✓] Tesseract OCR binary found (version: {version})")
                return True
            except Exception:
                # Binary not found or not in PATH
                print("[✗] Tesseract OCR binary not found or not in PATH")
                
                if is_windows:
                    print("\n" + "="*60)
                    print("TESSERACT OCR INSTALLATION REQUIRED FOR WINDOWS")
                    print("="*60)
                    print("\nTo install Tesseract OCR on Windows:")
                    print("\nOption 1 - Using winget (Windows 10/11):")
                    print("  winget install UB-Mannheim.TesseractOCR")
                    print("\nOption 2 - Using Chocolatey:")
                    print("  choco install tesseract")
                    print("\nOption 3 - Manual download:")
                    print("  1. Download from: https://github.com/UB-Mannheim/tesseract/wiki")
                    print("  2. Run the installer")
                    print("  3. Add Tesseract to PATH (usually: C:\\Program Files\\Tesseract-OCR)")
                    print("\nAfter installation, restart your terminal/Python environment.")
                    print("="*60 + "\n")
                else:
                    print("\nTo install Tesseract OCR:")
                    print("  macOS: brew install tesseract")
                    print("  Linux: sudo apt-get install tesseract-ocr")
                
                return False
        except ImportError:
            print("[!] Cannot check Tesseract binary - pytesseract not installed")
            return False
    
    return True

