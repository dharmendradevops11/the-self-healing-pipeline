# Rough annual cost model for CI/CD pipeline failures
# Adjust the inputs for your team; the shape of the calculation matters more
# than any single number.

def annual_pipeline_failure_cost(
    failures_per_week: float,
    hours_lost_per_failure: float,
    engineers_involved: int,
    loaded_hourly_rate: float,
    weeks_per_year: int = 50,
) -> dict:
    annual_failures = failures_per_week * weeks_per_year
    engineer_hours = annual_failures * hours_lost_per_failure * engineers_involved
    direct_cost = engineer_hours * loaded_hourly_rate
    return {
        "annual_failures": annual_failures,
        "engineer_hours_lost": engineer_hours,
        "direct_cost_usd": direct_cost,
    }
result = annual_pipeline_failure_cost(
    failures_per_week=3,
    hours_lost_per_failure=1.5,
    engineers_involved=2,
    loaded_hourly_rate=150,
)
print(result)
# {'annual_failures': 150.0, 'engineer_hours_lost': 450.0, 'direct_cost_usd': 67500.0}
