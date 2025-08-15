# 🚀 Portfolio Agent - Complete Setup & Usage Guide

**✅ CURRENT STATUS: FULLY DEPLOYED & WORKING**

**What this system does:** 
- 🤖 Monitors 5 stocks (ASML, SNY, JD, UNH, XOM) automatically 24/7
- 📧 Sends email alerts when stocks hit buy/sell targets  
- 🎯 Updates targets monthly using Claude AI analysis
- 💰 Runs on Google Cloud Platform (~$3/month)

**🚀 QUICK CHECK:**
- **Functions deployed**: ✅ portfolio-monitor + monthly-target-update
- **Schedulers active**: ✅ Market hours monitoring + Monthly AI updates  
- **Market hours**: ✅ 9 AM - 5 PM ET, Mon-Fri, excluding holidays
- **Last tested**: ✅ Email alerts working, AI analysis working
- **Next alert**: During market hours only (if targets hit)

---

## ✅ STEP 1: Google Cloud Setup

### 1.1 Create Project
1. Go to https://cloud.google.com/ → "Get started for free"
2. Sign in with nbu864@gmail.com
3. Create project: `portfolio-monitor`

### 1.2 Install & Authenticate
```bash
# Install Google Cloud CLI (download from Google)
# Authenticate
gcloud auth login
gcloud config set project portfolio-monitor
```

---

## ✅ STEP 2: API Keys Setup

### 2.1 Gmail App Password
1. Go to https://myaccount.google.com/security
2. Enable 2-Factor Authentication (if not done)
3. Go to "App passwords" → Create for "Mail"
4. Copy 16-character password (like: `abcd efgh ijkl mnop`)

### 2.2 Claude API Key (NEW!)
1. Go to https://console.anthropic.com/
2. Sign up/Login with your account
3. Go to "API Keys" → Create new key
4. Copy the API key (starts with `sk-ant-api03-...`)
5. **Important:** This enables monthly AI target updates (~$2-5/month)

---

## ✅ STEP 3: Create Project Files

### 3.1 Create folder and virtual environment
```bash
mkdir portfolio-agent
cd portfolio-agent
python3 -m venv portfolio-env
source portfolio-env/bin/activate
```

### 3.2 Create main.py
**File: main.py** (Enhanced AI-powered portfolio monitoring - see full code above)

**Key enhancements in code:**
- 🤖 Claude AI integration for monthly target analysis
- 📊 Free analyst data aggregation (Yahoo Finance + MarketWatch)
- 🎯 Dynamic target loading from Firestore database
- 📧 Enhanced alerts with confidence scores and reasoning
- 🔄 Fallback to hardcoded targets if database unavailable

### 3.3 Create requirements.txt (UPDATED!)
**File: requirements.txt**
```
functions-framework==3.*
yfinance
pytz
beautifulsoup4
requests
google-cloud-firestore
anthropic
```

### 3.4 Create .env.yaml (UPDATED!)
**File: .env.yaml**
```yaml
GMAIL_USER: "nbu864@gmail.com"
GMAIL_PASSWORD: "your_16_character_app_password"
CLAUDE_API_KEY: "your_claude_api_key_here"
```

---

## ✅ STEP 4: Enhanced Local Testing

### 4.1 Install Enhanced Dependencies
```bash
# Install all packages locally
pip install yfinance pandas openpyxl beautifulsoup4 requests anthropic

# Test legacy system first
python test_local.py
# Should send test email to nbu864@gmail.com
```

### 4.2 Test Enhanced Features (NEW!)
```bash
# Test AI-powered analyst data collection
python test_enhanced.py
# Tests free analyst data aggregation and validation

# This will test:
# ✅ Yahoo Finance API enhanced extraction
# ✅ MarketWatch web scraping
# ✅ Data aggregation and confidence scoring
# ✅ All portfolio stocks analysis
```

**Note:** Enhanced testing takes 30-60 seconds due to web scraping multiple sources.

---

## ✅ STEP 5: Enable GCP Services

```bash
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudscheduler.googleapis.com  
gcloud services enable firestore.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Create Firestore database
gcloud firestore databases create --location=us-central1
```

---

## ✅ STEP 6: Deploy Enhanced Functions

### 6.1 Deploy Daily Monitoring Function (ENHANCED!)
```bash
gcloud functions deploy portfolio-monitor \
  --gen2 \
  --runtime python311 \
  --trigger-http \
  --entry-point portfolio_monitor \
  --memory 1GB \
  --timeout 180s \
  --region us-central1 \
  --env-vars-file .env.yaml \
  --allow-unauthenticated
```

### 6.2 Deploy Monthly Target Update Function (NEW!)
```bash
gcloud functions deploy monthly-target-update \
  --gen2 \
  --runtime python311 \
  --trigger-http \
  --entry-point monthly_target_update \
  --memory 1GB \
  --timeout 300s \
  --region us-central1 \
  --env-vars-file .env.yaml \
  --allow-unauthenticated
```

