# Baked into the container image, not into the remediation code —
# this is what makes the kill -USR2 below actually do anything:
#   CMD ["node", "--heapsnapshot-signal=SIGUSR2", "server.js"]

def remediate_memory_leak(service_name, pod_name):
    dump_path = f"s3://heap-dumps/{service_name}/{pod_name}-{int(time.time())}.heapsnapshot"
    # The process is already listening for SIGUSR2 because of the startup flag
    # above, so this signal alone triggers a snapshot — no restart required.
    kubectl_exec(pod_name, "kill -USR2 1")
    wait_for_heapsnapshot_file(pod_name, timeout_s=60)
    upload_heap_dump(pod_name, dump_path)
    kubectl_delete_pod(pod_name, grace_period=30)
    log_remediation(service_name, "graceful_restart_with_dump", dump_path)
