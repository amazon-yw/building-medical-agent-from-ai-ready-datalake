from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_logs as logs,
    aws_glue as glue,
    aws_sagemaker as sagemaker,
    aws_s3tables as s3tables,
    aws_datazone as datazone,
    aws_lakeformation as lakeformation,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_secretsmanager as secretsmanager,
    aws_ssm as ssm,
    aws_sso as sso,
    custom_resources as cr,
    Duration,
    RemovalPolicy,
    CustomResource,
    CfnResource,
    BundlingOptions,
    CfnOutput,
    Size,
)
from constructs import Construct
import os

class FhirDataStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        account_id = self.account
        
        # 0. S3 Tables Bucket and Namespace
        s3_table_bucket = s3tables.CfnTableBucket(
            self, "FhirTableBucket",
            table_bucket_name="fhir-bucket"
        )
        
        table_bucket_arn = f"arn:aws:s3tables:{self.region}:{account_id}:bucket/fhir-bucket"
        
        s3_table_bucket_policy = s3tables.CfnTableBucketPolicy(
            self, "FhirTableBucketPolicy",
            resource_policy={
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "s3tables.amazonaws.com"},
                        "Action": [
                            "s3tables:GetTable",
                            "s3tables:GetTableMetadataLocation",
                            "s3tables:GetTableBucket"
                        ],
                        "Resource": table_bucket_arn
                    }
                ]
            },
            table_bucket_arn=table_bucket_arn
        )
        s3_table_bucket_policy.add_dependency(s3_table_bucket)
        
        s3_namespace = s3tables.CfnNamespace(
            self, "FhirNamespace",
            namespace="data",
            table_bucket_arn=table_bucket_arn
        )
        s3_namespace.add_dependency(s3_table_bucket)
        
        # 1. S3 Bucket
        bucket = s3.Bucket(
            self, "FhirDataBucket",
            bucket_name=f"fhir-data-{account_id}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )
        
        # 2. Upload NDJSON files
        s3deploy.BucketDeployment(
            self, "DeployNdjsonFiles",
            sources=[s3deploy.Source.asset(os.path.join(os.path.dirname(__file__), "../../data/fhir"))],
            destination_bucket=bucket,
            destination_key_prefix="data/raw/",
            memory_limit=1024,
            ephemeral_storage_size=Size.gibibytes(5)
        )
        
        # 3. Upload SQL files
        s3deploy.BucketDeployment(
            self, "DeploySqlFiles",
            sources=[s3deploy.Source.asset(os.path.join(os.path.dirname(__file__), "../../data/ddl/v2"))],
            destination_bucket=bucket,
            destination_key_prefix="scripts/ddl/",
            exclude=["*.md"]
        )
        
        # VPC for RDS
        vpc = ec2.Vpc(
            self, "FhirVpc",
            max_azs=2,
            nat_gateways=1
        )
        
        # Add S3 Gateway VPC Endpoint for Glue Crawler
        vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)]
        )
        
        # Security Group for RDS
        db_security_group = ec2.SecurityGroup(
            self, "DbSecurityGroup",
            vpc=vpc,
            allow_all_outbound=True
        )
        
        # Security Group for Glue Connection
        glue_security_group = ec2.SecurityGroup(
            self, "GlueSecurityGroup",
            vpc=vpc,
            allow_all_outbound=True,
            description="Security group for Glue Connection"
        )
        
        db_security_group.add_ingress_rule(
            ec2.Peer.ipv4(vpc.vpc_cidr_block),
            ec2.Port.tcp(5432)
        )
        
        # Allow Glue to connect to RDS
        db_security_group.add_ingress_rule(
            glue_security_group,
            ec2.Port.tcp(5432),
            "Allow Glue Connection"
        )
        
        # Add self-referencing rule for Glue Crawler
        db_security_group.add_ingress_rule(
            db_security_group,
            ec2.Port.all_traffic(),
            "Allow Glue Crawler self-referencing traffic"
        )
        
        # Glue security group self-referencing
        glue_security_group.add_ingress_rule(
            glue_security_group,
            ec2.Port.all_traffic(),
            "Self-referencing rule for Glue"
        )
        
        # Security Group for SageMaker Unified Studio
        sagemaker_sg = ec2.SecurityGroup(
            self, "SageMakerUnifiedStudioSG",
            vpc=vpc,
            allow_all_outbound=True,
            description="Security group for SageMaker Unified Studio notebooks"
        )
        
        # Allow SageMaker to connect to Aurora
        db_security_group.add_ingress_rule(
            sagemaker_sg,
            ec2.Port.tcp(5432),
            "Allow SageMaker Unified Studio"
        )
        
        # 4. Aurora PostgreSQL Parameter Group for Glue compatibility
        db_parameter_group = rds.ParameterGroup(
            self, "FhirDbParameterGroup",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_16_6
            ),
            description="Parameter group for Glue JDBC compatibility",
            parameters={
                "password_encryption": "md5"
            }
        )
        
        # 4. Aurora PostgreSQL
        db_cluster = rds.DatabaseCluster(
            self, "FhirDatabase",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_16_6
            ),
            writer=rds.ClusterInstance.serverless_v2("writer"),
            serverless_v2_min_capacity=1,
            serverless_v2_max_capacity=4,
            vpc=vpc,
            security_groups=[db_security_group],
            parameter_group=db_parameter_group,
            default_database_name="fhir_database",
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # IAM Role for SageMaker access
        sagemaker_role = iam.Role(
            self, "SageMakerDbAccessRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess")
            ]
        )
        
        db_cluster.secret.grant_read(sagemaker_role)
        
        # 5. Table Creator Lambda (psycopg2 포함)
        table_creator = lambda_.Function(
            self, "FhirTableCreator",
            function_name="fhir-table-creator",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/table_creator"),
            timeout=Duration.minutes(15),
            memory_size=512,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            environment={
                "DB_SECRET_ARN": db_cluster.secret.secret_arn,
                "BUCKET_NAME": bucket.bucket_name,
                "DDL_PREFIX": "scripts/ddl/"
            }
        )
        
        bucket.grant_read(table_creator)
        db_cluster.secret.grant_read(table_creator)
        db_cluster.connections.allow_from(table_creator, ec2.Port.tcp(5432))
        
        # 6. Data Loader Lambdas (split by table)
        
        # 6a. Base entities loader (must run first)
        base_loader = lambda_.Function(
            self, "FhirBaseLoader",
            function_name="fhir-base-loader",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/data_loader"),
            timeout=Duration.minutes(5),
            memory_size=512,
            retry_attempts=0,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            environment={
                "DB_SECRET_ARN": db_cluster.secret.secret_arn,
                "BUCKET_NAME": bucket.bucket_name,
                "DATA_PREFIX": "data/raw/",
                "DDL_PREFIX": "scripts/ddl/",
                "RESOURCE_FILTER": "Patient,Practitioner,Organization,Location,Medication"
            }
        )
        
        # 6b. Large table loaders (one per table)
        observation_loader = lambda_.Function(
            self, "FhirObservationLoader",
            function_name="fhir-observation-loader",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/data_loader"),
            timeout=Duration.minutes(15),
            memory_size=3008,
            ephemeral_storage_size=Size.mebibytes(2048),
            retry_attempts=0,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            environment={
                "DB_SECRET_ARN": db_cluster.secret.secret_arn,
                "BUCKET_NAME": bucket.bucket_name,
                "DATA_PREFIX": "data/raw/",
                "DDL_PREFIX": "scripts/ddl/",
                "RESOURCE_FILTER": "Observation"
            }
        )
        
        procedure_loader = lambda_.Function(
            self, "FhirProcedureLoader",
            function_name="fhir-procedure-loader",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/data_loader"),
            timeout=Duration.minutes(10),
            memory_size=1024,
            retry_attempts=0,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            environment={
                "DB_SECRET_ARN": db_cluster.secret.secret_arn,
                "BUCKET_NAME": bucket.bucket_name,
                "DATA_PREFIX": "data/raw/",
                "DDL_PREFIX": "scripts/ddl/",
                "RESOURCE_FILTER": "Procedure"
            }
        )
        
        diagnostic_loader = lambda_.Function(
            self, "FhirDiagnosticLoader",
            function_name="fhir-diagnostic-loader",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/data_loader"),
            timeout=Duration.minutes(10),
            memory_size=2048,
            retry_attempts=0,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            environment={
                "DB_SECRET_ARN": db_cluster.secret.secret_arn,
                "BUCKET_NAME": bucket.bucket_name,
                "DATA_PREFIX": "data/raw/",
                "DDL_PREFIX": "scripts/ddl/",
                "RESOURCE_FILTER": "DiagnosticReport"
            }
        )
        
        eob_loader = lambda_.Function(
            self, "FhirEobLoader",
            function_name="fhir-eob-loader",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/data_loader"),
            timeout=Duration.minutes(10),
            memory_size=2048,
            retry_attempts=0,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            environment={
                "DB_SECRET_ARN": db_cluster.secret.secret_arn,
                "BUCKET_NAME": bucket.bucket_name,
                "DATA_PREFIX": "data/raw/",
                "DDL_PREFIX": "scripts/ddl/",
                "RESOURCE_FILTER": "ExplanationOfBenefit"
            }
        )
        
        claim_loader = lambda_.Function(
            self, "FhirClaimLoader",
            function_name="fhir-claim-loader",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/data_loader"),
            timeout=Duration.minutes(10),
            memory_size=2048,
            retry_attempts=0,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            environment={
                "DB_SECRET_ARN": db_cluster.secret.secret_arn,
                "BUCKET_NAME": bucket.bucket_name,
                "DATA_PREFIX": "data/raw/",
                "DDL_PREFIX": "scripts/ddl/",
                "RESOURCE_FILTER": "Claim"
            }
        )
        
        # 6c. Document loader (DocumentReference + Provenance - large files)
        doc_loader = lambda_.Function(
            self, "FhirDocLoader",
            function_name="fhir-doc-loader",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/data_loader"),
            timeout=Duration.minutes(10),
            memory_size=512,
            retry_attempts=0,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            environment={
                "DB_SECRET_ARN": db_cluster.secret.secret_arn,
                "BUCKET_NAME": bucket.bucket_name,
                "DATA_PREFIX": "data/raw/",
                "DDL_PREFIX": "scripts/ddl/",
                "RESOURCE_FILTER": "DocumentReference,Provenance"
            }
        )

        # 6d. Encounter loader (Encounter + MedicationRequest + Condition - medium files)
        encounter_loader = lambda_.Function(
            self, "FhirEncounterLoader",
            function_name="fhir-encounter-loader",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/data_loader"),
            timeout=Duration.minutes(10),
            memory_size=512,
            retry_attempts=0,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            environment={
                "DB_SECRET_ARN": db_cluster.secret.secret_arn,
                "BUCKET_NAME": bucket.bucket_name,
                "DATA_PREFIX": "data/raw/",
                "DDL_PREFIX": "scripts/ddl/",
                "RESOURCE_FILTER": "Encounter,MedicationRequest,Condition"
            }
        )

        # 6e. Small tables loader (remaining small files)
        small_loader = lambda_.Function(
            self, "FhirSmallLoader",
            function_name="fhir-small-loader",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/data_loader"),
            timeout=Duration.minutes(10),
            memory_size=512,
            retry_attempts=0,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            environment={
                "DB_SECRET_ARN": db_cluster.secret.secret_arn,
                "BUCKET_NAME": bucket.bucket_name,
                "DATA_PREFIX": "data/raw/",
                "DDL_PREFIX": "scripts/ddl/",
                "RESOURCE_FILTER": "SupplyDelivery,MedicationAdministration,Immunization,Device,ImagingStudy,CareTeam,CarePlan,AllergyIntolerance,PractitionerRole"
            }
        )
        
        # Grant permissions to all loaders
        all_loaders = [
            base_loader, observation_loader, procedure_loader, 
            diagnostic_loader, eob_loader, claim_loader,
            doc_loader, encounter_loader, small_loader
        ]
        
        for loader in all_loaders:
            bucket.grant_read(loader)
            db_cluster.secret.grant_read(loader)
            db_cluster.connections.allow_from(loader, ec2.Port.tcp(5432))
        
        # 7. Custom Resource to execute Lambdas in sequence
        provider = cr.Provider(
            self, "DbInitProvider",
            on_event_handler=lambda_.Function(
                self, "DbInitHandler",
                runtime=lambda_.Runtime.PYTHON_3_13,
                handler="index.handler",
                code=lambda_.Code.from_inline(f"""
import boto3
import json
import time

lambda_client = boto3.client('lambda')

def handler(event, context):
    request_type = event['RequestType']
    
    if request_type == 'Create':
        # Wait for database to be ready
        print("Waiting for database to be ready...")
        time.sleep(60)
        
        # Execute table creator with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Attempt {{attempt + 1}}/{{max_retries}} - Creating tables...")
                response1 = lambda_client.invoke(
                    FunctionName='{table_creator.function_name}',
                    InvocationType='RequestResponse'
                )
                
                result1 = json.loads(response1['Payload'].read())
                if response1['StatusCode'] != 200 or 'errorMessage' in result1:
                    if attempt < max_retries - 1:
                        print(f"Retry after error: {{result1}}")
                        time.sleep(30)
                        continue
                    raise Exception(f"Table creation failed: {{result1}}")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Retry after exception: {{str(e)}}")
                    time.sleep(30)
                    continue
                raise
        
        # Execute data loaders sequentially
        print("Starting data loading...")
        
        # Phase 1: Base entities (synchronous - must complete first)
        print("Phase 1: Loading base entities (sync)...")
        response_base = lambda_client.invoke(
            FunctionName='{base_loader.function_name}',
            InvocationType='RequestResponse'
        )
        result_base = json.loads(response_base['Payload'].read())
        if response_base['StatusCode'] != 200 or 'errorMessage' in result_base:
            raise Exception(f"Base loader failed: {{result_base}}")
        print("Phase 1 completed successfully")
        
        # Phase 2: Large tables (async - one per table)
        print("Phase 2: Loading large tables (async)...")
        large_loaders = [
            '{observation_loader.function_name}',
            '{procedure_loader.function_name}',
            '{diagnostic_loader.function_name}',
            '{eob_loader.function_name}',
            '{claim_loader.function_name}'
        ]
        
        for loader_name in large_loaders:
            response = lambda_client.invoke(
                FunctionName=loader_name,
                InvocationType='Event'
            )
            if response['StatusCode'] != 202:
                print(f"Warning: Failed to start {{loader_name}}")
        
        # Phase 3: Small/Medium tables (async)
        print("Phase 3: Loading small/medium tables (async)...")
        for loader_name in ['{doc_loader.function_name}', '{encounter_loader.function_name}', '{small_loader.function_name}']:
            resp = lambda_client.invoke(FunctionName=loader_name, InvocationType='Event')
            if resp['StatusCode'] != 202:
                print(f"Warning: Failed to start {{loader_name}}")
        
        print("Base entities loaded. Large/small tables loading in background.")
    
    return {{'PhysicalResourceId': 'DbInitialization'}}
"""),
                timeout=Duration.minutes(15)
            )
        )
        
        provider.on_event_handler.add_to_role_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[
                    table_creator.function_arn,
                    base_loader.function_arn,
                    observation_loader.function_arn,
                    procedure_loader.function_arn,
                    diagnostic_loader.function_arn,
                    eob_loader.function_arn,
                    claim_loader.function_arn,
                    doc_loader.function_arn,
                    encounter_loader.function_arn,
                    small_loader.function_arn
                ]
            )
        )
        
        db_init = CustomResource(
            self, "DbInitialization",
            service_token=provider.service_token
        )
        
        # Ensure database is created before initialization
        db_init.node.add_dependency(db_cluster)
        
        # 8. Glue Catalog Integration
        
        # 8a. Glue Database
        glue_database = glue.CfnDatabase(
            self, "FhirGlueDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="fhir_db",
                description="FHIR data from Aurora PostgreSQL"
            )
        )
        
        # 8b. Glue Connection to Aurora
        glue_connection = glue.CfnConnection(
            self, "FhirGlueConnection",
            catalog_id=self.account,
            connection_input=glue.CfnConnection.ConnectionInputProperty(
                name="fhir-aurora-connection",
                description="Connection to FHIR Aurora PostgreSQL",
                connection_type="JDBC",
                connection_properties={
                    "JDBC_CONNECTION_URL": f"jdbc:postgresql://{db_cluster.cluster_endpoint.hostname}:5432/fhir_database?ssl=true&sslmode=require",
                    "SECRET_ID": db_cluster.secret.secret_name,
                    "JDBC_ENFORCE_SSL": "true",
                    "SKIP_CUSTOM_JDBC_CERT_VALIDATION": "true"
                },
                physical_connection_requirements=glue.CfnConnection.PhysicalConnectionRequirementsProperty(
                    security_group_id_list=[glue_security_group.security_group_id],
                    subnet_id=vpc.private_subnets[1].subnet_id
                )
            )
        )
        
        # 8c. Glue Crawler IAM Role
        crawler_role = iam.Role(
            self, "GlueCrawlerRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess")
            ]
        )
        
        # Grant Glue access to Secrets Manager
        db_cluster.secret.grant_read(crawler_role)
        
        # Grant Glue access to JDBC driver in S3
        crawler_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:GetObject"],
            resources=[f"arn:aws:s3:::fhir-data-{account_id}-{self.region}/jdbc-drivers/*"]
        ))
        
        # Grant PassRole permission (Glue may need to pass the role)
        crawler_role.add_to_policy(iam.PolicyStatement(
            actions=["iam:PassRole"],
            resources=[crawler_role.role_arn]
        ))
        
        # Grant Glue access to use the connection and VPC
        crawler_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "glue:GetConnection",
                "ec2:DescribeNetworkInterfaces",
                "ec2:CreateNetworkInterface",
                "ec2:DeleteNetworkInterface",
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeVpcAttribute",
                "ec2:DescribeRouteTables",
                "ec2:CreateTags",
                "ec2:DeleteTags"
            ],
            resources=["*"]
        ))
        
        # Grant Glue Crawler access to Glue Database
        crawler_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "glue:GetDatabase",
                "glue:GetTable",
                "glue:GetTables",
                "glue:CreateTable",
                "glue:UpdateTable",
                "glue:DeleteTable",
                "glue:BatchCreatePartition",
                "glue:BatchDeletePartition",
                "glue:BatchUpdatePartition",
                "glue:GetPartition",
                "glue:GetPartitions",
                "glue:CreatePartition",
                "glue:UpdatePartition",
                "glue:DeletePartition"
            ],
            resources=[
                f"arn:aws:glue:{self.region}:{self.account}:catalog",
                f"arn:aws:glue:{self.region}:{self.account}:database/fhir_db",
                f"arn:aws:glue:{self.region}:{self.account}:table/fhir_db/*"
            ]
        ))
        
        # 8d. Glue Crawler
        glue_crawler = glue.CfnCrawler(
            self, "FhirGlueCrawler",
            name="fhir-aurora-crawler",
            role=crawler_role.role_arn,
            database_name=glue_database.ref,
            targets=glue.CfnCrawler.TargetsProperty(
                jdbc_targets=[
                    glue.CfnCrawler.JdbcTargetProperty(
                        connection_name=glue_connection.ref,
                        path="fhir_database/public/%"
                    )
                ]
            ),
            schema_change_policy=glue.CfnCrawler.SchemaChangePolicyProperty(
                update_behavior="UPDATE_IN_DATABASE",
                delete_behavior="LOG"
            ),
            configuration='{"Version":1.0,"CrawlerOutput":{"Partitions":{"AddOrUpdateBehavior":"InheritFromTable"}}}'
        )
        
        glue_crawler.add_dependency(glue_connection)
        glue_crawler.add_dependency(glue_database)
        glue_crawler.node.add_dependency(db_init)
        
        # 9. SageMaker Studio Domain (IAM-based)
        
        # 9a. SageMaker Execution Role
        sagemaker_execution_role = iam.Role(
            self, "SageMakerExecutionRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("sagemaker.amazonaws.com"),
                iam.ServicePrincipal("datazone.amazonaws.com"),
                iam.ServicePrincipal("glue.amazonaws.com"),
                iam.ServicePrincipal("bedrock.amazonaws.com"),
                iam.ServicePrincipal("scheduler.amazonaws.com"),
                iam.ServicePrincipal("lakeformation.amazonaws.com"),
                iam.ServicePrincipal("airflow-serverless.amazonaws.com"),
                iam.ServicePrincipal("athena.amazonaws.com"),
                iam.ServicePrincipal("redshift.amazonaws.com"),
                iam.ServicePrincipal("emr-serverless.amazonaws.com")
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess")
            ]
        )
        
        # Grant access to Glue Catalog
        sagemaker_execution_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "glue:GetDatabase",
                "glue:GetTable",
                "glue:GetTables",
                "glue:GetPartition",
                "glue:GetPartitions",
                "glue:CreateTable",
                "glue:UpdateTable",
                "glue:DeleteTable"
            ],
            resources=[
                f"arn:aws:glue:{self.region}:{self.account}:catalog",
                f"arn:aws:glue:{self.region}:{self.account}:database/fhir_db",
                f"arn:aws:glue:{self.region}:{self.account}:table/fhir_db/*"
            ]
        ))
        
        # Grant access to S3 Tables
        sagemaker_execution_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "s3tables:GetTable",
                "s3tables:GetTableBucket",
                "s3tables:GetTableMetadataLocation",
                "s3tables:CreateTable",
                "s3tables:UpdateTable",
                "s3tables:DeleteTable",
                "s3tables:PutTableData",
                "s3tables:GetTableData",
                "s3tables:ListTables",
                "s3tables:ListNamespaces"
            ],
            resources=[
                table_bucket_arn,
                f"{table_bucket_arn}/*"
            ]
        ))
        
        # Grant Lake Formation permissions
        sagemaker_execution_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "lakeformation:GetDataAccess",
                "lakeformation:GrantPermissions"
            ],
            resources=["*"]
        ))
        
        # Grant IAM permissions for self-management and service integration
        sagemaker_execution_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "iam:GetRole",
                "iam:PassRole"
            ],
            resources=[
                sagemaker_execution_role.role_arn,
                f"arn:aws:iam::{self.account}:role/service-role/AmazonSageMaker*"
            ],
            conditions={
                "StringEquals": {
                    "iam:PassedToService": [
                        "sagemaker.amazonaws.com",
                        "glue.amazonaws.com",
                        "lakeformation.amazonaws.com",
                        "bedrock.amazonaws.com",
                        "scheduler.amazonaws.com",
                        "airflow-serverless.amazonaws.com",
                        "athena.amazonaws.com",
                        "redshift.amazonaws.com",
                        "emr-serverless.amazonaws.com"
                    ]
                }
            }
        ))
        
        # Lake Formation permissions on S3 Tables catalog database
        # Note: CfnPrincipalPermissions has a 12-char limit on CatalogId,
        # but S3 Tables catalog ID is "account:s3tablescatalog/bucket" (40+ chars).
        # Must use Custom Resource with AwsSdkCall instead.
        s3tables_catalog_id = f"{account_id}:s3tablescatalog/fhir-bucket"

        lf_grant_role = iam.Role(self, "LFGrantRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        lf_grant_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "lakeformation:*",
                "glue:*",
                "s3tables:*"
            ],
            resources=["*"]
        ))

        # Lambda to register role as LF admin, grant permissions, and clean up
        lf_grant_fn = lambda_.Function(self, "LFGrantFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import boto3, json, urllib.request
def send_response(event, context, status, data={}):
    body = json.dumps({'Status': status, 'Reason': str(data), 'PhysicalResourceId': context.log_stream_name, 'StackId': event['StackId'], 'RequestId': event['RequestId'], 'LogicalResourceId': event['LogicalResourceId'], 'Data': data}).encode()
    urllib.request.urlopen(urllib.request.Request(event['ResponseURL'], data=body, headers={'Content-Type':'','Content-Length':str(len(body))}, method='PUT'))

def handler(event, context):
    try:
        lf = boto3.client('lakeformation')
        props = event['ResourceProperties']
        role_arn = props['RoleArn']
        principal_arn = props['PrincipalArn']
        catalog_id = props['CatalogId']
        db_name = props['DatabaseName']

        if event['RequestType'] in ['Create', 'Update']:
            settings = lf.get_data_lake_settings()['DataLakeSettings']
            admins = settings.get('DataLakeAdmins', [])
            if not any(a['DataLakePrincipalIdentifier'] == role_arn for a in admins):
                admins.append({'DataLakePrincipalIdentifier': role_arn})
                settings['DataLakeAdmins'] = admins
                lf.put_data_lake_settings(DataLakeSettings=settings)

            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier': principal_arn},
                Resource={'Database': {'CatalogId': catalog_id, 'Name': db_name}},
                Permissions=['ALL'], PermissionsWithGrantOption=['ALL']
            )
            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier': principal_arn},
                Resource={'Table': {'CatalogId': catalog_id, 'DatabaseName': db_name, 'TableWildcard': {}}},
                Permissions=['ALL'], PermissionsWithGrantOption=['ALL']
            )

        elif event['RequestType'] == 'Delete':
            try:
                lf.revoke_permissions(
                    Principal={'DataLakePrincipalIdentifier': principal_arn},
                    Resource={'Table': {'CatalogId': catalog_id, 'DatabaseName': db_name, 'TableWildcard': {}}},
                    Permissions=['ALL'], PermissionsWithGrantOption=['ALL']
                )
            except: pass
            try:
                lf.revoke_permissions(
                    Principal={'DataLakePrincipalIdentifier': principal_arn},
                    Resource={'Database': {'CatalogId': catalog_id, 'Name': db_name}},
                    Permissions=['ALL'], PermissionsWithGrantOption=['ALL']
                )
            except: pass
            try:
                settings = lf.get_data_lake_settings()['DataLakeSettings']
                settings['DataLakeAdmins'] = [a for a in settings.get('DataLakeAdmins', []) if a['DataLakePrincipalIdentifier'] != role_arn]
                lf.put_data_lake_settings(DataLakeSettings=settings)
            except: pass

        send_response(event, context, 'SUCCESS')
    except Exception as e:
        print(e)
        send_response(event, context, 'FAILED', {'Error': str(e)})
