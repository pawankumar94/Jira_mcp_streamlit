import os
import streamlit as st
import asyncio
import json
import subprocess
from dotenv import load_dotenv
import time
import psutil
import sys
import re
import traceback

# Load environment variables
load_dotenv()

# Jira credentials from environment variables
JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# Path to MCP server
MCP_SERVER_PATH = os.getenv("MCP_SERVER_PATH", os.path.join("..", "Jira_mcp", "mcp_server.py"))

# Configure page appearance
st.set_page_config(
    page_title="Jira Assistant",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Check if a process is running based on a command pattern
def is_process_running(pattern):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if cmdline and any(pattern in cmd for cmd in cmdline if cmd):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

# Function to start the MCP server
def start_mcp_server():
    if is_process_running("mcp_server.py"):
        st.sidebar.success("MCP server is already running!")
        return True
    
    try:
        cmd = ["python", MCP_SERVER_PATH]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        
        # Give the server some time to start
        time.sleep(2)
        
        # Check if the process is still running (didn't crash immediately)
        if process.poll() is None:
            st.sidebar.success("MCP server started successfully!")
            return True
        else:
            stdout, stderr = process.communicate()
            st.sidebar.error(f"MCP server failed to start: {stderr}")
            return False
    except Exception as e:
        st.sidebar.error(f"Error starting MCP server: {str(e)}")
        return False

# Function to get available tools from the MCP server using the correct approach
async def get_tools():
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        
        # Create server parameters for stdio connection
        server_params = StdioServerParameters(
            command="python",  # Executable
            args=[MCP_SERVER_PATH],  # Path to the MCP server script
            env=None  # Use current environment
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the connection
                await session.initialize()
                
                # List available tools
                tools_result = await session.list_tools()
                
                # Extract tools from the result
                if hasattr(tools_result, 'tools'):
                    return tools_result.tools
                else:
                    st.sidebar.warning("Unexpected tools result format")
                    return []
    except Exception as e:
        st.sidebar.error(f"Error getting tools: {str(e)}")
        return []

# Function to call an MCP tool
async def call_tool(tool_name, params):
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        
        # Create server parameters for stdio connection
        server_params = StdioServerParameters(
            command="python",  # Executable
            args=[MCP_SERVER_PATH],  # Path to the MCP server script
            env=None  # Use current environment
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the connection
                await session.initialize()
                
                # Call the tool
                result = await session.call_tool(tool_name, arguments=params)
                
                # Extract content from the result
                if hasattr(result, 'content') and result.content:
                    # Extract text from the first content item
                    content_item = result.content[0]
                    if hasattr(content_item, 'text'):
                        return content_item.text
                
                return str(result)
    except Exception as e:
        traceback.print_exc()
        st.error(f"Error calling tool: {str(e)}")
        return f"Error: {str(e)}"

# Helper function to extract ticket information using regex
def extract_ticket_info(text):
    # Try to extract project, summary, description, issue_type, and assignee with improved regex
    project_match = re.search(r'(?:project\s+(?:key\s+)?|in\s+)(?:"|\')?([A-Z0-9]+)(?:"|\')?\b|project\s*[=:]\s*(?:"|\')?([A-Z0-9]+)(?:"|\')?', text, re.IGNORECASE)
    summary_match = re.search(r'(?:title|summary)[=:]?\s*["\']([^"\']+?)["\']|(?:title|summary)[=:]?\s*([^,\.]+)', text, re.IGNORECASE)
    description_match = re.search(r'description[=:]?\s*["\']([^"\']+?)["\']|description[=:]?\s*([^,\.]+)', text, re.IGNORECASE)
    issue_type_match = re.search(r'(?:create|add)\s+(?:a|an)?\s+([Bb]ug|[Tt]ask|[Ss]tory|[Ee]pic|[Ii]mprovement)|type[=:]?\s*["\']?([A-Za-z]+)["\']?', text, re.IGNORECASE)
    assignee_match = re.search(r'assign\s+(it\s+)?to\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)', text, re.IGNORECASE)
    
    project = project_match.group(1) or project_match.group(2) if project_match else None
    summary = (summary_match.group(1) or summary_match.group(2)).strip() if summary_match else None
    description = (description_match.group(1) or description_match.group(2)).strip() if description_match else None
    
    # More robust issue type detection
    issue_type = None
    if issue_type_match:
        issue_type = (issue_type_match.group(1) or issue_type_match.group(2)).title() if issue_type_match else None
    else:
        # Check for specific keywords in the text
        if re.search(r'\b[Bb]ug\b', text):
            issue_type = "Bug"
        elif re.search(r'\b[Tt]ask\b', text):
            issue_type = "Task"
        elif re.search(r'\b[Ss]tory\b', text):
            issue_type = "Story"
        elif re.search(r'\b[Ee]pic\b', text):
            issue_type = "Epic"
        else:
            issue_type = "Task"  # Default to Task
    
    assignee = assignee_match.group(2) if assignee_match else None
    
    # If no description provided but we have a summary, use a generic description
    if not description and summary:
        description = f"This {issue_type.lower()} requires attention. Please see the summary for details."
    
    ticket_info = {
        "project_key": project,
        "summary": summary,
        "description": description,
        "issue_type": issue_type
    }
    
    # Add assignee if available
    if assignee:
        print(f"DEBUG - Adding assignee: {assignee}")
        ticket_info["assignee"] = assignee
    
    return ticket_info

# Function to handle ticket creation from natural language
async def create_jira_ticket_from_text(text):
    ticket_info = extract_ticket_info(text)
    st.session_state.ticket_info = ticket_info
    
    # Validate ticket information
    missing_fields = []
    if not ticket_info["project_key"]:
        missing_fields.append("project key")
    if not ticket_info["summary"]:
        missing_fields.append("summary/title")
    if not ticket_info["description"]:
        missing_fields.append("description")
    
    if missing_fields:
        return f"Error: Could not determine the following fields: {', '.join(missing_fields)}. Please provide all required information."
    
    # Print the ticket info for debugging
    print(f"Creating ticket with: {json.dumps(ticket_info, indent=2)}")
    
    # Create ticket
    result = await call_tool("create_jira_ticket", ticket_info)
    return result

# Function to search for Jira tickets
async def search_jira_tickets(query, max_results=10):
    params = {
        "query": query  # Changed from "jql_query" to "query" to match the MCP server's expectation
    }
    
    try:
        result = await call_tool("search_jira_tickets", params)
        # Check if the result contains an error
        if result.startswith('Error:') or 'errorMessages' in result:
            error_data = None
            try:
                error_data = json.loads(result.replace('Error:', '').strip())
            except json.JSONDecodeError:
                return f"Error: {result}"
                
            if error_data and 'errorMessages' in error_data:
                error_msg = error_data['errorMessages'][0] if error_data['errorMessages'] else "Unknown error"
                # Make error messages more user-friendly
                if "does not exist for the field 'project'" in error_msg:
                    return f"Error: Could not find the specified project. Please check the project key."
                elif "does not exist for the field 'assignee'" in error_msg:
                    return f"Error: Could not find the specified assignee. Please check the assignee name."
                else:
                    return f"Error: {error_msg}"
            else:
                return result
        return result
    except Exception as e:
        traceback.print_exc()
        return f"Error: {str(e)}"

# Function to get the default help message
def get_default_help_message():
    return f"""
👋 Welcome to Jira Assistant! I'm here to help you manage your Jira tickets efficiently.

Here are some things you can ask me to do:

1. Create a new ticket: 
   - "Create a bug in KAN titled 'Login page crashes' with description 'The login page crashes on Safari'"

2. Search for tickets: 
   - "Search for tickets in project KAN" 
   - "Find all open tickets"
   - "project = KAN AND issuetype = Task" (direct JQL query)

3. Get ticket details: 
   - "Show details for ticket KAN-123"
   - "Get info about KAN-123"
   - "Fetch details of ticket KAN-123"

What would you like to do today?
"""

# Function to get a Jira ticket by ID
async def get_jira_ticket(ticket_id):
    params = {
        "issue_key": ticket_id  # Changed from "ticket_id" to "issue_key" to match the MCP server's expectation
    }
    
    result = await call_tool("get_jira_ticket", params)
    return result

# Main function to set up the Streamlit app
def main():
    # Custom CSS for a cleaner UI
    st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton button {
        width: 100%;
    }
    .small-text {
        font-size: 14px;
    }
    .tool-box {
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 10px;
    }
    .success-box {
        background-color: #f0fff4;
        border: 1px solid #9ae6b4;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 10px;
    }
    .error-box {
        background-color: #fff5f5;
        border: 1px solid #feb2b2;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 10px;
    }
    /* Make chat input fixed at bottom with improved positioning */
    .stChatFloatingInputContainer {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        padding: 1rem !important;
        padding-bottom: 0.5rem !important;
        width: 100% !important;
        background-color: white !important;
        z-index: 999 !important;
        border-top: 1px solid #e6e9ef !important;
        box-shadow: 0px -4px 10px rgba(0, 0, 0, 0.05) !important;
    }
    /* Format chat messages */
    .stChatMessage {
        max-width: 100%;
        overflow-wrap: break-word;
        margin-bottom: 15px !important;
    }
    /* Fixed height scrollable container for chat */
    .chat-container {
        height: auto !important;
        overflow-y: visible !important;
        overflow-x: hidden !important;
        margin-top: 0 !important;
        padding-top: 0 !important;
        position: relative !important;
    }
    /* Force the chat interface to be at the top */
    .stChatContainer {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    /* Hide technical information in sidebar */
    .css-17ziqus {
        visibility: hidden;
    }
    /* Ensure spacing between messages */
    .message-spacer {
        height: 15px;
        width: 100%;
        display: block;
    }
    /* Chat footer to reserve space */
    .chat-footer-space {
        height: 150px;
        width: 100%;
        display: block;
    }
    /* Remove extra margins from the chat header elements */
    .chat-header h3, .chat-header p {
        margin-top: 0 !important;
        margin-bottom: 8px !important;
    }
    /* Force no padding on the tab container */
    .stTabs [data-baseweb=tab-panel] {
        padding-top: 0 !important;
    }
    /* Reset the layout for the entire chat interface */
    section[data-testid="stSidebar"] ~ div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"] {
        gap: 0 !important;
    }
    /* Streamlit vertical block override for chat */
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column"] > div[data-testid="stVerticalBlock"] {
        gap: 0 !important;
    }
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #f0f2f6;
        border-bottom: 2px solid #4059AD;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create a clean header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("Jira Assistant")
        st.subheader("Manage your Jira tickets with ease")
    
    # Display information about MCP client path in debug mode only
    st.sidebar.title("📊 Status")
    
    # Hide technical details in production mode
    if os.getenv("DEBUG_MODE", "false").lower() == "true":
        try:
            import mcp
            mcp_path = mcp.__file__
            mcp_version = getattr(mcp, "__version__", "unknown")
            st.sidebar.info(f"MCP version: {mcp_version}")
            st.sidebar.info(f"MCP path: {mcp_path}")
        except ImportError:
            st.sidebar.error("MCP package not properly installed")
    
    # Connection status indicator - simplified
    server_status = "🟢 Connected" if is_process_running("mcp_server.py") else "🔴 Disconnected"
    st.sidebar.success(server_status)
    
    # Initialize session state
    if "server_started" not in st.session_state:
        st.session_state.server_started = False
        
    if "tools" not in st.session_state:
        st.session_state.tools = []
        
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "chat"
        
    if "ticket_info" not in st.session_state:
        st.session_state.ticket_info = {
            "project_key": "",
            "summary": "",
            "description": "",
            "issue_type": "Task"
        }
    
    # Start MCP server on app startup if it's not already running
    if not st.session_state.server_started:
        st.session_state.server_started = start_mcp_server()
    
    # Button to restart the server - only show in debug mode
    if os.getenv("DEBUG_MODE", "false").lower() == "true":
        if st.sidebar.button("🔄 Restart MCP Server"):
            st.session_state.server_started = start_mcp_server()
    
    # Get available tools
    if st.session_state.server_started and not st.session_state.tools:
        try:
            # Get tools using the async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            st.session_state.tools = loop.run_until_complete(get_tools())
            loop.close()
        except Exception as e:
            if os.getenv("DEBUG_MODE", "false").lower() == "true":
                st.sidebar.error(f"Failed to get tools: {str(e)}")
    
    # Display available tools - only in debug mode
    if os.getenv("DEBUG_MODE", "false").lower() == "true":
        st.sidebar.subheader("🛠️ Available Tools")
        if st.session_state.tools:
            for tool in st.session_state.tools:
                # Use direct attribute access
                st.sidebar.markdown(f"**{tool.name}**: {tool.description}")
        else:
            st.sidebar.warning("No tools found. MCP server may not be properly connected.")
            
            # Refresh tools button
            if st.sidebar.button("🔄 Refresh Tools"):
                try:
                    # Get tools using the async function
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    st.session_state.tools = loop.run_until_complete(get_tools())
                    loop.close()
                except Exception as e:
                    st.sidebar.error(f"Failed to refresh tools: {str(e)}")
    
    # Add instructions to sidebar for demo
    st.sidebar.subheader("📝 Quick Guide")
    st.sidebar.info("""
    **Create a ticket**: 
    "Create a task in KAN titled '...' with description '...'"
    
    **Search tickets**:
    "Show all tasks assigned to Pawan Kumar"
    
    **Get ticket details**:
    "Get details for ticket KAN-123"
    """)
    
    # Add tabs for different functionalities
    tab1, tab2, tab3 = st.tabs(["💬 Chat", "🎫 Create Ticket", "🔍 Search Tickets"])
    
    # Tab 1: Chat Interface
    with tab1:
        # Force the chat to stay at the top with CSS
        st.markdown("""
        <style>
        /* Force the chat interface to top position */
        .main .block-container {
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }
        
        /* Target all vertical blocks to remove margins/padding */
        [data-testid="stVerticalBlock"] {
            gap: 0 !important;
            padding-top: 0 !important;
            margin-top: 0 !important;
        }
        
        /* Target the chat container to avoid unwanted space */
        .element-container, .stMarkdown {
            margin-top: 0 !important;
            padding-top: 0 !important;
            margin-bottom: 0 !important;
        }
        
        /* Force tabs content to top */
        .stTabs [data-baseweb=tab-panel] {
            padding-top: 0 !important;
        }
        
        /* Custom chat styles */
        .chat-header {
            margin-bottom: 0 !important;
            padding-bottom: 0 !important;
        }
        
        /* Target the actual chat messages section */
        .stChatMessage {
            margin-top: 0 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Create compact header with minimal spacing
        st.markdown('<div class="chat-header">', unsafe_allow_html=True)
        st.markdown("### Chat with Jira Assistant")
        st.markdown("Ask questions or give commands to manage your Jira tickets.")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Insert fake messages at the top to begin with content
        if not st.session_state.messages:
            st.session_state.messages = [
                {"role": "assistant", "content": get_default_help_message()}
            ]
        
        # Display messages immediately after header
        for i, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Add space at the bottom to ensure messages don't get hidden behind the fixed input
        st.markdown('<div class="chat-footer-space"></div>', unsafe_allow_html=True)
        
        # Chat input at the bottom
        if user_input := st.chat_input("How can I help you with Jira today?", key="fixed_chat_input"):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
            
            # Process the request
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                response_placeholder.markdown("Processing your request...")
                
                # Check if it's a ticket creation request
                if re.search(r'create\s+(a|new)?\s*(ticket|task|bug|story|epic)', user_input, re.IGNORECASE):
                    response_placeholder.markdown("Creating a ticket based on your request...")
                    
                    with st.spinner("Processing ticket creation..."):
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(create_jira_ticket_from_text(user_input))
                        loop.close()
                    
                    if "Error:" in result:
                        response = f"""
I tried to create a ticket based on your request, but I need more information:

{result}

Please try again with more details.
"""
                    else:
                        response = f"""
Great! I've created the ticket for you:

{result}

Is there anything else you'd like me to do?
"""
                
                # Check if it's a search request
                elif re.search(r'(find|search|list|show)\s+(all|open|recent)?\s*(tickets|issues|tasks|bugs)(\s+.*?\s+|.*?\s+)(assign|assign.*?to|by|from|of|contain|containing|with|about|related|to)\s+(\w+\s+\w+|\w+)', user_input, re.IGNORECASE) or re.search(r'(find|search|list|show)\s+(all|open|recent)?\s*(tickets|issues|tasks)', user_input, re.IGNORECASE) or "query:" in user_input.lower():
                    response_placeholder.markdown("Searching for tickets based on your request...")
                    
                    # Extract assignee if mentioned
                    assignee_match = re.search(r'(assign|assign.*?to|by|from|of)\s+([A-Za-z]+\s+[A-Za-z]+|[A-Za-z]+)', user_input, re.IGNORECASE)
                    assignee = assignee_match.group(2) if assignee_match else None
                    
                    # Extract text content if looking for tickets containing text
                    content_match = re.search(r'contain(?:ing|s)?\s+["\'"]?([^"\']+)["\'"]?|about\s+["\'"]?([^"\']+)["\'"]?|with\s+["\'"]?([^"\']+)["\'"]?|related\s+to\s+["\'"]?([^"\']+)["\'"]?', user_input, re.IGNORECASE)
                    search_text = None
                    if content_match:
                        search_text = next((g for g in content_match.groups() if g is not None), None)
                    
                    # Check if the user input already contains a well-formatted JQL query
                    jql_pattern = re.search(r'(?:query:|using query:)\s*(project\s*=\s*[A-Z0-9]+.+)', user_input, re.IGNORECASE)
                    if jql_pattern:
                        # Use the provided JQL directly
                        jql_query = jql_pattern.group(1).strip()
                        print(f"Using provided JQL: {jql_query}")
                    else:
                        # Extract project if mentioned
                        project_match = re.search(r'(?:project\s+(?:key\s+)?|in\s+)(?:"|\')?([A-Z0-9]+)(?:"|\')?\b|project\s*[=:]\s*(?:"|\')?([A-Z0-9]+)(?:"|\')?', user_input, re.IGNORECASE)
                        project = project_match.group(1) or project_match.group(2) if project_match else None
                        
                        # Check for issue type
                        issue_type_match = re.search(r'(?:type|issuetype)\s*[=:]\s*["\']?([A-Za-z]+)["\']?', user_input, re.IGNORECASE)
                        issue_type = issue_type_match.group(1) if issue_type_match else None
                        
                        # Build JQL query
                        jql_parts = []
                        
                        if project:
                            jql_parts.append(f"project = {project}")
                        
                        if issue_type:
                            jql_parts.append(f"issuetype = {issue_type}")
                        
                        if assignee:
                            jql_parts.append(f"assignee = \"{assignee}\"")
                        
                        if search_text:
                            jql_parts.append(f"text ~ \"{search_text}\"")
                        
                        if "open" in user_input.lower():
                            jql_parts.append("status != 'Done' AND status != 'Closed'")
                        
                        if jql_parts:
                            jql_query = " AND ".join(jql_parts)
                        else:
                            jql_query = "order by created DESC"
                    
                    # Store the search context for future reference
                    st.session_state.last_search_query = jql_query
                    
                    with st.spinner("Searching tickets..."):
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            result = loop.run_until_complete(search_jira_tickets(jql_query))
                            
                            response = f"""
Here are the tickets I found:

{result}

Is there anything specific you'd like to know about any of these tickets?
"""
                        except Exception as e:
                            print(f"Search error in chat: {traceback.format_exc()}")
                            response = f"""
I encountered an error while searching for tickets:
{str(e)}

Please check your search query and try again. Here are some example queries you can try:
- "Find all open tickets in KAN"
- "Search for tickets in project KAN"
- "Show me tickets containing 'authentication'"
"""
                        loop.close()
                
                # Check if it's a ticket details request by ID or description
                elif re.search(r'(details|info|status|fetch|get|show|display|view|retrieve)\s+(details\s+)?(of|for|about)?\s*(ticket|issue)?:?\s*([A-Z]+-\d+)', user_input, re.IGNORECASE) or re.search(r'([A-Z]+-\d+).*?(details|info|status)', user_input, re.IGNORECASE) or re.search(r'(details|info|status|fetch|get|show|display|view|retrieve).*?(the|this|that|our)?\s*(ticket|issue)?\s*(we|you|I)?\s*(just)?\s*(created|made)', user_input, re.IGNORECASE) or re.search(r'(details|info|status).*?(oauth2|authentication|ticket)', user_input, re.IGNORECASE):
                    
                    # First, check for direct ticket ID in the request
                    ticket_match = re.search(r'([A-Z]+-\d+)', user_input, re.IGNORECASE)
                    
                    if ticket_match:
                        # Direct ticket ID found
                        ticket_id = ticket_match.group(1)
                        response_placeholder.markdown(f"Getting details for ticket {ticket_id}...")
                    else:
                        # Look for contextual references to tickets
                        
                        # Case 1: Reference to "the ticket we just created"
                        if re.search(r'(created|made)', user_input, re.IGNORECASE):
                            # Check the most recent ticket creation in the conversation history
                            for message in reversed(st.session_state.messages):
                                if "Ticket created:" in message.get("content", ""):
                                    ticket_match = re.search(r'Ticket created: ([A-Z]+-\d+)', message["content"])
                                    if ticket_match:
                                        ticket_id = ticket_match.group(1)
                                        response_placeholder.markdown(f"Getting details for the ticket you just created ({ticket_id})...")
                                        break
                            else:
                                response = "I couldn't find a recently created ticket in our conversation. Could you specify the ticket ID you'd like details for?"
                                response_placeholder.markdown(response)
                                st.session_state.messages.append({"role": "assistant", "content": response})
                                return
                                
                        # Case 2: Reference to a ticket by description (e.g., "OAuth2 ticket")
                        elif re.search(r'(oauth2|authentication)', user_input, re.IGNORECASE):
                            # Check the most recent search results or conversation for relevant tickets
                            # For simplicity in the screencast, let's assume this refers to the most recently created ticket
                            for message in reversed(st.session_state.messages):
                                if "Ticket created:" in message.get("content", ""):
                                    ticket_match = re.search(r'Ticket created: ([A-Z]+-\d+)', message["content"])
                                    if ticket_match:
                                        ticket_id = ticket_match.group(1)
                                        response_placeholder.markdown(f"Getting details for the OAuth2 authentication ticket ({ticket_id})...")
                                        break
                            else:
                                response = "I couldn't find a ticket related to OAuth2 or authentication in our conversation. Could you specify the ticket ID you'd like details for?"
                                response_placeholder.markdown(response)
                                st.session_state.messages.append({"role": "assistant", "content": response})
                                return
                        else:
                            response = "I couldn't determine which ticket you're referring to. Could you specify the ticket ID you'd like details for?"
                            response_placeholder.markdown(response)
                            st.session_state.messages.append({"role": "assistant", "content": response})
                            return
                    
                    with st.spinner(f"Retrieving ticket {ticket_id}..."):
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(get_jira_ticket(ticket_id))
                        loop.close()
                    
                    response = f"""
Here are the details for ticket {ticket_id}:

{result}

Is there anything else you'd like to know?
"""
                
                # Check if user is asking about tickets assigned to someone or containing text
                elif re.search(r'(tickets|tasks|issues|bugs)(\s+.*?\s+|.*?\s+)(assign|assign.*?to|by|from|of)\s+([A-Za-z]+\s+[A-Za-z]+|[A-Za-z]+)', user_input, re.IGNORECASE) or re.search(r'(tickets|tasks|issues|bugs)(\s+.*?\s+|.*?\s+)(contain|containing|with|about|related\s+to)\s+["\']?([^"\']+)["\']?', user_input, re.IGNORECASE):
                    assignee_match = re.search(r'(assign|assign.*?to|by|from|of)\s+([A-Za-z]+\s+[A-Za-z]+|[A-Za-z]+)', user_input, re.IGNORECASE)
                    content_match = re.search(r'(tickets|tasks|issues|bugs)(\s+.*?\s+|.*?\s+)(contain|containing|with|about|related\s+to)\s+["\']?([^"\']+)["\']?', user_input, re.IGNORECASE)
                    
                    if assignee_match:
                        assignee = assignee_match.group(4)
                        # Improved project regex to more reliably detect KAN project
                        project_match = re.search(r'(?:project|in)\s+(?:the\s+)?(?:"|\')?([A-Z0-9]+)(?:"|\')?(?:\s+project)?', user_input, re.IGNORECASE)
                        project = project_match.group(1) if project_match else None
                        
                        # Build JQL query
                        jql_parts = []
                        if project:
                            jql_parts.append(f"project = {project}")
                        else:
                            # Default to KAN project if not specified
                            jql_parts.append("project = KAN")
                        
                        # Fix for assignee search - use exact name for the query
                        jql_parts.append(f"assignee = \"{assignee}\"")
                        
                        # Check for task/bug specific queries
                        if "task" in user_input.lower():
                            jql_parts.append("issuetype = Task")
                        elif "bug" in user_input.lower():
                            jql_parts.append("issuetype = Bug")
                        
                        jql_query = " AND ".join(jql_parts)
                        
                        print(f"DEBUG - Final JQL query: {jql_query}")
                        
                        response_placeholder.markdown(f"Searching for tickets assigned to {assignee}...")
                        
                        with st.spinner("Searching tickets..."):
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                result = loop.run_until_complete(search_jira_tickets(jql_query))
                                
                                response = f"""
Here are the tickets assigned to {assignee}:

{result}

Is there anything specific you'd like to know about any of these tickets?
"""
                            except Exception as e:
                                print(f"Search error in chat: {traceback.format_exc()}")
                                response = f"""
I encountered an error while searching for tickets assigned to {assignee}:
{str(e)}

Please check the assignee name and try again.
"""
                            loop.close()
                    elif content_match:
                        search_text = content_match.group(4)
                        project_match = re.search(r'(?:project|in)\s+(?:the\s+)?(?:"|\')?([A-Z0-9]+)(?:"|\')?(?:\s+project)?', user_input, re.IGNORECASE)
                        project = project_match.group(1) if project_match else None
                        
                        # Build JQL query
                        jql_parts = []
                        if project:
                            jql_parts.append(f"project = {project}")
                        else:
                            # Default to KAN project if not specified
                            jql_parts.append("project = KAN")
                        
                        # Add text search
                        jql_parts.append(f"text ~ \"{search_text}\"")
                        
                        jql_query = " AND ".join(jql_parts)
                        
                        print(f"DEBUG - Text search JQL query: {jql_query}")
                        
                        response_placeholder.markdown(f"Searching for tickets containing '{search_text}'...")
                        
                        with st.spinner("Searching tickets..."):
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                result = loop.run_until_complete(search_jira_tickets(jql_query))
                                
                                response = f"""
Here are the tickets containing '{search_text}':

{result}

Is there anything specific you'd like to know about any of these tickets?
"""
                            except Exception as e:
                                print(f"Search error in chat: {traceback.format_exc()}")
                                response = f"""
I encountered an error while searching for tickets containing '{search_text}':
{str(e)}

Please try a different search term or query format.
"""
                            loop.close()
                
                # Fallback response for unhandled queries
                else:
                    # Try to handle ticket description retrieval or other contextual requests
                    ticket_mention = re.search(r'(description|details|info)\s+(?:of|for|about)?\s*(?:the)?\s*(?:ticket|issue)?\s*(?:we|you)?\s*(?:just)?\s*created', user_input, re.IGNORECASE)
                    
                    if ticket_mention:
                        # Look for the most recently created ticket in the conversation
                        for message in reversed(st.session_state.messages):
                            if "Ticket created:" in message.get("content", ""):
                                ticket_match = re.search(r'Ticket created: ([A-Z]+-\d+)', message["content"])
                                if ticket_match:
                                    ticket_id = ticket_match.group(1)
                                    response_placeholder.markdown(f"Getting details for the ticket you just created ({ticket_id})...")
                                    
                                    with st.spinner(f"Retrieving ticket {ticket_id}..."):
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        result = loop.run_until_complete(get_jira_ticket(ticket_id))
                                        loop.close()
                                    
                                    response = f"""
Here are the details for the ticket you just created ({ticket_id}):

{result}

Is there anything else you'd like to know?
"""
                                    break
                        else:
                            response = "I couldn't find a recently created ticket in our conversation. Could you specify the ticket ID you'd like details for?"
                    else:
                        # General fallback response for unknown queries
                        response = """
I'm not sure how to handle that request. Here are some things I can help you with:

1. Create a new ticket:
   - "Create a bug in KAN titled 'Login issue' with description 'Users cannot log in'"

2. Search for tickets:
   - "Show all tasks assigned to Pawan Kumar in KAN"
   - "Find open tickets containing 'authentication'"

3. Get ticket details:
   - "Show details for ticket KAN-123"

Could you try phrasing your request differently?
"""
                
                # Display final response
                response_placeholder.markdown(response)
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Tab 2: Create Ticket Form
    with tab2:
        st.markdown("### Create a New Jira Ticket")
        st.markdown("Fill out the form below to create a new ticket.")
        
        # Add form for ticket creation
        with st.form("create_ticket_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                project_key = st.text_input("Project Key", value=st.session_state.ticket_info.get("project_key", ""))
                summary = st.text_input("Ticket Summary/Title", value=st.session_state.ticket_info.get("summary", ""))
                assignee = st.text_input("Assignee (optional)", 
                                        value=st.session_state.ticket_info.get("assignee", ""),
                                        help="Enter the display name of the person to assign this ticket to (e.g., 'Pawan Kumar')")
            
            with col2:
                issue_type = st.selectbox("Issue Type", 
                                       ["Task", "Bug", "Story", "Epic", "Improvement"],
                                       index=["Task", "Bug", "Story", "Epic", "Improvement"].index(st.session_state.ticket_info.get("issue_type", "Task")))
            
            description = st.text_area("Description", value=st.session_state.ticket_info.get("description", ""), height=200)
            
            submitted = st.form_submit_button("Create Ticket")
            
            if submitted:
                if not project_key or not summary or not description:
                    st.error("Please fill in all required fields (Project Key, Summary, and Description).")
                else:
                    ticket_params = {
                        "project_key": project_key,
                        "summary": summary,
                        "description": description,
                        "issue_type": issue_type
                    }
                    
                    # Add assignee if provided
                    if assignee:
                        ticket_params["assignee"] = assignee
                    
                    with st.spinner("Creating ticket..."):
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            result = loop.run_until_complete(call_tool("create_jira_ticket", ticket_params))
                            loop.close()
                            
                            st.success(f"Ticket created successfully: {result}")
                            
                            # Clear the form
                            st.session_state.ticket_info = {
                                "project_key": "",
                                "summary": "",
                                "description": "",
                                "issue_type": "Task"
                            }
                            
                            # Add to chat history
                            st.session_state.messages.append({
                                "role": "user", 
                                "content": f"Create a {issue_type.lower()} in {project_key} titled '{summary}' with description '{description}'"
                            })
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": f"I've created a {issue_type.lower()} ticket for you: {result}"
                            })
                            
                        except Exception as e:
                            st.error(f"Error creating ticket: {str(e)}")
    
    # Tab 3: Search Tickets
    with tab3:
        st.markdown("### Search Jira Tickets")
        st.markdown("Use JQL (Jira Query Language) to search for tickets.")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            search_query = st.text_input(
                "JQL Query", 
                placeholder="Examples: project = KAN | project = KAN AND issuetype = Task | created >= -7d"
            )
        
        with col2:
            max_results = st.number_input("Max Results", min_value=1, max_value=100, value=10, 
                                         help="Note: The MCP server currently limits results to 10 regardless of this setting")
        
        if st.button("Search"):
            if not search_query:
                st.error("Please enter a search query.")
            else:
                with st.spinner("Searching tickets..."):
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        # Note: max_results is no longer used as the MCP server implementation doesn't support it
                        result = loop.run_until_complete(search_jira_tickets(search_query))
                        loop.close()
                        
                        st.markdown("### Search Results")
                        st.write(result)
                        
                        # Add to chat history
                        st.session_state.messages.append({
                            "role": "user", 
                            "content": f"Search for tickets using query: {search_query}"
                        })
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": f"Here are the search results:\n\n{result}"
                        })
                        
                    except Exception as e:
                        st.error(f"Error searching tickets: {str(e)}")
                        # Log the full error details for debugging
                        print(f"Search error details: {traceback.format_exc()}")
                        st.warning("Tip: Make sure your JQL syntax is correct. For example: 'project = KAN AND status != Done'")
        
        # Add some example queries
        with st.expander("Example JQL Queries"):
            st.markdown("""
            - `project = KAN AND status = 'In Progress'` - Find all in-progress tickets in the KAN project
            - `assignee = currentUser()` - Find all tickets assigned to you
            - `created >= -7d` - Find tickets created in the last 7 days
            - `project = KAN ORDER BY created DESC` - Find all tickets in KAN project, newest first
            - `project = KAN AND text ~ "authentication"` - Find tickets in KAN containing the word "authentication"
            """)

if __name__ == "__main__":
    main() 