#!/usr/bin/env python3
"""
Database Migration Management Script

Usage:
  python migrations.py init     # Initialize Alembic
  python migrations.py upgrade  # Upgrade to latest
  python migrations.py current  # Show current revision
  python migrations.py history  # Show migration history
"""

import sys
import subprocess
import os
from pathlib import Path

def run_alembic_command(args):
    """Run alembic command with error handling"""
    try:
        result = subprocess.run(
            ["alembic"] + args,
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        
        if result.stdout:
            print(result.stdout)
        
        if result.stderr and result.returncode != 0:
            print(f"Error: {result.stderr}", file=sys.stderr)
            return False
        
        return result.returncode == 0
        
    except FileNotFoundError:
        print("Error: Alembic not found. Install with: pip install alembic", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error running alembic: {e}", file=sys.stderr)
        return False

def initialize_alembic():
    """Initialize Alembic configuration"""
    print("Initializing Alembic...")
    
    # Check if already initialized
    if Path("alembic").exists():
        print("Alembic already initialized")
        return True
    
    # Initialize Alembic
    success = run_alembic_command(["init", "alembic"])
    
    if success:
        print("Alembic initialized successfully")
        print("Note: Make sure to update alembic.ini with your database URL")
    
    return success

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "init":
        success = initialize_alembic()
    elif command == "upgrade":
        print("Upgrading database to latest revision...")
        success = run_alembic_command(["upgrade", "head"])
    elif command == "current":
        print("Current database revision:")
        success = run_alembic_command(["current"])
    elif command == "history":
        print("Migration history:")
        success = run_alembic_command(["history"])
    elif command == "revision":
        message = input("Enter migration message: ")
        success = run_alembic_command(["revision", "--autogenerate", "-m", message])
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
