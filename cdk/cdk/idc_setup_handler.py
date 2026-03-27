import json
import boto3
import cfnresponse
import hashlib
import hmac
from datetime import datetime
import urllib3
import uuid
import logging
import time

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sso_client = boto3.client('sso-admin')
id_store_client = boto3.client('identitystore')

def get_sso_start_url():
    """Get SSO start URL from the first available SSO instance"""
    try:
        response = sso_client.list_instances()
        if response['Instances']:
            identity_store_id = response['Instances'][0]['IdentityStoreId']
            return f"https://{identity_store_id}.awsapps.com/start"
        logger.warning('No SSO instances found')
        return None
    except Exception as e:
        logger.error(f'Failed to get SSO start URL: {str(e)}')
        return None
GROUPS = ["AllUsers"]
USERS = [
    {
        "user_name": "qdev",
        "email": "qdev@example.com",
        "display_name": "Application User",
        "given_name": "Application",
        "last_name": "User",
        "groups": ["AllUsers"]  
    }
]

def handler(event, context):
    logger.info('Lambda handler started')
    try:
        print('Received event: ' + json.dumps(event, indent=4, default=str))
        if event['RequestType'] in ['Create', 'Update']:
            identity_store_id = event['ResourceProperties']['IdentityStoreId']
            group_idx = {}
            user_id = []
            start_url = []
            group_id = []
            password_otp = []
            
            start_url.append(get_sso_start_url())
            for group in GROUPS:
                logger.info(f'Processing group: {group}')
                if not check_group_exists(identity_store_id, group):
                    resp = id_store_client.create_group(
                        IdentityStoreId=identity_store_id,
                        DisplayName=group,
                        Description=group
                    )
                    print("Group Creation:" + json.dumps(resp, indent=4, default=str))
                    group_idx[group] = resp["GroupId"]
                    group_id.append(resp["GroupId"])
            for user in USERS:
                logger.info(f'Processing user: {user["user_name"]}')
                user_exists = check_user_exists(identity_store_id, user["user_name"])
                if not user_exists:
                    user_resp = id_store_client.create_user(
                        IdentityStoreId=identity_store_id,
                        UserName=user["user_name"],
                        DisplayName=user["display_name"],
                        Emails=[{"Value": user["email"], "Type": "Work", "Primary": True}],
                        Name={"GivenName": user["given_name"], "FamilyName": user["last_name"]}
                    )
                    print("User Creation:" + json.dumps(user_resp, indent=4, default=str))
                    user_id.append(user_resp["UserId"])
                    # Assign groups
                    for grp in user["groups"]:
                        if grp in group_idx:
                            member_resp = id_store_client.create_group_membership(
                                IdentityStoreId=identity_store_id,
                                GroupId=group_idx[grp],
                                MemberId={"UserId": user_resp["UserId"]}
                            )
                            print("Group Member Creation:" + json.dumps(member_resp, indent=4, default=str))
                    
                    # Try to update password
                    try:
                        logger.info(f'Updating password for user: {user["user_name"]}')
                        password = update_password(user_resp["UserId"])
                        password_otp.append(password)
                    except Exception as e:
                        print(f"Failed to update password for user {user['user_name']}: {str(e)}")
                    
                    # Try to update SSO configuration
                    try:
                        logger.info('Updating SSO configuration')
                        sso_config = {
                            "mfaMode": "DISABLED",
                            "noMfaSignInBehavior": "ALLOWED_WITH_ENROLLMENT",
                            "allowedMfaTypes": ["TOTP", "WEBAUTHN"]
                        }
                        instance_arn = event['ResourceProperties'].get('InstanceArn', 'failtoreset')
                        if instance_arn:
                            update_sso_configuration(instance_arn, "APP_AUTHENTICATION_CONFIGURATION", sso_config)
                    except Exception as e:
                        print(f"Failed to update SSO configuration: {str(e)}")
                    
                    # Create CodeWhisperer profile
                    try:
                        logger.info('Creating CodeWhisperer profile')
                        if instance_arn:
                            create_codewhisperer_profile(instance_arn)
                            # Poll for profile status
                            while not check_codewhisperer_profile_status():
                                logger.info('Waiting for CodeWhisperer profile to become active...')
                                time.sleep(10)
                            logger.info('CodeWhisperer profile is now active')
                            # Create assignment for user
                            create_assignment(user_id[0])
                    except Exception as e:
                        print(f"Failed to create CodeWhisperer profile: {str(e)}")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, { 'StartURL': start_url, 'UserID': user_id, 'GroupID': group_id, 'PasswordOTP': password_otp}, identity_store_id)
        else:
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        logger.info('Lambda handler completed successfully')
        print("done")
    except Exception as e:
        logger.error(f'Lambda handler failed: {str(e)}')
        print(e)
        cfnresponse.send(event, context, cfnresponse.FAILED, {})
