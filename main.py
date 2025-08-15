#!/usr/bin/env python3
"""
Simple Portfolio Monitor - Cloud Function
Monitors your stocks and sends email alerts when buy/sell targets are hit
"""

import functions_framework
import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
import json
import os
import requests
from bs4 import BeautifulSoup
import re
from google.cloud import firestore
import logging
import anthropic
import pytz

# Your portfolio targets from your spreadsheet
PORTFOLIO = {
    'ASML': {
        'buy_target': 633.00, 
        'sell_target': 987.00
    },
    'SNY': {
        'buy_target': 45.00, 
        'sell_target': 62.00
    },
    'JD': {
        'buy_target': 26.50, 
        'sell_target': 41.00
    },
    'UNH': {
        'buy_target': 300.00, 
        'sell_target': 388.00
    },
    'XOM': {
        'buy_target': 110.00, 
        'sell_target': 130.00
    }
}

# US Stock Market Holidays (major ones that affect trading)
US_MARKET_HOLIDAYS_2025 = [
    date(2025, 1, 1),   # New Year's Day
    date(2025, 1, 20),  # Martin Luther King Jr. Day
    date(2025, 2, 17),  # Presidents' Day
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 26),  # Memorial Day
    date(2025, 6, 19),  # Juneteenth
    date(2025, 7, 4),   # Independence Day
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

def is_market_open():
    """
    Check if the US stock market is currently open
    Returns: (is_open: bool, reason: str)
    """
    # Get current time in Eastern Time (market timezone)
    et_tz = pytz.timezone('America/New_York')
    now_et = datetime.now(et_tz)
    current_date = now_et.date()
    current_time = now_et.time()
    
    # Check if today is a weekend (Saturday = 5, Sunday = 6)
    if now_et.weekday() >= 5:
        return False, f"Weekend (day {now_et.weekday()})"
    
    # Check if today is a market holiday
    if current_date in ALL_MARKET_HOLIDAYS:
        return False, f"Market holiday: {current_date}"
    
    # Check if current time is within market hours (9:00 AM - 5:00 PM ET)
    market_open = current_time.replace(second=0, microsecond=0) >= datetime.strptime("09:00", "%H:%M").time()
    market_close = current_time.replace(second=0, microsecond=0) <= datetime.strptime("17:00", "%H:%M").time()
    
    if not (market_open and market_close):
        return False, f"Outside market hours: {current_time.strftime('%H:%M')} ET (market: 9:00-17:00)"
    
    return True, f"Market open: {current_time.strftime('%H:%M')} ET"

@functions_framework.http
def portfolio_monitor(request):
    """
    Enhanced main function that checks portfolio and sends alerts using dynamic targets
    Only runs during market hours (9 AM - 5 PM ET, Mon-Fri, excluding holidays)
    """
    
    try:
        print("🔄 Starting enhanced portfolio check...")
        
        # Check if market is open first
        market_open, reason = is_market_open()
        
        if not market_open:
            print(f"⏸️ Market closed: {reason}")
            return {
                "status": "skipped",
                "timestamp": datetime.now().isoformat(),
                "reason": reason,
                "message": "Portfolio monitoring skipped - market closed"
            }
        
        print(f"✅ Market is open: {reason}")
        
        # Load current targets from Firestore (with fallback to hardcoded)
        dynamic_targets = load_targets_from_firestore()
        
        # Get current stock prices
        current_prices = get_stock_prices()
        
        # Check for buy/sell alerts with dynamic targets
        alerts = check_enhanced_alerts(current_prices, dynamic_targets)
        
        # Send email if there are alerts
        if alerts:
            send_enhanced_email(alerts, current_prices, dynamic_targets)
            print(f"📧 Enhanced email sent with {len(alerts)} alerts")
        else:
            print("✅ No alerts - all stocks within normal ranges")
        
        # Calculate total portfolio value (not tracked)
        total_value = 0.0
        
        # Count high confidence targets
        high_confidence_targets = sum(1 for target in dynamic_targets.values() 
                                     if target['confidence_score'] >= 7)
        
        # Return success response
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "prices": current_prices,
            "alerts": alerts,
            "portfolio_value": total_value,
            "dynamic_targets_loaded": True,
            "high_confidence_targets": high_confidence_targets,
            "targets_summary": {ticker: {
                'buy_target': target['buy_target'],
                'sell_target': target['sell_target'],
                'confidence': target['confidence_score']
            } for ticker, target in dynamic_targets.items()},
            "message": f"Checked {len(current_prices)} stocks with dynamic targets, found {len(alerts)} alerts"
        }
        
    except Exception as e:
        error_msg = f"Enhanced portfolio monitor error: {str(e)}"
        print(f"❌ {error_msg}")
        
        return {
            "status": "error",
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        }

