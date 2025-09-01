"""
Data collection services for Portfolio Agent
Handles stock price fetching, web scraping, and analyst data aggregation
"""

import yfinance as yf
from bs4 import BeautifulSoup
import re
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils import (get_http_session, remove_outliers, calculate_confidence_level, 
                    get_cached_data, cache_data)


def _is_marketwatch_enabled():
    """Check if MarketWatch scraping is enabled via environment variable"""
    return os.environ.get('ENABLE_MW_SCRAPE', 'true').lower() in ('true', '1', 'yes')


def _is_yahoo_web_enabled():
    """Check if Yahoo web scraping is enabled via environment variable"""
    return os.environ.get('ENABLE_YF_WEB_SCRAPE', 'true').lower() in ('true', '1', 'yes')


def _assess_data_quality(data_sources, target_prices):
    """Assess if data quality is sufficient to skip additional sources"""
    if not data_sources:
        return False
    
    # Check for high-quality primary source
    yahoo_api = data_sources.get('yahoo_api')
    if yahoo_api and yahoo_api.get('data_quality') == 'high':
        analyst_data = yahoo_api.get('analyst_data', {})
        if (analyst_data.get('target_mean') and 
            analyst_data.get('analyst_count', 0) >= 5):
            return True
    
    # Check if we have sufficient target price data
    if len(target_prices) >= 3:
        return True
    
    return False


def get_enhanced_yahoo_data(ticker):
    """Get comprehensive Yahoo Finance data including analyst targets and financials"""
    # Check cache first
    cached_data = get_cached_data(ticker, 'yahoo_api')
    if cached_data:
        return cached_data
    
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
        
        result = {
            'ticker': ticker,
            'analyst_data': analyst_data,
            'financials': financials,
            'data_quality': 'high' if current_price and analyst_data.get('target_mean') else 'medium'
        }
        
        # Cache the result
        cache_data(ticker, 'yahoo_api', result)
        return result
        
    except Exception as e:
        print(f"   ❌ Error fetching enhanced data for {ticker}: {e}")
        return {
            'ticker': ticker,
            'analyst_data': {},
            'financials': {'current_price': None},
            'data_quality': 'low'
        }


