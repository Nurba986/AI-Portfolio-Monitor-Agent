# Portfolio Agent - Automated Stock Monitoring System

## 🎯 What This System Does
- **Monitors 5 stocks** (ASML, SNY, JD, UNH, XOM) automatically in Google Cloud
- **Sends email alerts** when stocks hit buy/sell targets  
- **Updates targets monthly** using Claude AI analysis
- **Runs 24/7** even when your computer is off

## 🚀 Quick Status Check
- **✅ DEPLOYED**: Both functions running on Google Cloud Platform
- **✅ SCHEDULER**: 2 jobs active (hourly monitoring + monthly updates)  
- **✅ TESTED**: Email alerts and AI analysis working
- **📧 EMAIL**: Notifications every hour (only when alerts found)

## 🔧 Testing Commands (Run Locally First)
```bash
# Test email and basic monitoring
portfolio-env/bin/python3 test_local.py

# Test AI analyst data collection  
portfolio-env/bin/python3 test_enhanced.py

# Run main function locally
portfolio-env/bin/python3 main.py
```

## 🌐 Deployment Commands (Already Done)
```bash
# Deploy both cloud functions
gcloud functions deploy portfolio-monitor --runtime python312 --trigger-http --entry-point portfolio_monitor --source .
gcloud functions deploy monthly-target-update --runtime python312 --trigger-http --entry-point monthly_target_update --source .

# Set environment variables
gcloud functions set-env-vars portfolio-monitor GMAIL_USER=your_email@gmail.com GMAIL_PASSWORD=your_app_password CLAUDE_API_KEY=your_claude_key

# Create schedulers
gcloud scheduler jobs create http portfolio-monitor-job --location=us-central1 --schedule="0 * * * *" --uri=https://us-central1-portfolio-monitor-465018.cloudfunctions.net/portfolio-monitor
gcloud scheduler jobs create http monthly-target-update-job --location=us-central1 --schedule="0 9 1 * *" --uri=https://us-central1-portfolio-monitor-465018.cloudfunctions.net/monthly-target-update
```

## 📊 Current Architecture

### **Files Structure**
```
Portfolio-Agent/
├── main.py              ← Contains 2 cloud functions
├── requirements.txt     ← Python dependencies
└── portfolio-env/       ← Virtual environment for local testing
```

### **Cloud Functions (in main.py)**
1. **`portfolio_monitor()`** - Runs every hour
   - Gets current stock prices from Yahoo Finance
   - Compares to buy/sell targets
   - Sends email alerts when targets hit
   - Cost: ~FREE

2. **`monthly_target_update()`** - Runs 1st of month
   - Collects analyst data
   - Uses Claude AI for analysis  
   - Updates buy/sell targets in Firestore
   - Cost: ~$2.50/month

### **Google Cloud Scheduler Jobs**
- **portfolio-monitor-job**: Every hour (`0 * * * *`)
- **monthly-target-update-job**: Monthly (`0 9 1 * *`)
- **Location**: us-central1
- **Timezone**: America/New_York

## 🎯 How It Works (Simple Explanation)
1. **Monthly** (1st of month): AI analyzes each stock and sets new buy/sell targets
2. **Hourly** (24/7): Checks current prices vs targets, emails you if buy/sell signals found  
3. **Automatic**: Everything runs in Google Cloud without your computer

## 🔍 Key Features
- **Smart Targets**: AI-powered buy/sell prices updated monthly
- **Real-time Monitoring**: Stock prices checked every hour
- **Email Alerts**: Only get notified when action is needed
- **Confidence Scoring**: AI rates its target confidence (1-10)
- **Fallback System**: Uses hardcoded targets if AI fails
- **Cost Efficient**: ~$3/month total cost