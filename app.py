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
consensus_state_file = sorted(Path(".").glob("hand_*.js"))[-1]

class CodeState:
    @staticmethod
    def get_current_state():
        logger.debug("Loading consensus state")
        with open(consensus_state_file, "r") as f:
            content = f.read()
            logger.debug(f"Loaded content: {content[:100]}...")  # Log first 100 chars
            return content
    
    @staticmethod
    def update_current_state(new_state):
        logger.debug("Updating current state")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        versioned_file = f"hand_{timestamp}.js"
        with open(versioned_file, "w") as f:
            f.write(new_state)
        logger.info(f"Successfully updated current state to {versioned_file}")

    @staticmethod
    def generate_new_state(user_prompt):
        logger.info(f"Generating new state based on user prompt: {user_prompt}")
        current_state = CodeState.get_current_state()
        
        # Call Anthropic API using messages API
        try:
            ai_response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                temperature=0,
                system="You are an AI coding assistant that helps evolve a JavaScript application called 'hand.js' based on user feedback. Your goal is to generate an updated version of the entire 'hand.js' file, incorporating user-requested changes while ensuring the app remains robust and functional. Keep the changes incremental and concise. Output the entire updated 'hand.js' file without truncating it. You may reject user requests if they are too extensive or compromise the core body pose detection functionality of the app. OUTPUT THE FULL CODE.",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Here is the current state of the code:\n\n{current_state}\n\nPlease update the code based on the following request: {user_prompt}"
                            }
                        ]
                    }
                ]
            )
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {str(e)}")
            raise e
        else:
            # Extract new state from AI response
            new_state = extract_code_from_response(ai_response.content)
            if new_state:
                logger.debug("Generated new state from AI response")
                return new_state
            else:
                logger.warning("No code changes found in AI response")
                return current_state


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
                    if code_block:
                        return code_block
    
    # If no code block found, return None
    return None


logger.debug(f"Using {consensus_state_file} as consensus state file")

# Page config
st.set_page_config(page_title="Consensus Flow: Collaborative Body Art", layout="wide")

# Sidebar: User identification
st.sidebar.title("User Identification")
username = st.sidebar.text_input("Give yourself an identity")
if not username:
    st.sidebar.warning("Please enter your legal name to proceed.")

# Main content
st.title("Consensus Flow")

# Editor column
st.subheader("Code Viewer")
state = CodeState.get_current_state()

# Anthropic API setup
client = anthropic.Anthropic()

# Editing interface
if username:
    st.code(state, language="javascript")
    
    # Chat interface moved under user identification
    st.sidebar.subheader("Chat with AI to Edit Code")
    user_message = st.sidebar.text_input("Your message to the AI")
    if st.sidebar.button("Send"):
        logger.info(f"{username} sent message: {user_message}")
        
        try:
            new_state = CodeState.generate_new_state(user_message)
            
            # Show diff of changes
            diff = difflib.unified_diff(state.splitlines(), new_state.splitlines(), lineterm='')
            st.text('\n'.join(diff))
            
            CodeState.update_current_state(new_state)
            logger.info(f"Changes submitted successfully based on {username}'s request")
            # Show success message on top of the code editor
            st.success("Code updated based on your request!", anchor="viewer")
        except Exception as e:
            logger.error(f"Error generating new state: {str(e)}")
            st.error("Oops, something went wrong updating the code. Please try again.")
        
else:
    st.info("Please enter your name to view the code.")
    st.code(state, language="javascript")