def get_stock_prices_fast(portfolio_tickers):
    """Fast batch stock price fetching with threading"""
    try:
        # Try bulk download first (fastest method)
        print(f"📊 Starting price fetch for {len(portfolio_tickers)} stocks: {list(portfolio_tickers)}")
        print("📊 Attempting bulk price fetch...")
        tickers_list = list(portfolio_tickers)
        
        # Use yfinance bulk download for speed
        df = yf.download(tickers=tickers_list, period="1d", threads=True, progress=False)
        
        print(f"📊 DataFrame empty: {df.empty}")
        if not df.empty:
            print(f"📊 DataFrame shape: {df.shape}, columns: {list(df.columns)}")
            
            # Enhanced DataFrame handling with multi-index awareness
            prices = {}
            try:
                # Check if DataFrame has MultiIndex columns
                if hasattr(df.columns, 'levels'):
                    print("📊 MultiIndex DataFrame detected")
                    # Multi-ticker case with MultiIndex
                    try:
                        # Try to get Adj Close first, then Close
                        if ('Adj Close', ) in df.columns.get_level_values(0).unique():
                            last_prices = df['Adj Close'].iloc[-1]
                        elif ('Close', ) in df.columns.get_level_values(0).unique():
                            last_prices = df['Close'].iloc[-1]
                        else:
                            # Fallback to any price column
                            price_cols = [col for col in df.columns.get_level_values(0) if 'close' in col.lower()]
                            if price_cols:
                                last_prices = df[price_cols[0]].iloc[-1]
                            else:
                                raise ValueError("No price columns found")
                        
                        for ticker in tickers_list:
                            if ticker in last_prices and last_prices[ticker] > 0:
                                prices[ticker] = round(float(last_prices[ticker]), 2)
                                print(f"    {ticker}: ${last_prices[ticker]:.2f}")
                                
                    except Exception as multi_error:
                        print(f"📊 MultiIndex extraction failed: {multi_error}")
                        # Try alternative MultiIndex extraction
                        for ticker in tickers_list:
                            try:
                                # Try accessing individual ticker columns
                                if ('Adj Close', ticker) in df.columns:
                                    price = df[('Adj Close', ticker)].iloc[-1]
                                elif ('Close', ticker) in df.columns:
                                    price = df[('Close', ticker)].iloc[-1]
                                else:
                                    continue
                                    
                                if price and price > 0:
                                    prices[ticker] = round(float(price), 2)
                                    print(f"    {ticker}: ${price:.2f}")
                            except Exception as ticker_error:
                                print(f"📊 Failed to extract {ticker}: {ticker_error}")
                                continue
                else:
                    print("📊 Regular DataFrame (non-MultiIndex)")
                    # Handle both single and multi-ticker cases for regular DataFrame
                    if len(tickers_list) == 1:
                        # Single ticker case
                        try:
                            if "Adj Close" in df.columns:
                                last_price = df["Adj Close"].iloc[-1]
                            elif "Close" in df.columns:
                                last_price = df["Close"].iloc[-1]
                            else:
                                # Try any price column
                                price_cols = [col for col in df.columns if 'close' in col.lower()]
                                if price_cols:
                                    last_price = df[price_cols[0]].iloc[-1]
                                else:
                                    raise ValueError("No price columns found")
                            
                            if last_price and last_price > 0:
                                prices[tickers_list[0]] = round(float(last_price), 2)
                                print(f"    {tickers_list[0]}: ${last_price:.2f}")
                        except Exception as single_error:
                            print(f"📊 Single ticker extraction failed: {single_error}")
                    else:
                        # Multi-ticker case with regular DataFrame
                        try:
                            if "Adj Close" in df.columns:
                                last_prices = df["Adj Close"].iloc[-1]
                            elif "Close" in df.columns:
                                last_prices = df["Close"].iloc[-1]
                            else:
                                raise ValueError("No price columns found")
                            
                            for ticker in tickers_list:
                                if ticker in last_prices and last_prices[ticker] > 0:
                                    prices[ticker] = round(float(last_prices[ticker]), 2)
                                    print(f"    {ticker}: ${last_prices[ticker]:.2f}")
                        except Exception as multi_error:
                            print(f"📊 Multi-ticker extraction failed: {multi_error}")
                
                if prices:
                    print(f"📊 Successfully extracted {len(prices)} prices from DataFrame")
                    return prices
                else:
                    print(f"📊 No valid prices extracted from DataFrame")
                    
            except Exception as df_error:
                print(f"📊 DataFrame processing failed: {df_error}")
                import traceback
                print(f"📊 DataFrame error traceback: {traceback.format_exc()[:200]}...")
        else:
            print("❌ DataFrame is empty from yfinance")
    except Exception as e:
        print(f"❌ Bulk fetch failed: {e}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()[:300]}...")
    
    # Fallback: threaded individual fetches (limited concurrency to avoid rate limits)
    print("📊 Using threaded fallback fetch...")
    prices = {}
    
    def fetch_single_price(ticker):
        print(f"📊 Fetching {ticker} individually...")
        try:
            # Add delay to avoid rate limiting
            import time
            import random
            time.sleep(random.uniform(0.5, 1.5))  # Random delay 0.5-1.5 seconds
            
            stock = yf.Ticker(ticker)
            # Try fast_info first, then regular info
            try:
                fast_info = stock.fast_info
                price = fast_info.get("last_price")
                if price and price > 0:
                    print(f"✅ {ticker}: fast_info price ${price:.2f}")
                    return ticker, round(float(price), 2)
            except Exception as e:
                print(f"📊 {ticker}: fast_info failed ({e}), trying info...")
                
            # Add another small delay before trying info
            time.sleep(0.5)
            
            # Fallback to regular info
            info = stock.info
            price = (info.get('currentPrice') or 
                    info.get('regularMarketPrice') or 
                    info.get('ask') or 
                    info.get('bid'))
            if price and price > 0:
                print(f"✅ {ticker}: info price ${price:.2f}")
                return ticker, round(float(price), 2)
            else:
                print(f"❌ {ticker}: no valid price in info")
                
            # Final fallback: try 1-day history
            try:
                print(f"📊 {ticker}: trying 1-day history fallback...")
                hist = stock.history(period='1d')
                if not hist.empty and 'Close' in hist.columns:
                    last_close = hist['Close'].iloc[-1]
                    if last_close and last_close > 0:
                        print(f"✅ {ticker}: history price ${last_close:.2f}")
                        return ticker, round(float(last_close), 2)
            except Exception as hist_error:
                print(f"📊 {ticker}: history fallback failed: {hist_error}")
                
        except Exception as e:
            print(f"❌ Error fetching {ticker}: {e}")
            # If rate limited, suggest retrying
            if "429" in str(e):
                print(f"⚠️ {ticker}: Rate limited - will try again later")
        
        return ticker, None
    
    # Use ThreadPoolExecutor with very limited concurrency to avoid rate limits
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_ticker = {executor.submit(fetch_single_price, ticker): ticker for ticker in portfolio_tickers}
        
        for future in as_completed(future_to_ticker):
            ticker, price = future.result()
            if price:
                prices[ticker] = price
                print(f"    {ticker}: ${price:.2f}")
            else:
                print(f"     Could not get price for {ticker}")
    
    print(f"📊 FINAL RESULT: {len(prices)}/{len(portfolio_tickers)} stocks fetched successfully")
    print(f"📊 Successful: {list(prices.keys())}")
    if len(prices) < len(portfolio_tickers):
        failed = [t for t in portfolio_tickers if t not in prices]
        print(f"📊 Failed: {failed}")
    return prices


