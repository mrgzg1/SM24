import streamlit as st
from threading import Lock
import os
import tempfile
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Lock for mutex editing
mutex = Lock()
lock_holder = None  # Track who holds the lock

# Create temp directory for consensus state
temp_dir = Path(tempfile.gettempdir()) / "consensus_app"
temp_dir.mkdir(exist_ok=True)
consensus_state_file = temp_dir / "consensus_state.py"

logger.debug(f"Using temp directory: {temp_dir}")
logger.debug(f"Consensus state file: {consensus_state_file}")

# Load initial state
if not consensus_state_file.exists():
    logger.info("Creating initial consensus state file")
    with open(consensus_state_file, "w") as f:
        f.write("# Initial Python code\n\ndef main():\n    print('Hello World!')")

def load_consensus_state():
    logger.debug("Loading consensus state")
    with open(consensus_state_file, "r") as f:
        content = f.read()
        logger.debug(f"Loaded content: {content[:100]}...")  # Log first 100 chars
        return content

def save_consensus_state(new_state):
    logger.debug("Saving new consensus state")
    logger.debug(f"New state content: {new_state[:100]}...")  # Log first 100 chars
    with open(consensus_state_file, "w") as f:
        f.write(new_state)
    logger.info("Successfully saved new state")
        
def validate_python_code(code):
    logger.debug("Validating Python code")
    try:
        compile(code, '<string>', 'exec')
        logger.debug("Code validation successful")
        return True
    except SyntaxError as e:
        logger.error(f"Code validation failed: {str(e)}")
        return False

# Page config
st.set_page_config(page_title="Consensus Python Editor", layout="wide")

# Sidebar: User identification
st.sidebar.title("User Identification")
username = st.sidebar.text_input("Your Name")
if not username:
    st.sidebar.warning("Please enter your name to proceed.")

# Main content
st.title("Consensus Python Editor")

# Split into columns for editor and preview
col1, col2 = st.columns(2)

with col1:
    st.subheader("Code Editor")
    state = load_consensus_state()
    
    # Editing interface
    if username:
        new_state = st.text_area("Edit Python code:", value=state, height=400)

        if st.button("Submit Changes"):
            logger.info(f"Attempting to submit changes by {username}")
            if validate_python_code(new_state):
                with mutex:
                    if lock_holder is None:
                        lock_holder = username
                        logger.debug("Saving changes")
                        save_consensus_state(new_state)
                        lock_holder = None  # Release lock immediately after save
                        logger.info(f"Changes submitted successfully by {username}")
                        st.success("Changes submitted successfully!")
                    else:
                        logger.warning(f"Lock held by {lock_holder}, {username} cannot save")
                        st.warning(f"Cannot save - lock held by {lock_holder}. Please try again later.")
            else:
                logger.error(f"Invalid code submission by {username}")
                st.error("Invalid Python code. Please fix syntax errors.")
    else:
        st.info("Please enter your name to edit the code.")
        st.code(state, language="python")

with col2:
    st.subheader("Live Preview")
    try:
        with st.expander("Code Output", expanded=True):
            logger.debug("Attempting to execute current state")
            exec(state)
    except Exception as e:
        logger.error(f"Error executing code: {str(e)}")
        st.error(f"Error executing code: {str(e)}")