def get_enhanced_yahoo_data(ticker):
    """Get comprehensive Yahoo Finance data including analyst targets and financials"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Current price (multiple fallbacks)
        current_price = (info.get('currentPrice') or 
                        info.get('regularMarketPrice') or 
                        info.get('ask') or 
                        info.get('bid'))
        
        # Analyst targets
        analyst_data = {
            'target_mean': info.get('targetMeanPrice'),
            'target_high': info.get('targetHighPrice'),
            'target_low': info.get('targetLowPrice'),
            'recommendation_mean': info.get('recommendationMean'),  # 1=Strong Buy, 5=Strong Sell
            'analyst_count': info.get('numberOfAnalystOpinions')
        }
        
        # Financial metrics for Claude analysis
        financials = {
            'current_price': current_price,
            'market_cap': info.get('marketCap'),
            'pe_ratio': info.get('trailingPE'),
            'forward_pe': info.get('forwardPE'),
            'peg_ratio': info.get('pegRatio'),
            'price_to_book': info.get('priceToBook'),
            'debt_to_equity': info.get('debtToEquity'),
            'return_on_equity': info.get('returnOnEquity'),
            'revenue_growth': info.get('revenueGrowth'),
            'earnings_growth': info.get('earningsGrowth'),
            'profit_margins': info.get('profitMargins'),
            'operating_margins': info.get('operatingMargins'),
            'free_cash_flow': info.get('freeCashflow'),
            'total_cash': info.get('totalCash'),
            'total_debt': info.get('totalDebt'),
            'enterprise_value': info.get('enterpriseValue'),
            'ebitda': info.get('ebitda'),
            'revenue': info.get('totalRevenue'),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            '52_week_high': info.get('fiftyTwoWeekHigh'),
            '52_week_low': info.get('fiftyTwoWeekLow'),
            'beta': info.get('beta'),
            'dividend_yield': info.get('dividendYield')
        }
        
        return {
            'ticker': ticker,
            'analyst_data': analyst_data,
            'financials': financials,
            'data_quality': 'high' if current_price and analyst_data.get('target_mean') else 'medium'
        }
        
    except Exception as e:
        print(f"  ❌ Error fetching enhanced data for {ticker}: {e}")
        return {
            'ticker': ticker,
            'analyst_data': {},
            'financials': {'current_price': None},
            'data_quality': 'low'
        }

def get_stock_prices():
    """Get current prices for all stocks (backward compatibility)"""
    prices = {}
    
    for ticker in PORTFOLIO.keys():
        try:
            print(f"📊 Fetching {ticker}...")
            enhanced_data = get_enhanced_yahoo_data(ticker)
            current_price = enhanced_data['financials']['current_price']
            
            if current_price and current_price > 0:
                prices[ticker] = round(current_price, 2)
                print(f"  ✅ {ticker}: ${current_price:.2f}")
            else:
                print(f"  ⚠️ Could not get price for {ticker}")
                
        except Exception as e:
            print(f"  ❌ Error fetching {ticker}: {e}")
    
    return prices

def scrape_marketwatch_consensus(ticker):
    """Scrape MarketWatch for analyst consensus data"""
    try:
        url = f"https://www.marketwatch.com/investing/stock/{ticker}/analystestimates"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract consensus target price
        consensus_target = None
        analyst_count = None
        
        # Look for price target in various possible locations
        price_target_elements = soup.find_all(['span', 'div', 'td'], 
                                            text=re.compile(r'\$[\d,]+\.?\d*'))
        
        for element in price_target_elements:
            text = element.get_text()
            if 'price target' in text.lower() or 'consensus' in text.lower():
                # Extract price using regex
                price_match = re.search(r'\$([0-9,]+\.?\d*)', text)
                if price_match:
                    consensus_target = float(price_match.group(1).replace(',', ''))
                    break
        
        # Extract number of analysts
        analyst_elements = soup.find_all(text=re.compile(r'\d+\s*analyst'))
        for element in analyst_elements:
            analyst_match = re.search(r'(\d+)\s*analyst', element)
            if analyst_match:
                analyst_count = int(analyst_match.group(1))
                break
        
        # Extract rating distribution (Buy/Hold/Sell)
        rating_distribution = {'buy': 0, 'hold': 0, 'sell': 0}
        
        # Look for rating counts
        rating_elements = soup.find_all(['td', 'span'], text=re.compile(r'\d+'))
        buy_keywords = ['buy', 'strong buy']
        hold_keywords = ['hold', 'neutral']
        sell_keywords = ['sell', 'strong sell']
        
        for element in rating_elements:
            parent = element.parent
            if parent:
                parent_text = parent.get_text().lower()
                element_text = element.get_text()
                
                if any(keyword in parent_text for keyword in buy_keywords):
                    try:
                        rating_distribution['buy'] = int(element_text)
                    except ValueError:
                        pass
                elif any(keyword in parent_text for keyword in hold_keywords):
                    try:
                        rating_distribution['hold'] = int(element_text)
                    except ValueError:
                        pass
                elif any(keyword in parent_text for keyword in sell_keywords):
                    try:
                        rating_distribution['sell'] = int(element_text)
                    except ValueError:
                        pass
        
        return {
            'source': 'marketwatch',
            'ticker': ticker,
            'consensus_target': consensus_target,
            'analyst_count': analyst_count,
            'rating_distribution': rating_distribution,
            'data_quality': 'high' if consensus_target and analyst_count else 'low',
            'scraped_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"  ⚠️ MarketWatch scraping failed for {ticker}: {e}")
        return {
            'source': 'marketwatch',
            'ticker': ticker,
            'consensus_target': None,
            'analyst_count': None,
            'rating_distribution': {'buy': 0, 'hold': 0, 'sell': 0},
            'data_quality': 'failed',
            'error': str(e),
            'scraped_at': datetime.now().isoformat()
        }

def scrape_yahoo_web_targets(ticker):
    """Scrape Yahoo Finance web page for additional analyst data"""
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}/analysis"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract price targets from analyst section
        target_elements = soup.find_all(['span', 'div'], 
                                      text=re.compile(r'\d+\.\d+'))
        
        targets = {'mean': None, 'high': None, 'low': None}
        
        # Look for specific target labels
        for element in target_elements:
            parent_text = element.parent.get_text().lower() if element.parent else ""
            value_text = element.get_text()
            
            try:
                value = float(value_text)
                if 'mean target' in parent_text or 'average' in parent_text:
                    targets['mean'] = value
                elif 'high target' in parent_text or 'highest' in parent_text:
                    targets['high'] = value
                elif 'low target' in parent_text or 'lowest' in parent_text:
                    targets['low'] = value
            except ValueError:
                continue
        
        return {
            'source': 'yahoo_web',
            'ticker': ticker,
            'targets': targets,
            'data_quality': 'medium' if any(targets.values()) else 'low',
            'scraped_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"  ⚠️ Yahoo web scraping failed for {ticker}: {e}")
        return {
            'source': 'yahoo_web',
            'ticker': ticker,
            'targets': {'mean': None, 'high': None, 'low': None},
            'data_quality': 'failed',
            'error': str(e),
            'scraped_at': datetime.now().isoformat()
        }

def collect_analyst_data(ticker):
    """Collect analyst data from multiple free sources"""
    print(f"🔍 Collecting analyst data for {ticker}...")
    
    data_sources = {}
    
    # Source 1: Enhanced Yahoo Finance API
    try:
        yahoo_data = get_enhanced_yahoo_data(ticker)
        if yahoo_data['data_quality'] in ['high', 'medium']:
            data_sources['yahoo_api'] = yahoo_data
            print(f"  ✅ Yahoo API: {yahoo_data['data_quality']} quality")
        else:
            print(f"  ⚠️ Yahoo API: {yahoo_data['data_quality']} quality")
    except Exception as e:
        print(f"  ❌ Yahoo API failed: {e}")
    
    # Source 2: MarketWatch scraping
    try:
        mw_data = scrape_marketwatch_consensus(ticker)
        if mw_data['data_quality'] in ['high', 'medium']:
            data_sources['marketwatch'] = mw_data
            print(f"  ✅ MarketWatch: {mw_data['data_quality']} quality")
        else:
            print(f"  ⚠️ MarketWatch: {mw_data['data_quality']} quality")
    except Exception as e:
        print(f"  ❌ MarketWatch failed: {e}")
    
    # Source 3: Yahoo web scraping (backup)
    try:
        yahoo_web_data = scrape_yahoo_web_targets(ticker)
        if yahoo_web_data['data_quality'] in ['high', 'medium']:
            data_sources['yahoo_web'] = yahoo_web_data
            print(f"  ✅ Yahoo Web: {yahoo_web_data['data_quality']} quality")
        else:
            print(f"  ⚠️ Yahoo Web: {yahoo_web_data['data_quality']} quality")
    except Exception as e:
        print(f"  ❌ Yahoo Web failed: {e}")
    
    return aggregate_analyst_data(ticker, data_sources)

def aggregate_analyst_data(ticker, data_sources):
    """Aggregate and validate analyst data from multiple sources"""
    
    if not data_sources:
        return {
            'ticker': ticker,
            'consensus_target': None,
            'target_range': {'high': None, 'low': None},
            'analyst_count': None,
            'recommendation_score': None,
            'confidence_level': 0,
            'data_sources': [],
            'aggregated_at': datetime.now().isoformat(),
            'quality': 'failed'
        }
    
    # Collect all target prices
    target_prices = []
    analyst_counts = []
    recommendation_scores = []
    
    # Extract data from each source
    for source_name, source_data in data_sources.items():
        if source_name == 'yahoo_api':
            analyst_data = source_data['analyst_data']
            if analyst_data.get('target_mean'):
                target_prices.append(analyst_data['target_mean'])
            if analyst_data.get('target_high'):
                target_prices.append(analyst_data['target_high'])
            if analyst_data.get('target_low'):
                target_prices.append(analyst_data['target_low'])
            if analyst_data.get('analyst_count'):
                analyst_counts.append(analyst_data['analyst_count'])
            if analyst_data.get('recommendation_mean'):
                recommendation_scores.append(analyst_data['recommendation_mean'])
                
        elif source_name == 'marketwatch':
            if source_data.get('consensus_target'):
                target_prices.append(source_data['consensus_target'])
            if source_data.get('analyst_count'):
                analyst_counts.append(source_data['analyst_count'])
                
        elif source_name == 'yahoo_web':
            targets = source_data.get('targets', {})
            for target_type, value in targets.items():
                if value:
                    target_prices.append(value)
    
    # Remove outliers (beyond 3 standard deviations)
    if len(target_prices) > 2:
        target_prices = remove_outliers(target_prices)
    
    # Calculate aggregated metrics
    consensus_target = None
    target_high = None
    target_low = None
    
    if target_prices:
        target_prices = [p for p in target_prices if p and p > 0]
        if target_prices:
            consensus_target = round(sum(target_prices) / len(target_prices), 2)
            target_high = round(max(target_prices), 2)
            target_low = round(min(target_prices), 2)
    
    # Aggregate analyst count
    total_analysts = max(analyst_counts) if analyst_counts else None
    
    # Aggregate recommendation score (1=Strong Buy, 5=Strong Sell)
    avg_recommendation = None
    if recommendation_scores:
        avg_recommendation = round(sum(recommendation_scores) / len(recommendation_scores), 2)
    
    # Calculate confidence level (0-10)
    confidence = calculate_confidence_level(data_sources, target_prices, analyst_counts)
    
    # Determine overall quality
    quality = 'high' if confidence >= 7 else 'medium' if confidence >= 4 else 'low'
    
    return {
        'ticker': ticker,
        'consensus_target': consensus_target,
        'target_range': {'high': target_high, 'low': target_low},
        'analyst_count': total_analysts,
        'recommendation_score': avg_recommendation,
        'confidence_level': confidence,
        'data_sources': list(data_sources.keys()),
        'raw_targets': target_prices,
        'aggregated_at': datetime.now().isoformat(),
        'quality': quality
    }

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

def create_claude_analysis_prompt(ticker, financials, analyst_data):
    """Create comprehensive prompt for Claude analysis"""
    
    # Format financial data
    current_price = financials.get('current_price', 'N/A')
    pe_ratio = financials.get('pe_ratio', 'N/A')
    forward_pe = financials.get('forward_pe', 'N/A')
    peg_ratio = financials.get('peg_ratio', 'N/A')
    debt_equity = financials.get('debt_to_equity', 'N/A')
    roe = financials.get('return_on_equity', 'N/A')
    revenue_growth = financials.get('revenue_growth', 'N/A')
    earnings_growth = financials.get('earnings_growth', 'N/A')
    profit_margins = financials.get('profit_margins', 'N/A')
    free_cash_flow = financials.get('free_cash_flow', 'N/A')
    market_cap = financials.get('market_cap', 'N/A')
    sector = financials.get('sector', 'N/A')
    week_52_high = financials.get('52_week_high', 'N/A')
    week_52_low = financials.get('52_week_low', 'N/A')
    beta = financials.get('beta', 'N/A')
    
    # Format analyst data
    consensus_target = analyst_data.get('consensus_target', 'N/A')
    target_high = analyst_data.get('target_range', {}).get('high', 'N/A')
    target_low = analyst_data.get('target_range', {}).get('low', 'N/A')
    analyst_count = analyst_data.get('analyst_count', 'N/A')
    recommendation = analyst_data.get('recommendation_score', 'N/A')
    confidence = analyst_data.get('confidence_level', 'N/A')
    
    # Convert numbers to readable format
    def format_number(num):
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
        if num is None or num == 'N/A':
            return 'N/A'
        if isinstance(num, (int, float)):
            return f"{num*100:.1f}%"
        return str(num)
    
    prompt = f"""
