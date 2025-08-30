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
import os
try:
    import yaml
except ImportError:
    print("Warning: PyYAML not installed, using manual .env parsing")
    yaml = None
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
        
        # Send enhanced email with AI insights (ALWAYS send daily summary)
        email_sent = False
        email_error = None
        
        try:
            # Always send daily summary - even if no alerts
            send_enhanced_email(alerts, current_prices, dynamic_targets)
            email_sent = True
            if alerts:
                print(f"📧 Daily summary sent successfully with {len(alerts)} trading opportunities")
            else:
                print("📧 Daily status summary sent successfully - no trading opportunities")
        except Exception as e:
            email_error = str(e)
            print(f"❌ Failed to send daily summary email: {email_error}")
        
        # Calculate portfolio metrics
        total_value = calculate_portfolio_value(current_prices)
        high_confidence_targets = sum(1 for target in dynamic_targets.values() 
                                     if target['confidence_score'] >= 7)
        
        # Return success response with email status
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "prices": current_prices,
            "alerts": alerts,
            "portfolio_value": total_value,
            "dynamic_targets_loaded": True,
            "high_confidence_targets": high_confidence_targets,
            "email_sent": email_sent,
            "email_error": email_error,
            "targets_summary": {ticker: {
                'buy_target': target['buy_target'],
                'sell_target': target['sell_target'],
                'confidence': target['confidence_score']
            } for ticker, target in dynamic_targets.items()},
            "message": f"Checked {len(current_prices)} stocks with dynamic targets, found {len(alerts)} alerts. Email status: {'sent' if email_sent else 'failed'}"
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
        email_sent = False
        email_error = None
        
        if updated_targets:
            try:
                send_target_update_email(updated_targets, total_cost)
                email_sent = True
                print(f"📧 Target update email sent successfully")
            except Exception as e:
                email_error = str(e)
                print(f"❌ Failed to send target update email: {email_error}")
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "updated_stocks": len(updated_targets),
            "estimated_cost": f"${total_cost:.2f}",
            "email_sent": email_sent,
            "email_error": email_error,
            "targets": {ticker: {
                'buy_target': data['buy_target'],
                'sell_target': data['sell_target'],
                'confidence': data['confidence_score']
            } for ticker, data in updated_targets.items()},
            "message": f"Updated targets for {len(updated_targets)} stocks. Email status: {'sent' if email_sent else 'failed'}"
        }
        
    except Exception as e:
        error_msg = f"Monthly target update error: {str(e)}"
        print(f"❌ {error_msg}")
        
        return {
            "status": "error",
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        }


def load_local_env():
    """Load environment variables from .env.yaml for local testing"""
    try:
        env_file = os.path.join(os.path.dirname(__file__), '.env.yaml')
        if os.path.exists(env_file):
            if yaml:
                with open(env_file, 'r') as f:
                    env_vars = yaml.safe_load(f)
                    for key, value in env_vars.items():
                        os.environ[key] = str(value)
                    print(f"✅ Loaded {len(env_vars)} environment variables from .env.yaml")
            else:
                # Manual parsing if PyYAML not available
                with open(env_file, 'r') as f:
                    lines = f.readlines()
                    env_count = 0
                    for line in lines:
                        if ':' in line and not line.strip().startswith('#'):
                            key, value = line.strip().split(':', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            os.environ[key] = value
                            env_count += 1
                    print(f"✅ Loaded {env_count} environment variables from .env.yaml (manual parsing)")
        else:
            print("⚠️ No .env.yaml file found for local testing")
    except Exception as e:
        print(f"❌ Failed to load .env.yaml: {e}")


def test_email():
    """Simple email test function"""
    from services.email_service import _send_email
    
    print("🧪 Testing email functionality...")
    
    # Test basic email sending
    subject = "Portfolio Agent - Email Test"
    html_body = """
    <html>
    <body style="font-family: Arial, sans-serif; margin: 20px;">
        <h2 style="color: #1a73e8;">Email Test Successful!</h2>
        <p>This is a test email from your Portfolio Agent.</p>
        <p><strong>Time:</strong> """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
        <p>If you receive this email, your email configuration is working correctly.</p>
    </body>
    </html>
    """
    
    success, result = _send_email(subject, html_body)
    
    if success:
        print(f"✅ Test email sent successfully to {result}")
        return True
    else:
        print(f"❌ Test email failed: {result}")
        return False


# For local testing
if __name__ == "__main__":
    print("🧪 Testing portfolio monitor locally...")
    
    # Load environment variables for local testing
    load_local_env()
    
    # Enable market hours bypass for testing
    os.environ['BYPASS_MARKET_HOURS'] = 'true'
    
    print("\n" + "="*50)
    print("RUNNING EMAIL TEST")
    print("="*50)
    
    # Test email first
    email_works = test_email()
    
    print("\n" + "="*50)
    print("RUNNING PORTFOLIO MONITOR")
    print("="*50)
    
    if email_works:
        class MockRequest:
            pass
        
        result = portfolio_monitor(MockRequest())
        print(json.dumps(result, indent=2, default=str))
    else:
        print("❌ Skipping portfolio monitor test due to email failure")

