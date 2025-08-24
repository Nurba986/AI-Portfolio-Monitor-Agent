# PRODUCT REQUIREMENTS DOCUMENT

## Portfolio Agent - AI-Powered Stock Monitoring System

**Overview**

- **Product Name**: Portfolio Agent
- **Problem**: Individual investors lack automated, intelligent stock monitoring with timely alerts for trading opportunities across their portfolio
- **Users**: Individual stock investors who want systematic, AI-enhanced monitoring of their equity positions
- **Success**: Reliable daily monitoring with high-confidence trading signals that help users make better investment decisions

**Goals**

- **Primary Goal**: Provide automated daily stock monitoring with AI-powered buy/sell alerts for 18 selected stocks
- **Timeline**: System is production-ready and deployed on Google Cloud Platform

**Users**

- **Primary User**: Individual Stock Investor
  - **Goals**: 
    - Monitor multiple stocks efficiently without manual daily checking
    - Receive timely alerts when stocks hit buy/sell targets
    - Access AI-enhanced analysis for better trading decisions
  - **Pain Points**: 
    - Time-consuming manual portfolio monitoring
    - Missing trading opportunities due to lack of systematic alerts
    - Difficulty accessing professional-grade analysis tools
    - Inconsistent target pricing without fundamental backing

**Features**

- **Feature 1**: Daily Portfolio Monitoring
  - **What**: Automated stock price tracking with alert generation every weekday at 3 PM ET
  - **Why**: Provides consistent, timely notifications without manual intervention during market hours
  - **Requirements**:
    - Monitor 12 pre-configured stocks: ASML, SNY, JD, UNH, XOM, ADM, BABA, FSLR, NKE, NTR, RIO, TCEHY
    - Execute only during US market hours (9:30 AM - 4:00 PM ET, Monday-Friday)
    - Skip execution on US market holidays
    - Generate BUY, SELL, and WATCH alerts based on dynamic price targets
    - Send HTML email notifications with color-coded alerts

- **Feature 2**: AI-Powered Target Generation
  - **What**: Monthly analysis using Claude AI to generate intelligent buy/sell price targets
  - **Why**: Provides fundamental analysis-backed targets with confidence scoring, superior to static targets
  - **Requirements**:
    - Integrate with Anthropic Claude Haiku API for cost-optimized analysis
    - Combine multiple data sources: Yahoo Finance API, MarketWatch web scraping, analyst consensus
    - Generate confidence scores (1-10) based on data quality and consistency
    - Store analysis results in Google Firestore for persistence
    - Include key catalysts and risk factors for each target
    - Update targets monthly with latest financial data

- **Feature 3**: Enhanced Email Alert System
  - **What**: Rich HTML notifications with comprehensive portfolio insights
  - **Why**: Provides actionable information in a professional, easy-to-read format
  - **Requirements**:
    - Color-coded alerts (Green=BUY, Red=SELL, Yellow=WATCH)
    - Confidence indicators with visual scoring
    - Complete portfolio status table with current prices vs targets
    - AI analysis summary with target quality metrics
    - Support for custom recipient configuration
    - Mobile-friendly HTML formatting

- **Feature 4**: Market Hours Logic & Holiday Detection
  - **What**: Intelligent scheduling that respects US stock market operating hours
  - **Why**: Prevents unnecessary execution and API costs when markets are closed
  - **Requirements**:
    - Built-in US market holiday calendar (2025-2026)
    - Eastern Time zone awareness
    - Automatic weekend detection
    - Clear logging of skip reasons
    - Market status validation before expensive API calls

- **Feature 5**: Fallback & Reliability System
  - **What**: Multi-layered fallback mechanisms to ensure system reliability
  - **Why**: Maintains service availability even when external dependencies fail
  - **Requirements**:
    - Hardcoded price targets as Firestore fallback
    - Multiple stock price data sources (bulk + individual fetch)
    - Graceful error handling with detailed logging
    - Partial failure tolerance (continue monitoring other stocks if one fails)
    - Cost-optimized retry strategies

**User Flow**

1. **Daily Monitoring Flow**:
   - System triggers automatically at 3 PM ET on weekdays
   - Validates market is open, exits if closed/holiday
   - Loads dynamic targets from Firestore (falls back to hardcoded if needed)
   - Fetches current stock prices using optimized bulk API calls
   - Analyzes prices against targets, generates alerts with confidence scoring
   - Sends HTML email summary if alerts exist
   - Logs execution results for monitoring

