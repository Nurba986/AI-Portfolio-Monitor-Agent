"""
AI analysis services for Portfolio Agent
Handles Claude integration, prompt engineering, and target generation
"""

import os
import re
import anthropic
from datetime import datetime, timezone
from .utils import format_number, format_percentage


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
            print(f"  L No Claude API key found for {ticker}")
            return None
            
        # Initialize Claude client
        client = anthropic.Anthropic(api_key=claude_api_key)
        
        # Create analysis prompt
        prompt = create_claude_analysis_prompt(ticker, financials, analyst_data)
        
        print(f"  > Analyzing {ticker} with Claude...")
        
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
        print(f"  L Claude analysis failed for {ticker}: {e}")
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
                print(f"  => Invalid targets for {ticker}: sell ${sell_target} <= buy ${buy_target}")
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
            'generated_at': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        print(f"  L Failed to parse Claude response for {ticker}: {e}")
        return {
            'ticker': ticker,
            'buy_target': None,
            'sell_target': None,
            'confidence_score': 1,
            'key_catalyst': "Analysis failed",
            'risk_factor': "Unable to analyze",
            'error': str(e),
            'generated_at': datetime.now(timezone.utc).isoformat()
        }