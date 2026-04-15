# AWS Deployment Standard Operating Procedure

**Department:** Engineering  
**Classification:** Internal  
**Version:** v1 | **Last Updated:** 2026-01  
**Owner:** Platform Team  
**Access:** Engineers

---

## Overview

This SOP defines the standard process for deploying application changes to AWS production infrastructure. It covers Terraform infrastructure changes, ECS service updates, and Lambda function deployments. All deployments must follow this procedure.

---

## Prerequisites

Before executing any production deployment:

1. **AWS CLI configured** with appropriate IAM role (`deploy-role` in prod account)
2. **Terraform** v1.7+ installed locally or via CI runner
3. **GitHub Actions** workflow configured for the service
4. **AWS SSO session active**: `aws sso login --profile prod`
5. **Feature branch merged** to `main` and release tag created

---

## Infrastructure Deployments (Terraform)

### Step 1 — Plan review

```bash
cd terraform/environments/prod

terraform init -upgrade
terraform plan -out=plan.tfplan -var-file=prod.tfvars
```

Review the plan output carefully:
- Confirm resources being created, modified, and destroyed
- Any resource being **destroyed** requires engineering manager approval
- RDS, ECS clusters, VPC changes require 48-hour change window

### Step 2 — Peer review

Submit the `terraform plan` output as a comment in the relevant GitHub PR. A second engineer must review and approve before applying.

### Step 3 — Apply

```bash
terraform apply plan.tfplan
```

Monitor apply output for errors. If apply fails partway through:
1. Do NOT run `terraform destroy`
2. Check which resources were created successfully
3. Fix the error and re-run `terraform apply` — Terraform is idempotent

### Step 4 — State backup

After successful apply:
```bash
terraform state push  # or verify remote backend (S3 + DynamoDB lock)
```

---

## ECS Service Deployments

### Blue/Green Deployment (Recommended)

Use CodeDeploy with ECS blue/green for zero-downtime deployments of critical services.

**appspec.yml structure:**
```yaml
version: 0.0
Resources:
  - TargetService:
      Type: AWS::ECS::Service
      Properties:
        TaskDefinition: "<TASK_DEFINITION_ARN>"
        LoadBalancerInfo:
          ContainerName: "app"
          ContainerPort: 8000
Hooks:
  - BeforeAllowTraffic: "validate-deployment-lambda"
  - AfterAllowTraffic: "post-deploy-smoke-test-lambda"
```

**Deployment steps:**
1. Push new task definition to ECR
2. Create new ECS task definition revision
3. Trigger CodeDeploy deployment: the new task set receives 10% traffic for 5 minutes
4. If health checks pass, traffic shifts 100%
5. Old task set is terminated after 1 hour

### Rolling Deployment (Non-critical services)

```bash
aws ecs update-service \
  --cluster prod-cluster \
  --service $SERVICE_NAME \
  --task-definition $SERVICE_NAME:$NEW_REVISION \
  --deployment-configuration \
    "minimumHealthyPercent=50,maximumPercent=200"
```

---

## Lambda Deployments

### Direct Update

```bash
# Package and deploy
zip -r function.zip . -x "*.git*" -x "__pycache__/*"

aws lambda update-function-code \
  --function-name $FUNCTION_NAME \
  --zip-file fileb://function.zip \
  --region us-east-1
```

### Alias-based (production Lambda)

```bash
# Publish a new version
VERSION=$(aws lambda publish-version \
  --function-name $FUNCTION_NAME \
  --description "$(git log -1 --oneline)" \
  --query Version --output text)

# Shift alias traffic (10% canary for 15 minutes)
aws lambda update-alias \
  --function-name $FUNCTION_NAME \
  --name prod \
  --routing-config "AdditionalVersionWeights={$VERSION=0.1}"

# After validation, shift 100%
aws lambda update-alias \
  --function-name $FUNCTION_NAME \
  --name prod \
  --function-version $VERSION \
  --routing-config "AdditionalVersionWeights={}"
```

---

## Environment Variable Management

**All secrets must be stored in AWS Secrets Manager.** Never hardcode secrets in task definitions, Lambda env vars, or source code.

### Adding a new secret

```bash
aws secretsmanager create-secret \
  --name "prod/$SERVICE_NAME/$SECRET_NAME" \
  --secret-string "$SECRET_VALUE" \
  --region us-east-1
```

Reference in task definition:
```json
{
  "secrets": [
    {
      "name": "DATABASE_PASSWORD",
      "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:prod/service/db-password"
    }
  ]
}
```

### Rotating a secret

1. Create new secret version in Secrets Manager
2. Update ECS task definition with new secret ARN (or same ARN — ECS fetches at task start)
3. Force new deployment to pick up rotated credential
4. Verify old secret version can be deleted after 24 hours

---

## Change Management

| Change Type | Approval Required | Change Window |
|-------------|------------------|---------------|
| Application code update | 1 engineer review | Anytime (business hours) |
| Infrastructure change (non-destructive) | 2 engineer reviews | Tue/Thu 10:00–14:00 UTC |
| Database schema change | Engineering manager | Tue/Thu 10:00–14:00 UTC |
| Infrastructure deletion | Engineering manager + VPE | Pre-scheduled, Tue only |
| VPC / IAM changes | Security team review | Pre-scheduled, Tue only |

All changes must be tracked in JIRA under project `INFRA`.