**Results:**
- Daily Monitor: `https://us-central1-portfolio-monitor-458018.cloudfunctions.net/portfolio-monitor`
- Monthly Updates: `https://us-central1-portfolio-monitor-458018.cloudfunctions.net/monthly-target-update`

---

## ✅ STEP 7: Create Enhanced Schedulers

### 7.1 Daily Monitoring (**UPDATED TO MARKET HOURS ONLY**)
```bash
gcloud scheduler jobs create http portfolio-monitor-job \
  --location=us-central1 \
  --schedule="0 * * * *" \
  --time-zone="America/New_York" \
  --uri="https://us-central1-portfolio-monitor-465018.cloudfunctions.net/portfolio-monitor" \
  --http-method=GET \
  --description="Portfolio monitoring during market hours (9 AM - 5 PM ET, Mon-Fri, excluding holidays)"
```

### 7.2 Monthly AI Target Updates 
```bash
gcloud scheduler jobs create http monthly-target-update-job \
  --location=us-central1 \
  --schedule="0 9 1 * *" \
  --time-zone="America/New_York" \
  --uri="https://us-central1-portfolio-monitor-465018.cloudfunctions.net/monthly-target-update" \
  --http-method=GET \
  --description="Monthly AI target updates using Claude analysis"
```

**🕐 CURRENT SCHEDULES:**
- **Daily:** Every hour during market hours (`0 * * * *`) - **LIVE NOW**
  - **Market Hours:** 9 AM - 5 PM ET, Monday-Friday only
  - **Holidays:** Automatically excluded (New Year's, MLK Day, Presidents' Day, Good Friday, Memorial Day, Juneteenth, July 4th, Labor Day, Thanksgiving, Christmas)
- **Monthly:** 1st of each month at 9 AM EST (`0 9 1 * *`) - **LIVE NOW**
- **Project:** portfolio-monitor-465018
- **Location:** us-central1

---

## 📊 YOUR ENHANCED PORTFOLIO TARGETS

### Current Hardcoded Targets (Fallback)
| Stock | Buy Target | Sell Target | Status |
|-------|------------|-------------|--------|
| ASML  | ≤ $633     | ≥ $987      | 🔄 Will be enhanced by AI |
| SNY   | ≤ $45      | ≥ $62       | 🔄 Will be enhanced by AI |
| JD    | ≤ $26.50   | ≥ $41       | 🔄 Will be enhanced by AI |
| UNH   | ≤ $300     | ≥ $388      | 🔄 Will be enhanced by AI |
| XOM   | ≤ $110     | ≥ $130      | 🔄 Will be enhanced by AI |

### Dynamic AI Targets (After First Monthly Update)
- 🤖 **Generated by:** Claude AI fundamental analysis
- 📊 **Based on:** Free analyst consensus + financial metrics  
- 🎯 **Confidence scores:** 1-10 rating for each target
- 📈 **Updated:** Monthly with latest market data
- 🔄 **Fallback:** Uses hardcoded targets if AI unavailable

---

## 🔧 ENHANCED USEFUL COMMANDS

### Test functions manually:
```bash
# Test daily monitoring (enhanced with AI targets):
curl https://us-central1-portfolio-monitor-458018.cloudfunctions.net/portfolio-monitor

# Test monthly target updates (NEW!):
curl https://us-central1-portfolio-monitor-458018.cloudfunctions.net/monthly-target-update
```

### View enhanced logs:
```bash
# Daily monitoring logs
gcloud functions logs read portfolio-monitor --region=us-central1 --limit=10

# Monthly update logs
gcloud functions logs read monthly-target-update --region=us-central1 --limit=10
```

### Update functions (after code changes):
```bash
# Update daily monitoring
gcloud functions deploy portfolio-monitor \
  --gen2 \
  --runtime python311 \
  --trigger-http \
  --entry-point portfolio_monitor \
  --memory 1GB \
  --timeout 180s \
  --region us-central1 \
  --env-vars-file .env.yaml \
  --allow-unauthenticated

# Update monthly target updates
gcloud functions deploy monthly-target-update \
  --gen2 \
  --runtime python311 \
  --trigger-http \
  --entry-point monthly_target_update \
  --memory 1GB \
  --timeout 300s \
  --region us-central1 \
  --env-vars-file .env.yaml \
  --allow-unauthenticated
```

### Manage enhanced schedulers:
```bash
# Daily monitoring
gcloud scheduler jobs pause portfolio-monitor-job --location=us-central1
gcloud scheduler jobs resume portfolio-monitor-job --location=us-central1

# Monthly updates
gcloud scheduler jobs pause monthly-target-update-job --location=us-central1
gcloud scheduler jobs resume monthly-target-update-job --location=us-central1
```

---

## 📧 ENHANCED EMAIL ALERTS

### Daily Alerts (Enhanced with AI)
**Enhanced email alerts when:**
- 🟢 **HIGH PRIORITY BUY:** AI target hit with confidence 7+/10 + catalyst reasoning
- 🔴 **HIGH PRIORITY SELL:** AI target hit with confidence 7+/10 + profit estimates  
- 🟡 **WATCH SIGNAL:** Stock within 5% of AI buy target
- 💡 **MEDIUM PRIORITY:** Lower confidence signals (4-6/10)