def scrape_marketwatch_consensus(ticker):
    """Scrape MarketWatch for analyst consensus data"""
    # Check cache first
    cached_data = get_cached_data(ticker, 'marketwatch')
    if cached_data:
        return cached_data
    
    try:
        url = f"https://www.marketwatch.com/investing/stock/{ticker}/analystestimates"
        
        response = get_http_session().get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract consensus target price
        consensus_target = None
        analyst_count = None
        
        # Look for price target in various possible locations (fixed deprecated syntax)
        price_target_elements = soup.find_all(['span', 'div', 'td'], 
                                            string=re.compile(r'\$[\d,]+\.?\d*'))
        
        for element in price_target_elements:
            text = element.get_text()
            if 'price target' in text.lower() or 'consensus' in text.lower():
                # Extract price using regex
                price_match = re.search(r'\$([0-9,]+\.?\d*)', text)
                if price_match:
                    consensus_target = float(price_match.group(1).replace(',', ''))
                    break
        
        # Extract number of analysts (fixed deprecated syntax)
        analyst_elements = soup.find_all(string=re.compile(r'\d+\s*analyst'))
        for element in analyst_elements:
            analyst_match = re.search(r'(\d+)\s*analyst', element)
            if analyst_match:
                analyst_count = int(analyst_match.group(1))
                break
        
        # Extract rating distribution (Buy/Hold/Sell)
        rating_distribution = {'buy': 0, 'hold': 0, 'sell': 0}
        
        # Look for rating counts (fixed deprecated syntax)
        rating_elements = soup.find_all(['td', 'span'], string=re.compile(r'\d+'))
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
        
        result = {
            'source': 'marketwatch',
            'ticker': ticker,
            'consensus_target': consensus_target,
            'analyst_count': analyst_count,
            'rating_distribution': rating_distribution,
            'data_quality': 'high' if consensus_target and analyst_count else 'low',
            'scraped_at': datetime.now().isoformat()
        }
        
        # Cache the result
        cache_data(ticker, 'marketwatch', result)
        return result
        
    except Exception as e:
        print(f"     MarketWatch scraping failed for {ticker}: {e}")
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
    # Check cache first
    cached_data = get_cached_data(ticker, 'yahoo_web')
    if cached_data:
        return cached_data
    
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}/analysis"
        
        response = get_http_session().get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract price targets from analyst section (fixed deprecated syntax)
        target_elements = soup.find_all(['span', 'div'], 
                                      string=re.compile(r'\d+\.\d+'))
        
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
        
        result = {
            'source': 'yahoo_web',
            'ticker': ticker,
            'targets': targets,
            'data_quality': 'medium' if any(targets.values()) else 'low',
            'scraped_at': datetime.now().isoformat()
        }
        
        # Cache the result
        cache_data(ticker, 'yahoo_web', result)
        return result
        
    except Exception as e:
        print(f"     Yahoo web scraping failed for {ticker}: {e}")
        return {
            'source': 'yahoo_web',
            'ticker': ticker,
            'targets': {'mean': None, 'high': None, 'low': None},
            'data_quality': 'failed',
            'error': str(e),
            'scraped_at': datetime.now().isoformat()
        }


