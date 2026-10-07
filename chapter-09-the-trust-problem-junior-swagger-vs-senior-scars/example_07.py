def record_outcome(execution_id, hypothesis, confidence, human_verdict, fix_worked):
    dynamodb.put_item(
        TableName='agent-trust-ledger',
        Item={
            'execution_id': execution_id,
            'hypothesis': hypothesis,
            'confidence_score': confidence,
            'human_verdict': human_verdict,    # approved / rejected / modified
            'fix_worked': fix_worked,          # verified post-deployment
            'timestamp': datetime.utcnow().isoformat()
        }
    )
