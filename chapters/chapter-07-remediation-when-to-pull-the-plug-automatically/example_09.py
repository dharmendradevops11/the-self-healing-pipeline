def remediate_unresponsive(service_name, platform):
    if platform == "ecs":
        ecs.update_service(cluster=SERVICE_CLUSTERS[service_name],
                           service=service_name, forceNewDeployment=True)
    elif platform == "ec2":
        instance_id = get_instance_id(service_name)
        ec2.reboot_instances(InstanceIds=[instance_id])
    log_remediation(service_name, "restart", platform)
