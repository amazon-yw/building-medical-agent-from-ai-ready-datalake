#!/usr/bin/env python3
"""
Local test script for Lambda function
Tests imports and basic logic without AWS dependencies
"""
import sys
import os

# Add current directory to path (simulating Lambda environment)
sys.path.insert(0, os.path.dirname(__file__))

print("Testing imports...")

try:
    import psycopg2
    print(f"✓ psycopg2 imported successfully (version: {psycopg2.__version__})")
except ImportError as e:
    print(f"✗ Failed to import psycopg2: {e}")
    sys.exit(1)

try:
    import json
    print("✓ json imported successfully")
except ImportError as e:
    print(f"✗ Failed to import json: {e}")
    sys.exit(1)

try:
    import boto3
    print("✓ boto3 imported successfully")
except ImportError as e:
    print(f"✗ Failed to import boto3: {e}")
    sys.exit(1)

print("\nTesting Lambda handler structure...")

try:
    import index
    print("✓ index module imported successfully")
    
    # Check if handler function exists
    if hasattr(index, 'handler'):
        print("✓ handler function exists")
    else:
        print("✗ handler function not found")
        sys.exit(1)
        
except Exception as e:
    print(f"✗ Failed to import index: {e}")
    sys.exit(1)

print("\n✅ All tests passed! Lambda function should work.")
