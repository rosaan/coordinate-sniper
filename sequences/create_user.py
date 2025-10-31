"""
Sequence for creating a new user in the VAEEG application.
"""
from utils import click, click_and_type, wait, get_clipboard
from utils.app_manager import connect_or_start, bring_up_window

# Coordinate definitions for the create user flow
CREATE_USER_BTN = (442.5, 205.0)
CLIENT_ID = (436.25, 380.0)
FIRST_NAME = (468.75, 481.25)
LAST_NAME = (631.25, 481.25)
SAVE_BTN = (677.5, 208.75)
RECORDING_LINK_COPY = (1023.75, 386.25)
CLOSE_LINK_CODE = (1303.75, 213.75)

# Application configuration
EXE_PATH = r"C:\\Program Files (x86)\\VAEEG\\VA.exe"
WINDOW_TITLE_REGEX = r"VAEEG - \[Client\]"


def create_user(client_id: str, first_name: str, last_name: str, 
                exe_path: str = EXE_PATH, 
                window_title_regex: str = WINDOW_TITLE_REGEX) -> str:
    """
    Create a new user and retrieve the recording link.
    
    Args:
        client_id: Client ID to use
        first_name: First name for the user
        last_name: Last name for the user
        exe_path: Path to the VAEEG executable
        window_title_regex: Regex pattern to match the window title
        
    Returns:
        The recording link URL
    """
    # Connect to or start the application
    app = connect_or_start(exe_path)
    win = bring_up_window(app, window_title_regex)
    
    # Execute the create user sequence
    click(CREATE_USER_BTN)
    click_and_type(CLIENT_ID, client_id)
    click_and_type(FIRST_NAME, first_name)
    click_and_type(LAST_NAME, last_name)
    click(SAVE_BTN)
    wait(5)
    click(RECORDING_LINK_COPY)
    wait(1)
    click(CLOSE_LINK_CODE)
    
    # Get the URL from clipboard
    url = get_clipboard()
    
    return url
