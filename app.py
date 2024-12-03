import streamlit as st
from threading import Lock
import os
import tempfile
from pathlib import Path
import logging
import anthropic

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Lock for mutex editing
mutex = Lock()
lock_holder = None  # Track who holds the lock

# Use hand.js as consensus state file
consensus_state_file = Path("hand.js")


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


logger.debug(f"Using hand.js as consensus state file")

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

# Page config
st.set_page_config(page_title="Consensus Python Editor", layout="wide")

# Sidebar: User identification
st.sidebar.title("User Identification")
username = st.sidebar.text_input("Your Name")
if not username:
    st.sidebar.warning("Please enter your name to proceed.")

# Main content
st.title("Consensus Python Editor")

# Editor column
st.subheader("Code Editor")
state = load_consensus_state()

# Anthropic API setup
client = anthropic.Anthropic()

# Editing interface
if username:
    st.code(state, language="javascript")

    # Chat interface
    st.subheader("Chat with AI to Edit Code")
    user_message = st.text_input("Your message to the AI")
    if st.button("Send"):
        logger.info(f"{username} sent message: {user_message}")
        
        # Call Anthropic API using messages API
        try:
            ai_response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                temperature=0,
                system="You are an AI assistant that helps edit code. Respond with the updated code based on the user's request.",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Here is the current state of the code:\n\n{state}\n\nPlease update the code based on the following request: {user_message}"
                            }
                        ]
                    }
                ]
            )
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {str(e)}")
            st.error("Oops, something went wrong calling the AI assistant. Please try again.")
        else:
            # Display AI response
            st.write("AI Assistant:")
            st.write(ai_response.content)
            
            # Extract and save new state if provided
            new_state = extract_code_from_response(ai_response.content)
            if new_state:
                logger.debug("Saving changes from AI response")
                save_consensus_state(new_state)
                logger.info(f"Changes submitted successfully based on {username}'s request")
                st.success("Code updated based on your request!")
            else:
                logger.info("No code changes found in AI response")
                st.info("The AI did not suggest any code changes.")
        
else:
    st.info("Please enter your name to edit the code.")
    st.code(state, language="javascript")
