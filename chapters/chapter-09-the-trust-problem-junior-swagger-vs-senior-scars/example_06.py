def apply_ecs_scaling(cluster, service_name, new_memory):
    # Capture the current task definition before touching anything.
    current = ecs.describe_task_definition(taskDefinition=service_name)
    old_task_def_arn = current['taskDefinition']['taskDefinitionArn']

    # Register a new revision with the updated memory limit. ECS task
    # definitions are immutable, so a change always means a new revision.
    td = current['taskDefinition']
    new_revision = ecs.register_task_definition(
        family=td['family'],
        containerDefinitions=td['containerDefinitions'],
        cpu=td.get('cpu'),
        memory=str(new_memory),
        networkMode=td.get('networkMode'),
        requiresCompatibilities=td.get('requiresCompatibilities', []),
        executionRoleArn=td.get('executionRoleArn'),
        taskRoleArn=td.get('taskRoleArn'),
    )

    ecs.update_service(
        cluster=cluster,
        service=service_name,
        taskDefinition=new_revision['taskDefinition']['taskDefinitionArn'],
    )

    def rollback():
        # Rolling back is just pointing the service at the old revision.
        ecs.update_service(
            cluster=cluster,
            service=service_name,
            taskDefinition=old_task_def_arn,
        )

    return {'applied': True, 'rollback': rollback}
