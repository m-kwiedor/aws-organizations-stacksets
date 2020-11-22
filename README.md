# Deploy CI/CD Pipeline Artefact



## Prerequisite

* At minimum 2 AWS accounts

Role Policy CI/CD Pipeline in Organizations

What problem does this artefact solve?

Customers who cannot use an AWS SSO, but have several accounts under one AWS Organization, build their own solutions by choosing one account as central login account, which contains the corresponding IAM users or IAM Federation with an AD. 
This account is then used to connect to other accounts via an assume role. For this to be possible, roles must be present in the accounts and must also be kept synchronous (via Organization Units). 
However, most companies fail because although CloudFormation or Terraform is ideally used to create the roles, they are manually deployed to the accounts, especially if they have hundreds of accounts, mostly running out of sync by deployment of new and changed role over their Organization after some months. 
This is where the CI/CD pipeline comes in, which allows the OU structure to be easily mapped in the code revision tool of choice and CloudFormation roles and policies to be stored there, which are automatically changed in the accounts when changes are made.


What are the assumptions / prerequisites to run deployment

You should have an Master Account in place, which has enabled AWS Organization and Trusted Relationship with CloudFormation Stacksets. 
To test the CI/CD Pipeline you need a GitHub Account to store the Roles/Policies and create a Token that Codepipeline GitHub Connector could access your GitHub. This is described in the manual as well. To use the CI/CD Pipeline with other Sources (like S3, Codecommit etc.) the source connector at Codepipeline has to be changed.
How to do this is described in the manual, all other infrastructure like S3 Buckets, Codepipeline and Lambda got deployed through CloudFormation scripts.

What Resources will be created?

-	S3 Bucket and Policy
-	Codepipeline
-	Lambda
-	Role and Policies for Codepipeline and Lambda execution
-	Stacksets

### What is the high level workflow of the resources of the artefact

![flow-diagram](docs/images/flow-diagram.png)

What is the usage pattern for this Artefact in the context of an AWS Organization

Multi Account setup, as it is for IAM region doesn’t take care

- What implicit / explicit parameter settings do I have to consider before stack deploy
	- Can the stack be deployed as-is without any adjustments?
	- Example: I need to setup proper IAM roles that will be useful for my org
- What is not supported yet / Ideas for improvement?
- Caveats:
	- Warn about things that might throw off a customer
- Open Known Issues:
	- anything not support?
- How do I deploy the stack?

