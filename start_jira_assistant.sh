#!/bin/bash

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to cleanup on exit
cleanup() {
    echo -e "${YELLOW}Cleaning up processes...${NC}"
    # Find and kill any running MCP server processes that were started by this script
    if [ -n "$MCP_PID" ] && ps -p $MCP_PID > /dev/null; then
        echo "Stopping MCP server (PID: $MCP_PID)"
        kill $MCP_PID
    fi
    
    # Find and kill any running Streamlit processes
    STREAMLIT_PID=$(pgrep -f "streamlit run streamlit_app.py")
    if [ -n "$STREAMLIT_PID" ]; then
        echo "Stopping Streamlit (PID: $STREAMLIT_PID)"
        kill $STREAMLIT_PID
    fi
    
    echo -e "${GREEN}Cleanup complete.${NC}"
    exit 0
}

# Register the cleanup function to be called on script exit
trap cleanup EXIT

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3 to run this application.${NC}"
    exit 1
fi

# Check if required packages are installed
echo -e "${YELLOW}Checking required packages...${NC}"
if ! python3 -c "import mcp" &> /dev/null; then
    echo -e "${RED}MCP package is not installed. Please install it with 'pip install mcp'.${NC}"
    exit 1
fi

if ! python3 -c "import streamlit" &> /dev/null; then
    echo -e "${RED}Streamlit is not installed. Please install it with 'pip install streamlit'.${NC}"
    exit 1
fi

if ! python3 -c "import google.generativeai" &> /dev/null; then
    echo -e "${YELLOW}Warning: Google Generative AI package not found. Installing...${NC}"
    pip install google-generativeai
fi

# Check if .env file exists and contains required variables
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found.${NC}"
    echo "Creating a sample .env file. Please update it with your actual credentials."
    cat > .env << EOL
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token
GEMINI_API_KEY=your-gemini-api-key
EOL
    exit 1
fi

# Check if all required variables are set in .env file
required_vars=("JIRA_URL" "JIRA_EMAIL" "JIRA_API_TOKEN" "GEMINI_API_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if ! grep -q "^$var=" .env || [ -z "$(grep "^$var=" .env | cut -d '=' -f2)" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo -e "${RED}Error: The following required variables are missing or empty in the .env file:${NC}"
    for var in "${missing_vars[@]}"; do
        echo " - $var"
    done
    echo "Please update your .env file with these values."
    exit 1
fi

# Check MCP server path
MCP_SERVER_PATH="../Jira_mcp/mcp_server.py"
if [ ! -f "$MCP_SERVER_PATH" ]; then
    echo -e "${YELLOW}Warning: MCP server not found at $MCP_SERVER_PATH${NC}"
    
    # Try alternative location
    MCP_SERVER_PATH="./mcp_server.py"
    if [ ! -f "$MCP_SERVER_PATH" ]; then
        echo -e "${RED}Error: Cannot find MCP server script. Please specify the correct path.${NC}"
        read -p "Enter path to MCP server script (or press Enter to cancel): " custom_path
        
        if [ -z "$custom_path" ]; then
            echo -e "${RED}Cancelled.${NC}"
            exit 1
        elif [ ! -f "$custom_path" ]; then
            echo -e "${RED}Error: File not found at $custom_path${NC}"
            exit 1
        else
            MCP_SERVER_PATH="$custom_path"
        fi
    fi
fi

# Check if MCP server is already running
if pgrep -f "python.*mcp_server.py" > /dev/null; then
    echo -e "${GREEN}MCP server is already running.${NC}"
    
    # Validate server by running a test
    echo -e "${YELLOW}Validating MCP server connection...${NC}"
    if python3 test_mcp_client.py connect > /dev/null 2>&1; then
        echo -e "${GREEN}MCP server connection is working properly.${NC}"
    else
        echo -e "${RED}Warning: MCP server is running but connection test failed.${NC}"
        read -p "Do you want to restart the MCP server? (y/n): " restart_server
        if [[ $restart_server =~ ^[Yy]$ ]]; then
            pkill -f "python.*mcp_server.py"
            echo -e "${YELLOW}Starting MCP server at $MCP_SERVER_PATH${NC}"
            python3 "$MCP_SERVER_PATH" > /dev/null 2>&1 &
            MCP_PID=$!
            
            # Wait for server to start
            echo -e "${YELLOW}Waiting for MCP server to start...${NC}"
            sleep 2
            
            # Validate server connection
            if python3 test_mcp_client.py connect > /dev/null 2>&1; then
                echo -e "${GREEN}MCP server started successfully.${NC}"
            else
                echo -e "${RED}Error: Failed to start MCP server. Please check the server script.${NC}"
                exit 1
            fi
        fi
    fi
else
    echo -e "${YELLOW}Starting MCP server at $MCP_SERVER_PATH${NC}"
    python3 "$MCP_SERVER_PATH" > /dev/null 2>&1 &
    MCP_PID=$!
    
    # Wait for server to start
    echo -e "${YELLOW}Waiting for MCP server to start...${NC}"
    sleep 2
    
    # Validate server connection
    if python3 test_mcp_client.py connect > /dev/null 2>&1; then
        echo -e "${GREEN}MCP server started successfully.${NC}"
    else
        echo -e "${RED}Error: Failed to start MCP server. Please check the server script.${NC}"
        exit 1
    fi
fi

# Get and display MCP version
MCP_VERSION=$(python3 -c "import mcp; print(getattr(mcp, '__version__', 'unknown'))")
echo -e "${GREEN}Using MCP version: ${MCP_VERSION}${NC}"

# Start the Streamlit app
echo -e "${GREEN}Starting Streamlit application...${NC}"
echo -e "${YELLOW}Access the application at http://localhost:8501${NC}"
streamlit run streamlit_app.py 