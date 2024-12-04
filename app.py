import streamlit as st
from threading import Lock
import os
import tempfile
from pathlib import Path
import logging
import anthropic
from datetime import datetime
import difflib

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Lock for mutex editing
mutex = Lock()
lock_holder = None  # Track who holds the lock

# Use latest version of hand.js as consensus state file
consensus_state_files = sorted(Path(".").glob("hand_*.js"))
logger.debug("~~~")
logger.debug(consensus_state_files)
default_state_file = consensus_state_files[0]

class CodeState:
    @staticmethod
    def get_current_state(state_file):
        logger.debug(f"Loading consensus state from {state_file}")
        with open(state_file, "r") as f:
            content = f.read()
            logger.debug(f"Loaded content: {content[:100]}...")  # Log first 100 chars
            return content
    
    @staticmethod
    def update_current_state(new_state):
        logger.debug("Updating current state")
        if not new_state:
            logger.info("No new state to update")
            return
            
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        versioned_file = f"hand_{timestamp}.js"
        
        # Update hand.html with new filename
        html_path = Path("hand.html").absolute()
        logger.debug(f"Reading hand.html from: {html_path}")
        with open(html_path, "r") as f:
            html_content = f.read()
        
        # Replace script src containing hand*.js with new filename
        import re
        updated_html = re.sub(
            r'<script src="hand_[^"]*\.js">', 
            f'<script src="{versioned_file}">', 
            html_content
        )
        
        logger.debug(f"Writing updated hand.html back to: {html_path}")
        with open(html_path, "w") as f:
            f.write(updated_html)
            
        # Write new state file
        js_path = Path(versioned_file).absolute()
        logger.debug(f"Writing new state file to: {js_path}")
        with open(js_path, "w") as f:
            f.write(new_state)
            
        logger.info(f"Successfully updated current state to {versioned_file}")

    @staticmethod
    def generate_new_state(user_prompt, state_file, username):
        global lock_holder
        
        # Try to acquire lock
        if not mutex.acquire(blocking=False):
            logger.warning(f"Lock acquisition failed - held by {lock_holder}")
            raise Exception(f"Another user ({lock_holder}) is currently editing. Please wait and try again.")
        
        lock_holder = username
        logger.info(f"Lock acquired by {username}")
        
        try:
            logger.info(f"Generating new state based on user prompt: {user_prompt}")
            current_state = CodeState.get_current_state(state_file)
            
            # Call Anthropic API using messages API
            try:
                ai_response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=8192,
                    temperature=0,
                    system="You are an AI coding assistant that helps evolve a JavaScript application called 'hand.js' based on user feedback. Your goal is to generate an updated version of the entire 'hand.js' file, incorporating user-requested changes while ensuring the app remains robust and functional. Keep the changes incremental and concise. Output the entire updated 'hand.js' file without truncating it. You may reject user requests if they are too extensive or compromise the core body pose detection functionality of the app. OUTPUT THE FULL CODE. DO NOT SKIP SECTIONS LIKE SUCH: // [Rest of the code remains exactly the same] WRITE THE FULL CODE",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Here is the current state of the code:\n\n```{current_state}```\n\nPlease update the code based on the following request: \n{user_prompt}"
                                }
                            ]
                        }
                    ]
                )
                logger.debug(ai_response)
            except Exception as e:
                logger.error(f"Error calling Anthropic API: {str(e)}")
                raise e
            else:
                # Extract new state from AI response
                new_state = extract_code_from_response(ai_response.content)
                if new_state:
                    # Check if code actually changed
                    if new_state == current_state:
                        logger.info("No code changes detected in AI response")
                        return None
                        
                    logger.debug("Generated new state from AI response")
                    return new_state
                else:
                    logger.warning("No code changes found in AI response")
                    return None
        finally:
            # Always release lock
            mutex.release()
            lock_holder = None
            logger.info(f"Lock released by {username}")


