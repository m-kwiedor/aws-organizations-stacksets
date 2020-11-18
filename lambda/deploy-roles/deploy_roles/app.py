from __future__ import print_function

import botocore
import boto3
import json
import logging
import os
import shutil
import traceback
import uuid
import yaml
import zipfile

from boto3.session import Session
from cfn_tools import CfnYamlLoader
from cfn_tools import CfnYamlDumper
from cfn_tools import ODict

code_pipeline = boto3.client('codepipeline')
sts_client = boto3.client('sts')
accountid = sts_client.get_caller_identity()["Account"]

region = os.environ['AWS_REGION']

log = logging.getLogger()
log.setLevel(logging.INFO)

BASEPATH = '/tmp/github/'
STACKSETSUFIX = 'role-policies-'

def handler(event, context):
    print(event)
    try:
        job_id = event['CodePipeline.job']['id']
        job_data = event['CodePipeline.job']['data']
        artifact_data = job_data['inputArtifacts'][0]
        organizations = setup_organizations_client()
        
        extract_codepipeline_artifact(artifact_data)
        get_organizations_unit_ids(organizations.list_roots()['Roots'][0]['Id'], '')
        
        #cleanup_tmp_directory()
        #put_job_success(job_id, "Success")


    except Exception as e:
        log.error('Function failed due to exception.')
        log.error(e)
        traceback.print_exc()
        #put_job_failure(job_id, 'Function exception: ' + str(e))


def get_organizations_unit_ids(parent_id, parent_name):
    full_result = []
    
    organizations = setup_organizations_client()
    
    paginator = organizations.get_paginator('list_children')
    iterator = paginator.paginate(
        ParentId=parent_id,
        ChildType='ORGANIZATIONAL_UNIT')
        
    for page in iterator:
        for organization_unit in page['Children']:
            organization_unit_details = organizations.describe_organizational_unit(OrganizationalUnitId=organization_unit['Id'])
            organization_name_path = os.path.join(parent_name, organization_unit_details['OrganizationalUnit']['Name'])

            create_stacksets(organization_unit['Id'], organization_name_path)
            get_organizations_unit_ids(organization_unit['Id'], organization_name_path)
            

def extract_codepipeline_artifact(artifact):
    s3 = setup_s3_client()
    bucket = artifact['location']['s3Location']['bucketName']
    key = artifact['location']['s3Location']['objectKey']
    tmp_file = '/tmp/' + str(uuid.uuid4())
    s3.download_file(bucket, key, tmp_file)
    with zipfile.ZipFile(tmp_file, 'r') as zip:
        zip.extractall(BASEPATH)
        log.debug('Extract Complete')

def create_stacksets(organization_unit_id, organization_name_path):
    resources = get_resources(organization_unit_id, organization_name_path)
    
    if resources is None:
        return
    
    stackset_template = yaml.dump(resources, Dumper=CfnYamlDumper, default_flow_style=False, allow_unicode=True)
    log.info('\n' + stackset_template)

    cloudformation = setup_cloudformation_client()

    exists = stackset_exists(STACKSETSUFIX + organization_unit_id)

    if exists:
        log.info('Stackset found')
        update_stackset(organization_unit_id, organization_name_path, stackset_template)
    else:
        log.error('Stackset not found')
        create_stackset(organization_unit_id, organization_name_path, stackset_template)


def create_stackset(organization_unit_id, organization_name_path, stackset_template):
    log.info('Create Stackset for OU %s | %s', organization_unit_id, organization_name_path)

    cloudformation = setup_cloudformation_client()

    responseCreate = cloudformation.create_stack_set(
        StackSetName = STACKSETSUFIX + organization_unit_id,
        Description = 'Role Policy Stack Set for OU ' + organization_name_path,
        TemplateBody = stackset_template,
        Capabilities = [
            'CAPABILITY_IAM',
            'CAPABILITY_NAMED_IAM'
        ],
        Tags = [
            {
                'Key': 'OU_ID',
                'Value': organization_unit_id
            }, {
                'Key': 'OU',
                'Value': organization_name_path
            }
        ],
        PermissionModel = 'SERVICE_MANAGED',
        AutoDeployment = {
            'Enabled': True,
            'RetainStacksOnAccountRemoval': False
        }
    )
    
    log.info(responseCreate)
    
    responseUpdate = cloudformation.create_stack_instances(
        StackSetName = STACKSETSUFIX + organization_unit_id,
        DeploymentTargets = {
            'Accounts': [],
            'OrganizationalUnitIds': [
                organization_unit_id
            ]
        },
        Regions = [
            region
        ],
        OperationPreferences = {
            'FailureToleranceCount': 0,
            'MaxConcurrentCount': 1
        }
    )
    
    log.info(responseUpdate)
    

