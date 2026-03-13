#!/usr/bin/env python3
"""
Syntax and structure validation for Lambda functions
"""
import ast
import sys

def validate_lambda_code(filepath):
    print(f"Validating {filepath}...")
    
    try:
        with open(filepath, 'r') as f:
            code = f.read()
        
        # Parse the code
        tree = ast.parse(code)
        print("✓ Syntax is valid")
        
        # Check for handler function
        functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        if 'handler' in functions:
            print("✓ handler function found")
        else:
            print("✗ handler function not found")
            return False
            
        # Check imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend([alias.name for alias in node.names])
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
        
        print(f"✓ Imports found: {', '.join(set(imports))}")
        
        # Check for required imports
        required = ['json', 'boto3', 'psycopg2']
        missing = [imp for imp in required if imp not in imports]
        if missing:
            print(f"⚠ Missing imports: {', '.join(missing)}")
        
        return True
        
    except SyntaxError as e:
        print(f"✗ Syntax error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

print("=" * 60)
print("Lambda Function Validation")
print("=" * 60)

table_creator_valid = validate_lambda_code('index.py')

print("\n" + "=" * 60)
if table_creator_valid:
    print("✅ Validation passed!")
else:
    print("❌ Validation failed!")
    sys.exit(1)
