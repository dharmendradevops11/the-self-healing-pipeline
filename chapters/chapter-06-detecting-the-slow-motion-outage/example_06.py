import pandas as pd

def calculate_flakiness_scores(test_runs, window_size=50):
    """
    test_runs: list of dicts with 'test_name', 'timestamp', 'passed' (bool)
    Returns: dict of test_name -> flakiness_score
    """
    df = pd.DataFrame(test_runs).sort_values('timestamp')
    scores = {}

    for test_name in df['test_name'].unique():
        test_data = df[df['test_name'] == test_name].tail(window_size)
        if len(test_data) < 10:
            continue

        pass_rate = test_data['passed'].mean()
        # Flakiness is highest near 0.5, lowest at the extremes
        flakiness = 0.0 if pass_rate in (0.0, 1.0) else 1 - abs(2 * pass_rate - 1)

        scores[test_name] = {
            'flakiness_score': flakiness,
            'pass_rate': pass_rate,
            'sample_size': len(test_data)
        }
    return scores