def extract_code_from_response(response):
    print(response)
    # Look for code block delimited by triple backticks
    for block in response:
        if isinstance(block, anthropic.types.TextBlock):
            text = block.text
            code_start = text.find("```")
            if code_start != -1:
                code_end = text.find("```", code_start + 3)
                if code_end != -1:
                    code_block = text[code_start + 3:code_end].strip()
                    # Remove "javascript" or similar language identifier from first line if present
                    if code_block:
                        lines = code_block.split('\n')
                        if lines[0].lower().strip() in ['javascript', 'js']:
                            code_block = '\n'.join(lines[1:])
                        return code_block
    
    # If no code block found, return None
    return None


logger.debug(f"Using {default_state_file} as default consensus state file")
# Page config
st.set_page_config(page_title="Consensus Flow: Collaborative Body Art", layout="wide")

# Sidebar: User identification
st.sidebar.title("User Identification")

# Check if username is already in session state
if 'username' not in st.session_state:
    username = st.sidebar.text_input("Give yourself an identity")
    if username:
        logger.debug("Saving username to session state")
        st.session_state.username = username
        # st.write(st.session_state.username)
        logger.debug(f"Saved username: {st.session_state.username}")  # Debug line
else:
    username = st.session_state.username
    logger.debug(f"Retrieved username from session state: {username}")  # Debug line
    st.sidebar.text_input("Give yourself an identity", value=username, disabled=False)

if not username:
    st.sidebar.warning("Please enter your legal name to proceed.")

# Main content
st.title("Consensus Flow")

# Editor column
st.subheader("Code Viewer")

# Add dropdown to select file version
selected_state_file = st.selectbox("Select file version", consensus_state_files, index=len(consensus_state_files)-1)
state = CodeState.get_current_state(selected_state_file)

# Add delete all button
if 'confirm_delete' not in st.session_state:
    st.session_state.confirm_delete = False

if st.sidebar.button("Delete All Versions", type="secondary"):
    st.session_state.confirm_delete = True

if st.session_state.confirm_delete:
    if st.sidebar.button("Confirm Delete All?", type="primary"):
        # Delete all hand_*.js files except hand_0base.js
        for file in Path(".").glob("hand_*.js"):
            if file.name != "hand_0base.js":
                file.unlink()
        st.sidebar.success("All versions deleted except base version")
        st.session_state.confirm_delete = False
        # Refresh the page to update the file list
        st.rerun()
    if st.sidebar.button("Cancel", type="secondary"):
        st.session_state.confirm_delete = False

# Anthropic API setup
client = anthropic.Anthropic()

# Editing interface
if username:
    # Only show code editor when not generating
    if not st.session_state.get('generation_in_progress', False):
        code_container = st.empty()
        code_container.code(state, language="javascript")
    else:
        # Clear the code display while generating
        st.empty()
    
    # Chat interface moved under user identification
    st.sidebar.subheader("Chat with AI to Edit Code")
    user_message = st.sidebar.text_input("Your message to the AI")

    # Initialize generation_in_progress in session state if not present
    if 'generation_in_progress' not in st.session_state:
        st.session_state.generation_in_progress = False

    # Disable button when message empty or generation in progress
    button_disabled = not user_message or st.session_state.generation_in_progress
    if st.sidebar.button("Send", disabled=button_disabled):
        if not st.session_state.generation_in_progress:
            logger.info(f"{username} sent message: {user_message}")
            st.session_state.generation_in_progress = True
            
            # Create a loading placeholder
            with st.spinner("🤖 Neural circuits firing... pondering your request..."):
                try:
                    new_state = CodeState.generate_new_state(user_message, selected_state_file, username)
                    
                    if new_state is None:
                        st.info("No code changes were needed based on your request.")
                    else:
                        CodeState.update_current_state(new_state)
                        logger.info(f"Changes submitted successfully based on {username}'s request")
                        # Show success message on top of the code editor
                        st.success("Code updated based on your request!")
                except Exception as e:
                    logger.error(f"Error generating new state: {str(e)}")
                    st.error(str(e))
                finally:
                    st.session_state.generation_in_progress = False
        else:
            st.warning("Please wait for the current request to complete before submitting a new one.")

else:
    st.info("Please enter your name to view the code.")
    st.code(state, language="javascript")