def check_user_exists(identity_store_id, user_id):
    logger.info(f'Checking if user exists: {user_id}')
    try:
        response = id_store_client.list_users(
            IdentityStoreId=identity_store_id,
            Filters=[
                {
                    'AttributePath': 'UserName',
                    'AttributeValue': user_id
                }
            ]
        )
        return len(response['Users']) > 0
    except Exception as e:
        print(f"Error checking user existence: {str(e)}")
        return False
def check_group_exists(identity_store_id, group_name):
    logger.info(f'Checking if group exists: {group_name}')
    try:
        response = id_store_client.list_groups(
            IdentityStoreId=identity_store_id,
            Filters=[
                {
                    'AttributePath': 'DisplayName',
                    'AttributeValue': group_name
                }
            ]
        )
        return len(response['Groups']) > 0
    except Exception as e:
        print(f"Error checking group existence: {str(e)}")
        return False

def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

def get_signature_key(key, date_stamp, region_name, service_name):
    k_date = sign(('AWS4' + key).encode('utf-8'), date_stamp)
    k_region = sign(k_date, region_name)
    k_service = sign(k_region, service_name)
    k_signing = sign(k_service, 'aws4_request')
    return k_signing

def update_password(user_id, password_mode="OTP"):
    logger.info(f'Starting password update for user: {user_id}')
    session = boto3.Session()
    credentials = session.get_credentials()
    
    access_key = credentials.access_key
    secret_key = credentials.secret_key
    session_token = credentials.token
    
    method = 'POST'
    service = 'userpool'
    host = 'up.sso.us-east-1.amazonaws.com'
    region = 'us-east-1'
    endpoint = f'https://{host}/'
    
    payload = {
        "UserId": user_id,
        "PasswordMode": password_mode
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    
    t = datetime.utcnow()
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = t.strftime('%Y%m%d')
    
    canonical_uri = '/'
    canonical_querystring = ''
    payload_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
    
    canonical_headers = f'host:{host}\n'
    canonical_headers += f'x-amz-content-sha256:{payload_hash}\n'
    canonical_headers += f'x-amz-date:{amz_date}\n'
    canonical_headers += f'x-amz-security-token:{session_token}\n'
    canonical_headers += f'x-amz-target:SWBUPService.UpdatePassword\n'
    canonical_headers += f'x-amz-user-agent:aws-sdk-js/2.1467.0 promise\n'
    
    signed_headers = 'host;x-amz-content-sha256;x-amz-date;x-amz-security-token;x-amz-target;x-amz-user-agent'
    
    canonical_request = f'{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}'
    
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f'{date_stamp}/{region}/{service}/aws4_request'
    string_to_sign = f'{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()}'
    
    signing_key = get_signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    authorization_header = f'{algorithm} Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}'
    
    headers = {
        'Authorization': authorization_header,
        'Content-Type': 'application/x-amz-json-1.0',
        'X-Amz-Date': amz_date,
        'X-Amz-Security-Token': session_token,
        'X-Amz-Target': 'SWBUPService.UpdatePassword',
        'X-Amz-User-Agent': 'aws-sdk-js/2.1467.0 promise',
        'X-Amz-Content-Sha256': payload_hash
    }
    
    http = urllib3.PoolManager()
    response = http.request('POST', endpoint, headers=headers, body=payload_json)
    if response.status == 200:
        password = json.loads(response.data.decode('utf-8'))["Password"]
        print(f"New password: {password}")
        return password
    else:
        logger.error(f"Password update request failed with status {response.status}")
        logger.error(f"Response body: {response.data.decode('utf-8')}")                
        return None

def create_codewhisperer_profile(instance_arn):
    logger.info('Starting CodeWhisperer profile creation')
    session = boto3.Session()
    credentials = session.get_credentials()
    
    access_key = credentials.access_key
    secret_key = credentials.secret_key
    session_token = credentials.token
    client_token = str(uuid.uuid4())
    
    method = 'POST'
    service = 'codewhisperer'
    host = 'codewhisperer.us-east-1.amazonaws.com'
    region = 'us-east-1'
    endpoint = f'https://{host}/'
    
    payload = {
        "profileName": "QDevProfile-us-east-1",
        "referenceTrackerConfiguration": {"recommendationsWithReferences": "ALLOW"},
        "activeFunctionalities": ["ANALYSIS", "CONVERSATIONS", "TASK_ASSIST", "TRANSFORMATIONS", "COMPLETIONS"],
        "optInFeatures": {"dashboardAnalytics": {"toggle": "ON"}},
        "identitySource": {"ssoIdentitySource": {"instanceArn": instance_arn, "ssoRegion": "us-east-1"}},
        "clientToken": client_token
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    
    t = datetime.utcnow()
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = t.strftime('%Y%m%d')
    
    canonical_uri = '/'
    canonical_querystring = ''
    payload_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
    
    canonical_headers = f'host:{host}\n'
    canonical_headers += f'x-amz-content-sha256:{payload_hash}\n'
    canonical_headers += f'x-amz-date:{amz_date}\n'
    canonical_headers += f'x-amz-security-token:{session_token}\n'
    canonical_headers += f'x-amz-target:AWSCodeWhispererService.CreateProfile\n'
    canonical_headers += f'x-amz-user-agent:aws-sdk-js/2.1692.0 promise\n'
    
    signed_headers = 'host;x-amz-content-sha256;x-amz-date;x-amz-security-token;x-amz-target;x-amz-user-agent'
    
    canonical_request = f'{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}'
    
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f'{date_stamp}/{region}/{service}/aws4_request'
    string_to_sign = f'{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()}'
    
    signing_key = get_signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    authorization_header = f'{algorithm} Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}'
    
    headers = {
        'Authorization': authorization_header,
        'Content-Type': 'application/x-amz-json-1.0',
        'X-Amz-Date': amz_date,
        'X-Amz-Security-Token': session_token,
        'X-Amz-Target': 'AWSCodeWhispererService.CreateProfile',
        'X-Amz-User-Agent': 'aws-sdk-js/2.1692.0 promise',
        'X-Amz-Content-Sha256': payload_hash
    }
    
    http = urllib3.PoolManager()
    response = http.request('POST', endpoint, headers=headers, body=payload_json)
    logger.info(f'CodeWhisperer profile creation response: {response.status}')
    return response

def update_sso_configuration(instance_arn, config_type, sso_config):
    logger.info(f'Starting SSO configuration update for instance: {instance_arn}')
    session = boto3.Session()
    credentials = session.get_credentials()
    
    access_key = credentials.access_key
    secret_key = credentials.secret_key
    session_token = credentials.token
    
    method = 'POST'
    service = 'sso'
    host = 'sso.us-east-1.amazonaws.com'
    region = 'us-east-1'
    endpoint = f'https://{host}/control/'
    
    payload = {
        "instanceArn": instance_arn,
        "configurationType": config_type,
        "ssoConfiguration": sso_config
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    
    t = datetime.utcnow()
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = t.strftime('%Y%m%d')
    
    canonical_uri = '/control/'
    canonical_querystring = ''
    payload_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
    
    canonical_headers = f'host:{host}\n'
    canonical_headers += f'x-amz-content-sha256:{payload_hash}\n'
    canonical_headers += f'x-amz-date:{amz_date}\n'
    canonical_headers += f'x-amz-security-token:{session_token}\n'
    canonical_headers += f'x-amz-target:SWBService.UpdateSsoConfiguration\n'
    canonical_headers += f'x-amz-user-agent:aws-sdk-js/2.1467.0 promise\n'
    
    signed_headers = 'host;x-amz-content-sha256;x-amz-date;x-amz-security-token;x-amz-target;x-amz-user-agent'
    
    canonical_request = f'{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}'
    
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f'{date_stamp}/{region}/{service}/aws4_request'
    string_to_sign = f'{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()}'
    
    signing_key = get_signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    authorization_header = f'{algorithm} Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}'
    
    headers = {
        'Authorization': authorization_header,
        'Content-Type': 'application/x-amz-json-1.1',
        'X-Amz-Date': amz_date,
        'X-Amz-Security-Token': session_token,
        'X-Amz-Target': 'SWBService.UpdateSsoConfiguration',
        'X-Amz-User-Agent': 'aws-sdk-js/2.1467.0 promise',
        'X-Amz-Content-Sha256': payload_hash
    }
    
    http = urllib3.PoolManager()
    response = http.request('POST', endpoint, headers=headers, body=payload_json)
    print(f"Response: {response.data.decode('utf-8')}")
    return response

def check_codewhisperer_profile_status():
    logger.info('Checking CodeWhisperer profile status')
    session = boto3.Session()
    credentials = session.get_credentials()
    
    access_key = credentials.access_key
    secret_key = credentials.secret_key
    session_token = credentials.token
    
    method = 'POST'
    service = 'codewhisperer'
    host = 'codewhisperer.us-east-1.amazonaws.com'
    region = 'us-east-1'
    endpoint = f'https://{host}/'
    
    payload_json = '{}'
    
    t = datetime.utcnow()
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = t.strftime('%Y%m%d')
    
    canonical_uri = '/'
    canonical_querystring = ''
    payload_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
    
    canonical_headers = f'host:{host}\n'
    canonical_headers += f'x-amz-content-sha256:{payload_hash}\n'
    canonical_headers += f'x-amz-date:{amz_date}\n'
    canonical_headers += f'x-amz-security-token:{session_token}\n'
    canonical_headers += f'x-amz-target:AWSCodeWhispererService.ListProfiles\n'
    canonical_headers += f'x-amz-user-agent:aws-sdk-js/2.1692.0 promise\n'
    
    signed_headers = 'host;x-amz-content-sha256;x-amz-date;x-amz-security-token;x-amz-target;x-amz-user-agent'
    
    canonical_request = f'{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}'
    
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f'{date_stamp}/{region}/{service}/aws4_request'
    string_to_sign = f'{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()}'
    
    signing_key = get_signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    authorization_header = f'{algorithm} Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}'
    
    headers = {
        'Authorization': authorization_header,
        'Content-Type': 'application/x-amz-json-1.0',
        'X-Amz-Date': amz_date,
        'X-Amz-Security-Token': session_token,
        'X-Amz-Target': 'AWSCodeWhispererService.ListProfiles',
        'X-Amz-User-Agent': 'aws-sdk-js/2.1692.0 promise',
        'X-Amz-Content-Sha256': payload_hash
    }
    
    http = urllib3.PoolManager()
    response = http.request('POST', endpoint, headers=headers, body=payload_json)
    
    if response.status == 200:
        data = json.loads(response.data.decode('utf-8'))
        profiles = data.get('profiles', [])
        for profile in profiles:
            if profile.get('status') == 'ACTIVE':
                logger.info(f'Found active profile: {profile.get("profileName")}')
                return True
        logger.info('No active profiles found')
        return False
    else:
        logger.error(f'Failed to check profile status: {response.status}')
        return False

def create_assignment(user_id):
    logger.info(f'Creating CodeWhisperer assignment for user: {user_id}')
    session = boto3.Session()
    credentials = session.get_credentials()
    
    access_key = credentials.access_key
    secret_key = credentials.secret_key
    session_token = credentials.token
    
    method = 'POST'
    service = 'q'
    host = 'codewhisperer.us-east-1.amazonaws.com'
    region = 'us-east-1'
    endpoint = f'https://{host}/'
    
    payload = {
        "principalId": user_id,
        "principalType": "USER",
        "subscriptionType": "Q_DEVELOPER_STANDALONE_PRO"
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    
    t = datetime.utcnow()
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = t.strftime('%Y%m%d')
    
    canonical_uri = '/'
    canonical_querystring = ''
    payload_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
    
    canonical_headers = f'host:{host}\n'
    canonical_headers += f'x-amz-content-sha256:{payload_hash}\n'
    canonical_headers += f'x-amz-date:{amz_date}\n'
    canonical_headers += f'x-amz-security-token:{session_token}\n'
    canonical_headers += f'x-amz-target:AmazonQDeveloperService.CreateAssignment\n'
    canonical_headers += f'x-amz-user-agent:aws-sdk-js/2.1692.0 promise\n'
    
    signed_headers = 'host;x-amz-content-sha256;x-amz-date;x-amz-security-token;x-amz-target;x-amz-user-agent'
    
    canonical_request = f'{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}'
    
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f'{date_stamp}/{region}/{service}/aws4_request'
    string_to_sign = f'{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()}'
    
    signing_key = get_signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    authorization_header = f'{algorithm} Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}'
    
    headers = {
        'Authorization': authorization_header,
        'Content-Type': 'application/x-amz-json-1.0',
        'X-Amz-Date': amz_date,
        'X-Amz-Security-Token': session_token,
        'X-Amz-Target': 'AmazonQDeveloperService.CreateAssignment',
        'X-Amz-User-Agent': 'aws-sdk-js/2.1692.0 promise',
        'X-Amz-Content-Sha256': payload_hash
    }
    
    http = urllib3.PoolManager()
    response = http.request('POST', endpoint, headers=headers, body=payload_json)
    logger.info(f'Assignment creation response: {response.status}')
    return response