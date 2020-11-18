#!/bin/bash

cd deploy_roles
pip install -r requirements.txt --target ./package
cd package
zip -r deployment-package.zip ./*
cd ..
zip -g package/deployment-package.zip *.py
zip -g package/deployment-package.zip cfn_tools/*
aws s3 cp package/deployment-package.zip s3://$1/role-policy-lambda/deployment-package.zip
rm -rf package
cd ..