Analyze {ticker} for 12-month price targets using fundamental analysis:

CURRENT MARKET DATA:
- Current Price: {format_number(current_price)}
- Market Cap: {format_number(market_cap)}
- Sector: {sector}
- 52-Week Range: {format_number(week_52_low)} - {format_number(week_52_high)}
- Beta: {beta}

VALUATION METRICS:
- P/E Ratio: {pe_ratio}
- Forward P/E: {forward_pe}
- PEG Ratio: {peg_ratio}
- Price/Book: {financials.get('price_to_book', 'N/A')}

FINANCIAL HEALTH:
- Debt/Equity: {debt_equity}
- Return on Equity: {format_percentage(roe)}
- Profit Margins: {format_percentage(profit_margins)}
- Free Cash Flow: {format_number(free_cash_flow)}

GROWTH METRICS:
- Revenue Growth: {format_percentage(revenue_growth)}
- Earnings Growth: {format_percentage(earnings_growth)}

ANALYST CONSENSUS:
- Average Target: {format_number(consensus_target)}
- Target Range: {format_number(target_low)} - {format_number(target_high)}
- Analyst Coverage: {analyst_count} analysts
- Recommendation Score: {recommendation} (1=Strong Buy, 5=Strong Sell)
- Data Confidence: {confidence}/10

