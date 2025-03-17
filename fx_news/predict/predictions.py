import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
import logging 
import os
import json

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger("predictions")
logger.setLevel(logging.WARNING)  # Set to INFO for production, DEBUG for development

# Base directory for storing rate data
BASE_DIR = "fx_news/scrapers/rates"
YTD_DIR = f"{BASE_DIR}/ytd"
FIVE_D_DIR = f"{BASE_DIR}/5d"


def get_historical_data_for_forecasting(base, quote):
    """
    Get historical data for forecasting from locally stored YTD or 5D data
    
    Args:
        base: Base currency code
        quote: Quote currency code
        
    Returns:
        DataFrame with historical data for forecasting
    """
    # Path to the Source data file
    filename = f"{FIVE_D_DIR}/{base.lower()}_{quote.lower()}.json"

    # filename = f"{YTD_DIR}/{base.lower()}_{quote.lower()}.json"
    logger.info(f"Looking for file: {filename}")
    logger.info(f"File exists: {os.path.exists(filename)}")
    
    if not os.path.exists(filename):
        logger.warning(f"Source rate data file not found for {base}/{quote}")
        return None
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Extract timestamps and close prices
        if "spark" in data and "result" in data["spark"] and len(data["spark"]["result"]) > 0:
            result = data["spark"]["result"][0]
            
            if "response" in result and len(result["response"]) > 0:
                response_data = result["response"][0]
                
                timestamps = response_data.get("timestamp", [])
                close_prices = response_data.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                
                if timestamps and close_prices and len(timestamps) == len(close_prices):
                    # Create a DataFrame with the format expected by your forecasting functions
                    df = pd.DataFrame({
                        "timestamp": [datetime.fromtimestamp(ts) for ts in timestamps],
                        "rate": close_prices
                    })
                    
                    # Set timestamp as index if required by your forecasting functions
                    df['ds'] = df['timestamp']
                    df['y'] = df['rate']
                    
                    logger.info(f"Successfully loaded historical data for forecasting {base}/{quote} with {len(df)} points")
                    return df
    except Exception as e:
        logger.error(f"Error loading source rate data for forecasting: {str(e)}")
        # Print stack trace for debugging
        import traceback
        traceback.print_exc()
    
    return None


