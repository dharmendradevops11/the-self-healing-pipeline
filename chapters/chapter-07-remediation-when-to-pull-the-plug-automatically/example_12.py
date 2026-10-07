def remediate_pool_exhaustion(service_name, dry_run=True):
    # Idempotency & precondition check: prevent rapid consecutive resizes
    if was_resized_in_last_30_minutes(service_name):
        logger.warning(f"Connection pool for {service_name} was already resized recently. Skipping.")
        return RemediationResult.SKIPPED

    config = get_pool_config(service_name)
    current_size = config["max_connections"]

    if dry_run:
        logger.info(f"[Dry-run] Would reset connection pool and resize from {current_size} to {current_size + 10}")
        return RemediationResult.SKIPPED

    # Execution phase with backup of state
    reset_connection_pool(service_name)
    if current_size < POOL_SIZE_CEILING[service_name]:
        new_size = current_size + 10
        resize_pool(service_name, new_max=new_size)

        # Rollback behavior: if database health drops or fails check, roll back the resize
        if not verify_database_health(service_name):
            logger.error(f"Post-remediation health check failed. Rolling back pool size to {current_size}")
            resize_pool(service_name, new_max=current_size)
            return RemediationResult.FAILED

    log_remediation(service_name, "pool_reset_and_resize", current_size)
    return RemediationResult.SUCCESS