"""),
            role=lf_grant_role,
            timeout=Duration.seconds(60)
        )

        lf_provider = cr.Provider(self, "LFGrantProvider",
            on_event_handler=lf_grant_fn,
            provider_function_name="LFGrantProvider",
        )

        lf_permissions = CustomResource(self, "LFPermissions",
            service_token=lf_provider.service_token,
            properties={
                "RoleArn": lf_grant_role.role_arn,
                "PrincipalArn": sagemaker_execution_role.role_arn,
                "CatalogId": s3tables_catalog_id,
                "DatabaseName": "data"
            }
        )
        lf_permissions.node.add_dependency(s3_namespace)

        # Grant access to Secrets Manager
        db_cluster.secret.grant_read(sagemaker_execution_role)
        
        # Grant access to S3 bucket
        bucket.grant_read_write(sagemaker_execution_role)
        
        # ============================================================
        # EMR Serverless Application
        # ============================================================

        # Security Group for EMR Serverless
        emr_sg = ec2.SecurityGroup(
            self, "EmrServerlessSG",
            vpc=vpc,
            description="Security group for EMR Serverless Application",
            allow_all_outbound=True
        )
        # Self-referencing rule required for EMR Serverless workers
        emr_sg.add_ingress_rule(emr_sg, ec2.Port.all_traffic(), "EMR Serverless self-referencing")

        # EMR Serverless Execution Role
        emr_execution_role = iam.Role(
            self, "EmrServerlessExecutionRole",
            role_name="fhir-emr-serverless-execution-role",
            assumed_by=iam.ServicePrincipal("emr-serverless.amazonaws.com"),
        )

        # S3 access
        bucket.grant_read_write(emr_execution_role)

        # S3 Tables access
        emr_execution_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "s3tables:GetTable",
                "s3tables:GetTableBucket",
                "s3tables:GetTableMetadataLocation",
                "s3tables:GetTableData",
                "s3tables:ListTables",
                "s3tables:ListNamespaces",
                "s3tables:GetNamespace",
                "s3tables:PutTableData",
            ],
            resources=[table_bucket_arn, f"{table_bucket_arn}/*"]
        ))

        # Glue Catalog access
        emr_execution_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "glue:GetDatabase", "glue:GetDatabases",
                "glue:GetTable", "glue:GetTables",
                "glue:GetPartition", "glue:GetPartitions",
                "glue:GetUserDefinedFunctions",
            ],
            resources=[
                f"arn:aws:glue:{self.region}:{self.account}:catalog",
                f"arn:aws:glue:{self.region}:{self.account}:database/*",
                f"arn:aws:glue:{self.region}:{self.account}:table/*",
            ]
        ))

        # Lake Formation data access
        emr_execution_role.add_to_policy(iam.PolicyStatement(
            actions=["lakeformation:GetDataAccess"],
            resources=["*"]
        ))

        # CloudWatch Logs for EMR Serverless
        emr_execution_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
            ],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/emr-serverless/*"]
        ))

        # EMR Serverless Application (Spark)
        emr_app = CfnResource(
            self, "FhirEmrServerlessApp",
            type="AWS::EMRServerless::Application",
            properties={
                "Name": "fhir-data-query",
                "ReleaseLabel": "emr-7.12.0",
                "Type": "SPARK",
                "Architecture": "X86_64",
                "AutoStartConfiguration": {"Enabled": True},
                "AutoStopConfiguration": {"Enabled": False},
                "NetworkConfiguration": {
                    "SubnetIds": [subnet.subnet_id for subnet in vpc.private_subnets],
                    "SecurityGroupIds": [emr_sg.security_group_id]
                },
                "InteractiveConfiguration": {
                    "LivyEndpointEnabled": True,
                    "StudioEnabled": True
                },
                "InitialCapacity": [
                    {
                        "Key": "Driver",
                        "Value": {
                            "WorkerCount": 1,
                            "WorkerConfiguration": {
                                "Cpu": "4 vCPU",
                                "Memory": "16 GB"
                            }
                        }
                    },
                    {
                        "Key": "Executor",
                        "Value": {
                            "WorkerCount": 2,
                            "WorkerConfiguration": {
                                "Cpu": "4 vCPU",
                                "Memory": "16 GB"
                            }
                        }
                    }
                ],
                "MaximumCapacity": {
                    "Cpu": "400 vCPU",
                    "Memory": "3000 GB",
                    "Disk": "20000 GB"
                },
                "RuntimeConfiguration": [
                    {
                        "Classification": "spark-defaults",
                        "Properties": {
                            "spark.jars.packages": "software.amazon.s3tables:s3-tables-catalog-for-iceberg-runtime:0.1.3",
                            "spark.sql.catalog.s3tablescatalog": "org.apache.iceberg.spark.SparkCatalog",
                            "spark.sql.catalog.s3tablescatalog.catalog-impl": "software.amazon.s3tables.iceberg.S3TablesCatalog",
                            "spark.sql.catalog.s3tablescatalog.warehouse": f"arn:aws:s3tables:{self.region}:{self.account}:bucket/fhir-bucket",
                            "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
                        }
                    }
                ],
            }
        )

        # EMR Studio (required for console management of EMR Serverless)
        emr_studio_engine_sg = ec2.SecurityGroup(
            self, "EmrStudioEngineSG",
            vpc=vpc,
            description="EMR Studio Engine security group",
            allow_all_outbound=True
        )
        emr_studio_workspace_sg = ec2.SecurityGroup(
            self, "EmrStudioWorkspaceSG",
            vpc=vpc,
            description="EMR Studio Workspace security group",
            allow_all_outbound=True
        )
        emr_studio_engine_sg.add_ingress_rule(
            emr_studio_workspace_sg, ec2.Port.tcp(18888), "Workspace to Engine"
        )
        emr_studio_workspace_sg.add_ingress_rule(
            emr_studio_engine_sg, ec2.Port.tcp(18888), "Engine to Workspace"
        )

        emr_studio_service_role = iam.Role(
            self, "EmrStudioServiceRole",
            assumed_by=iam.ServicePrincipal("elasticmapreduce.amazonaws.com"),
            inline_policies={
                "S3Access": iam.PolicyDocument(statements=[
                    iam.PolicyStatement(
                        actions=["s3:*"],
                        resources=[bucket.bucket_arn, f"{bucket.bucket_arn}/*"]
                    )
                ]),
                "EC2Access": iam.PolicyDocument(statements=[
                    iam.PolicyStatement(
                        actions=[
                            "ec2:CreateNetworkInterface", "ec2:CreateNetworkInterfacePermission",
                            "ec2:DeleteNetworkInterface", "ec2:DeleteNetworkInterfacePermission",
                            "ec2:DescribeNetworkInterfaces", "ec2:DescribeVpcs", "ec2:DescribeSubnets",
                            "ec2:DescribeSecurityGroups", "ec2:ModifyNetworkInterfaceAttribute",
                            "ec2:AuthorizeSecurityGroupEgress", "ec2:AuthorizeSecurityGroupIngress",
                        ],
                        resources=["*"]
                    ),
                    iam.PolicyStatement(
                        actions=["ec2:CreateTags"],
                        resources=["arn:aws:ec2:*:*:network-interface/*"],
                        conditions={"ForAllValues:StringEquals": {"aws:TagKeys": ["aws:elasticmapreduce:editor-id", "aws:elasticmapreduce:job-flow-id"]}}
                    )
                ])
            }
        )

        emr_studio = CfnResource(
            self, "FhirEmrStudio",
            type="AWS::EMR::Studio",
            properties={
                "Name": "fhir-emr-studio",
                "Description": "EMR Studio for FHIR data lake",
                "AuthMode": "IAM",
                "VpcId": vpc.vpc_id,
                "SubnetIds": [subnet.subnet_id for subnet in vpc.private_subnets],
                "DefaultS3Location": f"s3://{bucket.bucket_name}/emr-studio/",
                "ServiceRole": emr_studio_service_role.role_arn,
                "EngineSecurityGroupId": emr_studio_engine_sg.security_group_id,
                "WorkspaceSecurityGroupId": emr_studio_workspace_sg.security_group_id,
            }
        )

        CfnOutput(self, "EmrStudioUrl", value=emr_studio.get_att("Url").to_string())

        # Start EMR Serverless Application on deploy
        start_emr_fn = lambda_.Function(self, "StartEmrAppFn",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import boto3, json, urllib.request, time
def send(event, context, status, data={}):
    body = json.dumps({'Status': status, 'Reason': str(data), 'PhysicalResourceId': context.log_stream_name,
        'StackId': event['StackId'], 'RequestId': event['RequestId'], 'LogicalResourceId': event['LogicalResourceId'], 'Data': data}).encode()
    urllib.request.urlopen(urllib.request.Request(event['ResponseURL'], data=body, method='PUT', headers={'Content-Type': ''}))
def handler(event, context):
    if event['RequestType'] == 'Delete':
        return send(event, context, 'SUCCESS')
    try:
        client = boto3.client('emr-serverless')
        app_id = event['ResourceProperties']['ApplicationId']
        client.start_application(applicationId=app_id)
        for _ in range(60):
            state = client.get_application(applicationId=app_id)['application']['state']
            if state == 'STARTED': break
            time.sleep(10)
        send(event, context, 'SUCCESS', {'State': state})
    except Exception as e:
        send(event, context, 'FAILED', {'Error': str(e)})
"""),
            timeout=Duration.minutes(15),
        )
        start_emr_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["emr-serverless:StartApplication", "emr-serverless:GetApplication"],
            resources=[f"arn:aws:emr-serverless:{self.region}:{self.account}:/applications/*"]
        ))

        start_emr = CustomResource(self, "StartEmrApp",
            service_token=start_emr_fn.function_arn,
            properties={"ApplicationId": emr_app.ref}
        )
        start_emr.node.add_dependency(emr_app)

        # Grant SageMaker execution role to pass EMR execution role & manage EMR Serverless
        sagemaker_execution_role.add_to_policy(iam.PolicyStatement(
            actions=["iam:PassRole"],
            resources=[emr_execution_role.role_arn],
            conditions={
                "StringEquals": {
                    "iam:PassedToService": "emr-serverless.amazonaws.com"
                }
            }
        ))
        sagemaker_execution_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "emr-serverless:GetApplication",
                "emr-serverless:ListApplications",
                "emr-serverless:StartApplication",
                "emr-serverless:StopApplication",
                "emr-serverless:StartJobRun",
                "emr-serverless:GetJobRun",
                "emr-serverless:ListJobRuns",
                "emr-serverless:CancelJobRun",
                "emr-serverless:AccessLivyEndpoints",
                "emr-serverless:GetDashboardForJobRun",
            ],
            resources=[f"arn:aws:emr-serverless:{self.region}:{self.account}:/applications/*"]
        ))

        # Grant Code Editor role EMR Serverless permissions (defined after Code Editor section)

        # Lake Formation permissions for EMR execution role on S3 Tables
        lf_emr_permissions = CustomResource(self, "LFEmrPermissions",
            service_token=lf_provider.service_token,
            properties={
                "RoleArn": lf_grant_role.role_arn,
                "PrincipalArn": emr_execution_role.role_arn,
                "CatalogId": s3tables_catalog_id,
                "DatabaseName": "data"
            }
        )
        lf_emr_permissions.node.add_dependency(s3_namespace)

        # Output
        CfnOutput(self, "EmrServerlessAppId", value=emr_app.ref)
        CfnOutput(self, "EmrServerlessExecutionRoleArn", value=emr_execution_role.role_arn)
        CfnOutput(self, "S3TableBucketArn", value=table_bucket_arn)
        CfnOutput(self, "S3TableBucketName", value=s3_table_bucket.table_bucket_name)
        CfnOutput(self, "SageMakerExecutionRoleArn", value=sagemaker_execution_role.role_arn)
        CfnOutput(self, "SageMakerSecurityGroupId", value=sagemaker_sg.security_group_id)
        CfnOutput(self, "VpcId", value=vpc.vpc_id)
        CfnOutput(self, "PrivateSubnets", value=",".join([subnet.subnet_id for subnet in vpc.private_subnets]))
        CfnOutput(self, "DbSecurityGroupId", value=db_security_group.security_group_id)
        CfnOutput(self, "AuroraEndpoint", value=db_cluster.cluster_endpoint.hostname)
        CfnOutput(self, "AuroraSecretArn", value=db_cluster.secret.secret_arn)
        CfnOutput(self, "GlueDatabaseName", value="data")

        # ============================================================
        # Code Editor (EC2 + CloudFront)
        # ============================================================

        code_editor_user = "participant"
        home_folder = "/workshop"

        # Secret for Code Editor password
        code_editor_secret = secretsmanager.Secret(self, "CodeEditorSecret",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                password_length=16,
                exclude_punctuation=True,
                secret_string_template=f'{{"username":"{code_editor_user}"}}',
                generate_string_key="password"
            ),
            removal_policy=RemovalPolicy.DESTROY
        )

        # IAM Role for Code Editor EC2
        code_editor_role = iam.Role(self, "CodeEditorRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ec2.amazonaws.com"),
                iam.ServicePrincipal("ssm.amazonaws.com")
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSGlueConsoleFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonAthenaFullAccess"),
            ]
        )
        # S3 Tables full access
        code_editor_role.add_to_policy(iam.PolicyStatement(
            actions=["s3tables:*"],
            resources=["*"]
        ))
        # Lake Formation
        code_editor_role.add_to_policy(iam.PolicyStatement(
            actions=["lakeformation:*"],
            resources=["*"]
        ))
        # EMR Serverless
        code_editor_role.add_to_policy(iam.PolicyStatement(
            actions=["emr-serverless:*"],
            resources=["*"]
        ))
        # CDK deploy permissions
        code_editor_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("PowerUserAccess")
        )
        code_editor_role.add_to_policy(iam.PolicyStatement(
            actions=["iam:*"],
            resources=["*"]
        ))
        # AWS Marketplace permissions for Bedrock model access
        code_editor_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "aws-marketplace:ViewSubscriptions",
                "aws-marketplace:Subscribe",
                "aws-marketplace:Unsubscribe",
            ],
            resources=["*"]
        ))
        # Secrets Manager read for DB credentials
        db_cluster.secret.grant_read(code_editor_role)

        # Security Group - allow CloudFront origin-facing
        code_editor_sg = ec2.SecurityGroup(self, "CodeEditorSG",
            vpc=vpc,
            description="Code Editor - CloudFront ingress only",
            allow_all_outbound=True
        )
        code_editor_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(80),
            "CloudFront origin-facing"
        )

        # EC2 Instance
        code_editor_instance = ec2.Instance(self, "CodeEditorInstance",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            instance_type=ec2.InstanceType("m7g.large"),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(
                cpu_type=ec2.AmazonLinuxCpuType.ARM_64
            ),
            role=code_editor_role,
            security_group=code_editor_sg,
            block_devices=[ec2.BlockDevice(
                device_name="/dev/xvda",
                volume=ec2.BlockDeviceVolume.ebs(40, volume_type=ec2.EbsDeviceVolumeType.GP3, encrypted=True)
            )],
            user_data=ec2.UserData.custom(f"#!/bin/bash\nmkdir -p {home_folder} && chown -R {code_editor_user}:{code_editor_user} {home_folder}\nhostname CodeEditor\ndnf install -y python3.12 python3.12-pip\n"),
        )
        code_editor_instance.instance.add_property_override("Tags", [{"Key": "Name", "Value": "CodeEditor"}])

        # SSM Document for bootstrapping
        ssm_doc = ssm.CfnDocument(self, "CodeEditorSSMDoc",
            document_type="Command",
            content={
                "schemaVersion": "2.2",
                "description": "Bootstrap Code Editor",
                "parameters": {
                    "CodeEditorPassword": {"type": "String", "default": "changeme"}
                },
                "mainSteps": [
                    {
                        "name": "InstallCodeEditor",
                        "action": "aws:runShellScript",
                        "inputs": {
                            "timeoutSeconds": 900,
                            "runCommand": [
                                "#!/bin/bash",
                                "set -euo pipefail",
                                # Base packages
                                "dnf install -y --allowerasing curl gnupg whois argon2 unzip nginx openssl jq git",
                                # Add user
                                f"adduser -c '' {code_editor_user} || true",
                                f"passwd -l {code_editor_user}",
                                f'echo "{code_editor_user}:{{{{ CodeEditorPassword }}}}" | chpasswd',
                                f"usermod -aG wheel {code_editor_user}",
                                "sed -i 's/# %wheel/%wheel/g' /etc/sudoers",
                                # Profile
                                "echo LANG=en_US.utf-8 >> /etc/environment",
                                f"echo 'export AWS_REGION={self.region}' >> /home/{code_editor_user}/.bashrc",
                                f"echo 'export AWS_ACCOUNTID={self.account}' >> /home/{code_editor_user}/.bashrc",
                                # AWS CLI
                                f"sudo -u {code_editor_user} curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip -o /tmp/aws-cli.zip",
                                "unzip -q -d /tmp /tmp/aws-cli.zip && /tmp/aws/install && rm -rf /tmp/aws",
                                # Node.js 22 LTS, pip, AWS CDK
                                "curl -fsSL https://rpm.nodesource.com/setup_22.x | bash -",
                                "dnf install -y nodejs python3-pip",
                                "npm install -g aws-cdk",
                                # Git config
                                f'sudo -u {code_editor_user} git config --global user.email "participant@example.com"',
                                f'sudo -u {code_editor_user} git config --global user.name "Workshop Participant"',
                                f'sudo -u {code_editor_user} git config --global init.defaultBranch "main"',
                                # Install Code Editor
                                f"export CodeEditorUser={code_editor_user}",
                                "curl -fsSL https://code-editor.amazonaws.com/content/code-editor-server/dist/aws-workshop-studio/install.sh | bash -s -- 2>&1 || true",
                                # Nginx
                                'tee /etc/nginx/conf.d/code-editor.conf <<\'NGINX\'\n'
                                'server {\n'
                                '    listen 80;\n'
                                '    server_name *.cloudfront.net;\n'
                                '    proxy_set_header Host $host;\n'
                                '    proxy_set_header Upgrade $http_upgrade;\n'
                                '    proxy_set_header Connection "upgrade";\n'
                                '    proxy_buffering off;\n'
                                '    location / { proxy_pass http://localhost:8080/; }\n'
                                '}\n'
                                'NGINX',
                                "systemctl enable nginx && systemctl restart nginx",
                                # Auth token
                                f"sudo -u {code_editor_user} mkdir -p /home/{code_editor_user}/.code-editor-server/data",
                                f'echo -n "{{{{ CodeEditorPassword }}}}" > /home/{code_editor_user}/.code-editor-server/data/token',
                                # Settings
                                f"sudo -u {code_editor_user} mkdir -p /home/{code_editor_user}/.code-editor-server/data/User",
                                f"mkdir -p {home_folder} && chown -R {code_editor_user}:{code_editor_user} {home_folder}",
                                f'cat > /home/{code_editor_user}/.code-editor-server/data/User/settings.json << \'SETTINGS\'\n'
                                '{"aws.telemetry":false,"extensions.autoUpdate":false,"telemetry.telemetryLevel":"off",\n'
                                '"security.workspace.trust.enabled":false,"workbench.startupEditor":"none",\n'
                                f'"terminal.integrated.cwd":"{home_folder}"}}\n'
                                'SETTINGS',
                                f"chown -R {code_editor_user}:{code_editor_user} /home/{code_editor_user}",
                                f"systemctl enable --now code-editor@{code_editor_user}",
                                f"systemctl restart code-editor@{code_editor_user}",
                            ]
                        }
                    }
                ]
            }
        )

        # Lambda to run SSM doc on instance
        ssm_runner_role = iam.Role(self, "SSMRunnerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")]
        )
        ssm_runner_role.add_to_policy(iam.PolicyStatement(
            actions=["ssm:SendCommand"],
            resources=[
                f"arn:aws:ssm:{self.region}:{self.account}:document/*",
                f"arn:aws:ec2:{self.region}:{self.account}:instance/{code_editor_instance.instance_id}"
            ]
        ))
        ssm_runner_role.add_to_policy(iam.PolicyStatement(
            actions=["ssm:ListCommandInvocations", "ssm:GetCommandInvocation"],
            resources=["*"]
        ))

        run_ssm_fn = lambda_.Function(self, "RunSSMDocFn",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import boto3, json, urllib.request, time, logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
def send(event, context, status, data={}, reason=''):
    body = json.dumps({'Status': status, 'Reason': reason or f'See CW {context.log_stream_name}',
        'PhysicalResourceId': context.log_stream_name, 'StackId': event['StackId'],
        'RequestId': event['RequestId'], 'LogicalResourceId': event['LogicalResourceId'], 'Data': data})
    urllib.request.urlopen(urllib.request.Request(event['ResponseURL'], data=body.encode(), method='PUT', headers={'Content-Type': ''}))
def handler(event, context):
    if event['RequestType'] != 'Create':
        return send(event, context, 'SUCCESS')
    props = event['ResourceProperties']
    ssm = boto3.client('ssm')
    for attempt in range(5):
        try:
            resp = ssm.send_command(InstanceIds=[props['InstanceId']], DocumentName=props['DocumentName'],
                Parameters={'CodeEditorPassword': [props['Password']]}, CloudWatchOutputConfig={'CloudWatchOutputEnabled': True})
            return send(event, context, 'SUCCESS', {'CommandId': resp['Command']['CommandId']})
        except ssm.exceptions.InvalidInstanceId:
            logger.info(f'Instance not ready, attempt {attempt+1}')
            time.sleep(60)
    send(event, context, 'FAILED', reason='Instance not ready')
"""),
            timeout=Duration.seconds(600),
            role=ssm_runner_role,
            architecture=lambda_.Architecture.ARM_64
        )

        # Custom resource to get password from secret
        get_pwd_fn = lambda_.Function(self, "GetSecretPwdFn",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import boto3, json, urllib.request
def send(event, context, status, data={}, noEcho=False):
    body = json.dumps({'Status': status, 'Reason': f'See CW {context.log_stream_name}',
        'PhysicalResourceId': context.log_stream_name, 'StackId': event['StackId'],
        'RequestId': event['RequestId'], 'LogicalResourceId': event['LogicalResourceId'],
        'NoEcho': noEcho, 'Data': data})
    urllib.request.urlopen(urllib.request.Request(event['ResponseURL'], data=body.encode(), method='PUT', headers={'Content-Type': ''}))
def handler(event, context):
    if event['RequestType'] == 'Delete':
        return send(event, context, 'SUCCESS')
    secret = boto3.client('secretsmanager').get_secret_value(SecretId=event['ResourceProperties']['SecretArn'])
    send(event, context, 'SUCCESS', json.loads(secret['SecretString']), noEcho=True)
"""),
            timeout=Duration.seconds(10),
            architecture=lambda_.Architecture.ARM_64
        )
        code_editor_secret.grant_read(get_pwd_fn)

        secret_plaintext = CustomResource(self, "SecretPlaintext",
            service_token=get_pwd_fn.function_arn,
            properties={"SecretArn": code_editor_secret.secret_arn}
        )

        # Trigger SSM doc
        run_ssm = CustomResource(self, "RunCodeEditorSSMDoc",
            service_token=run_ssm_fn.function_arn,
            properties={
                "InstanceId": code_editor_instance.instance_id,
                "DocumentName": ssm_doc.ref,
                "Password": secret_plaintext.get_att_string("password")
            }
        )
        run_ssm.node.add_dependency(code_editor_instance)
        run_ssm.node.add_dependency(ssm_doc)

        # CloudFront distribution
        cf_distribution = cloudfront.Distribution(self, "CodeEditorCF",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.HttpOrigin(
                    code_editor_instance.instance_public_dns_name,
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY
                ),
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.ALLOW_ALL,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
            ),
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
        )

        CfnOutput(self, "CodeEditorURL",
            value=f"https://{cf_distribution.distribution_domain_name}/?folder={home_folder}&tkn=" + secret_plaintext.get_att_string("password")
        )

        # Grant Code Editor role EMR Serverless permissions
        code_editor_role.add_to_policy(iam.PolicyStatement(
            actions=["iam:PassRole"],
            resources=[emr_execution_role.role_arn],
            conditions={
                "StringEquals": {
                    "iam:PassedToService": "emr-serverless.amazonaws.com"
                }
            }
        ))
        code_editor_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "emr-serverless:GetApplication",
                "emr-serverless:ListApplications",
                "emr-serverless:StartApplication",
                "emr-serverless:StopApplication",
                "emr-serverless:StartJobRun",
                "emr-serverless:GetJobRun",
                "emr-serverless:ListJobRuns",
                "emr-serverless:CancelJobRun",
                "emr-serverless:AccessLivyEndpoints",
                "emr-serverless:GetDashboardForJobRun",
            ],
            resources=[f"arn:aws:emr-serverless:{self.region}:{self.account}:/applications/*"]
        ))

        # ============================================================
        # IAM Identity Center (SSO) + Q Developer Pro
        # ============================================================

        # SSO Instance
        sso_instance = sso.CfnInstance(self, "SSOInstance")

        # Lambda role for IDC setup
        idc_lambda_role = iam.Role(self, "IDCLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess"),
            ],
        )
        idc_lambda_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "sso:DescribeInstance", "sso:ListInstances",
                "identitystore:CreateGroup", "identitystore:CreateGroupMembership",
                "identitystore:CreateUser", "identitystore:ListUsers", "identitystore:ListGroups",
            ],
            resources=[
                sso_instance.attr_instance_arn,
                f"arn:aws:identitystore::{self.account}:identitystore/*",
                "arn:aws:identitystore:::*",
            ],
        ))

        # Lambda to create IDC user, group, Q Developer Pro profile
        idc_lambda = lambda_.Function(self, "IDCSetupLambda",
            runtime=lambda_.Runtime.PYTHON_3_10,
            handler="index.handler",
            timeout=Duration.minutes(5),
            role=idc_lambda_role,
            code=lambda_.Code.from_inline(open(
                os.path.join(os.path.dirname(__file__), "idc_setup_handler.py")
            ).read()),
        )

        # Custom resource to trigger IDC setup
        idc_setup = CustomResource(self, "IDCSetup",
            service_token=idc_lambda.function_arn,
            properties={
                "InstanceArn": sso_instance.attr_instance_arn,
                "IdentityStoreId": sso_instance.attr_identity_store_id,
            },
        )
        idc_setup.node.add_dependency(sso_instance)

        # Outputs
        CfnOutput(self, "IDCUsername", value="qdev")
        CfnOutput(self, "IDCUserEmail", value="qdev@example.com")
        CfnOutput(self, "IDCStartURL",
            value=idc_setup.get_att_string("StartURL"))
        CfnOutput(self, "IDCPassword",
            value=idc_setup.get_att_string("PasswordOTP"))
        CfnOutput(self, "IDCRegion", value="us-east-1")

        # ============================================================
        # Bedrock Model Access Activation
        # ============================================================

        bedrock_access_fn = lambda_.Function(self, "BedrockModelAccessFn",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            timeout=Duration.seconds(120),
            code=lambda_.Code.from_inline("""
import boto3, json, urllib.request, time
def send(event, ctx, status, data={}):
    body = json.dumps({"Status": status, "Reason": str(data), "PhysicalResourceId": ctx.log_stream_name,
        "StackId": event["StackId"], "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"], "Data": data}).encode()
    urllib.request.urlopen(urllib.request.Request(event["ResponseURL"], data=body, method="PUT", headers={"Content-Type": ""}))
def handler(event, ctx):
    if event["RequestType"] == "Delete": return send(event, ctx, "SUCCESS")
    try:
        client = boto3.client("bedrock", region_name=event["ResourceProperties"]["Region"])
        for m in event["ResourceProperties"]["ModelIds"]:
            try:
                client.put_foundation_model_entitlement(modelId=m)
                print(f"Enabled: {m}")
            except Exception as e: print(f"{m}: {e}")
        time.sleep(5)
        send(event, ctx, "SUCCESS")
    except Exception as e:
        print(e)
        send(event, ctx, "FAILED", {"Error": str(e)})
"""),
        )
        bedrock_access_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:PutFoundationModelEntitlement", "bedrock:GetFoundationModelAvailability"],
            resources=["*"],
        ))
        bedrock_access_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["aws-marketplace:ViewSubscriptions", "aws-marketplace:Subscribe"],
            resources=["*"],
        ))

        CustomResource(self, "BedrockModelAccess",
            service_token=bedrock_access_fn.function_arn,
            properties={
                "Region": self.region,
                "ModelIds": ["anthropic.claude-sonnet-4-20250514"],
            },
        )