def forecast_with_darts(sub, forecast_days=7, model_type='auto'):
    """
    Forecast currency exchange rates using DARTS models
    
    Args:
        sub: Subscription dictionary containing currency pair information
        forecast_days: Number of days to forecast (default: 7)
        model_type: Type of model to use ('auto', 'arima', 'exponential', 'nbeats', etc.)
    
    Returns:
        Plotly figure with historical data and forecast
    """
    import plotly.graph_objects as go
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta
    import streamlit as st
    import warnings
    warnings.filterwarnings("ignore")  # Suppress warnings
    
    try:
        from darts import TimeSeries
        from darts.models import ExponentialSmoothing, ARIMA, AutoARIMA, NBEATSModel
        from darts.metrics import mape, rmse
    except ImportError:
        st.warning("DARTS library is not installed. Please install it with: pip install darts")
        return None
    
    # First get the historical data
    pair_key = f"{sub['base'].lower()}_{sub['quote'].lower()}"
    
    # Initialize placeholder for the data
    historical_df = None
    
    # Check if we have cached historical data for this pair
    if 'historical_rate_cache' in st.session_state and pair_key in st.session_state.historical_rate_cache:
        # Get cached historical data
        historical_df = st.session_state.historical_rate_cache[pair_key]['data'].copy()
        
        # Add real-time data if available
        if pair_key in st.session_state.rate_history and len(st.session_state.rate_history[pair_key]) > 1:
            realtime_df = pd.DataFrame(st.session_state.rate_history[pair_key])
            
            # Find the last timestamp in historical data
            last_historical_time = historical_df['timestamp'].max()
            
            # Filter real-time data to only include points after the historical data
            new_realtime_df = realtime_df[realtime_df['timestamp'] > last_historical_time]
            
            # If we have new real-time data points, append them
            if not new_realtime_df.empty:
                historical_df = pd.concat([historical_df, new_realtime_df], ignore_index=True)
    else:
        st.warning("No historical data available for forecasting. Please wait for data to load.")
        return None
    
    if historical_df is None or historical_df.empty or len(historical_df) < 10:
        st.warning("Insufficient data for DARTS forecasting (need at least 10 data points).")
        return None
    
    # DARTS requires a clean time series with evenly spaced timestamps
    # We'll resample the data to ensure even spacing
    historical_df = historical_df.sort_values('timestamp')
    
    # Determine appropriate frequency based on data
    time_diff = (historical_df['timestamp'].max() - historical_df['timestamp'].min()).total_seconds()
    data_points = len(historical_df)
    avg_seconds_between_points = time_diff / max(1, data_points - 1)
    
    # Choose frequency based on average time between data points
    if avg_seconds_between_points < 300:  # Less than 5 minutes
        freq = '5min'
    elif avg_seconds_between_points < 3600:  # Less than 1 hour
        freq = '1H'
    elif avg_seconds_between_points < 86400:  # Less than 1 day
        freq = '6H'
    else:  # Daily or more
        freq = '1D'
    
    # Create a date range with the chosen frequency
    date_range = pd.date_range(start=historical_df['timestamp'].min(), 
                              end=historical_df['timestamp'].max(), 
                              freq=freq)
    
    # Create a DataFrame with the new date range
    resampled_df = pd.DataFrame({'timestamp': date_range})
    
    # Merge with original data and forward-fill missing values
    merged_df = pd.merge_asof(resampled_df, historical_df, on='timestamp')
    merged_df = merged_df.ffill()  # Forward-fill missing values
    
    # Show a spinner while we process the forecast
    with st.spinner("Generating DARTS forecast..."):
        # Convert to DARTS TimeSeries
        try:
            series = TimeSeries.from_dataframe(
                merged_df,
                time_col='timestamp',
                value_cols='rate',
                fill_missing_dates=True,
                freq=freq
            )
        except Exception as e:
            st.error(f"Error creating TimeSeries: {e}")
            return None
        
        # Split data for training and testing
        train_size = max(int(len(series) * 0.8), len(series) - 30)  # Use 80% for training or all but 30 points
        train, test = series[:train_size], series[train_size:]
        
        # Make sure we have enough test data for validation
        if len(test) < 2:
            test = series[-5:]  # Use last 5 points if not enough test data
        
        # Initialize selected model based on model_type
        selected_model = None
        
        if model_type == 'auto' or model_type == 'autoarima':
            try:
                selected_model = AutoARIMA(
                    start_p=1, start_q=1, max_p=3, max_q=3, 
                    seasonal=True, m=7,  # Weekly seasonality
                    d=1, D=0  # Differencing parameters
                )
            except Exception as e:
                st.warning(f"Error initializing AutoARIMA: {e}. Falling back to ExponentialSmoothing.")
                model_type = 'exponential'  # Fall back to simpler model
                
        if model_type == 'arima':
            try:
                selected_model = ARIMA(p=2, d=1, q=1)
            except Exception as e:
                st.warning(f"Error initializing ARIMA: {e}. Falling back to ExponentialSmoothing.")
                model_type = 'exponential'  # Fall back to simpler model
                
        if model_type == 'exponential' or selected_model is None:
            try:
                selected_model = ExponentialSmoothing(
                    seasonal_periods=7,  # Weekly seasonality
                    trend='add',
                    seasonal='add',
                    damped=True
                )
            except Exception as e:
                st.error(f"Error initializing ExponentialSmoothing: {e}")
                return None
        
        if model_type == 'nbeats':
            try:
                # Only use this for larger datasets
                if len(series) > 100:
                    selected_model = NBEATSModel(
                        input_chunk_length=24,
                        output_chunk_length=forecast_days,
                        n_epochs=50,
                        random_state=42
                    )
                else:
                    st.warning("Not enough data for NBEATS model. Using ExponentialSmoothing instead.")
                    selected_model = ExponentialSmoothing(seasonal_periods=7)
            except Exception as e:
                st.warning(f"Error initializing NBEATS: {e}. Falling back to ExponentialSmoothing.")
                selected_model = ExponentialSmoothing(seasonal_periods=7)
        
        # Train the model
        try:
            selected_model.fit(train)
        except Exception as e:
            st.error(f"Error training model: {e}")
            return None
        
        # Calculate forecast horizon (number of steps to forecast)
        # Convert forecast_days to the appropriate number of time steps based on frequency
        if freq == '5min':
            horizon = forecast_days * 24 * 12  # 12 5-minute intervals per hour
        elif freq == '1H':
            horizon = forecast_days * 24  # 24 hours per day
        elif freq == '6H':
            horizon = forecast_days * 4  # 4 6-hour intervals per day
        else:  # '1D'
            horizon = forecast_days
        
        # Generate forecast
        try:
            forecast = selected_model.predict(horizon)
        except Exception as e:
            st.error(f"Error generating forecast: {e}")
            return None
        
        # Calculate error metrics on test data
        if len(test) > 0:
            try:
                # Make a historical forecast for the test period for evaluation
                historical_forecast = selected_model.predict(len(test))
                
                # Calculate error metrics
                mape_value = mape(test, historical_forecast)
                rmse_value = rmse(test, historical_forecast)
                
                # Calculate mean error percentage for display
                error_pct = mape_value * 100  # Convert to percentage
            except Exception as e:
                st.warning(f"Error calculating metrics: {e}")
                mape_value = None
                rmse_value = None
                error_pct = None
        else:
            mape_value = None
            rmse_value = None
            error_pct = None
        
        # Prepare data for plotting
        # Convert series and forecast to pandas DataFrames for easier plotting
        series_df = series.pd_dataframe().reset_index()
        series_df.columns = ['timestamp', 'actual']
        
        forecast_df = forecast.pd_dataframe().reset_index()
        forecast_df.columns = ['timestamp', 'forecast']
        
        # Create dark-themed figure for visualization
        fig = go.Figure()
        
        # Add historical data trace
        fig.add_trace(go.Scatter(
            x=series_df['timestamp'],
            y=series_df['actual'],
            mode='lines',
            name='Historical',
            line=dict(color='#4D9BF5', width=2),
            hovertemplate='%{x}<br>Rate: %{y:.4f}<extra></extra>'
        ))
        
        # Add forecast line
        fig.add_trace(go.Scatter(
            x=forecast_df['timestamp'],
            y=forecast_df['forecast'],
            mode='lines',
            name='DARTS Forecast',
            line=dict(color='#9C27B0', width=2, dash='dash'),  # Purple for DARTS vs orange for Prophet
            hovertemplate='%{x}<br>Forecast: %{y:.4f}<extra></extra>'
        ))
        
        # Calculate confidence intervals (simulated, as DARTS doesn't always provide them)
        # Use historical volatility to estimate
        if len(series_df) > 10:
            volatility = series_df['actual'].pct_change().std() * 100  # Percentage volatility
            
            # Scale confidence interval based on volatility
            ci_factor = max(1.5, min(5, volatility * 2))  # Scale based on volatility, between 1.5% and 5%
            
            # Create upper and lower bounds
            upper_bound = forecast_df['forecast'] * (1 + ci_factor/100)
            lower_bound = forecast_df['forecast'] * (1 - ci_factor/100)
            
            # Add confidence interval
            fig.add_trace(go.Scatter(
                x=forecast_df['timestamp'].tolist() + forecast_df['timestamp'].tolist()[::-1],
                y=upper_bound.tolist() + lower_bound.tolist()[::-1],
                fill='toself',
                fillcolor='rgba(156, 39, 176, 0.2)',  # Light purple
                line=dict(color='rgba(156, 39, 176, 0)'),
                name='Confidence Interval',
                hoverinfo='skip'
            ))
        
        # Add chart title
        model_name = model_type.upper() if model_type != 'auto' else 'AutoARIMA'
        fig.update_layout(
            title=f"{sub['base']}/{sub['quote']} DARTS {model_name} Forecast ({forecast_days} days)",
            title_font_color="#FFFFFF"
        )
        
        # Apply dark theme styling
        fig.update_layout(
            height=400,
            margin=dict(l=0, r=0, t=40, b=0),
            paper_bgcolor="#121212",  # Dark background
            plot_bgcolor="#121212",   # Dark background
            font=dict(color="#FFFFFF"),  # Pure white text for better visibility
            xaxis=dict(
                gridcolor="#333333",  # Darker grid
                tickcolor="#FFFFFF",  # Pure white tick marks
                linecolor="#555555",  # Medium gray axis line
                tickfont=dict(color="#FFFFFF", size=12),  # Brighter, larger tick labels
                title_font=dict(color="#FFFFFF", size=14)  # Brighter, larger axis title
            ),
            yaxis=dict(
                gridcolor="#333333",  # Darker grid
                tickcolor="#FFFFFF",  # Pure white tick marks
                linecolor="#555555",  # Medium gray axis line
                tickfont=dict(color="#FFFFFF", size=12),  # Brighter, larger tick labels
                title_font=dict(color="#FFFFFF", size=14)  # Brighter, larger axis title
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(color="#FFFFFF", size=12),  # White legend text
                bgcolor="rgba(18, 18, 18, 0.5)",  # Semi-transparent background
                bordercolor="#555555"  # Medium gray border
            )
        )
        
        # Add the FX-Pulsar watermark
        fig.add_annotation(
            text="FX-PULSAR DARTS",
            x=0.95,  # Position at 95% from the left
            y=0.10,  # Position at 10% from the bottom
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(
                family="Arial",
                size=28,
                color="rgba(255, 255, 255, 0.15)"  # Semi-transparent white
            ),
            align="right",
            opacity=0.7,
            textangle=0
        )
        
        # Prepare forecast data and metrics for return
        forecast_result = {
            'data': {
                'timestamps': forecast_df['timestamp'].tolist(),
                'values': forecast_df['forecast'].tolist(),
                'upper': upper_bound.tolist() if 'upper_bound' in locals() else None,
                'lower': lower_bound.tolist() if 'lower_bound' in locals() else None
            },
            'metrics': {
                'mape': mape_value,
                'rmse': rmse_value,
                'error_pct': error_pct,
                'model': model_type
            }
        }
        
        # Return the figure and forecast data
        return fig, forecast_result