**Schedule:** Every hour during market hours (9:00 AM - 5:00 PM ET, Mon-Fri, excluding holidays)

**Enhanced email format:** 
- 🎯 Confidence-scored alerts with visual indicators
- 📊 AI analysis summary with target quality metrics
- 🔥 Key catalysts and risk factors for each stock
- 📈 Data freshness indicators and source tracking

### Monthly Target Update Emails (NEW!)
**What you get:**
- 🤖 Summary of Claude AI analysis for all 5 stocks
- 📊 New buy/sell targets with confidence scores
- 💡 Key catalysts driving each target
- 📈 Comparison vs previous targets and analyst consensus
- 💰 Estimated monthly AI cost (~$2-5)

---

## 🚨 TROUBLESHOOTING - Based on Real Issues Fixed

### **Problem: Getting emails outside market hours**
**Solution:**
✅ **FIXED:** Function now automatically checks market hours and only runs 9 AM - 5 PM ET, Mon-Fri, excluding holidays. 

**Problem: Getting emails on weekends/holidays**
**Solution:**
✅ **FIXED:** Function includes US stock market holiday calendar and weekend detection.

### **Problem: ModuleNotFoundError when testing locally**
**Solution:**
```bash
# Use virtual environment Python
portfolio-env/bin/python3 test_local.py
portfolio-env/bin/python3 test_enhanced.py
```

### **Problem: Missing monthly scheduler**
**Solution:**
```bash
# Create missing monthly scheduler
gcloud scheduler jobs create http monthly-target-update-job --location=us-central1 --schedule="0 9 1 * *" --uri=https://us-central1-portfolio-monitor-465018.cloudfunctions.net/monthly-target-update
```

### **Problem: Need to specify location for gcloud commands**
**Solution:**
```bash
# Always add --location=us-central1 for this project
gcloud scheduler jobs list --location=us-central1
gcloud functions logs read portfolio-monitor --region=us-central1
```

### **Common Issues**

**Function not working?**
- Check logs: `gcloud functions logs read portfolio-monitor --region=us-central1`
- Test manually: Visit function URL in browser
- Verify environment variables are set

**No emails?**
- Check spam folder
- Verify Gmail app password in .env.yaml  
- Test with: `curl [FUNCTION_URL]`
- Check if alerts are actually triggering (prices vs targets)

**Web scraping failing?**
- Normal behavior - MarketWatch blocks automated requests
- Yahoo Finance API is primary data source (working)
- System automatically falls back to hardcoded targets

**Cost concerns?**
- Daily monitoring: ~FREE (Yahoo Finance API, market hours only)
- Monthly AI updates: ~$2.50 (Claude API)
- Total: ~$3/month maximum
- **Reduced costs:** Market hours limitation reduces function executions by ~65%

---

## 💰 ENHANCED MONTHLY COST BREAKDOWN

### Enhanced System Costs
- **Cloud Functions:** ~$1.00/month (2 functions, more compute)
- **Cloud Scheduler:** ~$0.20/month (2 schedulers)
- **Firestore Database:** ~$0.25/month (dynamic target storage)
- **Claude API:** ~$2-5/month (monthly AI analysis)
- **Analyst Data:** FREE (Yahoo Finance + web scraping)
- **Email alerts:** FREE (Gmail)
- **Total:** ~$3-6/month (vs previous $0.65/month)

### Value Analysis
- **Previous:** Static targets, basic alerts
- **Enhanced:** AI-powered dynamic targets with confidence scores
- **ROI:** Potentially significant through better-timed trades
- **Cost per stock per month:** ~$0.60-1.20 (5 stocks)

---

## 📋 ENHANCED PROJECT FILES SUMMARY

```
portfolio-agent/
├── main.py              # Enhanced AI-powered portfolio monitoring
├── requirements.txt     # Enhanced Python dependencies (7 packages)
├── .env.yaml           # Gmail + Claude API credentials (keep private!)
├── test_local.py       # Legacy local testing script
├── test_enhanced.py    # NEW: AI analyst data testing
└── portfolio-env/      # Python virtual environment
```

### Enhanced Functions Deployed
- **Daily Monitor:** `https://us-central1-portfolio-monitor-458018.cloudfunctions.net/portfolio-monitor`
- **Monthly Updates:** `https://us-central1-portfolio-monitor-458018.cloudfunctions.net/monthly-target-update`

### Key Enhancements
- 🤖 **AI Analysis:** Claude API for fundamental analysis
- 📊 **Free Data:** Yahoo Finance + MarketWatch scraping  
- 🎯 **Smart Targets:** Confidence-scored buy/sell recommendations
- 📧 **Rich Alerts:** Enhanced emails with catalysts and reasoning
- 🔄 **Resilient:** Fallback to hardcoded targets if needed

**Your enhanced system now combines professional analyst consensus with AI analysis for significantly more intelligent portfolio monitoring!**