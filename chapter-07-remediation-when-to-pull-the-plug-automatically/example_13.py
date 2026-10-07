def remediate_failed_deployment(service_name):
    last_good = get_last_known_good_version(service_name)
    if service_has_feature_flag(service_name):
        toggle_flag(service_name, enabled=False)
    else:
        ecs.update_service(cluster=SERVICE_CLUSTERS[service_name],
                           service=service_name,
                           taskDefinition=last_good.task_def_arn)
    log_remediation(service_name, "rollback", last_good.version)
