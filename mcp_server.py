from fastmcp import FastMCP
import requests
import os
from dotenv import load_dotenv
from typing import Dict, Any, List

# Load env vars
load_dotenv()

# Jira credentials
JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Content-Type": "application/json"}

# Initialize MCP server
mcp = FastMCP("JiraMCP")

def list_tools() -> Dict[str, Any]:
    """List all available Jira MCP tools.
    
    This tool provides information about all available Jira operations,
    including their parameters and expected return values.
    
    Returns:
        Dict containing list of available tools with their schemas
    """
    return {
        "tools": [
            {
                "name": "create_jira_ticket",
                "description": "Create a new Jira ticket",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string", "description": "Project key for the ticket"},
                        "summary": {"type": "string", "description": "Summary/title of the ticket"},
                        "description": {"type": "string", "description": "Detailed description of the ticket"},
                        "issue_type": {"type": "string", "description": "Type of issue (Task, Bug, etc.)"},
                        "assignee": {"type": "string", "description": "Username or display name of the assignee"}
                    },
                    "required": ["project_key", "summary", "description"]
                }
            },
            {
                "name": "update_jira_ticket",
                "description": "Update an existing Jira ticket",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string", "description": "The key of the ticket to update"},
                        "summary": {"type": "string", "description": "New summary/title for the ticket"},
                        "description": {"type": "string", "description": "New description for the ticket"},
                        "status": {"type": "string", "description": "New status for the ticket"}
                    },
                    "required": ["issue_key"]
                }
            },
            {
                "name": "delete_jira_ticket",
                "description": "Delete a Jira ticket",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string", "description": "The key of the ticket to delete"}
                    },
                    "required": ["issue_key"]
                }
            },
            {
                "name": "get_jira_ticket",
                "description": "Get details of a Jira ticket",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string", "description": "The key of the ticket to retrieve"}
                    },
                    "required": ["issue_key"]
                }
            },
            {
                "name": "add_comment_to_ticket",
                "description": "Add a comment to a Jira ticket",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string", "description": "The key of the ticket"},
                        "comment": {"type": "string", "description": "Comment text to add"}
                    },
                    "required": ["issue_key", "comment"]
                }
            },
            {
                "name": "assign_jira_ticket",
                "description": "Assign a Jira ticket to a user",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string", "description": "The key of the ticket"},
                        "assignee": {"type": "string", "description": "Email or account ID of the assignee"}
                    },
                    "required": ["issue_key", "assignee"]
                }
            },
            {
                "name": "search_jira_tickets",
                "description": "Search for Jira tickets using JQL",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "JQL query string"}
                    },
                    "required": ["query"]
                }
            }
        ]
    }

# Tool to create a Jira ticket
@mcp.tool()
def create_jira_ticket(project_key: str, summary: str, description: str, issue_type: str = "Task", assignee: str = None) -> str:
    """Create a new Jira ticket. Returns ticket key or error."""
    url = f"{JIRA_URL}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]},
            "issuetype": {"name": issue_type}
        }
    }
    
    # Add assignee if provided
    if assignee:
        print(f"Adding assignee to ticket: {assignee}")
        # For Jira Cloud, first we need to get the account ID for the user
        search_url = f"{JIRA_URL}/rest/api/3/user/search?query={assignee}"
        user_response = requests.get(search_url, auth=AUTH, headers=HEADERS)
        
        if user_response.status_code == 200 and user_response.json():
            # Use the first matching user's account ID
            account_id = user_response.json()[0].get('accountId')
            if account_id:
                payload["fields"]["assignee"] = {"accountId": account_id}
                print(f"Found account ID for {assignee}: {account_id}")
            else:
                print(f"No account ID found for user: {assignee}")
        else:
            print(f"Error finding user {assignee}: {user_response.text}")
    
    response = requests.post(url, json=payload, auth=AUTH, headers=HEADERS)
    return f"Ticket created: {response.json()['key']}" if response.status_code == 201 else f"Error: {response.text}"

# Tool to update a Jira ticket
@mcp.tool()
def update_jira_ticket(issue_key: str, summary: str = None, description: str = None, status: str = None) -> str:
    """Update an existing Jira ticket. Provide issue_key and fields to update. Returns success or error."""
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
    payload = {"fields": {}}
    if summary:
        payload["fields"]["summary"] = summary
    if description:
        payload["fields"]["description"] = {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]}
    if status:
        transitions = requests.get(f"{url}/transitions", auth=AUTH, headers=HEADERS).json()["transitions"]
        transition_id = next((t["id"] for t in transitions if t["name"].lower() == status.lower()), None)
        if transition_id:
            response = requests.post(f"{url}/transitions", json={"transition": {"id": transition_id}}, auth=AUTH, headers=HEADERS)
            return "Status updated" if response.status_code == 204 else f"Error: {response.text}"
        return "Error: Invalid status"
    if not payload["fields"]:
        return "Error: No fields to update"
    response = requests.put(url, json=payload, auth=AUTH, headers=HEADERS)
    return "Ticket updated" if response.status_code == 204 else f"Error: {response.text}"

# Tool to delete a Jira ticket
@mcp.tool()
def delete_jira_ticket(issue_key: str) -> str:
    """Delete a Jira ticket by issue_key. Returns success or error."""
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
    response = requests.delete(url, auth=AUTH, headers=HEADERS)
    return "Ticket deleted" if response.status_code == 204 else f"Error: {response.text}"

# Tool to get ticket details
@mcp.tool()
def get_jira_ticket(issue_key: str) -> str:
    """Retrieve details of a Jira ticket by issue_key. Returns ticket info or error."""
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
    response = requests.get(url, auth=AUTH, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        return f"Ticket {issue_key}: {data['fields']['summary']} - {data['fields']['status']['name']}"
    return f"Error: {response.text}"

# Tool to add a comment to a ticket
@mcp.tool()
def add_comment_to_ticket(issue_key: str, comment: str) -> str:
    """Add a comment to a Jira ticket. Returns success or error."""
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/comment"
    payload = {"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]}}
    response = requests.post(url, json=payload, auth=AUTH, headers=HEADERS)
    return "Comment added" if response.status_code == 201 else f"Error: {response.text}"

# Tool to assign a ticket
@mcp.tool()
def assign_jira_ticket(issue_key: str, assignee: str) -> str:
    """Assign a Jira ticket to a user by email or account ID. Returns success or error."""
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/assignee"
    payload = {"accountId": assignee}
    response = requests.put(url, json=payload, auth=AUTH, headers=HEADERS)
    return "Ticket assigned" if response.status_code == 204 else f"Error: {response.text}"

# Tool to search tickets
@mcp.tool()
def search_jira_tickets(query: str) -> str:
    """Search Jira tickets using JQL. Returns list of ticket keys or error."""
    url = f"{JIRA_URL}/rest/api/3/search"
    payload = {"jql": query, "maxResults": 10}
    response = requests.post(url, json=payload, auth=AUTH, headers=HEADERS)
    if response.status_code == 200:
        issues = [issue["key"] for issue in response.json()["issues"]]
        return f"Found tickets: {', '.join(issues)}" if issues else "No tickets found"
    return f"Error: {response.text}"

@mcp.prompt()
def echo_prompt(message: str) -> str:
    """Create an echo prompt"""
    return f"Please process this message: {message}"

if __name__ == "__main__":
    mcp.run()  # Default to stdio transport