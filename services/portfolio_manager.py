"""
Portfolio management services for Portfolio Agent
Handles target loading, alert generation, and portfolio calculations
"""

from datetime import datetime, timezone, timedelta
from google.cloud import firestore


def load_targets_from_firestore(portfolio_config):
    """Load current portfolio targets from Firestore database"""
    try:
        db = firestore.Client()
        targets_collection = db.collection('portfolio_targets')
        
        portfolio_targets = {}
        
        for ticker in portfolio_config.keys():
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
                    print(f"  => Loaded {ticker}: Buy ${data.get('buy_target')}, Sell ${data.get('sell_target')}")
                else:
                    # Fallback to hardcoded targets if no Firestore data
                    portfolio_targets[ticker] = {
                        'buy_target': portfolio_config[ticker]['buy_target'],
                        'sell_target': portfolio_config[ticker]['sell_target'],
                        'confidence_score': 3,  # Default low confidence
                        'key_catalyst': 'Hardcoded target',
                        'risk_factor': 'No recent analysis',
                        'updated_at': None,
                        'analyst_consensus': None
                    }
                    print(f"  ⚠️ Using fallback targets for {ticker}")
                    
            except Exception as e:
                print(f"  ⚠️ Error loading {ticker} from Firestore: {type(e).__name__}: {e}")
                # Log additional context for debugging
                import os
                project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'unknown')
                print(f"     Context: Project={project_id}, Document=portfolio_targets/{ticker}")
                # Use hardcoded fallback
                portfolio_targets[ticker] = {
                    'buy_target': portfolio_config[ticker]['buy_target'],
                    'sell_target': portfolio_config[ticker]['sell_target'],
                    'confidence_score': 3,
                    'key_catalyst': 'Hardcoded target',
                    'risk_factor': 'Database error',
                    'updated_at': None,
                    'analyst_consensus': None
                }
        
        print(f"✅ Loaded targets for {len(portfolio_targets)} stocks")
        return portfolio_targets
        
    except Exception as e:
        print(f"⚠️ Failed to connect to Firestore: {type(e).__name__}: {e}")
        # Log additional context for debugging
        import os
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'unknown')
        creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'not_set')
        print(f"     Context: Project={project_id}, Credentials={creds_path}")
        print(f"     Collection: portfolio_targets, Operation: bulk_load")
        print("📊 Using hardcoded portfolio targets as fallback")
        
        # Return hardcoded targets as fallback
        fallback_targets = {}
        for ticker, config in portfolio_config.items():
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
        confidence_icon = "⭐⭐⭐" if confidence >= 8 else "⭐⭐" if confidence >= 6 else "⭐"
        
        # BUY SIGNAL: Price at or below buy target
        if price <= buy_target:
            alert = f"🟢 BUY SIGNAL: {ticker} hit ${price:.2f} (target <=${buy_target:.2f}) {confidence_icon} Confidence: {confidence}/10. Catalyst: {catalyst[:50]}..."
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
            alert = f"🔴 SELL SIGNAL: {ticker} hit ${price:.2f} (target >=${sell_target:.2f}) {confidence_icon} Est. gain: {profit_pct:.1f}%. Confidence: {confidence}/10."
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


def check_alerts(current_prices, portfolio_config):
    """Legacy alert checking function (backward compatibility)"""
    alerts = []
    
    for ticker, price in current_prices.items():
        if price <= 0:
            continue
            
        config = portfolio_config[ticker]
        buy_target = config['buy_target']
        sell_target = config['sell_target']
        
        # BUY SIGNAL: Price at or below buy target
        if price <= buy_target:
            alert = f"🟢 BUY SIGNAL: {ticker} hit ${price:.2f} (target <=${buy_target:.2f}). Time to buy!"
            alerts.append(alert)
            print(f"  🟢 BUY alert: {ticker}")
        
        # SELL SIGNAL: Price at or above sell target
        elif price >= sell_target:
            profit_pct = ((price - buy_target) / buy_target) * 100
            alert = f"🔴 SELL SIGNAL: {ticker} hit ${price:.2f} (target >=${sell_target:.2f}). Consider taking profits! Est. gain: {profit_pct:.1f}%"
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


def save_targets_to_firestore(ticker, claude_analysis, analyst_data, financials):
    """Save analysis results to Firestore"""
    try:
        db = firestore.Client()
        
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
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'data_sources': analyst_data['data_sources'],
            'pe_ratio': financials.get('pe_ratio'),
            'market_cap': financials.get('market_cap')
        }
        
        # Save to Firestore
        db.collection('portfolio_targets').document(ticker).set(target_doc)
        return target_doc
        
    except Exception as e:
        print(f"  ⚠️ Failed to save {ticker} to Firestore: {type(e).__name__}: {e}")
        # Log additional context for debugging
        import os
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'unknown')
        print(f"     Context: Project={project_id}, Document=portfolio_targets/{ticker}")
        print(f"     Operation: save_target, Data_size={len(str(target_doc))} chars")
        # Log if specific Firestore errors
        if 'permission' in str(e).lower():
            print(f"     Hint: Check Firestore permissions for project {project_id}")
        elif 'quota' in str(e).lower():
            print(f"     Hint: Check Firestore quotas and billing for project {project_id}")
        return None


def _parse_iso_to_utc(dt_value):
    """Parse ISO timestamp or datetime to timezone-aware UTC datetime"""
    try:
        if isinstance(dt_value, datetime):
            if dt_value.tzinfo is None:
                return dt_value.replace(tzinfo=timezone.utc)
            return dt_value.astimezone(timezone.utc)
        if isinstance(dt_value, str):
            dt_str = dt_value.replace('Z', '+00:00')
            parsed = datetime.fromisoformat(dt_str)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
    except Exception as e:
        print(f"  ⚠️ Failed to parse timestamp '{dt_value}': {e}")
    return None


def can_send_summary(kind: str = 'daily_summary', cooldown_minutes: int = 60):
    """Check Firestore for last send time; enforce cooldown window"""
    try:
        db = firestore.Client()
        doc_ref = db.collection('system_status').document(kind)
        doc = doc_ref.get()
        now_utc = datetime.now(timezone.utc)
        if doc.exists:
            data = doc.to_dict()
            last_sent_val = data.get('last_sent')
            last_sent = _parse_iso_to_utc(last_sent_val)
            if last_sent:
                delta = now_utc - last_sent
                if delta < timedelta(minutes=cooldown_minutes):
                    remaining = int((timedelta(minutes=cooldown_minutes) - delta).total_seconds() // 60)
                    print(f"⏳ Dedup: last '{kind}' sent {int(delta.total_seconds()//60)} min ago; {remaining} min left in cooldown")
                    return False, remaining
        return True, None
    except Exception as e:
        print(f"⚠️ Dedup check failed ({type(e).__name__}): {e}. Proceeding to send.")
        return True, None


def mark_summary_sent(kind: str = 'daily_summary', meta: dict | None = None):
    """Record that a summary email was sent now with optional metadata"""
    try:
        db = firestore.Client()
        doc_ref = db.collection('system_status').document(kind)
        payload = {
            'last_sent': datetime.now(timezone.utc).isoformat(),
            'meta': meta or {}
        }
        doc_ref.set(payload)
        print(f"✅ Dedup: recorded '{kind}' sent")
        return True
    except Exception as e:
        print(f"⚠️ Failed to record dedup state: {type(e).__name__}: {e}")
        return False
