import json
import boto3
import psycopg2
import os
import time

s3 = boto3.client('s3')
secrets = boto3.client('secretsmanager')

def handler(event, context):
    conn = None
    try:
        # Get DB credentials
        secret_arn = os.environ['DB_SECRET_ARN']
        secret = json.loads(secrets.get_secret_value(SecretId=secret_arn)['SecretString'])
        
        print(f"Secret keys: {list(secret.keys())}")
        
        # Connect to database with retry
        max_retries = 5
        for attempt in range(max_retries):
            try:
                print(f"Connection attempt {attempt + 1}/{max_retries}")
                conn = psycopg2.connect(
                    host=secret.get('host'),
                    port=secret.get('port', 5432),
                    database=secret.get('dbname') or secret.get('database'),
                    user=secret.get('username') or secret.get('user'),
                    password=secret.get('password'),
                    connect_timeout=10
                )
                print("Database connection successful")
                break
            except psycopg2.OperationalError as e:
                print(f"Connection failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(30)
                else:
                    raise
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Get SQL files from S3
        bucket = os.environ['BUCKET_NAME']
        prefix = os.environ['DDL_PREFIX']
        
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        sql_files = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.sql')]
        sql_files.sort()
        
        # Execute SQL files in order
        for sql_file in sql_files:
            if 'master' in sql_file:
                continue
                
            print(f"Executing {sql_file}")
            obj = s3.get_object(Bucket=bucket, Key=sql_file)
            sql_content = obj['Body'].read().decode('utf-8')
            
            # Remove comments and split by semicolon
            lines = [line for line in sql_content.split('\n') if not line.strip().startswith('--')]
            clean_sql = '\n'.join(lines)
            statements = [s.strip() for s in clean_sql.split(';') if s.strip()]
            
            for statement in statements:
                try:
                    cursor.execute(statement)
                    print(f"Executed statement successfully")
                except Exception as stmt_error:
                    print(f"Error executing statement: {stmt_error}")
                    print(f"Statement: {statement[:200]}")
                    raise
        
        cursor.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'body': json.dumps('Tables created successfully')
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        if conn:
            conn.close()
        raise e
