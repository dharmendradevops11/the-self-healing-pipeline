def predict_with_seasonality(metric_data, threshold, hours_ahead=1):
    """
    metric_data: DataFrame with 'ds' (datetime) and 'y' (metric value) columns
    """
    df = pd.DataFrame({'ds': metric_data.index, 'y': metric_data.values})

    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,       # not useful for pipeline metrics
        changepoint_prior_scale=0.05    # how flexible the trend is
    )
    model.fit(df)
