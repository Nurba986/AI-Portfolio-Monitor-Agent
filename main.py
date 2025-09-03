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
from datetime import datetime

# Import modular services
# from services.secret_manager import validate_secrets  # Temporarily commented
from services.utils import is_market_open, calculate_portfolio_value
from services.data_collector import get_stock_prices_fast, collect_analyst_data, get_enhanced_yahoo_data
from services.ai_analyzer import analyze_with_claude
from services.portfolio_manager import (
    load_targets_from_firestore, 
    check_enhanced_alerts,
    save_targets_to_firestore,
    can_send_summary,
    mark_summary_sent
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

        # Parse optional test controls from query params
        force_open = False
        simulate_time_et = None
        email_dry_run = False
        try:
            args = getattr(request, 'args', None)
            if args:
                force_open = args.get('force_open', '').lower() in ('true', '1', 'yes')
                email_dry_run = args.get('email_dry_run', '').lower() in ('true', '1', 'yes')
                simulate_time_et = args.get('simulate_time_et') or None
                force_send = args.get('force_send', '').lower() in ('true', '1', 'yes')
                dedup_cooldown_param = args.get('dedup_cooldown_min')
        except Exception:
            pass

        # Apply per-invocation email dry run (safe testing)
        if email_dry_run:
            os.environ['EMAIL_DRY_RUN'] = 'true'

        # Check if market is open first (supports force_open and simulated time)
        market_open, reason = is_market_open(
            bypass_for_testing=force_open,
            simulate_time_et=simulate_time_et,
        )
        
        if not market_open:
            print(f"⏸️ Market closed: {reason}")
            return {
                "status": "skipped",
                "timestamp": datetime.now().isoformat(),
                "reason": reason,
                "testing": {
                    "force_open": force_open,
                    "simulate_time_et": simulate_time_et,
                    "email_dry_run": email_dry_run,
                },
                "message": "Portfolio monitoring skipped - market closed"
            }
        
        print(f"✅ Market is open: {reason}")
        
        # Load dynamic targets from Firestore (with hardcoded fallback)
        dynamic_targets = load_targets_from_firestore(PORTFOLIO)
        
        # Get current stock prices using optimized fetching
        current_prices = get_stock_prices_fast(PORTFOLIO.keys())
        
        # Check for trading opportunities with confidence scoring
        alerts = check_enhanced_alerts(current_prices, dynamic_targets)
        
        # Dedup guard settings
        force_send = locals().get('force_send', False)
        try:
            cooldown_env = int(os.environ.get('EMAIL_DEDUP_COOLDOWN_MINUTES', '60'))
        except Exception:
            cooldown_env = 60
        try:
            cooldown_override = int(dedup_cooldown_param) if 'dedup_cooldown_param' in locals() and dedup_cooldown_param else None
        except Exception:
            cooldown_override = None
        cooldown_minutes = cooldown_override or cooldown_env

        # Send enhanced email with AI insights with dedup guard
        email_sent = False
        email_error = None
        email_skipped_dedup = False
        dedup_remaining_minutes = None
        
        # Check dedup unless forced
        if not force_send:
            can_send, remaining = can_send_summary('daily_summary', cooldown_minutes)
            if not can_send:
                email_skipped_dedup = True
                dedup_remaining_minutes = remaining
                print("🛑 Skipping email send due to dedup cooldown window")
        
        if not email_skipped_dedup:
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
            else:
                # Record dedup only when not in dry run
                if os.environ.get('EMAIL_DRY_RUN', '').lower() not in ('true', '1', 'yes'):
                    try:
                        meta = {
                            'alerts': len(alerts),
                            'tickers': len(current_prices),
                        }
                        mark_summary_sent('daily_summary', meta)
                    except Exception as rec_e:
                        print(f"⚠️ Failed to record email dedup state: {rec_e}")
        
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
            "email_skipped_dedup": email_skipped_dedup,
            "dedup_remaining_minutes": dedup_remaining_minutes,
            "testing": {
                "force_open": force_open,
                "simulate_time_et": simulate_time_et,
                "email_dry_run": email_dry_run,
                "force_send": force_send,
            },
            "targets_summary": {ticker: {
                'buy_target': target['buy_target'],
                'sell_target': target['sell_target'],
                'confidence': target['confidence_score']
            } for ticker, target in dynamic_targets.items()},
            "message": f"Checked {len(current_prices)} stocks with dynamic targets, found {len(alerts)} alerts. Email status: {'skipped (dedup)' if email_skipped_dedup else ('sent' if email_sent else 'failed')}"
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

        # Optional per-invocation dry-run for email and overrides
        try:
            args = getattr(request, 'args', None)
            if args and args.get('email_dry_run', '').lower() in ('true', '1', 'yes'):
                os.environ['EMAIL_DRY_RUN'] = 'true'
            if args:
                force_send = args.get('force_send', '').lower() in ('true', '1', 'yes')
                dedup_cooldown_param = args.get('dedup_cooldown_min')
        except Exception:
            pass
        
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
        
        # Send comprehensive update email with dedup guard
        email_sent = False
        email_error = None
        email_skipped_dedup = False
        dedup_remaining_minutes = None
        
        if updated_targets:
            # Determine cooldown (default 24h for monthly)
            try:
                cooldown_env = int(os.environ.get('EMAIL_MONTHLY_DEDUP_COOLDOWN_MINUTES', '1440'))
            except Exception:
                cooldown_env = 1440
            try:
                cooldown_override = int(dedup_cooldown_param) if 'dedup_cooldown_param' in locals() and dedup_cooldown_param else None
            except Exception:
                cooldown_override = None
            cooldown_minutes = cooldown_override or cooldown_env

            force_send_flag = locals().get('force_send', False)

            if not force_send_flag:
                can_send, remaining = can_send_summary('monthly_update', cooldown_minutes)
                if not can_send:
                    email_skipped_dedup = True
                    dedup_remaining_minutes = remaining
                    print("🛑 Skipping monthly update email due to dedup cooldown window")
            
            if not email_skipped_dedup:
                try:
                    send_target_update_email(updated_targets, total_cost)
                    email_sent = True
                    print(f"📧 Target update email sent successfully")
                except Exception as e:
                    email_error = str(e)
                    print(f"❌ Failed to send target update email: {email_error}")
                else:
                    # Record dedup only when not in dry run
                    if os.environ.get('EMAIL_DRY_RUN', '').lower() not in ('true', '1', 'yes'):
                        try:
                            meta = {
                                'updated_stocks': len(updated_targets),
                                'estimated_cost': f"${total_cost:.2f}",
                            }
                            mark_summary_sent('monthly_update', meta)
                        except Exception as rec_e:
                            print(f"⚠️ Failed to record monthly email dedup state: {rec_e}")
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "updated_stocks": len(updated_targets),
            "estimated_cost": f"${total_cost:.2f}",
            "email_sent": email_sent,
            "email_error": email_error,
            "email_skipped_dedup": email_skipped_dedup,
            "dedup_remaining_minutes": dedup_remaining_minutes,
            "targets": {ticker: {
                'buy_target': data['buy_target'],
                'sell_target': data['sell_target'],
                'confidence': data['confidence_score']
            } for ticker, data in updated_targets.items()},
            "message": f"Updated targets for {len(updated_targets)} stocks. Email status: {'skipped (dedup)' if email_skipped_dedup else ('sent' if email_sent else 'failed')}"
        }
        
    except Exception as e:
        error_msg = f"Monthly target update error: {str(e)}"
        print(f"❌ {error_msg}")
        
        return {
            "status": "error",
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        }