def _render_darts_forecast_content(sub):
    """Helper function that contains the UI elements for DARTS forecast"""
    import streamlit as st
    from datetime import datetime, timedelta
    
    # Create a unique base key for this currency pair
    pair_key = f"{sub['base'].lower()}_{sub['quote'].lower()}_darts"
    
    # Create controls in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Forecast period selection with unique key
        forecast_days = st.slider(
            "Forecast Period (Days)", 
            min_value=1, 
            max_value=30, 
            value=7,
            help="Select how many days to forecast",
            key=f"darts_days_{pair_key}"  # Unique key
        )
    
    with col2:
        # Model selection
        model_type = st.selectbox(
            "Model Type",
            options=["auto", "arima", "exponential", "nbeats"],
            index=0,
            help="Select forecasting model type",
            key=f"darts_model_{pair_key}"  # Unique key
        )
    
    with col3:
        # Button to run/refresh forecast with unique key
        run_forecast = st.button(
            "Generate Forecast", 
            use_container_width=True,
            key=f"darts_generate_{pair_key}"  # Unique key
        )
    
    # Initialize forecast state if it doesn't exist
    if 'darts_forecast_results' not in st.session_state:
        st.session_state.darts_forecast_results = {}
    
    # Run forecast if button is clicked or if we haven't forecasted this pair yet
    if run_forecast or pair_key not in st.session_state.darts_forecast_results:
        # Generate the forecast
        forecast_result = forecast_with_darts(sub, forecast_days, model_type)
        
        if forecast_result:
            fig, forecast_data = forecast_result
            
            # Store in session state
            st.session_state.darts_forecast_results[pair_key] = {
                'fig': fig,
                'data': forecast_data,
                'timestamp': datetime.now(),
                'params': {
                    'days': forecast_days,
                    'model': model_type
                }
            }
    
    # Display forecast if available
    if pair_key in st.session_state.darts_forecast_results:
        forecast_result = st.session_state.darts_forecast_results[pair_key]
        
        # Display the chart
        st.plotly_chart(forecast_result['fig'], use_container_width=True)
        
        # Display metrics and key insights
        st.markdown("### DARTS Model Analysis")
        
        # Create columns for metrics
        metric_cols = st.columns(3)
        
        with metric_cols[0]:
            st.markdown("#### Model Performance")
            
            # Only show if we have metrics
            metrics = forecast_result['data'].get('metrics', {})
            error_pct = metrics.get('error_pct')
            
            if error_pct is not None:
                # Determine accuracy level and color
                if error_pct < 1:
                    accuracy_level = "Excellent"
                    color = "#4CAF50"  # Green
                elif error_pct < 5:
                    accuracy_level = "Good"
                    color = "#8BC34A"  # Light Green
                elif error_pct < 10:
                    accuracy_level = "Acceptable"
                    color = "#FFC107"  # Amber
                elif error_pct < 15:
                    accuracy_level = "Fair"
                    color = "#FF9800"  # Orange
                else:
                    accuracy_level = "Poor"
                    color = "#F44336"  # Red
                
                st.markdown(f"""
                <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Model Type:</span>
                        <span style="color:white;">{metrics.get('model', 'Unknown').upper()}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Accuracy:</span>
                        <span style="color:{color};">{accuracy_level}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:white;">Error Rate:</span>
                        <span style="color:white;">{error_pct:.2f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Model Type:</span>
                        <span style="color:white;">{metrics.get('model', 'Unknown').upper()}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Accuracy:</span>
                        <span style="color:#FFC107;">Not Available</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:white;">Note:</span>
                        <span style="color:white;">Insufficient validation data</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        with metric_cols[1]:
            st.markdown("#### Short-term Projection")
            
            # Get data for short-term prediction (next day)
            forecast_data = forecast_result['data'].get('data', {})
            if forecast_data and forecast_data.get('timestamps') and forecast_data.get('values'):
                # Find the prediction for tomorrow
                tomorrow = datetime.now() + timedelta(days=1)
                
                # Find the closest timestamp to tomorrow
                timestamps = forecast_data['timestamps']
                values = forecast_data['values']
                
                # Make sure we have timestamps as datetime objects for comparison
                if isinstance(timestamps[0], str):
                    timestamps = [datetime.fromisoformat(ts.rstrip('Z')) if 'T' in ts 
                                 else datetime.strptime(ts, '%Y-%m-%d') 
                                 for ts in timestamps]
                
                # Find index of closest timestamp to tomorrow
                closest_idx = min(range(len(timestamps)), 
                                 key=lambda i: abs((timestamps[i] - tomorrow).total_seconds()))
                
                if closest_idx < len(values):
                    tomorrow_pred = values[closest_idx]
                    
                    # Check if we can calculate change direction
                    current_rate = sub.get('current_rate')
                    if current_rate:
                        change = ((tomorrow_pred - current_rate) / current_rate) * 100
                        direction = "up" if change > 0 else "down"
                        color = "#4CAF50" if change > 0 else "#F44336"
                        
                        st.markdown(f"""
                        <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:white;">24h Forecast:</span>
                                <span style="color:{color};">{tomorrow_pred:.4f}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:white;">Direction:</span>
                                <span style="color:{color};">Trending {direction}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between;">
                                <span style="color:white;">Expected Change:</span>
                                <span style="color:{color};">{change:.2f}%</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:white;">24h Forecast:</span>
                                <span style="color:white;">{tomorrow_pred:.4f}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("Short-term projection data not available.")
        
        with metric_cols[2]:
            st.markdown("#### End of Forecast")
            
            # Get data for end-of-forecast prediction
            forecast_data = forecast_result['data'].get('data', {})
            if forecast_data and forecast_data.get('values') and len(forecast_data['values']) > 0:
                # Get the last prediction point
                end_pred = forecast_data['values'][-1]
                
                # Check if we can calculate change direction
                current_rate = sub.get('current_rate')
                if current_rate:
                    total_change = ((end_pred - current_rate) / current_rate) * 100
                    direction = "up" if total_change > 0 else "down"
                    color = "#4CAF50" if total_change > 0 else "#F44336"
                    
                    st.markdown(f"""
                    <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">{forecast_days}d Forecast:</span>
                            <span style="color:{color};">{end_pred:.4f}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">Direction:</span>
                            <span style="color:{color};">Trending {direction}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:white;">Expected Change:</span>
                            <span style="color:{color};">{total_change:.2f}%</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">{forecast_days}d Forecast:</span>
                            <span style="color:white;">{end_pred:.4f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("End of forecast data not available.")
        
        # Add last updated time and disclaimer
        st.caption(f"Last updated: {forecast_result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        st.markdown("""
        <div style="font-size:0.8em; color:#999; margin-top:20px;">
        <strong>About DARTS Models:</strong> DARTS provides multiple time series forecasting models with different strengths:
        <ul style="margin-top:5px; margin-bottom:5px; padding-left:20px;">
          <li><strong>Auto:</strong> AutoARIMA automatically finds optimal ARIMA parameters</li>
          <li><strong>ARIMA:</strong> Good for data with trends and some seasonality</li>
          <li><strong>Exponential:</strong> Handles data with trends and seasonality via exponential smoothing</li>
          <li><strong>NBEATS:</strong> Neural network approach for complex patterns (requires more data)</li>
        </ul>
        <strong>Disclaimer:</strong> Forecasts are statistical projections and should not be the sole basis for trading decisions.
        </div>
        """, unsafe_allow_html=True)
    else:
        # Show a message if no forecast is available yet
        st.info("Waiting for sufficient historical data to generate a DARTS forecast. Please try again once the chart data is loaded or click 'Generate Forecast'.")

def add_darts_forecast_tab(sub):
    """
    Add a DARTS forecast tab to a tab UI
    
    Args:
        sub: Subscription dictionary containing currency pair information
    """
    import streamlit as st
    
    # Render the DARTS forecast content directly
    _render_darts_forecast_content(sub)


def add_forecast_comparison_card(sub):
    """
    Add a comparative analysis of different forecasting models for a currency pair
    
    Args:
        sub: Subscription dictionary containing currency pair information
    """
    import streamlit as st

    base = sub['base']
    quote = sub['quote']
    
    # Get historical data from locally stored YTD data
    df = get_historical_data_for_forecasting(base, quote)
    
    if df is None or df.empty:
        st.error(f"No historical data available for {base}/{quote} forecasting")
        return

    # Get pair key
    pair_key = f"{sub['base'].lower()}_{sub['quote'].lower()}"
    darts_pair_key = f"{pair_key}_darts"
    
    # Check if we have forecasts from either model
    prophet_forecast = st.session_state.get('forecast_results', {}).get(pair_key)
    darts_forecast = st.session_state.get('darts_forecast_results', {}).get(darts_pair_key)
    
    # If no forecasts at all, just show a simple message
    if not prophet_forecast and not darts_forecast:
        st.info("Generate forecasts using both Prophet and DARTS tabs to see model comparison.")
        return
    
    # Create a comparison section
    st.markdown("### Forecast Model Comparison")
    st.markdown("Compare predictions from different forecasting approaches:")
    
    # Create two columns for summary cards
    col1, col2 = st.columns(2)
    
    # Prophet summary card
    with col1:
        if prophet_forecast:
            st.markdown("#### Prophet Forecast")
            st.info("Prophet forecast is available. Please check the Prophet tab for details.")
        else:
            st.info("Generate a Prophet forecast to see comparison.")
    
    # DARTS summary card
    with col2:
        if darts_forecast:
            st.markdown("#### DARTS Forecast")
            st.info("DARTS forecast is available. Please check the DARTS tab for details.")
        else:
            st.info("Generate a DARTS forecast to see comparison.")

    
def forecast_currency_rates(sub, forecast_days=7, confidence_interval=0.8):
    """
    Forecast currency exchange rates using Facebook Prophet
    
    Args:
        sub: Subscription dictionary containing currency pair information
        forecast_days: Number of days to forecast (default: 7)
        confidence_interval: Confidence interval for forecast (default: 0.8)
    
    Returns:
        Plotly figure with historical data and forecast, or None if no data is available
    """
    import plotly.graph_objects as go
    import pandas as pd
    from datetime import datetime, timedelta
    import streamlit as st
    
    try:
        from prophet import Prophet
        from prophet.diagnostics import cross_validation, performance_metrics
    except ImportError:
        st.warning("Prophet library is not installed. Please install it to use forecasting.")
        return None
    
    # First get the historical data directly from the source rate YTD or 5D data file
    pair_key = f"{sub['base'].lower()}_{sub['quote'].lower()}"
    
    # Get historical data using the function that reads JSON directly
    historical_df = get_historical_data_for_forecasting(sub['base'], sub['quote'])
    
    if historical_df is None or historical_df.empty:
        st.warning("No historical data available for forecasting. Please wait for data to load.")
        return None
    
    # Show a spinner while we process the forecast
    with st.spinner("Generating forecast..."):
        # Prepare data for Prophet (requires 'ds' for dates and 'y' for values)
        prophet_df = historical_df[['timestamp', 'rate']].copy()
        prophet_df.columns = ['ds', 'y']
        
        # Create and fit the Prophet model with optimized parameters
        model = Prophet(
            # Core parameters
            interval_width=confidence_interval,
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=True,
            
            # Changepoint parameters - control flexibility
            changepoint_prior_scale=0.05,  # Flexibility of the trend, higher values allow more flexibility
            changepoint_range=0.95,        # Proportion of history where trend changes can occur
            
            # Seasonality parameters
            seasonality_mode='multiplicative',  # Better for financial data with non-constant variance
            seasonality_prior_scale=10.0,       # Higher values allow stronger seasonality
        )
        
        # Add country-specific holidays if appropriate
        if st.session_state.get('market_type') == 'Currency':
            # For currency pairs, add US, EU, UK, JP holidays as these affect forex markets
            try:
                from prophet.holidays import add_country_holidays
                model.add_country_holidays(country_name='US')
                model.add_country_holidays(country_name='UK')
                # Add more relevant countries based on the currency pair
            except Exception as e:
                st.warning(f"Could not add holidays: {str(e)}")
            
        # Fit the model
        model.fit(prophet_df)
        
        # Create future dataframe for predictions
        future = model.make_future_dataframe(periods=forecast_days, freq='D')
        
        # Add intraday predictions if we have intraday data
        if len(historical_df) > 0:
            time_diff = (historical_df['timestamp'].max() - historical_df['timestamp'].min()).total_seconds()
            data_points = len(historical_df)
            avg_time_between_points = time_diff / max(1, data_points - 1)
            
            # If average time between points is less than a day, we have intraday data
            if avg_time_between_points < 86400:  # seconds in a day
                # Make future dataframe with intraday frequency
                if avg_time_between_points < 3600:  # less than an hour
                    freq = '5min'
                elif avg_time_between_points < 21600:  # less than 6 hours
                    freq = '1H'
                else:
                    freq = '6H'
                
                future = model.make_future_dataframe(
                    periods=int(forecast_days * 24),  # Convert days to hours
                    freq=freq
                )
        
        # Make predictions
        forecast = model.predict(future)
        
        # Perform model validation through cross-validation
        forecast_metrics = None
        if len(prophet_df) > 30:  # Only do CV if we have enough data
            initial_days = int(len(prophet_df) * 0.5)  # Use 50% of data for initial training
            period_days = int(len(prophet_df) * 0.2)  # Increment by 20% of data
            horizon_days = min(forecast_days, int(len(prophet_df) * 0.3))  # Forecast horizon (30% of data or requested days)
            
            try:
                cv_results = cross_validation(
                    model=model,
                    initial=f"{initial_days} days",
                    period=f"{period_days} days",
                    horizon=f"{horizon_days} days",
                    parallel="processes"
                )
                
                # Get performance metrics
                cv_metrics = performance_metrics(cv_results)
                
                # Calculate mean absolute percentage error (MAPE)
                mape = cv_metrics['mape'].mean() * 100  # Convert to percentage
                
                # Store metrics for display
                forecast_metrics = {
                    'MAPE': f"{mape:.2f}%",
                    'MAE': f"{cv_metrics['mae'].mean():.6f}",
                    'RMSE': f"{cv_metrics['rmse'].mean():.6f}"
                }
            except Exception as e:
                st.warning(f"Cross-validation error: {e}. Using model without validation.")
                forecast_metrics = None
        
        # Create dark-themed figure for visualization
        fig = go.Figure()
        
        # Add historical data trace
        fig.add_trace(go.Scatter(
            x=historical_df['timestamp'],
            y=historical_df['rate'],
            mode='lines',
            name='Historical',
            line=dict(color='#4D9BF5', width=2),
            hovertemplate='%{x}<br>Rate: %{y:.4f}<extra></extra>'
        ))
        
        # Add forecast line
        fig.add_trace(go.Scatter(
            x=forecast['ds'],
            y=forecast['yhat'],
            mode='lines',
            name='Forecast',
            line=dict(color='#FFA500', width=2, dash='dash'),
            hovertemplate='%{x}<br>Forecast: %{y:.4f}<extra></extra>'
        ))
        
        # Add prediction intervals
        fig.add_trace(go.Scatter(
            x=forecast['ds'].tolist() + forecast['ds'].tolist()[::-1],
            y=forecast['yhat_upper'].tolist() + forecast['yhat_lower'].tolist()[::-1],
            fill='toself',
            fillcolor='rgba(255, 165, 0, 0.2)',
            line=dict(color='rgba(255, 165, 0, 0)'),
            name=f'{int(confidence_interval*100)}% Prediction Interval',
            hoverinfo='skip'
        ))
        
        # Add chart title
        fig.update_layout(
            title=f"{sub['base']}/{sub['quote']} Rate Forecast ({forecast_days} days)",
            title_font_color="#FFFFFF"
        )
        
        # Apply dark theme styling
        fig.update_layout(
            height=400,
            margin=dict(l=0, r=0, t=40, b=0),
            paper_bgcolor="#121212",  # Dark background
            plot_bgcolor="#121212",   # Dark background
            font=dict(color="#FFFFFF"),  # Pure white text for better visibility
            xaxis=dict(
                gridcolor="#333333",  # Darker grid
                tickcolor="#FFFFFF",  # Pure white tick marks
                linecolor="#555555",  # Medium gray axis line
                tickfont=dict(color="#FFFFFF", size=12),  # Brighter, larger tick labels
                title_font=dict(color="#FFFFFF", size=14)  # Brighter, larger axis title
            ),
            yaxis=dict(
                gridcolor="#333333",  # Darker grid
                tickcolor="#FFFFFF",  # Pure white tick marks
                linecolor="#555555",  # Medium gray axis line
                tickfont=dict(color="#FFFFFF", size=12),  # Brighter, larger tick labels
                title_font=dict(color="#FFFFFF", size=14)  # Brighter, larger axis title
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(color="#FFFFFF", size=12),  # White legend text
                bgcolor="rgba(18, 18, 18, 0.5)",  # Semi-transparent background
                bordercolor="#555555"  # Medium gray border
            )
        )
        
        # Add the FX-Pulsar watermark
        fig.add_annotation(
            text="FX-PULSAR FORECAST",
            x=0.95,  # Position at 95% from the left
            y=0.10,  # Position at 10% from the bottom
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(
                family="Arial",
                size=28,
                color="rgba(255, 255, 255, 0.15)"  # Semi-transparent white
            ),
            align="right",
            opacity=0.7,
            textangle=0
        )
        
        # Return the figure and metrics
        return fig, forecast_metrics, forecast

def _render_forecast_content(sub):
    """Helper function that contains the actual forecast UI elements"""
    import streamlit as st
    from datetime import datetime, timedelta
    
    # Create a unique base key for this currency pair
    pair_key = f"{sub['base'].lower()}_{sub['quote'].lower()}"
    
    # Create two columns for controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Forecast period selection with unique key
        forecast_days = st.slider(
            "Forecast Period (Days)", 
            min_value=1, 
            max_value=30, 
            value=7,
            help="Select how many days to forecast",
            key=f"forecast_days_{pair_key}"  # Unique key based on currency pair
        )
    
    with col2:
        # Confidence interval selection with unique key
        confidence = st.slider(
            "Confidence Interval", 
            min_value=0.5, 
            max_value=0.95, 
            value=0.8, 
            step=0.05,
            format="%.0f%%",
            help="Confidence level for prediction intervals",
            key=f"confidence_{pair_key}"  # Unique key based on currency pair
        )
    
    with col3:
        # Button to run/refresh forecast with unique key
        run_forecast = st.button(
            "Generate Forecast", 
            use_container_width=True,
            key=f"generate_forecast_{pair_key}"  # Unique key based on currency pair
        )
    
    # Initialize forecast state if it doesn't exist
    if 'forecast_results' not in st.session_state:
        st.session_state.forecast_results = {}
    
    # Get pair key
    pair_key = f"{sub['base'].lower()}_{sub['quote'].lower()}"
        
    # Run forecast if button is clicked or if we haven't forecasted this pair yet
    if run_forecast or pair_key not in st.session_state.forecast_results:
        # Generate the forecast
        forecast_result = forecast_currency_rates(sub, forecast_days, confidence)
        
        if forecast_result:
            fig, metrics, forecast_data = forecast_result
            
            # Store in session state
            st.session_state.forecast_results[pair_key] = {
                'fig': fig,
                'metrics': metrics,
                'data': forecast_data,
                'timestamp': datetime.now(),
                'params': {
                    'days': forecast_days,
                    'confidence': confidence
                }
            }
    
    # Display forecast if available
    if pair_key in st.session_state.forecast_results:
        forecast_result = st.session_state.forecast_results[pair_key]
        
        # Display the chart
        st.plotly_chart(forecast_result['fig'], use_container_width=True)
        
        # Display metrics and key insights
        st.markdown("### Forecast Insights")
        
        # Create columns for metrics
        metric_cols = st.columns(3)
        
        with metric_cols[0]:
            st.markdown("#### Short-term Prediction")
            # Get tomorrow's prediction
            tomorrow = datetime.now() + timedelta(days=1)
            tomorrow_pred = None
            if 'data' in forecast_result and not forecast_result['data'].empty:
                future_rows = forecast_result['data'][forecast_result['data']['ds'] > tomorrow]
                if not future_rows.empty:
                    tomorrow_pred = future_rows.iloc[0]
            
            if tomorrow_pred is not None:
                current_rate = sub.get('current_rate')
                if current_rate:
                    change = ((tomorrow_pred['yhat'] - current_rate) / current_rate) * 100
                    direction = "up" if change > 0 else "down"
                    color = "#4CAF50" if change > 0 else "#F44336"
                    
                    st.markdown(f"""
                    <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">24h Forecast:</span>
                            <span style="color:{color};">{tomorrow_pred['yhat']:.4f}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">Direction:</span>
                            <span style="color:{color};">Trending {direction}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:white;">Expected Change:</span>
                            <span style="color:{color};">{change:.2f}%</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">24h Forecast:</span>
                            <span style="color:white;">{tomorrow_pred['yhat']:.4f}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">Lower bound:</span>
                            <span style="color:white;">{tomorrow_pred['yhat_lower']:.4f}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:white;">Upper bound:</span>
                            <span style="color:white;">{tomorrow_pred['yhat_upper']:.4f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
        with metric_cols[1]:
            st.markdown("#### End of Forecast")
            # Get end of forecast prediction
            end_pred = None
            if 'data' in forecast_result and not forecast_result['data'].empty:
                end_pred = forecast_result['data'].iloc[-1]
            
            if end_pred is not None:
                current_rate = sub.get('current_rate')
                if current_rate:
                    total_change = ((end_pred['yhat'] - current_rate) / current_rate) * 100
                    direction = "up" if total_change > 0 else "down"
                    color = "#4CAF50" if total_change > 0 else "#F44336"
                    
                    st.markdown(f"""
                    <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">{forecast_days}d Forecast:</span>
                            <span style="color:{color};">{end_pred['yhat']:.4f}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">Direction:</span>
                            <span style="color:{color};">Trending {direction}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:white;">Expected Change:</span>
                            <span style="color:{color};">{total_change:.2f}%</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">{forecast_days}d Forecast:</span>
                            <span style="color:white;">{end_pred['yhat']:.4f}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">Lower bound:</span>
                            <span style="color:white;">{end_pred['yhat_lower']:.4f}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:white;">Upper bound:</span>
                            <span style="color:white;">{end_pred['yhat_upper']:.4f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
        with metric_cols[2]:
            st.markdown("#### Model Accuracy")
            # Display model metrics if available
            if 'metrics' in forecast_result and forecast_result['metrics']:
                metrics = forecast_result['metrics']
                
                # Interpret MAPE value
                mape_value = float(metrics['MAPE'].replace('%', ''))
                if mape_value < 1:
                    accuracy_level = "Excellent"
                    color = "#4CAF50"  # Green
                elif mape_value < 5:
                    accuracy_level = "Good"
                    color = "#8BC34A"  # Light Green
                elif mape_value < 10:
                    accuracy_level = "Acceptable"
                    color = "#FFC107"  # Amber
                elif mape_value < 15:
                    accuracy_level = "Fair"
                    color = "#FF9800"  # Orange
                else:
                    accuracy_level = "Poor"
                    color = "#F44336"  # Red
                
                st.markdown(f"""
                <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Accuracy:</span>
                        <span style="color:{color};">{accuracy_level}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Error Rate (MAPE):</span>
                        <span style="color:white;">{metrics['MAPE']}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:white;">Last Updated:</span>
                        <span style="color:white;">{forecast_result['timestamp'].strftime('%H:%M:%S')}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Model Validation:</span>
                        <span style="color:#FFC107;">Not Available</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Note:</span>
                        <span style="color:white;">Insufficient data for validation</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:white;">Last Updated:</span>
                        <span style="color:white;">{forecast_result['timestamp'].strftime('%H:%M:%S')}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # Disclaimer
        st.markdown("""
        <div style="font-size:0.8em; color:#999; margin-top:20px;">
        <strong>Disclaimer:</strong> Forecasts are based on historical patterns and should not be the sole basis for trading decisions. 
        Past performance does not guarantee future results. Market conditions can change rapidly due to unforeseen events.
        </div>
        """, unsafe_allow_html=True)
    else:
        # Show a message if no forecast is available yet
        st.info("Waiting for sufficient historical data to generate a forecast. Please try again once the chart data is loaded.")

def add_forecast_to_dashboard(sub, use_expander=False):
    """
    Add a forecast section to the currency pair dashboard
    
    Args:
        sub: Subscription dictionary containing currency pair information
        use_expander: Whether to use an expander for the forecast section
    """
    import streamlit as st
    import pandas as pd
    from datetime import datetime

    base = sub['base']
    quote = sub['quote']
    
    content = st.container()
    with content:
        # Get historical data from locally stored source rate 5D or YTD data
        df = get_historical_data_for_forecasting(base, quote)
        
        if df is None or df.empty:
            st.error(f"No historical data available for {base}/{quote} forecasting")
            return
        
        # Make sure the DataFrame has the expected columns for Prophet
        if 'ds' not in df.columns or 'y' not in df.columns:
            # Add the Prophet-specific columns if they don't exist
            df['ds'] = df['timestamp']
            df['y'] = df['rate']
        
        # Store the data in the session state where the forecast functions expect it
        pair_key = f"{base.lower()}_{quote.lower()}"
        if 'historical_rate_cache' not in st.session_state:
            st.session_state.historical_rate_cache = {}
        
        st.session_state.historical_rate_cache[pair_key] = {
            'data': df,
            'last_fetch_time': datetime.now()
        }
        
        # Now call the original forecast content renderer
        if use_expander:
            with st.expander("📈 Price Forecast", expanded=False):
                _render_forecast_content(sub)
        else:
            # Otherwise just render the content directly
            _render_forecast_content(sub)