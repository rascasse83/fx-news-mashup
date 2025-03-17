### Accuracy Levels

The model reports its accuracy level:
- **Excellent**: Error rate under 1%
- **Good**: Error rate 1-5%
- **Acceptable**: Error rate 5-10%
- **Fair**: Error rate 10-15%
- **Poor**: Error rate above 15%

## Technical Details

The forecast model:
- Blends historical data from Yahoo Finance with real-time data
- Uses multiplicative seasonality (better for financial data)
- Performs cross-validation to assess forecast accuracy
- Adapts to intraday or daily data automatically

## Important Disclaimer

**Forecasts are statistical projections based on historical patterns and should not be the sole basis for trading decisions. Past performance does not guarantee future results. Market conditions can change rapidly due to unforeseen events.**

## Advanced Settings

Advanced users can modify the forecasting parameters in the source code:
- `changepoint_prior_scale`: Controls flexibility of the trend (default: 0.05)
- `seasonality_prior_scale`: Controls strength of seasonality (default: 10.0)
- `seasonality_mode`: 'multiplicative' for financial data with non-constant variance
- Holiday settings: Can be customized based on relevant countries

These settings can be found in the `forecast_currency_rates` function in the `fx_news/predict/predictions.py` file.