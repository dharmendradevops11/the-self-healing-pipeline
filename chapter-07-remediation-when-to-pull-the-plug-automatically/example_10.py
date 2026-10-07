def remediate_disk_exhaustion(instance_id, threshold_pct=85, dry_run=True):
    # Precondition: check if disk usage actually exceeds threshold
    current_usage = get_disk_usage(instance_id)
    if current_usage < threshold_pct:
        logger.info(f"Precondition not met: Disk usage ({current_usage}%) under threshold ({threshold_pct}%)")
        return RemediationResult.SKIPPED

    # Exclusion rules: protect critical system/systemd mount directories
    commands = [
        "find /var/log -name '*.log' -mtime +7 -type f -delete" if not dry_run else "find /var/log -name '*.log' -mtime +7 -type f",
        "find /tmp -mtime +1 -type f -not -path '/tmp/systemd*' -delete" if not dry_run else "find /tmp -mtime +1 -type f -not -path '/tmp/systemd*'",
        "docker system prune -f --filter until=48h" if not dry_run else "echo '[dry-run] docker system prune'"
    ]

    ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands},
    )
    log_remediation(instance_id, "disk_cleanup", threshold_pct, dry_run=dry_run)
    return RemediationResult.SUCCESS
