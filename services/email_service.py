"""
Email service for Portfolio Agent
Consolidates all email functionality with shared utilities
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone


def _setup_smtp_connection():
    """Setup and return configured SMTP connection"""
    sender_email = os.environ['GMAIL_USER']
    sender_password = os.environ['GMAIL_PASSWORD']
    
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, sender_password)
    
    return server, sender_email


def _send_email(subject, html_body):
    """Common email sending functionality"""
    try:
        server, sender_email = _setup_smtp_connection()
        recipient = os.environ.get('ALERT_RECIPIENT', sender_email)
        
        # Create and send email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient
        msg.attach(MIMEText(html_body, 'html'))
        
        server.send_message(msg)
        server.quit()
        
        return True, recipient
        
    except Exception as e:
        return False, str(e)


def send_enhanced_email(alerts, current_prices, dynamic_targets):
    """Enhanced email alert with dynamic targets and confidence scores"""
    try:
        # Count alert types
        buy_alerts = sum(1 for alert in alerts if alert['type'] == 'BUY')
        sell_alerts = sum(1 for alert in alerts if alert['type'] == 'SELL')
        watch_alerts = sum(1 for alert in alerts if alert['type'] == 'WATCH')
        
        # Create email subject with alert breakdown  
        subject = f"=> Daily Portfolio Summary - {buy_alerts}BUY {sell_alerts}SELL {watch_alerts}WATCH"
        
        # Create enhanced HTML email body
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <h2 style="color: #1a73e8;">=> Daily Portfolio Summary</h2>
            <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d at %H:%M:%S EST')}</p>
            <p><strong>Signal Summary:</strong> {buy_alerts} Buy, {sell_alerts} Sell, {watch_alerts} Watch Opportunities</p>
            <p><strong>Portfolio:</strong> {len(current_prices)} stocks monitored with AI-powered targets (daily at 3 PM ET)</p>
            
            <h3 style="color: #ea4335;">=> Trading Opportunities ({len(alerts)})</h3>
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
            
            confidence_bar = "*" * min(confidence, 10)  # Visual confidence indicator
            
            html_body += f"""
            <li style="color: {color}; margin: 10px 0; padding: 10px; background-color: {color}15; border-radius: 5px;">
                <strong>[{priority}]</strong> {alert['message']}<br>
                <small style="color: #666;">Confidence: {confidence_bar} ({confidence}/10)</small>
            </li>
            """
        
        html_body += """
            </ul>
            
            <h3 style="color: #1a73e8;">=> Enhanced Stock Status</h3>
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
            buy_target = target_config.get('buy_target', 0)
            sell_target = target_config.get('sell_target', 0)
            confidence = target_config.get('confidence_score', 3)
            catalyst = target_config.get('key_catalyst', 'N/A')[:30] + "..."
            
            # Color code based on targets and confidence
            if buy_target and price <= buy_target:
                row_color = "#e8f5e8"  # Light green
            elif sell_target and price >= sell_target:
                row_color = "#fce8e6"  # Light red
            elif confidence >= 7:
                row_color = "#f0f9ff"  # Light blue for high confidence
            else:
                row_color = "white"
            
            # Confidence indicator
            confidence_icon = "***" if confidence >= 8 else "**" if confidence >= 6 else "*"
            
            buy_display = f"${buy_target:.2f}" if buy_target else "N/A"
            sell_display = f"${sell_target:.2f}" if sell_target else "N/A"
            
            html_body += f"""
                <tr style="background-color: {row_color};">
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>{ticker}</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${price:.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{buy_display}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{sell_display}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{confidence_icon} {confidence}/10</td>
                    <td style="border: 1px solid #ddd; padding: 8px; font-size: 11px;">{catalyst}</td>
                </tr>
            """
        
        # Add AI insights summary
        high_confidence = sum(1 for target in dynamic_targets.values() 
                             if target['confidence_score'] >= 7)
        # Count recent updates (with proper timezone handling)
        now_utc = datetime.now(timezone.utc)
        recent_updates = 0
        for target in dynamic_targets.values():
            if target['updated_at']:
                try:
                    # Parse ISO format datetime with timezone awareness
                    updated_at_str = target['updated_at'].replace('Z', '+00:00')
                    updated_at = datetime.fromisoformat(updated_at_str)
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    
                    days_diff = (now_utc - updated_at).days
                    if days_diff <= 30:
                        recent_updates += 1
                except (ValueError, TypeError):
                    # Skip invalid datetime strings
                    continue
        
        html_body += f"""
            </table>
            
            <h3 style="color: #1a73e8;">=> AI Analysis Summary</h3>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <p><strong>=> Target Quality:</strong> {high_confidence}/{len(dynamic_targets)} stocks with high confidence (7+/10)</p>
                <p><strong>=> Data Freshness:</strong> {recent_updates}/{len(dynamic_targets)} targets updated within 30 days</p>
                <p><strong>=> Alert Accuracy:</strong> Enhanced with analyst consensus + Claude AI analysis</p>
                <p><strong>=> Next Update:</strong> Targets refresh monthly with latest fundamentals</p>
            </div>
            
            <hr style="margin: 20px 0;">
            <p style="color: #666; font-size: 12px;">
                => Daily Portfolio Monitor powered by Claude AI + Free Analyst Data<br>
                => Dynamic targets updated monthly | => Daily monitoring at 3 PM ET | => Confidence-weighted signals<br>
                Data sources: Yahoo Finance API, MarketWatch, Claude AI analysis<br>
                => Cost-optimized: Daily monitoring reduces costs by ~86% while maintaining effectiveness
            </p>
        </body>
        </html>
        """
        
        success, result = _send_email(subject, html_body)
        
        if success:
            print(f"=> Daily portfolio summary sent successfully to {result}")
        else:
            print(f"=> Failed to send enhanced email: {result}")
            
    except Exception as e:
        print(f"=> Failed to send enhanced email: {e}")


