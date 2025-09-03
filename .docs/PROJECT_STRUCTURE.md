# Project Structure Portfolio Agent

> **Architectural map of the project for AI agents and developers**

## 🏗️ General Architecture

The project is a **Serverless Cloud Functions Application** based on **Python + Google Cloud Functions + Claude AI** with monolithic architecture. Uses **Python 3.13** with **gcloud CLI** for deployment and **Local Testing** for validation.

### Technology Stack

- **Runtime**: Python 3.13 with Google Cloud Functions Framework
- **AI/ML**: Claude AI (Anthropic) for fundamental analysis
- **Data Sources**: Yahoo Finance API, MarketWatch scraping, Google Firestore
- **Notifications**: Gmail SMTP with HTML email templates
- **Deployment**: Google Cloud Functions + Cloud Scheduler

## 📁 Directory Structure

### Root Directory

```
/Portfolio-Agent/
├── main.py                  # Single entry point with all Cloud Functions
├── requirements.txt         # Python dependencies
├── .env.yaml               # Environment variables (local only)
├── CLAUDE.md               # AI agent guidance
├── README.md               # Project documentation
└── portfolio-env/          # Python virtual environment
```

### Virtual Environment (`portfolio-env/`)

```
portfolio-env/
├── bin/                    # Python executables and activation scripts
├── include/               # C headers for Python extensions
├── lib/python3.13/        # Installed packages and dependencies
└── pyvenv.cfg            # Virtual environment configuration
```

## 🧩 Key Architecture Components

### 1. Entry Point (`main.py`)

- Contains both Cloud Functions: `portfolio_monitor()` and `monthly_target_update()`
- Stock portfolio configuration (PORTFOLIO dictionary with 12 stocks)
- Market hours validation and holiday detection logic
- Email notification system with HTML templates

### 2. Cloud Functions Architecture

- **portfolio_monitor()**: Daily stock monitoring at 3 PM ET (Mon-Fri)
- **monthly_target_update()**: AI-powered target generation (1st of month)
- **Helper Functions**: 20+ utility functions for data processing, alerts, AI analysis

### 3. Data Flow Pattern

Each monitoring cycle includes:

- **Price Fetching** (`get_stock_prices_fast()`)
- **Target Comparison** (`check_enhanced_alerts()`)
- **Email Alerts** (`send_enhanced_email()`)
- **Portfolio Valuation** (`calculate_portfolio_value()`)

## 🔧 Configuration Files

### Requirements (`requirements.txt`)

- **Runtime**: `functions-framework==3.*`
- **Finance Data**: `yfinance`, `pytz`
- **Web Scraping**: `beautifulsoup4`, `requests`, `urllib3`
- **Cloud Services**: `google-cloud-firestore`
- **AI Integration**: `anthropic`

### Environment Variables (`.env.yaml`)

- **Email**: GMAIL_USER, GMAIL_PASSWORD, ALERT_RECIPIENT
- **AI**: CLAUDE_API_KEY
- **Security**: All credentials stored locally, not in git

## 🎯 Main Application Modules

### Core Stock Monitoring Functions:

#### 1. Market Data Collection (`main.py:320-359`)

- Bulk + threaded stock price fetching (3-5x performance)
- Yahoo Finance API integration with retry logic
- Real-time price validation and error handling
- Multi-source data aggregation

#### 2. AI-Powered Analysis (`main.py:717-933`)

- Claude AI fundamental analysis integration
- Analyst consensus data scraping (MarketWatch)
- Confidence scoring system (1-10 scale)
- Target price generation with reasoning

#### 3. Alert System (`main.py:1207-1315`)

- Buy/sell/watch signal generation
- HTML email formatting with color coding
- Portfolio value tracking and reporting
- Market hours and holiday validation

#### 4. Data Storage Integration (`main.py:1135-1207`)

- Google Firestore for dynamic target storage
- Fallback to hardcoded targets system
- Historical data persistence
- Target update management

#### 5. Email Notification System (`main.py:1315-1484`)

- Gmail SMTP integration with retry logic
- HTML template generation
- Confidence indicators and signal colors
- Portfolio summary and value calculations

## 🔄 Data Flow

### Portfolio Monitoring Flow

```
Market Hours Check → Stock Price Fetch → Target Comparison → Alert Generation → Email Send
     ↓                     ↓                    ↓                  ↓              ↓
Holiday Detection → Bulk API Calls → Dynamic Targets → Buy/Sell Signals → HTML Email
```

### Monthly Target Update Flow:

- **Data Collection**: Multi-source analyst data gathering
- **AI Analysis**: Claude AI fundamental analysis with financials
- **Target Generation**: Buy/sell price recommendations with confidence
- **Storage Update**: Firestore database target updates
- **Notification**: Summary email with new targets

## 🛠️ Development Tools

### Local Development

```bash
source portfolio-env/bin/activate    # Activate virtual environment
pip install -r requirements.txt      # Install dependencies
python main.py                      # Test locally
```

### Google Cloud Deployment

```bash
gcloud functions deploy portfolio-monitor --runtime python313 --trigger-http --entry-point portfolio_monitor --env-vars-file .env.yaml
gcloud functions deploy monthly-target-update --runtime python313 --trigger-http --entry-point monthly_target_update --env-vars-file .env.yaml
```

### Cloud Scheduler Setup

```bash
gcloud scheduler jobs create http portfolio-monitor-job --schedule="0 15 * * 1-5" --time-zone="America/New_York"
gcloud scheduler jobs create http monthly-target-update-job --schedule="0 9 1 * *" --time-zone="America/New_York"
```

## 🔗 External Dependencies

### Main Libraries

- **functions-framework**: Google Cloud Functions runtime environment
- **yfinance**: Yahoo Finance API client for stock price data
- **anthropic**: Claude AI API client for fundamental analysis
- **google-cloud-firestore**: NoSQL database for dynamic target storage
- **beautifulsoup4**: HTML parsing for MarketWatch scraping
- **requests + urllib3**: HTTP client with retry logic

## 📊 Metrics and Monitoring

### Project Size

- ~1 main Python file (600+ lines)
- ~18 monitored stocks with dynamic targets
- ~20+ utility functions for data processing
- Monthly AI analysis with confidence scoring

### Performance

- Bulk + threaded stock price fetching (3-5x faster)
- Market hours validation prevents unnecessary execution
- Cost-optimized Claude Haiku model usage
- HTML email alerts only when targets are hit

## 🚨 Important Development Notes

### Architectural Constraints

1. **Single File Structure**: All logic contained in main.py for simplicity
2. **Serverless Limitations**: No persistent local storage, relies on Firestore
3. **Market Hours Only**: Functions only execute during valid trading hours
4. **Email Dependencies**: Requires Gmail app password configuration

### Integration Points

- **Yahoo Finance API**: Primary stock price data source with bulk fetching
- **Google Firestore**: Dynamic target storage with fallback system
- **Claude AI API**: Monthly fundamental analysis and target generation
- **Gmail SMTP**: HTML email notifications with retry logic

### Critical Dependencies

- **Claude API Key**: Required for AI-powered target generation
- **Gmail Credentials**: Essential for email alert functionality  
- **Google Cloud Project**: Firestore database and Cloud Functions deployment

***

> **Note**: This document serves as a navigation map for AI agents and developers. The project uses a minimalist single-file architecture optimized for serverless deployment and cost efficiency.