Based on this data, provide:

1. BUY TARGET: Conservative entry point for new positions
2. SELL TARGET: Profit-taking level for existing positions
3. CONFIDENCE: Rating from 1-10 based on analysis quality
4. KEY CATALYST: Most important factor driving your targets
5. RISK FACTOR: Primary concern for the investment

Requirements:
- Use DCF-style thinking: focus on intrinsic value vs current price
- Consider analyst consensus but form independent opinion
- Factor in sector trends and market conditions
- Provide targets that are actionable for 12-month timeframe
- Be conservative on buy targets, optimistic but realistic on sell targets

Format your response as:
BUY TARGET: $XXX.XX
SELL TARGET: $XXX.XX
CONFIDENCE: X/10
KEY CATALYST: [One sentence explanation]
RISK FACTOR: [One sentence explanation]
"""
    
    return prompt

def analyze_with_claude(ticker, financials, analyst_data):
    """Use Claude API to analyze stock and generate buy/sell targets"""
    try:
        # Get Claude API key from environment
        claude_api_key = os.environ.get('CLAUDE_API_KEY')
        if not claude_api_key:
            print(f"  ❌ No Claude API key found for {ticker}")
            return None
            
        # Initialize Claude client
        client = anthropic.Anthropic(api_key=claude_api_key)
        
        # Create analysis prompt
        prompt = create_claude_analysis_prompt(ticker, financials, analyst_data)
        
        print(f"  🤖 Analyzing {ticker} with Claude...")
        
        # Make API call to Claude
        message = client.messages.create(
            model="claude-3-haiku-20240307",  # Use faster, cheaper model
            max_tokens=500,
            temperature=0.3,  # Lower temperature for more consistent analysis
            messages=[
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
        )
        
        # Parse Claude response
        response_text = message.content[0].text
        return parse_claude_response(ticker, response_text, analyst_data)
        
    except Exception as e:
        print(f"  ❌ Claude analysis failed for {ticker}: {e}")
        return None

def parse_claude_response(ticker, response_text, analyst_data):
    """Parse Claude's response to extract targets and reasoning"""
    try:
        # Extract targets using regex
        buy_target_match = re.search(r'BUY TARGET:\s*\$?([0-9,]+\.?[0-9]*)', response_text, re.IGNORECASE)
        sell_target_match = re.search(r'SELL TARGET:\s*\$?([0-9,]+\.?[0-9]*)', response_text, re.IGNORECASE)
        confidence_match = re.search(r'CONFIDENCE:\s*([0-9]+)', response_text, re.IGNORECASE)
        catalyst_match = re.search(r'KEY CATALYST:\s*([^\n]+)', response_text, re.IGNORECASE)
        risk_match = re.search(r'RISK FACTOR:\s*([^\n]+)', response_text, re.IGNORECASE)
        
        # Extract and validate targets
        buy_target = None
        sell_target = None
        
        if buy_target_match:
            try:
                buy_target = float(buy_target_match.group(1).replace(',', ''))
            except ValueError:
                pass
                
        if sell_target_match:
            try:
                sell_target = float(sell_target_match.group(1).replace(',', ''))
            except ValueError:
                pass
        
        # Extract confidence score
        confidence_score = 5  # Default
        if confidence_match:
            try:
                confidence_score = int(confidence_match.group(1))
                confidence_score = max(1, min(confidence_score, 10))  # Clamp to 1-10
            except ValueError:
                pass
        
        # Extract reasoning
        catalyst = catalyst_match.group(1).strip() if catalyst_match else "Fundamental analysis"
        risk = risk_match.group(1).strip() if risk_match else "Market volatility"
        
        # Validate targets make sense
        if buy_target and sell_target:
            if sell_target <= buy_target:
                print(f"  ⚠️ Invalid targets for {ticker}: sell ${sell_target} <= buy ${buy_target}")
                # Try to fix by adjusting
                sell_target = buy_target * 1.15  # 15% minimum upside
        
        return {
            'ticker': ticker,
            'buy_target': round(buy_target, 2) if buy_target else None,
            'sell_target': round(sell_target, 2) if sell_target else None,
            'confidence_score': confidence_score,
            'key_catalyst': catalyst,
            'risk_factor': risk,
            'analyst_consensus': analyst_data.get('consensus_target'),
            'claude_response': response_text,
            'generated_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"  ❌ Failed to parse Claude response for {ticker}: {e}")
        return {
            'ticker': ticker,
            'buy_target': None,
            'sell_target': None,
            'confidence_score': 1,
            'key_catalyst': "Analysis failed",
            'risk_factor': "Unable to analyze",
            'error': str(e),
            'generated_at': datetime.now().isoformat()
        }

@functions_framework.http
def monthly_target_update(request):
    """Monthly function to update portfolio targets using Claude analysis"""
    
    try:
        print("🔄 Starting monthly target update...")
        
        # Initialize Firestore client
        db = firestore.Client()
        
        updated_targets = {}
        total_cost = 0
        
        # Process each stock in portfolio
        for ticker in PORTFOLIO.keys():
            try:
                print(f"\n📊 Processing {ticker}...")
                
                # Step 1: Collect analyst data from free sources
                analyst_data = collect_analyst_data(ticker)
                
                if analyst_data['quality'] == 'failed':
                    print(f"  ⚠️ Skipping {ticker} - no analyst data available")
                    continue
                
                # Step 2: Get enhanced financial data
                enhanced_data = get_enhanced_yahoo_data(ticker)
                financials = enhanced_data['financials']
                
                if not financials.get('current_price'):
                    print(f"  ⚠️ Skipping {ticker} - no price data available")
                    continue
                
                # Step 3: Analyze with Claude
                claude_analysis = analyze_with_claude(ticker, financials, analyst_data)
                
                if not claude_analysis or not claude_analysis['buy_target']:
                    print(f"  ⚠️ Claude analysis failed for {ticker}")
                    continue
                
                # Step 4: Store results in Firestore
                target_doc = {
                    'ticker': ticker,
                    'buy_target': claude_analysis['buy_target'],
                    'sell_target': claude_analysis['sell_target'],
                    'confidence_score': claude_analysis['confidence_score'],
                    'key_catalyst': claude_analysis['key_catalyst'],
                    'risk_factor': claude_analysis['risk_factor'],
                    'analyst_consensus': analyst_data['consensus_target'],
                    'analyst_confidence': analyst_data['confidence_level'],
                    'current_price': financials['current_price'],
                    'sector': financials.get('sector'),
                    'updated_at': datetime.now().isoformat(),
                    'data_sources': analyst_data['data_sources'],
                    'pe_ratio': financials.get('pe_ratio'),
                    'market_cap': financials.get('market_cap')
                }
                
                # Save to Firestore
                db.collection('portfolio_targets').document(ticker).set(target_doc)
                updated_targets[ticker] = target_doc
                total_cost += 0.50  # Approximate Claude API cost per stock
                
                print(f"  ✅ {ticker} targets updated: Buy ${claude_analysis['buy_target']}, Sell ${claude_analysis['sell_target']}")
                
            except Exception as e:
                print(f"  ❌ Failed to update {ticker}: {e}")
                continue
        
        # Send summary email
        if updated_targets:
            send_target_update_email(updated_targets, total_cost)
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "updated_stocks": len(updated_targets),
            "estimated_cost": f"${total_cost:.2f}",
            "targets": {ticker: {
                'buy_target': data['buy_target'],
                'sell_target': data['sell_target'],
                'confidence': data['confidence_score']
            } for ticker, data in updated_targets.items()},
            "message": f"Updated targets for {len(updated_targets)} stocks"
        }
        
    except Exception as e:
        error_msg = f"Monthly target update error: {str(e)}"
        print(f"❌ {error_msg}")
        
        return {
            "status": "error",
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        }

