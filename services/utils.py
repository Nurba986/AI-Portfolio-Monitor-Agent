"""
Utility functions for Portfolio Agent
Handles HTTP sessions, market hours, data formatting, and validation
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, date
import pytz


# Global HTTP session for requests with retry logic
_HTTP_SESSION = None

# US Stock Market Holidays (major ones that affect trading)
US_MARKET_HOLIDAYS_2025 = [
    date(2025, 9, 1),   # Labor Day
    date(2025, 11, 27), # Thanksgiving
    date(2025, 12, 25), # Christmas
]

# Add 2026 holidays for year transition
US_MARKET_HOLIDAYS_2026 = [
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # Martin Luther King Jr. Day
    date(2026, 2, 16),  # Presidents' Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day (observed)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
]

ALL_MARKET_HOLIDAYS = US_MARKET_HOLIDAYS_2025 + US_MARKET_HOLIDAYS_2026


def get_http_session():
    """Get a configured HTTP session with retry logic"""
    global _HTTP_SESSION
    if _HTTP_SESSION is not None:
        return _HTTP_SESSION
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    })
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    _HTTP_SESSION = session
    return session


def is_market_open(bypass_for_testing=False):
    """
    Check if the US stock market is currently open
    Args:
        bypass_for_testing (bool): If True, bypasses market hours check for testing/debugging
    Returns: (is_open: bool, reason: str)
    """
    # Allow bypass for testing and debugging
    if bypass_for_testing:
        print("TESTING MODE: Market hours check bypassed")
        return True, "Testing mode - market hours bypassed"
    
    # Check environment variable for bypass (useful for GCP debugging)
    import os
    if os.environ.get('BYPASS_MARKET_HOURS', '').lower() in ('true', '1', 'yes'):
        print("BYPASS_MARKET_HOURS enabled - skipping market hours validation")
        return True, "Market hours bypassed via BYPASS_MARKET_HOURS environment variable"
    
    # Get current time in Eastern Time (market timezone)
    et_tz = pytz.timezone('America/New_York')
    now_et = datetime.now(et_tz)
    current_date = now_et.date()
    current_time = now_et.time()
    
    # Check if today is a weekend (Saturday = 5, Sunday = 6)
    if now_et.weekday() >= 5:
        return False, f"Weekend ({now_et.strftime('%A')})"
    
    # Check if today is a market holiday
    if current_date in ALL_MARKET_HOLIDAYS:
        return False, f"Market holiday: {current_date.isoformat()}"
    
    # Check if current time is within market hours (9:30 AM - 4:00 PM ET) - Correct NYSE/NASDAQ hours
    market_open = current_time.replace(second=0, microsecond=0) >= datetime.strptime("09:30", "%H:%M").time()
    market_close = current_time.replace(second=0, microsecond=0) <= datetime.strptime("16:00", "%H:%M").time()
    
    if not (market_open and market_close):
        return False, f"Outside market hours: {current_time.strftime('%H:%M')} ET (market: 9:30-16:00)"
    
    return True, f"Market open: {current_time.strftime('%H:%M')} ET"


def remove_outliers(values):
    """Remove statistical outliers from a list of values"""
    if len(values) <= 2:
        return values
    
    mean_val = sum(values) / len(values)
    std_dev = (sum((x - mean_val) ** 2 for x in values) / len(values)) ** 0.5
    
    # Keep values within 3 standard deviations
    filtered_values = []
    for value in values:
        if abs(value - mean_val) <= 3 * std_dev:
            filtered_values.append(value)
    
    return filtered_values if filtered_values else values


def calculate_confidence_level(data_sources, target_prices, analyst_counts):
    """Calculate confidence level (0-10) based on data quality and consistency"""
    confidence = 0
    
    # Points for number of data sources
    confidence += min(len(data_sources) * 2, 6)  # Max 6 points for sources
    
    # Points for number of price targets
    if target_prices:
        confidence += min(len(target_prices), 3)  # Max 3 points for targets
        
        # Bonus for consistent targets (low variance)
        if len(target_prices) > 1:
            mean_target = sum(target_prices) / len(target_prices)
            variance = sum((x - mean_target) ** 2 for x in target_prices) / len(target_prices)
            coefficient_of_variation = (variance ** 0.5) / mean_target if mean_target > 0 else 1
            
            if coefficient_of_variation < 0.1:  # Less than 10% variation
                confidence += 1
    
    # Points for analyst coverage
    max_analysts = max(analyst_counts) if analyst_counts else 0
    if max_analysts >= 10:
        confidence += 2
    elif max_analysts >= 5:
        confidence += 1
    
    return min(confidence, 10)  # Cap at 10


def format_number(num):
    """Format numbers for display (e.g., $1.23B, $456.78M)"""
    if num is None or num == 'N/A':
        return 'N/A'
    if isinstance(num, (int, float)):
        if abs(num) >= 1e9:
            return f"${num/1e9:.2f}B"
        elif abs(num) >= 1e6:
            return f"${num/1e6:.2f}M"
        else:
            return f"${num:.2f}"
    return str(num)


def format_percentage(num):
    """Format percentages for display"""
    if num is None or num == 'N/A':
        return 'N/A'
    if isinstance(num, (int, float)):
        return f"{num*100:.1f}%"
    return str(num)


def calculate_portfolio_value(current_prices):
    """Calculate total portfolio value - returns 0 since no positions tracked"""
    return 0.0