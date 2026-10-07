import boto3
import time

ecs = boto3.client("ecs")
cloudwatch = boto3.client("cloudwatch")

SAFE_SERVICES = {
    "checkout-api": {"cluster": "prod-cluster", "min_healthy_pct": 50},
    "auth-service": {"cluster": "prod-cluster", "min_healthy_pct": 50},
}

def handler(event, context):
    alarm_name = event["detail"]["alarmName"]
    service_name = extract_service_from_alarm(alarm_name)

    if service_name not in SAFE_SERVICES:
        log_and_notify(f"No automation defined for {service_name}, escalating to human")
        return {"action": "escalated", "reason": "not_in_allowlist"}

    cfg = SAFE_SERVICES[service_name]

    response = ecs.update_service(
        cluster=cfg["cluster"],
        service=service_name,
        forceNewDeployment=True,
    )

    log_remediation_event(
        service=service_name,
        action="force_new_deployment",
        trigger_alarm=alarm_name,
        timestamp=time.time(),
    )

    return {"action": "restarted", "service": service_name}
