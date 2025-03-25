#!/usr/bin/env python3

import os
import sys
import subprocess
import json
import shutil
import importlib.util

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_status(message, status="info"):
    """Print a status message with appropriate colors."""
    if status == "success":
        print(f"{GREEN}✓ {message}{RESET}")
    elif status == "warning":
        print(f"{YELLOW}⚠ {message}{RESET}")
    elif status == "error":
        print(f"{RED}✗ {message}{RESET}")
    elif status == "header":
        print(f"\n{BOLD}{message}{RESET}")
    else:
        print(f"  {message}")

def check_module_importable(module_name):
    """Check if a module can be imported."""
    spec = importlib.util.find_spec(module_name)
    return spec is not None

def run_command(cmd, quiet=False):
    """Run a command and return its output and return code."""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if not quiet:
            print_status(f"Command: {' '.join(cmd)}")
            if result.stdout and not quiet:
                print_status(f"Output: {result.stdout.strip()}")
            if result.stderr and not quiet:
                print_status(f"Error: {result.stderr.strip()}", "warning")
        
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        if not quiet:
            print_status(f"Failed to run command: {e}", "error")
        return "", str(e), 1

def check_mcp_version():
    """Check the installed MCP version."""
    print_status("Checking MCP installation", "header")
    
    # Check if mcp module can be imported
    if check_module_importable("mcp"):
        print_status("MCP module is importable", "success")
        
        # Check version by importing
        try:
            import mcp
            version = getattr(mcp, "__version__", "unknown")
            print_status(f"MCP version (from module): {version}", "success")
        except ImportError as e:
            print_status(f"Error importing mcp: {e}", "error")
    else:
        print_status("MCP module is not importable", "error")
    
    # Check MCP CLI
    mcp_path = shutil.which("mcp")
    if mcp_path:
        print_status(f"MCP CLI found at: {mcp_path}", "success")
        
        # Check version using CLI
        stdout, stderr, ret_code = run_command(["mcp", "--version"], quiet=True)
        if ret_code == 0:
            print_status(f"MCP CLI version: {stdout.strip()}", "success")
        else:
            print_status("Failed to get MCP CLI version", "error")
            print_status(stderr)
    else:
        print_status("MCP CLI not found in PATH", "error")

def test_mcp_client():
    """Test MCP client functionality with the server."""
    print_status("Testing MCP client functionality", "header")
    
    # Path to MCP server
    mcp_server_path = os.path.join("..", "Jira_mcp", "mcp_server.py")
    if not os.path.exists(mcp_server_path):
        print_status(f"MCP server not found at: {mcp_server_path}", "error")
        return
    
    print_status(f"MCP server found at: {mcp_server_path}", "success")
    
    # Test getting tool list
    print_status("Testing tool list retrieval:")
    stdout, stderr, ret_code = run_command(["mcp", "client", "--tool-list", mcp_server_path])
    
    if ret_code == 0:
        try:
            tools = json.loads(stdout)
            print_status(f"Successfully retrieved {len(tools)} tools", "success")
            
            # Show tool names
            if tools:
                print_status("Available tools:")
                for tool in tools:
                    print_status(f"  - {tool.get('name', 'unnamed')}")
        except json.JSONDecodeError:
            print_status("Failed to parse tools JSON", "error")
    else:
        print_status("Failed to retrieve tools", "error")

def recommend_fixes():
    """Provide recommendations to fix common issues."""
    print_status("Recommendations", "header")
    
    print_status("If you're experiencing issues with MCP:")
    
    print_status("1. Reinstall the MCP package:")
    print_status("   pip uninstall -y mcp")
    print_status("   pip install --upgrade mcp>=1.4.0")
    
    print_status("2. Ensure the MCP server is running:")
    print_status("   python ../Jira_mcp/mcp_server.py")
    
    print_status("3. Try running the MCP client directly:")
    print_status("   mcp client --tool-list ../Jira_mcp/mcp_server.py")
    
    print_status("4. Check if the MCP CLI tools are in your PATH:")
    print_status("   which mcp")
    
    print_status("5. If MCP is installed in a virtual environment, make sure it's activated")

if __name__ == "__main__":
    print_status(f"MCP Diagnostic Tool", "header")
    print_status(f"Python version: {sys.version}")
    print_status(f"Current directory: {os.getcwd()}")
    
    check_mcp_version()
    test_mcp_client()
    recommend_fixes() 