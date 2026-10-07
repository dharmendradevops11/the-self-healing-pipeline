# forecast_engine.py — runs every 6 hours
class ForecastEngine:
    def __init__(self):
        self.metrics_client = CloudWatchClient()
        self.prophet = Prophet()
        self.alert_threshold_days = 7  # warn if exhaustion within a week

    def forecast_resource(self, metric_name, namespace, days_ahead=14):
        history = self.metrics_client.get_metric_history(metric_name, namespace, days=30)
        df = pd.DataFrame({'ds': history.index, 'y': history.values})
        self.prophet.fit(df)
        future = self.prophet.make_future_dataframe(periods=days_ahead, freq='D')
        forecast = self.prophet.predict(future)
        return forecast[forecast['ds'] > df['ds'].max()]
