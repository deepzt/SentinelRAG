# AWS Incident Response Runbook

**Department:** Engineering  
**Classification:** Internal  
**Version:** v2 | **Last Updated:** 2026-03  
**Owner:** Platform Team  
**Access:** Engineers and above

---

## Overview

This runbook covers the end-to-end incident response process for AWS infrastructure failures, with specific focus on ECS service outages, rollback procedures, and post-incident review requirements. All on-call engineers must be familiar with this document.

Incidents are classified by severity (SEV1–SEV4). SEV1 and SEV2 require immediate on-call response. SEV3 and SEV4 can be addressed in the next business day.

---

## Severity Definitions

- **SEV1** — Full production outage. Customer-facing APIs down or data loss risk. Response time: < 15 minutes.
- **SEV2** — Partial outage or severe degradation. >20% of requests failing. Response time: < 30 minutes.
- **SEV3** — Non-critical degradation. <20% of requests failing. No data loss risk. Response time: < 4 hours.
- **SEV4** — Minor issue. No user impact. Response time: next business day.

---

## Initial Response Checklist

When paged, complete these steps in order before attempting any remediation.

1. **Acknowledge the alert** in PagerDuty. Do not let it escalate.
2. **Join the incident Slack channel** `#incident-response`. Post: "I'm responding to [ALERT_NAME]."
3. **Verify the alert** — confirm the issue is real and not a monitoring false positive.
   - Check CloudWatch dashboards for the affected service.
   - Verify error rates in Datadog APM.
4. **Declare severity** in Slack: `!incident declare SEV[1-4] <brief description>`.
5. **Assign roles**: Incident Commander (IC), Communications Lead, Technical Lead.
6. **Start the incident timer** — note start time in the incident channel.

---

## ECS Service Rollback Procedure

Use this procedure when a new deployment causes a SEV1 or SEV2 incident.

### Step 1 — Identify the failing deployment

```bash
# List recent task definition revisions
aws ecs describe-services \
  --cluster prod-cluster \
  --services <SERVICE_NAME> \
  --query 'services[0].deployments'
```

Note the `taskDefinition` ARN of the current (failing) revision and the previous (stable) revision.

### Step 2 — Force a rollback to the previous revision

```bash
# Roll back to the last known-good task definition
aws ecs update-service \
  --cluster prod-cluster \
  --service <SERVICE_NAME> \
  --task-definition <PREVIOUS_TASK_DEF_ARN> \
  --force-new-deployment
```

### Step 3 — Monitor rollback progress

```bash
# Watch deployment status until only 1 deployment remains
watch -n 5 'aws ecs describe-services \
  --cluster prod-cluster \
  --services <SERVICE_NAME> \
  --query "services[0].deployments[*].{Status:status,Running:runningCount,Desired:desiredCount}"'
```

Rollback is complete when:
- Exactly 1 deployment is listed with status `PRIMARY`
- `runningCount` equals `desiredCount`
- CloudWatch error rates return to baseline

### Step 4 — Verify health

```bash
# Check target group health
aws elbv2 describe-target-health \
  --target-group-arn <TARGET_GROUP_ARN> \
  --query 'TargetHealthDescriptions[*].TargetHealth'
```

All targets should be `healthy` within 3 minutes of rollback completion.

---

## RDS Failover Procedure

If the incident involves database connectivity:

### Step 1 — Check RDS cluster status

```bash
aws rds describe-db-clusters \
  --db-cluster-identifier prod-postgres-cluster \
  --query 'DBClusters[0].{Status:Status,Writer:DBClusterMembers[?IsClusterWriter]}'
```

### Step 2 — Initiate failover if writer is unhealthy

```bash
aws rds failover-db-cluster \
  --db-cluster-identifier prod-postgres-cluster \
  --target-db-instance-identifier prod-postgres-replica-1
```

Failover typically completes in 60–120 seconds. DNS is updated automatically — no application changes needed.

---

## SQS Queue Backlog Procedure

When a processing service falls behind and queues grow:

```bash
# Check queue depth
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT/QUEUE_NAME \
  --attribute-names ApproximateNumberOfMessages

# Scale up the consumer ECS service temporarily
aws ecs update-service \
  --cluster prod-cluster \
  --service queue-consumer-service \
  --desired-count 10
```

Return desired count to normal after queue drains.

---

## Escalation Path

| Timeout | Action |
|---------|--------|
| 15 min  | Page secondary on-call engineer |
| 30 min  | Page engineering manager |
| 1 hour  | Page VP Engineering + CTO |
| 2 hours | External status page update required |

---

## Post-Incident Review

A Post-Incident Review (PIR) is required for all SEV1 and SEV2 incidents.

### Timeline
- PIR must be completed within **48 hours** of incident resolution.
- Draft submitted to `#post-incident-reviews` Slack channel.
- Review meeting scheduled within **5 business days**.

### PIR Template Sections
1. **Incident Summary** — what happened, impact, duration
2. **Timeline** — chronological log of events with timestamps
3. **Root Cause Analysis** — technical root cause (5 Whys)
4. **Contributing Factors** — monitoring gaps, process failures
5. **Action Items** — owners, due dates (tracked in Jira)
6. **Detection Improvements** — how to catch this earlier next time
7. **Prevention Measures** — how to stop this from recurring

---

## Useful CloudWatch Dashboards

- **API Health:** `prod-api-health`
- **ECS Services:** `prod-ecs-overview`
- **RDS Performance:** `prod-rds-metrics`
- **ALB Metrics:** `prod-alb-dashboard`

---

## Contact Reference

| Role | Contact |
|------|---------|
| On-call rotation | PagerDuty service: `platform-oncall` |
| Incident Slack | `#incident-response` |
| AWS Support | Case via console (Business support plan) |
| Database team | `@database-oncall` in Slack |
