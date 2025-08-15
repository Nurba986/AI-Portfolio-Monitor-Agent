# 🤖 Portfolio Agent - AI-Powered Stock Monitoring

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Functions-orange.svg)](https://cloud.google.com)
[![Claude AI](https://img.shields.io/badge/Claude%20AI-Powered-purple.svg)](https://anthropic.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Automated stock portfolio monitoring system that runs 24/7 on Google Cloud Platform. Uses AI-powered analysis to generate dynamic buy/sell targets and sends email alerts when opportunities arise.

## 🎯 What It Does

- **🤖 AI-Powered Targets**: Monthly Claude AI analysis generates intelligent buy/sell targets
- **📧 Smart Alerts**: Email notifications only when stocks hit your targets
- **🔄 24/7 Monitoring**: Runs automatically on Google Cloud Platform
- **📊 Multiple Data Sources**: Yahoo Finance API + analyst consensus data
- **💰 Cost Efficient**: ~$3/month total operating cost

## 🚀 Features

### **Automated Monitoring**
- Checks 5 stocks during market hours only (ASML, SNY, JD, UNH, XOM)
- Runs 9:00 AM - 5:00 PM ET, Monday-Friday, excluding holidays
- Compares current prices to AI-generated targets
- Sends email alerts with confidence scores and reasoning

### **AI-Powered Analysis**
- Monthly Claude AI fundamental analysis
- Integrates analyst consensus data
- Confidence-scored recommendations (1-10 scale)
- Key catalyst identification and risk assessment

### **Smart Notifications**
- HTML email alerts with color-coded signals
- Buy/sell/watch recommendations
- Portfolio value tracking
- Market insights and analysis summary

## 📊 Current Portfolio

| Stock | Current Status | AI Analysis |
|-------|---------------|-------------|
| ASML  | Semiconductor leader | Monthly AI target updates |
| SNY   | Healthcare dividend | Analyst consensus tracking |
| JD    | Chinese e-commerce | Growth potential analysis |
| UNH   | Healthcare insurance | Defensive positioning |
| XOM   | Energy sector | Commodity cycle timing |

## 🛠️ Technology Stack

- **Runtime**: Python 3.12
- **Cloud Platform**: Google Cloud Functions
- **Scheduler**: Google Cloud Scheduler  
- **Database**: Google Firestore
- **AI Analysis**: Claude AI (Anthropic)
- **Data Sources**: Yahoo Finance API, MarketWatch
- **Notifications**: Gmail SMTP

## 📋 Prerequisites

Before deploying, you'll need:

1. **Google Cloud Account** (free tier available)
2. **Gmail Account** with App Password enabled
3. **Claude AI API Key** (for monthly analysis)
4. **Python 3.12+** for local testing

## 🚀 Quick Start

### 1. Clone and Setup
```bash
git clone https://github.com/yourusername/Portfolio-Agent.git
cd Portfolio-Agent
python3 -m venv portfolio-env
source portfolio-env/bin/activate  # On Windows: portfolio-env\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Credentials
Create `.env.yaml`:
```yaml
GMAIL_USER: "your_email@gmail.com"
GMAIL_PASSWORD: "your_16_character_app_password"
CLAUDE_API_KEY: "your_claude_api_key_here"
```

### 3. Test Locally
```bash
# Test basic functionality
portfolio-env/bin/python3 test_local.py

# Test AI features
portfolio-env/bin/python3 test_enhanced.py
```

### 4. Deploy to Google Cloud
```bash
# Enable required services
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable firestore.googleapis.com

# Deploy functions
gcloud functions deploy portfolio-monitor \
  --runtime python312 \
  --trigger-http \
  --entry-point portfolio_monitor \
  --env-vars-file .env.yaml

gcloud functions deploy monthly-target-update \
  --runtime python312 \
  --trigger-http \
  --entry-point monthly_target_update \
  --env-vars-file .env.yaml

# Create schedulers
gcloud scheduler jobs create http portfolio-monitor-job \
  --location=us-central1 \
  --schedule="0 * * * *" \
  --time-zone="America/New_York" \
  --uri=https://YOUR_REGION-YOUR_PROJECT.cloudfunctions.net/portfolio-monitor

gcloud scheduler jobs create http monthly-target-update-job \
  --location=us-central1 \
  --schedule="0 9 1 * *" \
  --time-zone="America/New_York" \
  --uri=https://YOUR_REGION-YOUR_PROJECT.cloudfunctions.net/monthly-target-update
```

## 📧 Email Alerts

You'll receive email notifications when:

- 🟢 **BUY SIGNAL**: Stock price hits or drops below AI-generated buy target
- 🔴 **SELL SIGNAL**: Stock price hits or exceeds AI-generated sell target  
- 🟡 **WATCH SIGNAL**: Stock within 5% of buy target (early warning)

Each alert includes:
- Confidence score (1-10) from AI analysis
- Key catalyst driving the recommendation
- Risk factors to consider
- Current price vs target comparison

## 💰 Cost Breakdown

| Service | Monthly Cost |
|---------|-------------|
| Google Cloud Functions | ~$1.00 |
| Google Cloud Scheduler | ~$0.20 |
| Google Firestore | ~$0.25 |
| Claude AI API | ~$2.50 |
| **Total** | **~$3.95** |

*Costs based on typical usage. Free tiers may reduce actual costs.*

## 📁 Project Structure

```
Portfolio-Agent/
├── main.py                 # Core application with 2 cloud functions
├── requirements.txt        # Python dependencies
├── .env.yaml              # Credentials (not in git)
├── test_local.py          # Local testing script
├── test_enhanced.py       # AI features testing
├── AGENTS.md              # Development guide
├── complete_setup_guide.md # Detailed setup instructions
└── README.md              # This file
```

## 🔧 Configuration

### Portfolio Stocks
Edit the `PORTFOLIO` dictionary in `main.py` to modify:
- Stocks to monitor
- Hardcoded fallback targets
- Position sizes (for value calculation)

### AI Analysis
The system performs monthly AI analysis on the 1st of each month at 9 AM EST, updating:
- Buy/sell targets based on fundamental analysis
- Confidence scores for each recommendation
- Key catalysts and risk factors

### Alert Frequency
- **Monitoring**: Every hour during market hours (9 AM - 5 PM ET, Mon-Fri, excluding holidays)
- **Target Updates**: Monthly (1st of month)
- **Email Alerts**: Only when signals are triggered during market hours

## 🔍 Monitoring & Logs

```bash
# View function logs
gcloud functions logs read portfolio-monitor --region=us-central1

# Check scheduler status
gcloud scheduler jobs list --location=us-central1

# Test functions manually
curl https://YOUR_REGION-YOUR_PROJECT.cloudfunctions.net/portfolio-monitor
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## ⚠️ Disclaimer

This tool is for educational and informational purposes only. It does not constitute financial advice. Always do your own research and consult with financial professionals before making investment decisions.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Yahoo Finance](https://finance.yahoo.com) for real-time stock data
- [Anthropic Claude](https://anthropic.com) for AI analysis capabilities
- [Google Cloud Platform](https://cloud.google.com) for reliable infrastructure
- [MarketWatch](https://marketwatch.com) for analyst consensus data

---

**Made with ❤️ and AI**