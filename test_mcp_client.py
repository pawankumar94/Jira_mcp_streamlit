#!/usr/bin/env python3
"""
MCP Client Test Script

This script tests the connection to the MCP server and its Jira integration capabilities.
It provides several test functions for listing tools, creating tickets, and more.
"""
import os
import sys
import asyncio
import json
from dotenv import load_dotenv

# Import MCP client libraries
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("Error: MCP package not installed. Please install with 'pip install mcp'.")
    sys.exit(1)

# Load environment variables from .env file
load_dotenv()

# Path to MCP server
MCP_SERVER_PATH = os.path.join("..", "Jira_mcp", "mcp_server.py")

# Verify the MCP server path exists
if not os.path.exists(MCP_SERVER_PATH):
    print(f"Warning: MCP server script not found at {MCP_SERVER_PATH}")
    alt_path = os.path.join(".", "mcp_server.py")
    if os.path.exists(alt_path):
        print(f"Using alternative path: {alt_path}")
        MCP_SERVER_PATH = alt_path
    else:
        print("Error: Unable to locate MCP server script")
        sys.exit(1)

async def test_connection():
    """Test the connection to the MCP server"""
    print("Testing connection to MCP server...")
    
    try:
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
                print("✅ Connection successful!")
                
                # Get MCP server info
                try:
                    info = await session.server_info()
                    print(f"Server Name: {info.name}")
                    print(f"Version: {info.version}")
                    return True
                except Exception as e:
                    print(f"Could not get server info: {str(e)}")
                    return True  # Connection still successful
                
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False

async def test_list_tools():
    """Test listing available tools"""
    print("\nListing available tools...")
    
    try:
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
                    print(f"✅ Found {len(tools_result.tools)} tools:")
                    for tool in tools_result.tools:
                        print(f"  - {tool.name}: {tool.description}")
                    return tools_result.tools
                else:
                    print("❌ Unexpected tools result format")
                    return []
    except Exception as e:
        print(f"❌ Error listing tools: {str(e)}")
        return []

async def test_create_ticket():
    """Test creating a Jira ticket"""
    print("\nTesting ticket creation...")
    
    # Check Jira credentials
    if not os.getenv("JIRA_URL") or not os.getenv("JIRA_EMAIL") or not os.getenv("JIRA_API_TOKEN"):
        print("❌ Missing Jira credentials in environment variables")
        return False
    
    try:
        project_key = "KAN"
        summary = "Implement API authentication middleware"
        description = """
        Implement JWT authentication middleware for our API endpoints.
        
        Requirements:
        - Support JWT token validation
        - Implement rate limiting
        - Add proper error handling for authentication failures
        - Create unit tests for the middleware
        - Document the authentication process
        
        Priority: High
        """
        issue_type = "Task"
        
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
                
                # Create a ticket
                print(f"Creating ticket in project {project_key}...")
                result = await session.call_tool(
                    "create_jira_ticket", 
                    arguments={
                        "project_key": project_key,
                        "summary": summary,
                        "description": description,
                        "issue_type": issue_type
                    }
                )
                
                # Extract content from the result
                if hasattr(result, 'content') and result.content:
                    # Extract text from the first content item
                    content_item = result.content[0]
                    if hasattr(content_item, 'text'):
                        print(f"✅ {content_item.text}")
                        return True
                
                print(f"✅ Ticket created: {result}")
                return True
    except Exception as e:
        print(f"❌ Error creating ticket: {str(e)}")
        return False