def send_target_update_email(updated_targets, estimated_cost):
    """Send email notification about updated targets"""
    try:
        subject = f"=> Portfolio Targets Updated - {len(updated_targets)} stocks"
        
        # Create HTML email body
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <h2 style="color: #1a73e8;">=> Monthly Target Update</h2>
            <p><strong>Update Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')}</p>
            <p><strong>Stocks Analyzed:</strong> {len(updated_targets)}</p>
            <p><strong>Estimated Cost:</strong> ${estimated_cost:.2f}</p>
            
            <h3 style="color: #34a853;">=> New Price Targets</h3>
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
            
            <h3 style="color: #1a73e8;">=> Analysis Summary</h3>
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
                => Automated target update powered by Claude AI analysis + free analyst data.<br>
                Next update scheduled for next month. Daily monitoring continues with new targets.<br>
                Data sources: Yahoo Finance API, MarketWatch, web scraping
            </p>
        </body>
        </html>
        """
        
        success, result = _send_email(subject, html_body)
        
        if success:
            print(f"=> Target update email sent successfully to {result}")
        else:
            print(f"=> Failed to send target update email: {result}")
            
    except Exception as e:
        print(f"=> Failed to send target update email: {e}")


def send_email(alerts, current_prices, portfolio_config):
    """Send email alert with portfolio information (legacy function)"""
    try:
        # Create email subject
        subject = f"=> Portfolio Alert - {len(alerts)} notifications"
        
        # Create HTML email body
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <h2 style="color: #1a73e8;">=> Portfolio Alert</h2>
            <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')}</p>
            <p><strong>Monitoring:</strong> {len(current_prices)} stocks</p>
            
            <h3 style="color: #ea4335;">=> Alerts ({len(alerts)})</h3>
            <ul>
        """
        
        # Add alerts
        for alert in alerts:
            if "BUY" in alert:
                color = "#34a853"  # Green
            elif "SELL" in alert:
                color = "#ea4335"  # Red
            elif "WATCH" in alert:
                color = "#fbbc04"  # Yellow
            else:
                color = "#1a73e8"  # Blue
                
            html_body += f'<li style="color: {color}; margin: 10px 0;">{alert}</li>'
        
        html_body += """
            </ul>
            
            <h3 style="color: #1a73e8;">=> Current Stock Status</h3>
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
            config = portfolio_config[ticker]
            
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
                => Automated alert from your Portfolio Monitor running on Google Cloud Platform.<br>
                Agent checks your stocks and sends alerts when buy/sell targets are hit.
            </p>
        </body>
        </html>
        """
        
        success, result = _send_email(subject, html_body)
        
        if success:
            print(f"=> Email alert sent successfully to {result}")
        else:
            print(f"=> Failed to send email: {result}")
            
    except Exception as e:
        print(f"=> Failed to send email: {e}")