def send_target_update_email(updated_targets, estimated_cost):
    """Send email notification about updated targets"""
    try:
        # Email configuration
        sender_email = os.environ.get('GMAIL_USER', 'nbu864@gmail.com')
        sender_password = os.environ.get('GMAIL_PASSWORD', 'your_app_password')
        recipient = 'nbu864@gmail.com'
        
        subject = f"🎯 Portfolio Targets Updated - {len(updated_targets)} stocks"
        
        # Create HTML email body
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <h2 style="color: #1a73e8;">🎯 Monthly Target Update</h2>
            <p><strong>Update Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')}</p>
            <p><strong>Stocks Analyzed:</strong> {len(updated_targets)}</p>
            <p><strong>Estimated Cost:</strong> ${estimated_cost:.2f}</p>
            
            <h3 style="color: #34a853;">📊 New Price Targets</h3>
            <table style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f1f3f4;">
                    <th style="border: 1px solid #ddd; padding: 8px;">Stock</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Current Price</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Buy Target</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Sell Target</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Confidence</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Key Catalyst</th>
                </tr>
        """
        
        for ticker, data in updated_targets.items():
            current_price = data['current_price']
            buy_target = data['buy_target']
            sell_target = data['sell_target']
            confidence = data['confidence_score']
            catalyst = data['key_catalyst']
            
            # Color code based on current vs buy target
            if current_price <= buy_target * 1.05:  # Within 5% of buy target
                row_color = "#e8f5e8"  # Light green
            elif current_price >= sell_target * 0.95:  # Within 5% of sell target
                row_color = "#fce8e6"  # Light red
            else:
                row_color = "white"
            
            html_body += f"""
                <tr style="background-color: {row_color};">
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>{ticker}</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${current_price:.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${buy_target:.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${sell_target:.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{confidence}/10</td>
                    <td style="border: 1px solid #ddd; padding: 8px; font-size: 12px;">{catalyst[:50]}...</td>
                </tr>
            """
        
        html_body += """
            </table>
            
            <h3 style="color: #1a73e8;">💡 Analysis Summary</h3>
            <ul>
        """
        
        # Add analysis insights
        buy_opportunities = sum(1 for data in updated_targets.values() 
                               if data['current_price'] <= data['buy_target'] * 1.10)
        sell_opportunities = sum(1 for data in updated_targets.values() 
                                if data['current_price'] >= data['sell_target'] * 0.90)
        high_confidence = sum(1 for data in updated_targets.values() 
                             if data['confidence_score'] >= 7)
        
        html_body += f"""
                <li><strong>{buy_opportunities}</strong> stocks near/below buy targets</li>
                <li><strong>{sell_opportunities}</strong> stocks near/above sell targets</li>
                <li><strong>{high_confidence}</strong> stocks with high confidence scores (7+/10)</li>
                <li>Average confidence level: <strong>{sum(data['confidence_score'] for data in updated_targets.values()) / len(updated_targets):.1f}/10</strong></li>
            </ul>
            
            <hr style="margin: 20px 0;">
            <p style="color: #666; font-size: 12px;">
                🤖 Automated target update powered by Claude AI analysis + free analyst data.<br>
                Next update scheduled for next month. Daily monitoring continues with new targets.<br>
                Data sources: Yahoo Finance API, MarketWatch, web scraping
            </p>
        </body>
        </html>
        """
        
        # Send email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient
        msg.attach(MIMEText(html_body, 'html'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        print(f"📧 Target update email sent successfully to {recipient}")
        
    except Exception as e:
        print(f"❌ Failed to send target update email: {e}")

def load_targets_from_firestore():
    """Load current portfolio targets from Firestore database"""
    try:
        db = firestore.Client()
        targets_collection = db.collection('portfolio_targets')
        
        portfolio_targets = {}
        
        for ticker in PORTFOLIO.keys():
            try:
                doc = targets_collection.document(ticker).get()
                
                if doc.exists:
                    data = doc.to_dict()
                    portfolio_targets[ticker] = {
                        'buy_target': data.get('buy_target'),
                        'sell_target': data.get('sell_target'),
                        'confidence_score': data.get('confidence_score', 5),
                        'key_catalyst': data.get('key_catalyst', 'N/A'),
                        'risk_factor': data.get('risk_factor', 'N/A'),
                        'updated_at': data.get('updated_at'),
                        'analyst_consensus': data.get('analyst_consensus')
                    }
                    print(f"  📊 Loaded {ticker}: Buy ${data.get('buy_target')}, Sell ${data.get('sell_target')}")
                else:
                    # Fallback to hardcoded targets if no Firestore data
                    portfolio_targets[ticker] = {
                        'buy_target': PORTFOLIO[ticker]['buy_target'],
                        'sell_target': PORTFOLIO[ticker]['sell_target'],
                        'confidence_score': 3,  # Default low confidence
                        'key_catalyst': 'Hardcoded target',
                        'risk_factor': 'No recent analysis',
                        'updated_at': None,
                        'analyst_consensus': None
                    }
                    print(f"  ⚠️ Using fallback targets for {ticker}")
                    
            except Exception as e:
                print(f"  ❌ Error loading {ticker} from Firestore: {e}")
                # Use hardcoded fallback
                portfolio_targets[ticker] = {
                    'buy_target': PORTFOLIO[ticker]['buy_target'],
                    'sell_target': PORTFOLIO[ticker]['sell_target'],
                    'confidence_score': 3,
                    'key_catalyst': 'Hardcoded target',
                    'risk_factor': 'Database error',
                    'updated_at': None,
                    'analyst_consensus': None
                }
        
        print(f"✅ Loaded targets for {len(portfolio_targets)} stocks")
        return portfolio_targets
        
    except Exception as e:
        print(f"❌ Failed to connect to Firestore: {e}")
        print("⚠️ Using hardcoded portfolio targets as fallback")
        
        # Return hardcoded targets as fallback
        fallback_targets = {}
        for ticker, config in PORTFOLIO.items():
            fallback_targets[ticker] = {
                'buy_target': config['buy_target'],
                'sell_target': config['sell_target'],
                'confidence_score': 3,
                'key_catalyst': 'Hardcoded target',
                'risk_factor': 'Database unavailable',
                'updated_at': None,
                'analyst_consensus': None
            }
        
        return fallback_targets

def check_enhanced_alerts(current_prices, dynamic_targets):
    """Enhanced alert checking with dynamic targets and confidence scores"""
    alerts = []
    
    for ticker, price in current_prices.items():
        if price <= 0:
            continue
            
        target_config = dynamic_targets.get(ticker)
        if not target_config:
            continue
            
        buy_target = target_config['buy_target']
        sell_target = target_config['sell_target']
        confidence = target_config['confidence_score']
        catalyst = target_config['key_catalyst']
        
        # Confidence indicator
        confidence_icon = "🔥" if confidence >= 8 else "⭐" if confidence >= 6 else "💡"
        
        # BUY SIGNAL: Price at or below buy target
        if price <= buy_target:
            alert = f"🟢 BUY SIGNAL: {ticker} hit ${price:.2f} (target ≤${buy_target:.2f}) {confidence_icon} Confidence: {confidence}/10. Catalyst: {catalyst[:50]}..."
            alerts.append({
                'type': 'BUY',
                'ticker': ticker,
                'current_price': price,
                'target_price': buy_target,
                'confidence': confidence,
                'catalyst': catalyst,
                'message': alert
            })
            print(f"  🟢 BUY alert: {ticker} (confidence {confidence}/10)")
        
        # SELL SIGNAL: Price at or above sell target
        elif price >= sell_target:
            profit_pct = ((price - buy_target) / buy_target) * 100
            alert = f"🔴 SELL SIGNAL: {ticker} hit ${price:.2f} (target ≥${sell_target:.2f}) {confidence_icon} Est. gain: {profit_pct:.1f}%. Confidence: {confidence}/10."
            alerts.append({
                'type': 'SELL',
                'ticker': ticker,
                'current_price': price,
                'target_price': sell_target,
                'confidence': confidence,
                'profit_pct': profit_pct,
                'message': alert
            })
            print(f"  🔴 SELL alert: {ticker} (confidence {confidence}/10)")
        
        # WARNING: Close to buy target (within 5%)
        else:
            buy_distance = abs(price - buy_target) / buy_target
            if buy_distance <= 0.05 and price > buy_target:
                distance_pct = ((price - buy_target) / buy_target) * 100
                alert = f"🟡 WATCH: {ticker} at ${price:.2f}, only {distance_pct:.1f}% above buy target ${buy_target:.2f}. {confidence_icon} Confidence: {confidence}/10"
                alerts.append({
                    'type': 'WATCH',
                    'ticker': ticker,
                    'current_price': price,
                    'target_price': buy_target,
                    'confidence': confidence,
                    'distance_pct': distance_pct,
                    'message': alert
                })
                print(f"  🟡 WATCH alert: {ticker} (confidence {confidence}/10)")
    
    return alerts

def check_alerts(current_prices):
    """Legacy alert checking function (backward compatibility)"""
    alerts = []
    
    for ticker, price in current_prices.items():
        if price <= 0:
            continue
            
        config = PORTFOLIO[ticker]
        buy_target = config['buy_target']
        sell_target = config['sell_target']
        
        # BUY SIGNAL: Price at or below buy target
        if price <= buy_target:
            alert = f"🟢 BUY SIGNAL: {ticker} hit ${price:.2f} (target ≤${buy_target:.2f}). Time to buy!"
            alerts.append(alert)
            print(f"  🟢 BUY alert: {ticker}")
        
        # SELL SIGNAL: Price at or above sell target
        elif price >= sell_target:
            profit_pct = ((price - buy_target) / buy_target) * 100
            alert = f"🔴 SELL SIGNAL: {ticker} hit ${price:.2f} (target ≥${sell_target:.2f}). Consider taking profits! Est. gain: {profit_pct:.1f}%"
            alerts.append(alert)
            print(f"  🔴 SELL alert: {ticker}")
        
        # WARNING: Close to buy target (within 3%)
        else:
            buy_distance = abs(price - buy_target) / buy_target
            if buy_distance <= 0.03 and price > buy_target:
                distance_pct = ((price - buy_target) / buy_target) * 100
                alert = f"🟡 WATCH: {ticker} at ${price:.2f}, only {distance_pct:.1f}% above buy target ${buy_target:.2f}"
                alerts.append(alert)
                print(f"  🟡 WATCH alert: {ticker}")
    
    return alerts

def calculate_portfolio_value(current_prices):
    """Calculate total portfolio value - returns 0 since no positions tracked"""
    return 0.0

def send_enhanced_email(alerts, current_prices, dynamic_targets):
    """Enhanced email alert with dynamic targets and confidence scores"""
    try:
        # Email configuration from environment variables
        sender_email = os.environ.get('GMAIL_USER', 'nbu864@gmail.com')
        sender_password = os.environ.get('GMAIL_PASSWORD', 'your_app_password')
        recipient = 'nbu864@gmail.com'
        
        # Count alert types
        buy_alerts = sum(1 for alert in alerts if alert['type'] == 'BUY')
        sell_alerts = sum(1 for alert in alerts if alert['type'] == 'SELL')
        watch_alerts = sum(1 for alert in alerts if alert['type'] == 'WATCH')
        
        # Create email subject with alert breakdown
        subject = f"🚨 Enhanced Portfolio Alert - {buy_alerts}🟢 {sell_alerts}🔴 {watch_alerts}🟡"
        
        # Portfolio value not tracked
        total_value = 0.0
        
        # Create enhanced HTML email body
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <h2 style="color: #1a73e8;">📊 Enhanced Portfolio Alert</h2>
            <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')}</p>
            <p><strong>Alert Summary:</strong> {buy_alerts} Buy, {sell_alerts} Sell, {watch_alerts} Watch</p>
            <p><strong>Monitoring:</strong> {len(current_prices)} stocks with AI-powered targets</p>
            
            <h3 style="color: #ea4335;">🚨 Priority Alerts ({len(alerts)})</h3>
            <ul>
        """
        
        # Add enhanced alerts with confidence indicators
        for alert in alerts:
            alert_type = alert['type']
            confidence = alert['confidence']
            
            if alert_type == "BUY":
                color = "#34a853"  # Green
                priority = "HIGH" if confidence >= 7 else "MEDIUM"
            elif alert_type == "SELL":
                color = "#ea4335"  # Red  
                priority = "HIGH" if confidence >= 7 else "MEDIUM"
            elif alert_type == "WATCH":
                color = "#fbbc04"  # Yellow
                priority = "LOW"
            else:
                color = "#1a73e8"  # Blue
                priority = "MEDIUM"
            
            confidence_bar = "🔥" * min(confidence, 10)  # Visual confidence indicator
            
            html_body += f"""
            <li style="color: {color}; margin: 10px 0; padding: 10px; background-color: {color}15; border-radius: 5px;">
                <strong>[{priority}]</strong> {alert['message']}<br>
                <small style="color: #666;">Confidence: {confidence_bar} ({confidence}/10)</small>
            </li>
            """
        
        html_body += """
            </ul>
            
            <h3 style="color: #1a73e8;">📈 Enhanced Stock Status</h3>
            <table style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f1f3f4;">
                    <th style="border: 1px solid #ddd; padding: 8px;">Stock</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Current</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Buy Target</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Sell Target</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Confidence</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Key Catalyst</th>
                </tr>
        """
        
        # Add enhanced stock table with confidence and catalysts
        for ticker, price in current_prices.items():
            target_config = dynamic_targets.get(ticker, {})
            buy_target = target_config.get('buy_target', 'N/A')
            sell_target = target_config.get('sell_target', 'N/A')
            confidence = target_config.get('confidence_score', 3)
            catalyst = target_config.get('key_catalyst', 'N/A')[:30] + "..."
            
            # Color code based on targets and confidence
            if price <= buy_target:
                row_color = "#e8f5e8"  # Light green
            elif price >= sell_target:
                row_color = "#fce8e6"  # Light red
            elif confidence >= 7:
                row_color = "#f0f9ff"  # Light blue for high confidence
            else:
                row_color = "white"
            
            # Confidence indicator
            confidence_icon = "🔥" if confidence >= 8 else "⭐" if confidence >= 6 else "💡"
            
            html_body += f"""
                <tr style="background-color: {row_color};">
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>{ticker}</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${price:.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${buy_target:.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${sell_target:.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{confidence_icon} {confidence}/10</td>
                    <td style="border: 1px solid #ddd; padding: 8px; font-size: 11px;">{catalyst}</td>
                </tr>
            """
        
        # Add AI insights summary
        high_confidence = sum(1 for target in dynamic_targets.values() 
                             if target['confidence_score'] >= 7)
        recent_updates = sum(1 for target in dynamic_targets.values() 
                           if target['updated_at'] and 
                           (datetime.now() - datetime.fromisoformat(target['updated_at'].replace('Z', '+00:00').replace('+00:00', ''))).days <= 30)
        
        html_body += f"""
            </table>
            
            <h3 style="color: #1a73e8;">🤖 AI Analysis Summary</h3>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <p><strong>📊 Target Quality:</strong> {high_confidence}/{len(dynamic_targets)} stocks with high confidence (7+/10)</p>
                <p><strong>🔄 Data Freshness:</strong> {recent_updates}/{len(dynamic_targets)} targets updated within 30 days</p>
                <p><strong>🎯 Alert Accuracy:</strong> Enhanced with analyst consensus + Claude AI analysis</p>
                <p><strong>💡 Next Update:</strong> Targets refresh monthly with latest fundamentals</p>
            </div>
            
            <hr style="margin: 20px 0;">
            <p style="color: #666; font-size: 12px;">
                🤖 Enhanced Portfolio Monitor powered by Claude AI + Free Analyst Data<br>
                📊 Dynamic targets updated monthly | 🔍 Real-time monitoring | 🎯 Confidence-weighted alerts<br>
                Data sources: Yahoo Finance API, MarketWatch, Claude AI analysis
            </p>
        </body>
        </html>
        """
        
        # Create and send email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient
        msg.attach(MIMEText(html_body, 'html'))
        
        # Connect to Gmail and send
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        print(f"📧 Enhanced email alert sent successfully to {recipient}")
        
    except Exception as e:
        print(f"❌ Failed to send enhanced email: {e}")

def send_email(alerts, current_prices):
    """Send email alert with portfolio information"""
    try:
        # Email configuration from environment variables
        sender_email = os.environ.get('GMAIL_USER', 'nbu864@gmail.com')
        sender_password = os.environ.get('GMAIL_PASSWORD', 'your_app_password')
        recipient = 'nbu864@gmail.com'
        
        # Create email subject
        subject = f"🚨 Portfolio Alert - {len(alerts)} notifications"
        
        # Portfolio value not tracked
        total_value = 0.0
        
        # Create HTML email body
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <h2 style="color: #1a73e8;">📊 Portfolio Alert</h2>
            <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')}</p>
            <p><strong>Monitoring:</strong> {len(current_prices)} stocks</p>
            
            <h3 style="color: #ea4335;">🚨 Alerts ({len(alerts)})</h3>
            <ul>
        """
        
        # Add alerts
        for alert in alerts:
            if "🟢" in alert:
                color = "#34a853"  # Green
            elif "🔴" in alert:
                color = "#ea4335"  # Red
            elif "🟡" in alert:
                color = "#fbbc04"  # Yellow
            else:
                color = "#1a73e8"  # Blue
                
            html_body += f'<li style="color: {color}; margin: 10px 0;">{alert}</li>'
        
        html_body += """
            </ul>
            
            <h3 style="color: #1a73e8;">📈 Current Stock Status</h3>
            <table style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f1f3f4;">
                    <th style="border: 1px solid #ddd; padding: 8px;">Stock</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Current Price</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Buy Target</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Sell Target</th>
                </tr>
        """
        
        # Add stock table
        for ticker, price in current_prices.items():
            config = PORTFOLIO[ticker]
            
            # Color code based on targets
            if price <= config['buy_target']:
                row_color = "#e8f5e8"  # Light green
            elif price >= config['sell_target']:
                row_color = "#fce8e6"  # Light red
            else:
                row_color = "white"
            
            html_body += f"""
                <tr style="background-color: {row_color};">
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>{ticker}</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${price:.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${config['buy_target']:.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${config['sell_target']:.2f}</td>
                </tr>
            """
        
        html_body += """
            </table>
            
            <hr style="margin: 20px 0;">
            <p style="color: #666; font-size: 12px;">
                🤖 Automated alert from your Portfolio Monitor running on Google Cloud Platform.<br>
                Agent checks your stocks and sends alerts when buy/sell targets are hit.
            </p>
        </body>
        </html>
        """
        
        # Create and send email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient
        msg.attach(MIMEText(html_body, 'html'))
        
        # Connect to Gmail and send
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        print(f"📧 Email alert sent successfully to {recipient}")
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# For local testing
if __name__ == "__main__":
    print("🧪 Testing portfolio monitor locally...")
    
    class MockRequest:
        pass
    
    result = portfolio_monitor(MockRequest())
    print(json.dumps(result, indent=2, default=str))