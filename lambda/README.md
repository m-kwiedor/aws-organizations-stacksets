# security-aod
Security AOD Artifact

Deploy Lambda:

pip install --target ./package -r requirements.txt
cd package
zip -r deployment-package.zip ./*
cd ..
zip -g package/deployment-package.zip app.py


aws lambda update-function-code --function-name role-policies-sync-lambda --zip-file fileb://package/deployment-package.zip --profile security_aod

aws cloudformation package --template-file deploy-roles.yaml --s3-bucket <S3Bucket> --s3-prefix role-policies-sync-lambda --output-template-file deploy-roles-packed.yaml --profile security_aod
aws cloudformation deploy --template-file /Users/kwiedorm/Code/Artifacts/security-aod/security-aod/lambda/deploy-roles/deploy-roles-packed.yaml --stack-name role-policies-sync-lambda --capabilities CAPABILITY_NAMED_IAM --profile security_aod


pip install -r requirements.txt --target ./package
cd package
zip -r deployment-package.zip ./*
cd ..
zip -g package/deployment-package.zip *.py
zip -g package/deployment-package.zip cfn_tools/*
