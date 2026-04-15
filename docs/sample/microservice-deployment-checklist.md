# Microservice Deployment Checklist

**Department:** Engineering  
**Classification:** Internal  
**Version:** v1 | **Last Updated:** 2026-02  
**Owner:** Platform Team  
**Access:** Engineers

---

## Overview

This checklist must be completed for every production deployment of a microservice. Items marked **BLOCKING** must be completed before proceeding. Skipping blocking items requires explicit sign-off from the engineering manager.

Estimated time: 30–60 minutes for a standard deployment.

---

## Pre-Deployment Checklist

### Code Readiness

- [ ] **BLOCKING** — All CI checks pass on the release branch (build, unit tests, integration tests, linting)
- [ ] **BLOCKING** — Code review approved by at least 2 engineers
- [ ] **BLOCKING** — No open SEV1/SEV2 incidents in the service's domain
- [ ] Security scan (Snyk/Dependabot) shows no critical vulnerabilities in new dependencies
- [ ] CHANGELOG updated with this release's changes
- [ ] API version bumped if breaking changes are included
- [ ] Feature flags configured for any gradual rollout

### Environment Checks

- [ ] **BLOCKING** — Staging deployment succeeded and has been running for >2 hours without errors
- [ ] **BLOCKING** — Smoke tests pass in staging (automated test suite + manual curl checks)
- [ ] Database migrations tested in staging (if applicable)
- [ ] New environment variables added to AWS Parameter Store / Secrets Manager in prod
- [ ] Dependent services verified compatible with new version
- [ ] Rollback plan documented (previous task definition ARN noted)

### Monitoring Readiness

- [ ] New metrics/logs included in CloudWatch dashboard
- [ ] Alert thresholds set for new endpoints or business metrics
- [ ] On-call engineer aware of the deployment and monitoring it

---

## Deployment Execution

### Step 1 — Build and push Docker image

```bash
# Build with build args
docker build \
  --build-arg BUILD_NUMBER=$BUILD_NUMBER \
  --build-arg GIT_SHA=$(git rev-parse --short HEAD) \
  -t $ECR_REGISTRY/$SERVICE_NAME:$VERSION .

# Push to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $ECR_REGISTRY

docker push $ECR_REGISTRY/$SERVICE_NAME:$VERSION
```

### Step 2 — Run database migrations (if applicable)

```bash
# Run migrations as a one-off ECS task before updating the service
aws ecs run-task \
  --cluster prod-cluster \
  --task-definition $SERVICE_NAME-migrations:latest \
  --overrides '{"containerOverrides":[{"name":"app","command":["alembic","upgrade","head"]}]}'
```

Wait for the migration task to complete successfully before proceeding.

### Step 3 — Update ECS service

```bash
# Register new task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Update service
aws ecs update-service \
  --cluster prod-cluster \
  --service $SERVICE_NAME \
  --task-definition $SERVICE_NAME:$NEW_REVISION \
  --deployment-configuration "minimumHealthyPercent=100,maximumPercent=200"
```

### Step 4 — Monitor deployment

Watch for:
- Deployment status: `PRIMARY` with all tasks running
- Error rates in CloudWatch/Datadog: no spike above baseline
- Response latency P50/P95: stable or improving
- Memory/CPU utilization: within expected range

---

## Post-Deployment Checklist

### Immediate (within 30 minutes)

- [ ] **BLOCKING** — Service health endpoint (`GET /health`) returns 200 on all instances
- [ ] **BLOCKING** — Error rate in production is at or below pre-deployment baseline
- [ ] Smoke tests pass against production
- [ ] No unexpected error patterns in CloudWatch Logs Insights
- [ ] New deployment visible in Datadog APM (correct service version tag)

### Within 2 hours

- [ ] Business metrics are stable (conversion rates, job throughput, etc.)
- [ ] No memory leaks detected (memory usage stable over 30 min)
- [ ] Slack `#deployments` channel updated with deployment status
- [ ] JIRA deployment ticket closed and linked to this checklist

---

## Rollback Criteria

Immediately initiate rollback (refer to `aws-incident-runbook.md`) if:
- Error rate exceeds 5% for more than 2 minutes
- P95 response latency more than doubles versus baseline
- Any SEV1/SEV2 alert fires within 30 minutes of deployment
- Memory usage trends upward continuously for 10+ minutes

---

## Rollback Execution (Quick Reference)

```bash
# Roll back to previous task definition
PREVIOUS_TASK_DEF=$(aws ecs describe-services \
  --cluster prod-cluster \
  --services $SERVICE_NAME \
  --query 'services[0].deployments[-1].taskDefinition' \
  --output text)

aws ecs update-service \
  --cluster prod-cluster \
  --service $SERVICE_NAME \
  --task-definition $PREVIOUS_TASK_DEF \
  --force-new-deployment
```

---

## Sign-off

| Role | Name | Time |
|------|------|------|
| Deploying Engineer | ___________ | _______ |
| On-call Engineer (awareness) | ___________ | _______ |
| Engineering Manager (if BLOCKING items skipped) | ___________ | _______ |
