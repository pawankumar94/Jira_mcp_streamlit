#!/bin/bash

# Script to restart the Streamlit application

echo "Stopping running Streamlit instances..."
# Find and kill any running Streamlit processes
pkill -f "streamlit run streamlit_app.py" || echo "No Streamlit process found"

# Give it a moment to shut down
sleep 2

echo "Restarting Streamlit application..."
# Start the Jira Assistant script which will handle MCP server setup and start Streamlit
./start_jira_assistant.sh &

echo "The application should be accessible at http://localhost:8501 in a moment."
echo "Use the browser to access the application." 