async def test_search_tickets():
    """Test searching for Jira tickets"""
    print("\nTesting ticket search...")
    
    # Check Jira credentials
    if not os.getenv("JIRA_URL") or not os.getenv("JIRA_EMAIL") or not os.getenv("JIRA_API_TOKEN"):
        print("❌ Missing Jira credentials in environment variables")
        return False
    
    try:
        project_key = "KAN"
        search_query = f"project = {project_key} ORDER BY created DESC"
        
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
                
                # Search for tickets
                print(f"Searching for tickets in project {project_key}...")
                result = await session.call_tool(
                    "search_jira_tickets", 
                    arguments={
                        "jql_query": search_query,
                        "max_results": 5
                    }
                )
                
                # Extract content from the result
                if hasattr(result, 'content') and result.content:
                    # Extract text from the first content item
                    content_item = result.content[0]
                    if hasattr(content_item, 'text'):
                        print(f"✅ Search results: {content_item.text}")
                        return True
                
                print(f"✅ Search completed: {result}")
                return True
    except Exception as e:
        print(f"❌ Error searching tickets: {str(e)}")
        return False

async def test_create_custom_ticket(project_key, summary, description, issue_type="Task"):
    """Test creating a custom Jira ticket with provided details"""
    print(f"\nCreating custom ticket in {project_key}: {summary}")
    
    # Check Jira credentials
    if not os.getenv("JIRA_URL") or not os.getenv("JIRA_EMAIL") or not os.getenv("JIRA_API_TOKEN"):
        print("❌ Missing Jira credentials in environment variables")
        return False
    
    try:
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
                
                # Create a ticket
                result = await session.call_tool(
                    "create_jira_ticket", 
                    arguments={
                        "project_key": project_key,
                        "summary": summary,
                        "description": description,
                        "issue_type": issue_type
                    }
                )
                
                # Extract content from the result
                if hasattr(result, 'content') and result.content:
                    # Extract text from the first content item
                    content_item = result.content[0]
                    if hasattr(content_item, 'text'):
                        print(f"✅ {content_item.text}")
                        return True
                
                print(f"✅ Ticket created: {result}")
                return True
    except Exception as e:
        print(f"❌ Error creating ticket: {str(e)}")
        return False

async def run_tests():
    """Run all tests"""
    # Dictionary to track test results
    test_results = {}
    
    # Test connection
    test_results["connection"] = await test_connection()
    
    # Test listing tools
    tools = await test_list_tools()
    test_results["list_tools"] = len(tools) > 0
    
    # Check if required tools are available before testing them
    jira_tools = [tool for tool in tools if "jira" in tool.name.lower()]
    if jira_tools:
        # Test ticket creation
        test_results["create_ticket"] = await test_create_ticket()
        
        # Test ticket search
        test_results["search_tickets"] = await test_search_tickets()
    else:
        print("Skipping Jira tests as no Jira tools were found")
    
    # Print summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
    print("="*50)
    
    # Return overall success
    return all(test_results.values())

async def main():
    """Main function"""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="MCP Client Test Script")
    parser.add_argument("command", nargs="?", default="all", choices=["all", "connect", "list", "create", "search", "test_create"], 
                        help="Test command to run (default: all)")
    parser.add_argument("--project", "-p", help="Project key for custom ticket creation")
    parser.add_argument("--title", "-t", help="Title for custom ticket creation")
    parser.add_argument("--description", "-d", help="Description for custom ticket creation")
    parser.add_argument("--type", "-y", default="Task", help="Issue type for custom ticket creation")
    
    args = parser.parse_args()
    
    if args.command == "all":
        await run_tests()
    elif args.command == "connect":
        await test_connection()
    elif args.command == "list":
        await test_list_tools()
    elif args.command == "create":
        await test_create_ticket()
    elif args.command == "search":
        await test_search_tickets()
    elif args.command == "test_create" and args.project and args.title and args.description:
        await test_create_custom_ticket(args.project, args.title, args.description, args.type)
    elif args.command == "test_create":
        # Default values for test_create if not provided
        project = args.project or "KAN"
        title = args.title or "Test ticket from MCP client"
        description = args.description or "This is a test ticket created from the MCP client test script."
        issue_type = args.type or "Task"
        await test_create_custom_ticket(project, title, description, issue_type)

if __name__ == "__main__":
    asyncio.run(main()) 