#!/usr/bin/env python3

import os
import sys
import asyncio
import argparse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Path to MCP server script
MCP_SERVER_PATH = os.path.join("..", "Jira_mcp", "mcp_server.py")

# Verify the MCP server path exists
if not os.path.exists(MCP_SERVER_PATH):
    MCP_SERVER_PATH = input("Enter the path to the MCP server script: ")
    if not os.path.exists(MCP_SERVER_PATH):
        print(f"Error: MCP server script not found at {MCP_SERVER_PATH}")
        sys.exit(1)

async def list_tools():
    """List all available Jira tools"""
    try:
        server_params = StdioServerParameters(
            command="python",
            args=[MCP_SERVER_PATH],
            env=None
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                
                if hasattr(tools_result, 'tools'):
                    tools = tools_result.tools
                    print(f"Found {len(tools)} tools:")
                    for tool in tools:
                        print(f"  - {tool.name}: {tool.description}")
                        print(f"    Required parameters: {', '.join(tool.inputSchema.get('required', []))}")
                else:
                    print("No tools found or unexpected result format")
        
        return True
    except Exception as e:
        print(f"Error listing tools: {str(e)}")
        return False

async def create_ticket(project_key, summary, description, issue_type="Task"):
    """Create a new Jira ticket"""
    if not project_key:
        print("Error: Project key is required")
        return None
    
    if not summary:
        print("Error: Summary/title is required")
        return None
    
    if not description:
        print("Error: Description is required")
        return None
    
    # Prepare the parameters for the tool
    params = {
        "project_key": project_key,
        "summary": summary,
        "description": description,
        "issue_type": issue_type
    }
    
    try:
        server_params = StdioServerParameters(
            command="python",
            args=[MCP_SERVER_PATH],
            env=None
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                print(f"Creating ticket in project {project_key}...")
                result = await session.call_tool("create_jira_ticket", arguments=params)
                
                if hasattr(result, 'content') and result.content:
                    content_item = result.content[0]
                    if hasattr(content_item, 'text'):
                        print(content_item.text)
                        return content_item.text
                
                print(f"Ticket creation response: {result}")
                return str(result)
    except Exception as e:
        print(f"Error creating ticket: {str(e)}")
        return f"Error: {str(e)}"

async def search_tickets(query, project_key=None, max_results=10):
    """Search for Jira tickets using JQL"""
    # Prepare the search query
    if project_key and "project" not in query.lower():
        search_query = f"project = {project_key} AND {query}"
    else:
        search_query = query
    
    params = {
        "query": search_query
    }
    
    try:
        server_params = StdioServerParameters(
            command="python",
            args=[MCP_SERVER_PATH],
            env=None
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                print(f"Searching for tickets with query: {search_query}...")
                result = await session.call_tool("search_jira_tickets", arguments=params)
                
                if hasattr(result, 'content') and result.content:
                    content_item = result.content[0]
                    if hasattr(content_item, 'text'):
                        print(content_item.text)
                        return content_item.text
                
                print(f"Search response: {result}")
                return str(result)
    except Exception as e:
        print(f"Error searching tickets: {str(e)}")
        return f"Error: {str(e)}"

async def get_ticket(ticket_id):
    """Get details of a Jira ticket"""
    if not ticket_id:
        print("Error: Ticket ID is required")
        return None
    
    params = {
        "issue_key": ticket_id
    }
    
    try:
        server_params = StdioServerParameters(
            command="python",
            args=[MCP_SERVER_PATH],
            env=None
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                print(f"Getting details for ticket {ticket_id}...")
                result = await session.call_tool("get_jira_ticket", arguments=params)
                
                if hasattr(result, 'content') and result.content:
                    content_item = result.content[0]
                    if hasattr(content_item, 'text'):
                        print(content_item.text)
                        return content_item.text
                
                print(f"Ticket details response: {result}")
                return str(result)
    except Exception as e:
        print(f"Error getting ticket details: {str(e)}")
        return f"Error: {str(e)}"

async def check_server_status():
    """Check MCP server status"""
    try:
        server_params = StdioServerParameters(
            command="python",
            args=[MCP_SERVER_PATH],
            env=None
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                try:
                    await session.initialize()
                    print("MCP server is responding correctly!")
                    return True
                except Exception as e:
                    print(f"MCP server connection error: {str(e)}")
                    return False
    except Exception as e:
        print(f"Error checking server status: {str(e)}")
        return False

def validate_jira_credentials():
    """Validate Jira credentials"""
    required_vars = ["JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables in your .env file or environment.")
        return False
    
    return True

async def main():
    parser = argparse.ArgumentParser(description="Jira MCP Client Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # List tools command
    list_parser = subparsers.add_parser("list", help="List available MCP tools")
    
    # Create ticket command
    create_parser = subparsers.add_parser("create", help="Create a Jira ticket")
    create_parser.add_argument("--project", "-p", required=True, help="Project key (e.g., KAN)")
    create_parser.add_argument("--title", "-t", required=True, help="Ticket title/summary")
    create_parser.add_argument("--description", "-d", required=True, help="Ticket description")
    create_parser.add_argument("--type", "-y", default="Task", help="Issue type (default: Task)")
    
    # Search tickets command
    search_parser = subparsers.add_parser("search", help="Search for Jira tickets")
    search_parser.add_argument("--query", "-q", required=True, help="JQL search query")
    search_parser.add_argument("--project", "-p", help="Project key to limit search to")
    search_parser.add_argument("--max", "-m", type=int, default=10, help="Maximum number of results")
    
    # Get ticket details command
    get_parser = subparsers.add_parser("get", help="Get Jira ticket details")
    get_parser.add_argument("--id", "-i", required=True, help="Ticket ID (e.g., KAN-1)")
    
    # Status check command
    status_parser = subparsers.add_parser("status", help="Check MCP server status")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Validate Jira credentials for commands that need them
    if args.command in ["create", "search", "get"]:
        if not validate_jira_credentials():
            return
    
    # Execute the requested command
    if args.command == "list":
        await list_tools()
    elif args.command == "create":
        await create_ticket(args.project, args.title, args.description, args.type)
    elif args.command == "search":
        await search_tickets(args.query, args.project, args.max)
    elif args.command == "get":
        await get_ticket(args.id)
    elif args.command == "status":
        await check_server_status()
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main()) 