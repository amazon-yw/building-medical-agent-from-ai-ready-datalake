#!/usr/bin/env python3
import os
import aws_cdk as cdk
from cdk.fhir_data_stack import FhirDataStack

app = cdk.App()
FhirDataStack(app, "FhirDataStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION', 'us-east-1')
    )
)

app.synth()