def collect_analyst_data(ticker):
    """Collect analyst data with smart fallback logic and feature flags"""
    print(f"=> Collecting analyst data for {ticker}...")
    
    data_sources = {}
    target_prices = []
    
    # Source 1: Enhanced Yahoo Finance API (ALWAYS enabled - primary source)
    try:
        yahoo_data = get_enhanced_yahoo_data(ticker)
        if yahoo_data['data_quality'] in ['high', 'medium']:
            data_sources['yahoo_api'] = yahoo_data
            print(f"    Yahoo API: {yahoo_data['data_quality']} quality")
            
            # Collect target prices for quality assessment
            analyst_data = yahoo_data.get('analyst_data', {})
            for key in ['target_mean', 'target_high', 'target_low']:
                if analyst_data.get(key):
                    target_prices.append(analyst_data[key])
        else:
            print(f"     Yahoo API: {yahoo_data['data_quality']} quality")
    except Exception as e:
        print(f"   ❌ Yahoo API failed: {e}")
    
    # Check if we have sufficient data quality to skip additional sources
    if _assess_data_quality(data_sources, target_prices):
        print(f"    Sufficient data quality from primary sources - skipping additional scraping")
        return aggregate_analyst_data(ticker, data_sources)
    
    # Source 2: MarketWatch scraping (conditional based on flag)
    if _is_marketwatch_enabled():
        try:
            mw_data = scrape_marketwatch_consensus(ticker)
            if mw_data['data_quality'] in ['high', 'medium']:
                data_sources['marketwatch'] = mw_data
                print(f"    MarketWatch: {mw_data['data_quality']} quality")
                
                # Add to target prices for next quality check
                if mw_data.get('consensus_target'):
                    target_prices.append(mw_data['consensus_target'])
            else:
                print(f"     MarketWatch: {mw_data['data_quality']} quality")
        except Exception as e:
            print(f"   ❌ MarketWatch failed: {e}")
    else:
        print(f"     MarketWatch scraping disabled via ENABLE_MW_SCRAPE")
    
    # Check again if we now have sufficient data
    if _assess_data_quality(data_sources, target_prices):
        print(f"    Sufficient data quality after MarketWatch - skipping Yahoo web scraping")
        return aggregate_analyst_data(ticker, data_sources)
    
    # Source 3: Yahoo web scraping (conditional based on flag - only if other sources failed)
    if _is_yahoo_web_enabled():
        try:
            yahoo_web_data = scrape_yahoo_web_targets(ticker)
            if yahoo_web_data['data_quality'] in ['high', 'medium']:
                data_sources['yahoo_web'] = yahoo_web_data
                print(f"    Yahoo Web: {yahoo_web_data['data_quality']} quality")
            else:
                print(f"     Yahoo Web: {yahoo_web_data['data_quality']} quality")
        except Exception as e:
            print(f"   ❌ Yahoo Web failed: {e}")
    else:
        print(f"     Yahoo web scraping disabled via ENABLE_YF_WEB_SCRAPE")
    
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
            'rating_distribution': {'buy': 0, 'hold': 0, 'sell': 0},
            'aggregated_at': datetime.now().isoformat(),
            'quality': 'failed'
        }
    
    # Collect all target prices
    target_prices = []
    analyst_counts = []
    recommendation_scores = []
    rating_distribution = {'buy': 0, 'hold': 0, 'sell': 0}
    
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
            
            # Aggregate rating distribution from MarketWatch
            mw_ratings = source_data.get('rating_distribution', {})
            for rating_type in ['buy', 'hold', 'sell']:
                rating_distribution[rating_type] += mw_ratings.get(rating_type, 0)
                
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
        'rating_distribution': rating_distribution,
        'raw_targets': target_prices,
        'aggregated_at': datetime.now().isoformat(),
        'quality': quality
    }