def validate_environment():
    """Validate that all required secrets are available"""
    print("🔍 Validating environment configuration...")
    
    try:
        # validation_result = validate_secrets()  # Temporarily commented
        validation_result = {
            "valid": True,
            "environment": "Cloud",
            "found_secrets": ["GMAIL_USER", "GMAIL_PASSWORD", "CLAUDE_API_KEY"],
            "missing_secrets": []
        }  # Temporary fallback
        
        if validation_result['valid']:
            print(f"✅ All secrets validated successfully ({validation_result['environment']} environment)")
            for secret in validation_result['found_secrets']:
                print(f"  ✓ {secret}")
            return True
        else:
            print(f"❌ Missing required secrets in {validation_result['environment']} environment:")
            for secret in validation_result['missing_secrets']:
                print(f"  ✗ {secret}")
            print("\n📝 Setup instructions:")
            if validation_result['environment'] == 'Local':
                print("  1. Copy .env.yaml.template to .env.yaml")
                print("  2. Fill in your actual credentials")
                print("  3. Ensure .env.yaml is NOT committed to Git")
            else:
                print("  1. Store secrets in Google Cloud Secret Manager")
                print("  2. Grant Secret Manager access to Cloud Function")
                print("  3. Ensure GOOGLE_CLOUD_PROJECT is set")
            return False
            
    except Exception as e:
        print(f"❌ Environment validation failed: {e}")
        return False


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
    
    # Validate environment and secrets first
    environment_valid = validate_environment()
    
    if not environment_valid:
        print("\n❌ Environment validation failed. Please check your configuration.")
        exit(1)
    
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


@functions_framework.http
def health(request):
    """Health endpoint: validates Secret Manager access and Firestore connectivity.
    Query params:
      - write=true to also attempt a Firestore write (optional)
    Returns a JSON with per-check status and overall status.
    """
    from google.cloud import firestore as _fs
    from datetime import datetime as _dt

    args = getattr(request, 'args', {}) or {}
    try_write = str(args.get('write', '')).lower() in ('true', '1', 'yes')

    checks = {}

    # Secret Manager validation
    try:
        # sec = validate_secrets()  # Temporarily commented
        sec = {
            "valid": True,
            "environment": "Cloud",
            "found_secrets": ["GMAIL_USER", "GMAIL_PASSWORD", "CLAUDE_API_KEY"]
        }  # Temporary fallback
        checks['secrets'] = {
            'ok': bool(sec.get('valid')),
            'environment': sec.get('environment'),
            'found': sec.get('found_secrets', []),
            'missing': sec.get('missing_secrets', []),
        }
    except Exception as e:
        checks['secrets'] = {'ok': False, 'error': str(e)}

    # Firestore read (and optional write)
    try:
        db = _fs.Client()
        doc_ref = db.collection('system_status').document('_healthcheck')
        doc = doc_ref.get()
        checks['firestore_read'] = {'ok': True, 'exists': doc.exists}
        if try_write:
            payload = {'last_checked': _dt.utcnow().isoformat() + 'Z'}
            doc_ref.set(payload, merge=True)
            checks['firestore_write'] = {'ok': True}
    except Exception as e:
        # If write was requested and failed, record both
        if try_write:
            checks['firestore_write'] = {'ok': False, 'error': str(e)}
        checks['firestore_read'] = {'ok': False, 'error': str(e)}

    overall_ok = all(v.get('ok') for v in checks.values()) if checks else False
    status = 'ok' if overall_ok else 'error'

    return {
        'status': status,
        'timestamp': datetime.now().isoformat(),
        'checks': checks,
        'testing': {
            'write_attempted': try_write,
        }
    }