2. **Monthly Target Update Flow**:
   - Triggers monthly via Cloud Scheduler
   - For each stock: collects analyst data, fetches enhanced financials
   - Submits comprehensive data to Claude AI for analysis
   - Parses AI response for buy/sell targets, confidence, catalysts, risks
   - Saves results to Firestore database
   - Sends summary email with updated targets and cost breakdown

**Technical**

- **Architecture**: Serverless microservices on Google Cloud Platform
- **Runtime**: Python 3.13 with modular service architecture
- **Integrations**: 
  - Yahoo Finance API (stock prices, financial data)
  - Anthropic Claude Haiku API (AI analysis)
  - Google Firestore (target storage)
  - Gmail SMTP (notifications)
  - MarketWatch (web scraping for analyst data)
- **Performance**: 
  - Daily execution: <60 seconds total runtime
  - Monthly updates: ~10 minutes for 18 stocks
  - Email delivery: <5 seconds
  - API cost optimization: ~$9/month for Claude API
- **Security**:
  - Environment variables for all credentials
  - Gmail app passwords (not account passwords)
  - HTTPS-only external communications
  - Input validation for all external API data
  - No sensitive data in logs or responses

**Success Metrics**

- **User Metrics**:
  - Email delivery success rate: >99%
  - Alert accuracy: High-confidence alerts (7+/10) comprise >50% of signals
  - System uptime during market hours: >99.5%
  - User engagement: Email open/click rates for trading alerts

- **Business Metrics**:
  - Cost efficiency: <$15/month total operating costs
  - Execution reliability: <1 failed run per month
  - Target freshness: >80% of targets updated within 30 days
  - Data quality: >90% of stocks have high-confidence targets

**Implementation**

- **Phase 1: Core System (Completed)**
  - Daily monitoring Cloud Function deployed
  - Email notification system operational
  - Hardcoded target fallback system
  - Market hours validation
  - Basic error handling and logging

- **Phase 2: AI Enhancement (Completed)**
  - Claude AI integration for target generation
  - Google Firestore integration for dynamic targets
  - Enhanced email templates with confidence scoring
  - Multi-source data collection and validation
  - Monthly target update automation

- **Phase 3: Optimization & Monitoring (Current)**
  - Performance monitoring and alerting
  - Cost optimization analysis
  - Enhanced error recovery mechanisms
  - Portfolio expansion capabilities
  - Advanced analytics and reporting

**Risks**

- **API Dependency Risk** → Implement multiple fallback data sources and graceful degradation
- **Cost Overrun Risk** → Use cost-optimized Claude Haiku model, implement rate limiting
- **Market Data Quality Risk** → Multi-source validation with confidence scoring system  
- **Email Delivery Risk** → Monitor delivery success, implement alternative notification channels
- **Cloud Platform Risk** → Design stateless functions, maintain deployment automation
- **Regulatory Risk** → Ensure compliance with financial data usage terms, add appropriate disclaimers

---

**Technical Architecture Details**

**Service Modules**:
- `main.py`: Cloud Functions entry points (portfolio_monitor, monthly_target_update)
- `services/utils.py`: Market hours validation, HTTP sessions, data formatting
- `services/data_collector.py`: Multi-source stock data aggregation with threading
- `services/ai_analyzer.py`: Claude AI integration and prompt engineering  
- `services/portfolio_manager.py`: Firestore integration, alert logic, target management
- `services/email_service.py`: HTML email generation and SMTP delivery

**Deployment**:
- Google Cloud Functions (serverless, auto-scaling)
- Google Cloud Scheduler (automated triggers)  
- Environment variables via .env.yaml (local) / Cloud Console (production)
- Requirements managed via requirements.txt with pinned versions

**Monitoring & Observability**:
- Structured logging with Cloud Functions logs
- Email delivery confirmation
- Error tracking with detailed stack traces
- Performance metrics via execution time logging
- Cost tracking via API usage monitoring

This PRD reflects the current production system's capabilities and provides a roadmap for future enhancements while maintaining the core value proposition of automated, intelligent stock monitoring.