def update_stackset(organization_unit_id, organization_name_path, stackset_template):
    log.info('Update Stackset for OU %s | %s', organization_unit_id, organization_name_path)

    cloudformation = setup_cloudformation_client()
    
    responseStackset = cloudformation.update_stack_set(
        StackSetName = STACKSETSUFIX + organization_unit_id,
        Description = 'Role Policy Stack Set for OU ' + organization_name_path,
        TemplateBody = stackset_template,
        UsePreviousTemplate = False,
        Capabilities = [
            'CAPABILITY_IAM',
            'CAPABILITY_NAMED_IAM'
        ],
        Tags = [
            {
                'Key': 'OU_ID',
                'Value': organization_unit_id
            }, {
                'Key': 'OU',
                'Value': organization_name_path
            }
        ],
        OperationPreferences = {
            'FailureToleranceCount': 0,
            'MaxConcurrentCount': 1
        },
        DeploymentTargets = {
            'OrganizationalUnitIds': [
                organization_unit_id
            ]
        },
        PermissionModel = 'SERVICE_MANAGED',
        AutoDeployment = {
            'Enabled': True,
            'RetainStacksOnAccountRemoval': False
        },
        Regions = [
            region
        ]
    )

def stackset_exists(stackset_name):
    cloudformation = setup_cloudformation_client()
    
    paginator = cloudformation.get_paginator('list_stack_sets')
    iterator = paginator.paginate(
        Status='ACTIVE')
        
    for page in iterator:
        for stackset in page['Summaries']:
            log.info(stackset)
            if stackset['StackSetName'] == stackset_name:
                return True

    return False

def get_resources(organization_unit_id, organization_name_path):
    file_path = os.path.join(BASEPATH, organization_name_path)
    
    if not os.path.exists(file_path):
        log.debug('No directory found for OU %s', organization_name_path)
        return None
    
    s3 = setup_s3_client()
    resources = ODict()
    resources['Resources'] = ODict()

    log.info('Processing Directory for OU %s', organization_name_path)
    
    # First find all YAML Files
    for fsObject in os.listdir(file_path):
        fsObjectAbsPath = os.path.abspath(os.path.join(file_path, fsObject))

        if os.path.isfile(fsObjectAbsPath):
            filename, file_extension = os.path.splitext(fsObjectAbsPath)

            if file_extension.lower() == '.yaml' or file_extension.lower() == '.yml':
                log.info('Processing YAML File %s', fsObjectAbsPath)
                yaml_object = load_yaml(fsObjectAbsPath)
                
                if yaml_object is None:
                    continue
                
                try:
                    resources['Resources'].update(yaml_object['Resources'])
                except:
                    log.debug('YAML File %s has no Resources', fsObjectAbsPath)

    if len(resources['Resources']) == 0:
        return None
    else:
        return(resources)                

def load_yaml(file):
    with open(file, 'r') as stream:
        try:
            yaml_object = yaml.load(stream, Loader=CfnYamlLoader)
            return yaml_object
        except yaml.YAMLError as exc:
            log.error(exc)
            return None
            
def cleanup_tmp_directory():
    shutil.rmtree(BASEPATH)

def setup_s3_client():
    """
    :return: Boto3 S3 session. Uses IAM credentials
    """
    session = Session()
    return session.client('s3', config=botocore.client.Config(signature_version='s3v4'))
    
def setup_organizations_client():
    """
    :return: Boto3 Organizations session. Uses IAM credentials
    """
    session = Session()
    return session.client('organizations', config=botocore.client.Config(signature_version='s3v4'))

def setup_cloudformation_client():
    """
    :return: Boto3 Organizations session. Uses IAM credentials
    """
    session = Session()
    return session.client('cloudformation', config=botocore.client.Config(signature_version='s3v4'))


def put_job_success(job, message):
    """Notify CodePipeline of a successful job

    Args:
        job: The CodePipeline job ID
        message: A message to be logged relating to the job status

    Raises:
        Exception: Any exception thrown by .put_job_success_result()

    """
    log.debug('Putting job success')
    log.debug(message)
    code_pipeline.put_job_success_result(jobId=job)


def put_job_failure(job, message):
    """Notify CodePipeline of a failed job

    Args:
        job: The CodePipeline job ID
        message: A message to be logged relating to the job status

    Raises:
        Exception: Any exception thrown by .put_job_failure_result()

    """
    log.debug('Putting job failure')
    log.debug(message)
    code_pipeline.put_job_failure_result(jobId=job, failureDetails={'message': message, 'type': 'JobFailed'})
