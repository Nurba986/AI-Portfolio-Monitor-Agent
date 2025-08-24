#!/usr/bin/env python3
"""
Portfolio Monitor - Cloud Function (Refactored)
Clean, modular architecture with single responsibility modules

Architecture:
- services/utils.py: Market hours, HTTP sessions, formatting
- services/data_collector.py: Stock prices, web scraping, analyst data
- services/ai_analyzer.py: Claude AI integration and analysis
- services/portfolio_manager.py: Target loading, alerts, calculations
- services/email_service.py: All email functionality consolidated

"""

import functions_framework
import json
from datetime import datetime

# Import modular services
from services.utils import is_market_open, calculate_portfolio_value
from services.data_collector import get_stock_prices_fast, collect_analyst_data, get_enhanced_yahoo_data
from services.ai_analyzer import analyze_with_claude
from services.portfolio_manager import (
    load_targets_from_firestore, 
    check_enhanced_alerts,
    save_targets_to_firestore
)
from services.email_service import send_enhanced_email, send_target_update_email

# Portfolio configuration - hardcoded targets as fallback
PORTFOLIO = {
    'ASML': {'buy_target': 633.00, 'sell_target': 987.00},
    'SNY': {'buy_target': 45.00, 'sell_target': 62.00},
    'JD': {'buy_target': 26.50, 'sell_target': 41.00},
    'UNH': {'buy_target': 300.00, 'sell_target': 388.00},
    'XOM': {'buy_target': 110.00, 'sell_target': 130.00},
    'ADM': {'buy_target': 50.00, 'sell_target': 70.00},
    'BABA': {'buy_target': 80.00, 'sell_target': 120.00},
    'FSLR': {'buy_target': 180.00, 'sell_target': 280.00},
    'NKE': {'buy_target': 75.00, 'sell_target': 105.00},
    'NTR': {'buy_target': 45.00, 'sell_target': 65.00},
    'RIO': {'buy_target': 55.00, 'sell_target': 75.00},
    'TCEHY': {'buy_target': 35.00, 'sell_target': 55.00},
}


@functions_framework.http
def portfolio_monitor(request):
    """
    Cloud Function entry point for daily portfolio monitoring
    """
    
    try:
        print("🔄 Starting portfolio monitoring...")
        
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
        
        # Load dynamic targets from Firestore (with hardcoded fallback)
        dynamic_targets = load_targets_from_firestore(PORTFOLIO)
        
        # Get current stock prices using optimized fetching
        current_prices = get_stock_prices_fast(PORTFOLIO.keys())
        
        # Check for trading opportunities with confidence scoring
        alerts = check_enhanced_alerts(current_prices, dynamic_targets)
        
        # Send enhanced email with AI insights
        if alerts:
            send_enhanced_email(alerts, current_prices, dynamic_targets)
            print(f"📧 Daily summary sent with {len(alerts)} trading opportunities")
        else:
            print("✅ No alerts - all stocks within normal ranges")
        
        # Calculate portfolio metrics
        total_value = calculate_portfolio_value(current_prices)
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
        error_msg = f"Portfolio monitor error: {str(e)}"
        print(f"❌ {error_msg}")
        
        return {
            "status": "error",
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        }


@functions_framework.http
def monthly_target_update(request):
    """Cloud Function entry point for monthly AI-powered target updates"""
    
    try:
        print("🔄 Starting monthly target update...")
        
        updated_targets = {}
        total_cost = 0
        
        # Process each stock in portfolio
        for ticker in PORTFOLIO.keys():
            try:
                print(f"\n📊 Processing {ticker}...")
                
                # Step 1: Collect multi-source analyst data
                analyst_data = collect_analyst_data(ticker)
                
                if analyst_data['quality'] == 'failed':
                    print(f"  ⚠️ Skipping {ticker} - no analyst data available")
                    continue
                
                # Step 2: Get enhanced financial data for Claude
                enhanced_data = get_enhanced_yahoo_data(ticker)
                financials = enhanced_data['financials']
                
                if not financials.get('current_price'):
                    print(f"  ⚠️ Skipping {ticker} - no price data available")
                    continue
                
                # Step 3: Generate AI-powered targets
                claude_analysis = analyze_with_claude(ticker, financials, analyst_data)
                
                if not claude_analysis or not claude_analysis['buy_target']:
                    print(f"  ⚠️ Claude analysis failed for {ticker}")
                    continue
                
                # Step 4: Save to Firestore database
                target_doc = save_targets_to_firestore(ticker, claude_analysis, analyst_data, financials)
                
                if target_doc:
                    updated_targets[ticker] = target_doc
                    total_cost += 0.50  # Approximate Claude API cost per stock
                    print(f"  ✅ {ticker} targets updated: Buy ${claude_analysis['buy_target']}, Sell ${claude_analysis['sell_target']}")
                
            except Exception as e:
                print(f"  ❌ Failed to update {ticker}: {e}")
                continue
        
        # Send comprehensive update email
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


# For local testing
if __name__ == "__main__":
    print("🧪 Testing portfolio monitor locally...")
    
    class MockRequest:
        pass
    
    result = portfolio_monitor(MockRequest())
    print(json.dumps(result, indent=2, default=str))

