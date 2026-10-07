# What pipeline ML actually looks like in practice
def predict_deployment_success(deployment_metadata):
    if deployment_metadata.get('day_of_week') == 'Friday':
        return {'success_probability': 0.2, 'reason': 'historical_pattern'}
    if deployment_metadata.get('files_changed') > 100:
        return {'success_probability': 0.5, 'reason': 'large_changeset'}
    return {'success_probability': 0.7, 'reason': 'no_strong_signal'}
