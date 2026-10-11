class AgentAuditLogger:
    def __init__(self, s3_client, bucket, execution_id):
        self.s3 = s3_client
        self.bucket = bucket
        self.execution_id = execution_id
        self.step_counter = 0

    def log_reasoning_step(self, step_type, input_data, output_data,
                           tool_calls=None, confidence=None):
        self.step_counter += 1
        audit_record = {
            'execution_id': self.execution_id,
            'step_number': self.step_counter,
            'timestamp': datetime.utcnow().isoformat(),
            'step_type': step_type,
            'input': input_data,
            'output': output_data,
            'tool_calls': tool_calls or [],
            'confidence_score': confidence
        }
        key = f"audit/{self.execution_id}/step_{self.step_counter:03d}_{step_type}.json"
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(audit_record, indent=2),
            ContentType='application/json'
        )
