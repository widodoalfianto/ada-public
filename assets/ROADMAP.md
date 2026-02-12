# Trading Platform - Future Development Roadmap

## Overview
This document outlines the planned features and enhancements for the stock trading analysis platform beyond the alpha release. The roadmap is organized into phases, with each phase building upon the previous one.

---

## Current State (Alpha Release)
- ✅ Real-time scanning of 6,000-8,000 NYSE + NASDAQ stocks
- ✅ Pre-market (7:30 AM ET) and end-of-day (4:30 PM ET) scans
- ✅ Technical indicators: SMA, EMA, RSI, MACD, Bollinger Bands, Volume analysis
- ✅ Discord alerts for MA crossovers, RSI extremes, volume spikes, gaps
- ✅ PostgreSQL + TimescaleDB for time-series data storage
- ✅ Finnhub API integration with rate limiting
- ✅ Microservices architecture (Data, Indicator, Scanner, Alert, Scheduler, API Gateway)

---

## Phase 1: Backtesting Engine (Q1 - Months 1-3)

### Priority: CRITICAL FOUNDATION
**Why First:** All future features (custom indicators, ML) require backtesting to validate effectiveness.

### Features

#### 1.1 Historical Signal Replay Engine
**Goal:** Replay any alert condition over historical data and calculate hypothetical returns.

**Requirements:**
- Query historical price data from database
- Re-run indicator calculations for past dates
- Detect signals using same logic as live scanner
- Track all signals chronologically

**Deliverables:**
- `backtesting_engine.py` module
- API endpoint: `POST /api/backtest/run`
- Input: strategy definition, date range, stock list
- Output: List of all signals with timestamps

**Technical Approach:**
```python
# Example usage
strategy = {
    "name": "9x20 MA Crossover",
    "conditions": {
        "type": "crossover",
        "indicator1": "SMA_9",
        "indicator2": "SMA_20",
        "direction": "above"
    }
}

results = backtest_engine.run(
    strategy=strategy,
    start_date="2022-01-01",
    end_date="2024-12-31",
    stocks=["AAPL", "MSFT", "GOOGL"]
)
```

#### 1.2 Trade Simulation
**Goal:** Simulate actual trades based on signals, including entry/exit prices, holding periods, and P&L.

**Requirements:**
- **Entry Logic:** Buy at next day's open after signal
- **Exit Logic:** Configurable (fixed holding period, stop loss, take profit, trailing stop)
- **Position Sizing:** Configurable (fixed amount, % of portfolio, risk-based)
- **Transaction Costs:** Include commission ($0.005/share typical) and slippage (0.1% typical)
- **Multiple Positions:** Support concurrent trades across different stocks

**Deliverables:**
- `trade_simulator.py` module
- Portfolio state tracking
- Trade journal (entry/exit prices, holding period, P&L)

**Trade Execution Model:**
```python
# Example trade flow
Signal detected: AAPL 9x20 cross on 2024-06-15
Entry: Buy at open on 2024-06-16 = $180.50
Position size: $10,000 / $180.50 = 55 shares
Exit rule: Sell after 20 days OR if price drops 5% (stop loss)
Actual exit: 2024-07-06 at $195.30 (20 days later)
Gross P&L: ($195.30 - $180.50) × 55 = $814
Commission: $0.005 × 55 × 2 = $0.55
Net P&L: $813.45
Return: 8.13%
```

#### 1.3 Performance Metrics Calculator
**Goal:** Calculate comprehensive statistics on strategy performance.

**Metrics to Calculate:**
- **Return Metrics:**
  - Total return (%)
  - CAGR (Compound Annual Growth Rate)
  - Monthly/yearly returns
  
- **Risk Metrics:**
  - Max drawdown (largest peak-to-trough decline)
  - Volatility (standard deviation of returns)
  - Sharpe ratio (return / volatility)
  - Sortino ratio (return / downside volatility)
  - Calmar ratio (return / max drawdown)
  
- **Win/Loss Metrics:**
  - Win rate (% profitable trades)
  - Profit factor (gross profit / gross loss)
  - Average win vs average loss
  - Largest win / largest loss
  - Consecutive wins / losses
  
- **Trading Metrics:**
  - Total trades
  - Average holding period
  - Trade frequency (trades per month)
  - Exposure time (% of time in market)

**Deliverables:**
- `performance_metrics.py` module
- JSON/dict output of all metrics
- Comparison module (compare multiple strategies)

#### 1.4 Visual Reporting
**Goal:** Generate visual reports showing backtest results.

**Charts to Generate:**
- **Equity Curve:** Portfolio value over time
- **Drawdown Chart:** Underwater periods
- **Monthly Returns Heatmap:** Color-coded grid of monthly returns
- **Trade Distribution:** Histogram of returns per trade
- **Win/Loss Streaks:** Visualization of consecutive wins/losses
- **Cumulative Returns:** Strategy vs buy-and-hold benchmark

**Deliverables:**
- `report_generator.py` module using matplotlib/plotly
- HTML report template with embedded charts
- PDF export capability
- API endpoint: `GET /api/backtest/{id}/report`

**Report Format:**
```
Backtest Report: 9x20 MA Crossover Strategy
Period: 2022-01-01 to 2024-12-31
Stocks: S&P 500 (503 stocks)

Performance Summary:
- Total Return: +47.3%
- CAGR: 14.8%
- Max Drawdown: -12.4%
- Sharpe Ratio: 1.83
- Win Rate: 62.4%
- Profit Factor: 2.1
- Total Trades: 1,247

[Equity Curve Chart]
[Monthly Returns Heatmap]
[Trade Distribution Histogram]
```

#### 1.5 Database Schema Extensions
**New Tables:**
```sql
-- Backtest configurations
CREATE TABLE backtests (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    strategy_json JSONB NOT NULL,
    start_date DATE,
    end_date DATE,
    initial_capital NUMERIC(12, 2),
    commission_per_share NUMERIC(8, 4),
    slippage_percent NUMERIC(5, 4),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Backtest trades
CREATE TABLE backtest_trades (
    id BIGSERIAL PRIMARY KEY,
    backtest_id INTEGER REFERENCES backtests(id),
    stock_id INTEGER REFERENCES stocks(id),
    entry_date DATE,
    entry_price NUMERIC(12, 4),
    exit_date DATE,
    exit_price NUMERIC(12, 4),
    shares INTEGER,
    gross_pnl NUMERIC(12, 4),
    net_pnl NUMERIC(12, 4),
    return_percent NUMERIC(8, 4),
    holding_days INTEGER
);

-- Backtest performance
CREATE TABLE backtest_performance (
    id SERIAL PRIMARY KEY,
    backtest_id INTEGER REFERENCES backtests(id) UNIQUE,
    total_return NUMERIC(8, 4),
    cagr NUMERIC(8, 4),
    max_drawdown NUMERIC(8, 4),
    sharpe_ratio NUMERIC(8, 4),
    win_rate NUMERIC(8, 4),
    profit_factor NUMERIC(8, 4),
    total_trades INTEGER,
    avg_holding_days NUMERIC(8, 2),
    metrics_json JSONB
);
```

### Testing Requirements
- Unit tests for all metric calculations (use known datasets)
- Integration tests for full backtest execution
- Performance tests: Backtest 3 years of S&P 500 in <10 minutes
- Validation: Compare results with manual calculations

### Success Criteria
- ✅ Can backtest any strategy over any time period
- ✅ Generates accurate P&L calculations
- ✅ Produces comprehensive performance metrics
- ✅ Visual reports are clear and actionable
- ✅ Backtests complete in reasonable time (<10 min for 3 years, 500 stocks)

---

## Phase 2: Custom Indicator Builder (Q2 - Months 4-6)

### Priority: HIGH
**Why:** Empowers users to experiment with novel trading ideas beyond pre-built indicators.

### Features

#### 2.1 Code-Based Indicator Interface
**Goal:** Allow users to write custom indicators in Python.

**Requirements:**
- Sandboxed Python execution environment (restrict file I/O, network, dangerous imports)
- Access to pandas, numpy, ta-lib functions
- Standard input: DataFrame with columns [date, open, high, low, close, volume]
- Standard output: Series or DataFrame with indicator values
- Automatic validation (check for NaN, infinite values, correct length)

**Example Custom Indicator:**
```python
def my_rsi_sma_combo(df, rsi_period=14, sma_period=20):
    """
    Custom indicator: RSI of price, then SMA of RSI
    Signal when SMA(RSI) crosses above 50
    """
    # Calculate RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(rsi_period).mean()
    loss = -delta.where(delta < 0, 0).rolling(rsi_period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # Calculate SMA of RSI
    rsi_sma = rsi.rolling(sma_period).mean()
    
    return rsi_sma

# User saves this to library, then uses in alerts:
# "Trigger alert when my_rsi_sma_combo > 50"
```

**Deliverables:**
- `custom_indicator_engine.py` with sandboxed execution
- API endpoints:
  - `POST /api/indicators/custom` - Create custom indicator
  - `GET /api/indicators/custom` - List user's indicators
  - `POST /api/indicators/custom/{id}/test` - Test on sample data
  - `DELETE /api/indicators/custom/{id}` - Delete indicator
- Web UI for code editor with syntax highlighting

#### 2.2 Indicator Testing Framework
**Goal:** Let users test custom indicators before deploying.

**Features:**
- **Sample Data Testing:** Run indicator on 10 sample stocks with 1 year data
- **Validation Checks:**
  - No NaN values in output (or handle gracefully)
  - Output length matches input length
  - Values in reasonable range (flag if >1000 or <-1000)
  - No infinite values
  - Calculation completes in <1 second per stock
- **Visual Preview:** Plot indicator on chart with price
- **Backtestability:** Indicator can be used in backtesting engine

**Deliverables:**
- Indicator testing module
- Visual chart preview (matplotlib/plotly)
- Test report with validation results

#### 2.3 Parameter Optimization
**Goal:** Find optimal parameters for indicators via backtesting.

**Features:**
- **Grid Search:** Test all combinations of parameters
  - Example: RSI period [10, 12, 14, 16, 18, 20]
  - MA period [9, 15, 20, 25, 30]
  - Generates 6 × 5 = 30 combinations
- **Optimization Metric:** Choose what to optimize (Sharpe ratio, total return, win rate)
- **Constraints:** Set min/max values for parameters
- **Results Ranking:** Show best parameter combinations
- **Overfitting Warning:** Flag if best parameters are suspiciously good

**Example:**
```python
# Optimize RSI oversold strategy
optimize_parameters(
    strategy="RSI_OVERSOLD",
    parameters={
        "rsi_period": range(10, 21, 2),  # [10, 12, 14, 16, 18, 20]
        "oversold_threshold": range(20, 36, 5)  # [20, 25, 30, 35]
    },
    optimize_for="sharpe_ratio",
    backtest_period="2022-01-01 to 2024-12-31"
)

# Output:
# Best: rsi_period=14, oversold_threshold=30, Sharpe=1.82
# 2nd: rsi_period=12, oversold_threshold=25, Sharpe=1.76
# ...
```

**Deliverables:**
- `parameter_optimizer.py` module
- API endpoint: `POST /api/optimize/parameters`
- Progress tracking (optimization can take hours)
- Results visualization (heatmap of parameter combinations vs performance)

#### 2.4 Indicator Library & Versioning
**Goal:** Save and manage custom indicators.

**Features:**
- Save indicators to personal library
- Version control (v1, v2, v3 when user edits)
- Rollback to previous versions
- Share indicators with other users (optional)
- Import indicators from community

**Database Schema:**
```sql
CREATE TABLE custom_indicators (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,  -- For future multi-user support
    name VARCHAR(255),
    description TEXT,
    code TEXT,  -- Python code
    parameters JSONB,  -- Default parameter values
    version INTEGER DEFAULT 1,
    is_public BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE indicator_versions (
    id SERIAL PRIMARY KEY,
    indicator_id INTEGER REFERENCES custom_indicators(id),
    version INTEGER,
    code TEXT,
    parameters JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Testing Requirements
- Security testing: Ensure sandbox prevents malicious code
- Performance testing: Custom indicators don't slow down scans
- Validation testing: Catch common errors (division by zero, etc.)

### Success Criteria
- ✅ Users can write and test custom indicators
- ✅ Custom indicators work in backtesting engine
- ✅ Parameter optimization finds better parameters than defaults
- ✅ No security vulnerabilities in code execution

---

## Phase 3: Machine Learning Integration (Q3-Q4 - Months 7-12)

### Priority: HIGH
**Why:** ML can significantly improve signal quality and discover non-obvious patterns.

### Overview
Use machine learning to predict whether a trading signal will be profitable, achieving 70-80% accuracy with proper calibration.

### 3.1 Data Preparation & Feature Engineering

#### Feature Categories:

**A. Indicator Features (at time of signal):**
- RSI value
- MACD line, signal line, histogram
- Price position vs all MAs (above/below, distance)
- Bollinger Band position (price vs upper/lower bands)
- ATR (volatility)
- Volume ratio (current vs average)

**B. Recent Price Action:**
- 5-day return
- 10-day return
- 20-day return
- Recent volatility (std dev of returns)
- Recent volume trend

**C. Market Context:**
- Sector performance (vs S&P 500)
- Market breadth (% stocks above 200-day MA)
- VIX level (market fear gauge)
- Market regime (bull/bear/sideways)

**D. Signal Timing:**
- Days since last signal on this stock
- Number of signals in past week (avoid crowded trades)
- Day of week (Monday vs Friday effects)

**E. Stock Characteristics:**
- Market cap
- Average daily volume
- Beta (vs market)
- Sector

#### Label Generation:
```python
# For each historical signal, calculate outcome
def generate_label(stock, signal_date, holding_period=20):
    """
    Label = 1 (profitable) if:
    - Price increases >5% within holding_period days
    OR
    - Price increases >3% with no drawdown >2%
    
    Label = 0 (not profitable) otherwise
    """
    entry_price = get_price(stock, signal_date + 1)  # Next day open
    
    for day in range(1, holding_period + 1):
        current_price = get_price(stock, signal_date + day)
        return_pct = (current_price - entry_price) / entry_price * 100
        
        if return_pct >= 5.0:
            return 1  # Profitable
        if return_pct <= -5.0:
            return 0  # Stop loss hit
    
    # After holding period
    final_return = (get_price(stock, signal_date + holding_period) - entry_price) / entry_price * 100
    return 1 if final_return > 2.0 else 0
```

**Deliverables:**
- `feature_engineering.py` module
- `label_generator.py` module
- Database table for training data:
```sql
CREATE TABLE ml_training_data (
    id BIGSERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    signal_date DATE,
    signal_type VARCHAR(50),  -- 'MA_CROSS', 'RSI_OVERSOLD', etc.
    features JSONB,  -- All feature values
    label INTEGER,  -- 0 or 1
    outcome_return NUMERIC(8, 4),  -- Actual return for analysis
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 3.2 Model Training Pipeline

#### Models to Try (in order):
1. **Logistic Regression** (baseline, interpretable)
2. **Random Forest** (good for feature importance)
3. **XGBoost** (usually best for tabular data)
4. **Neural Network** (if sufficient data, >100K samples)

#### Training Process:
```python
# 1. Load historical signals with outcomes
data = load_training_data(
    start_date="2019-01-01",
    end_date="2024-12-31",
    signal_types=["MA_CROSS_9_20", "RSI_OVERSOLD"]
)

# 2. Split data (time-series aware - no shuffle!)
train_end = "2023-12-31"
test_start = "2024-01-01"

train_data = data[data['signal_date'] <= train_end]
test_data = data[data['signal_date'] >= test_start]

# 3. Extract features and labels
X_train = train_data['features']
y_train = train_data['label']
X_test = test_data['features']
y_test = test_data['label']

# 4. Handle class imbalance (if needed)
from imblearn.over_sampling import SMOTE
X_train_balanced, y_train_balanced = SMOTE().fit_resample(X_train, y_train)

# 5. Train model
from xgboost import XGBClassifier
model = XGBClassifier(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8
)
model.fit(X_train_balanced, y_train_balanced)

# 6. Evaluate
y_pred_proba = model.predict_proba(X_test)[:, 1]
from sklearn.metrics import roc_auc_score, classification_report
print(f"AUC: {roc_auc_score(y_test, y_pred_proba)}")
print(classification_report(y_test, y_pred_proba > 0.5))
```

#### Hyperparameter Tuning:
```python
from optuna import create_study

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 100, 500),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
    }
    
    model = XGBClassifier(**params)
    model.fit(X_train, y_train)
    
    y_pred = model.predict_proba(X_test)[:, 1]
    return roc_auc_score(y_test, y_pred)

study = create_study(direction='maximize')
study.optimize(objective, n_trials=100)
best_params = study.best_params
```

**Deliverables:**
- `ml_pipeline.py` module
- Training scripts with logging
- Model versioning (save models with timestamp)
- Hyperparameter tuning scripts

### 3.3 Probability Calibration

**Goal:** When model says "73% confidence", it should be correct ~73% of the time.

**Calibration Methods:**
1. **Platt Scaling:** Logistic regression on model outputs
2. **Isotonic Regression:** Non-parametric, more flexible
3. **Temperature Scaling:** For neural networks

**Implementation:**
```python
from sklearn.calibration import CalibratedClassifierCV

# Calibrate using validation set
calibrated_model = CalibratedClassifierCV(
    model, 
    method='isotonic',  # or 'sigmoid' for Platt scaling
    cv='prefit'  # Model already trained
)
calibrated_model.fit(X_val, y_val)

# Now predictions are calibrated
y_pred_calibrated = calibrated_model.predict_proba(X_test)[:, 1]
```

**Validation:**
```python
# Create calibration curve
from sklearn.calibration import calibration_curve

prob_true, prob_pred = calibration_curve(
    y_test, 
    y_pred_calibrated, 
    n_bins=10
)

# Perfect calibration: prob_true ≈ prob_pred
# Plot: X-axis = predicted probability, Y-axis = actual success rate
```

**Deliverables:**
- Calibrated models
- Calibration curve visualization
- Expected Calibration Error (ECE) metric

### 3.4 Real-Time Signal Scoring

**Goal:** Score every live signal with probability of success.

**Implementation:**
```python
# When scanner detects signal
if ma_crossover_detected('AAPL', today):
    # Extract current features
    features = {
        'rsi_14': get_current_rsi('AAPL', 14),
        'price_vs_sma_200': get_price_vs_ma('AAPL', 200),
        'volume_ratio': get_volume_ratio('AAPL'),
        'recent_volatility': get_recent_volatility('AAPL', 20),
        'sector_strength': get_sector_performance('Technology'),
        'market_breadth': get_market_breadth(today),
        # ... all other features
    }
    
    # Score with ML model
    probability = ml_model.predict_proba([features])[0][1]
    confidence_pct = probability * 100
    
    # Decision logic
    if confidence_pct >= 70:
        priority = "HIGH"
        send_alert = True
    elif confidence_pct >= 50:
        priority = "MEDIUM"
        send_alert = True  # or False based on user settings
    else:
        priority = "LOW"
        send_alert = False  # Skip low-confidence signals
    
    # Send Discord alert with confidence score
    if send_alert:
        send_discord_alert(
            f"🚨 **{priority} CONFIDENCE SIGNAL ({confidence_pct:.1f}%)**\n"
            f"Symbol: AAPL\n"
            f"Signal: 9-day MA crossed above 20-day MA\n"
            f"ML Prediction: {confidence_pct:.1f}% probability of +5% gain within 20 days"
        )
```

**Deliverables:**
- Real-time scoring integration in scanner service
- Updated Discord alert format with confidence scores
- API endpoint: `POST /api/signals/score` for manual scoring
- Database field for storing ML confidence score

### 3.5 Feature Importance Analysis

**Goal:** Understand which features matter most for predictions.

**Methods:**
1. **Built-in Feature Importance (XGBoost):**
```python
import matplotlib.pyplot as plt

# Get feature importance
importance = model.feature_importances_
features = X_train.columns

# Plot
plt.barh(features, importance)
plt.xlabel('Importance Score')
plt.title('Feature Importance')
```

2. **SHAP (SHapley Additive exPlanations):**
```python
import shap

explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# Summary plot
shap.summary_plot(shap_values, X_test)

# For individual prediction
shap.force_plot(explainer.expected_value, shap_values[0], X_test.iloc[0])
```

**Use Cases:**
- Identify most predictive indicators
- Remove redundant features (improve speed)
- Explain individual predictions to users
- Guide feature engineering (create better features)

**Deliverables:**
- Feature importance dashboard
- SHAP visualization in backtest reports
- API endpoint: `GET /api/ml/feature-importance`

### 3.6 Walk-Forward Analysis (Overfitting Prevention)

**Goal:** Validate model generalizes to unseen future data.

**Method:**
```
Training Period 1: 2019-2020 → Test on 2021
Training Period 2: 2019-2021 → Test on 2022
Training Period 3: 2019-2022 → Test on 2023
Training Period 4: 2019-2023 → Test on 2024

Average performance across all test periods
```

**Implementation:**
```python
def walk_forward_validation(data, train_years=2, test_months=6):
    results = []
    
    start_year = 2019
    end_year = 2024
    
    for year in range(start_year + train_years, end_year + 1):
        train_start = f"{year - train_years}-01-01"
        train_end = f"{year - 1}-12-31"
        test_start = f"{year}-01-01"
        test_end = f"{year}-12-31"
        
        # Train on historical data
        train_data = data[
            (data['signal_date'] >= train_start) & 
            (data['signal_date'] <= train_end)
        ]
        
        # Test on future data
        test_data = data[
            (data['signal_date'] >= test_start) & 
            (data['signal_date'] <= test_end)
        ]
        
        model = train_model(train_data)
        performance = evaluate_model(model, test_data)
        
        results.append({
            'test_period': f"{test_start} to {test_end}",
            'accuracy': performance['accuracy'],
            'auc': performance['auc'],
            'calibration_error': performance['ece']
        })
    
    return results
```

**Deliverables:**
- Walk-forward validation script
- Report showing performance across time periods
- Flag strategies that degrade over time

### 3.7 Model Monitoring & Retraining

**Goal:** Track model performance in production and retrain when needed.

**Monitoring Metrics:**
- **Prediction Accuracy:** Compare predicted probability vs actual outcomes
- **Calibration Drift:** Is 70% still 70%?
- **Feature Drift:** Are feature distributions changing?
- **Performance Degradation:** Is Sharpe ratio declining?

**Auto-Retraining Triggers:**
- Monthly retraining (scheduled)
- Accuracy drops below threshold (e.g., <60%)
- Calibration error increases significantly
- New data accumulates (>10,000 new labeled samples)

**Implementation:**
```python
# Every month
def check_model_performance():
    # Get predictions from last month
    recent_predictions = get_predictions(last_30_days)
    
    # Wait for outcomes (20-day holding period)
    # Then compare predicted vs actual
    
    actual_accuracy = calculate_accuracy(recent_predictions)
    
    if actual_accuracy < 0.60:
        trigger_retraining()
        send_alert("Model accuracy dropped to {actual_accuracy:.1%}, retraining triggered")
```

**Deliverables:**
- Model performance dashboard
- Automated retraining pipeline
- A/B testing framework (compare old vs new model)

### 3.8 Advanced: Automated Strategy Discovery

**Goal:** Use genetic algorithms to discover novel profitable strategies.

**Genetic Algorithm Approach:**
```python
# 1. Generate random population of strategies
population = []
for i in range(100):
    strategy = {
        'indicator1': random.choice(['RSI', 'MACD', 'SMA', 'EMA']),
        'indicator1_params': random_params(),
        'operator': random.choice(['>', '<', 'crosses_above', 'crosses_below']),
        'indicator2': random.choice(['RSI', 'MACD', 'SMA', 'EMA']),
        'indicator2_params': random_params(),
        'AND_OR': random.choice(['AND', 'OR']),
        'condition2': random_condition(),
    }
    population.append(strategy)

# 2. Evaluate fitness (backtest each strategy)
fitness_scores = []
for strategy in population:
    backtest_result = backtest(strategy)
    fitness = backtest_result['sharpe_ratio']
    fitness_scores.append(fitness)

# 3. Selection (keep top 20%)
top_strategies = select_top_percent(population, fitness_scores, 0.20)

# 4. Crossover (combine top strategies)
offspring = []
for i in range(len(population) - len(top_strategies)):
    parent1, parent2 = random.sample(top_strategies, 2)
    child = crossover(parent1, parent2)
    offspring.append(child)

# 5. Mutation (random changes)
for strategy in offspring:
    if random.random() < 0.1:  # 10% mutation rate
        mutate(strategy)

# 6. New generation
population = top_strategies + offspring

# 7. Repeat for N generations (e.g., 50-100)
```

**Overfitting Prevention:**
- Test on out-of-sample data
- Penalize complex strategies (Occam's razor)
- Require minimum number of trades (>50)
- Require multiple years of positive performance

**Deliverables:**
- Genetic algorithm implementation
- Strategy evolution visualization
- Top discovered strategies ranked by fitness

### Database Schema for ML

```sql
-- ML models
CREATE TABLE ml_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    version VARCHAR(50),
    model_type VARCHAR(50),  -- 'xgboost', 'random_forest', etc.
    signal_types TEXT[],  -- Which signals this model scores
    training_start_date DATE,
    training_end_date DATE,
    training_samples INTEGER,
    test_accuracy NUMERIC(8, 4),
    test_auc NUMERIC(8, 4),
    calibration_error NUMERIC(8, 6),
    hyperparameters JSONB,
    feature_importance JSONB,
    model_file_path TEXT,  -- Path to serialized model
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ML predictions (for monitoring)
CREATE TABLE ml_predictions (
    id BIGSERIAL PRIMARY KEY,
    model_id INTEGER REFERENCES ml_models(id),
    stock_id INTEGER REFERENCES stocks(id),
    signal_date DATE,
    signal_type VARCHAR(50),
    features JSONB,
    predicted_probability NUMERIC(8, 6),
    prediction_binary INTEGER,  -- 0 or 1
    actual_outcome INTEGER,  -- Filled in later after holding period
    actual_return NUMERIC(8, 4),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Model performance tracking
CREATE TABLE ml_model_performance (
    id SERIAL PRIMARY KEY,
    model_id INTEGER REFERENCES ml_models(id),
    evaluation_date DATE,
    period_start DATE,
    period_end DATE,
    accuracy NUMERIC(8, 4),
    precision NUMERIC(8, 4),
    recall NUMERIC(8, 4),
    auc NUMERIC(8, 4),
    calibration_error NUMERIC(8, 6),
    total_predictions INTEGER,
    metrics_json JSONB
);
```

### Testing Requirements
- Validate feature engineering on known datasets
- Test model training pipeline end-to-end
- Verify calibration accuracy
- Integration test: Live signal → ML scoring → Discord alert
- Performance test: Score 1,000 signals in <1 second

### Success Criteria
- ✅ Model achieves 70-80% accuracy on out-of-sample test data
- ✅ Calibration error <5% (predicted probabilities match actual)
- ✅ Feature importance analysis provides actionable insights
- ✅ Real-time scoring adds <100ms latency to alerts
- ✅ Walk-forward validation shows consistent performance across years
- ✅ High-confidence signals (>70%) outperform low-confidence in backtests

---

## Phase 4: Advanced Features (Year 2+)

### 4.1 Paper Trading
- Simulate trades in real-time based on live signals
- Track paper portfolio performance
- Compare paper trading results to backtest predictions
- Validate strategies before deploying real capital

### 4.2 Multi-Asset Support
- **Cryptocurrencies:** Bitcoin, Ethereum, top 100 coins
- **Forex:** Major currency pairs (EUR/USD, GBP/USD, etc.)
- **Commodities:** Gold, Silver, Oil, Natural Gas
- **International Stocks:** European, Asian markets
- **ETFs:** Sector ETFs, Bond ETFs, Commodity ETFs

### 4.3 Alternative Data Integration
- **News Sentiment:** Scrape financial news, analyze sentiment
- **Social Media:** Twitter/Reddit mentions, sentiment analysis
- **Earnings Data:** EPS surprises, revenue beats
- **Insider Trading:** Track insider buy/sell activity
- **Options Flow:** Large options trades (institutional activity)

### 4.4 Intraday Trading
- 5-minute, 15-minute, 1-hour bars
- Intraday strategies (scalping, momentum)
- Higher frequency scanning during market hours
- Different API needed (Polygon.io paid tier, Alpaca, etc.)

### 4.5 Broker Integration
- Connect to Interactive Brokers, TD Ameritrade, Alpaca
- Auto-execute trades (with user approval)
- Real-time portfolio tracking
- Automatic stop-loss and take-profit orders

### 4.6 Community & Social Features
- Strategy marketplace (share profitable strategies)
- Leaderboard of best strategies
- Follow other traders
- Discussion forums per stock
- Strategy collaboration tools

### 4.7 Advanced Risk Management
- Portfolio-level risk limits
- Correlation analysis (avoid concentrated bets)
- Value at Risk (VaR) calculations
- Stress testing (what if market drops 20%?)
- Position sizing algorithms (Kelly criterion, risk parity)

---

## Technical Stack Additions

### Machine Learning
- `scikit-learn` - Classical ML algorithms
- `xgboost` or `lightgbm` - Gradient boosting
- `tensorflow` or `pytorch` - Deep learning (if needed)
- `optuna` - Hyperparameter optimization
- `shap` - Model interpretability
- `imbalanced-learn` - Handle class imbalance

### Backtesting
- `backtrader` or `zipline` - Established frameworks (optional)
- `vectorbt` - Fast vectorized backtesting (optional)
- Or custom implementation (recommended - you have the data)

### Data Science
- `jupyter` - Interactive development
- `matplotlib`, `plotly` - Visualization
- `seaborn` - Statistical plots
- `scipy` - Statistical tests

### Feature Engineering
- `tsfresh` - Automated time-series features
- `featuretools` - Automated feature engineering

---

## Implementation Timeline

### Q1 (Months 1-3): Backtesting Foundation
- Week 1-2: Historical signal replay engine
- Week 3-4: Trade simulator
- Week 5-6: Performance metrics calculator
- Week 7-8: Visual reporting
- Week 9-12: Testing, refinement, documentation

### Q2 (Months 4-6): Custom Indicators
- Week 1-2: Code-based indicator interface
- Week 3-4: Sandboxed execution environment
- Week 5-6: Indicator testing framework
- Week 7-8: Parameter optimization
- Week 9-10: Indicator library & versioning
- Week 11-12: Integration with backtesting, testing

### Q3 (Months 7-9): ML Foundation
- Week 1-2: Data preparation & feature engineering
- Week 3-4: Label generation, training data creation
- Week 5-6: Model training pipeline (baseline models)
- Week 7-8: XGBoost training & hyperparameter tuning
- Week 9-10: Probability calibration
- Week 11-12: Real-time signal scoring integration

### Q4 (Months 10-12): ML Advanced & Production
- Week 1-2: Feature importance analysis (SHAP)
- Week 3-4: Walk-forward validation
- Week 5-6: Model monitoring & retraining automation
- Week 7-8: Performance optimization
- Week 9-10: Automated strategy discovery (genetic algorithms)
- Week 11-12: Testing, documentation, production deployment

---

## Success Metrics

### Backtesting Engine
- ✅ Backtest 500 stocks over 3 years in <10 minutes
- ✅ Generate comprehensive performance reports
- ✅ Accurately simulate transaction costs and slippage
- ✅ Results match manual calculations (spot-checked)

### Custom Indicators
- ✅ Users can create and test custom indicators
- ✅ Indicators integrate with backtesting and live scanning
- ✅ Parameter optimization discovers better parameters
- ✅ No security vulnerabilities in code execution

### Machine Learning
- ✅ Model achieves 70-80% accuracy on test data
- ✅ Calibration error <5%
- ✅ High-confidence signals (>70%) outperform in live trading
- ✅ Feature importance provides actionable insights
- ✅ Walk-forward validation shows robust performance
- ✅ Model retraining maintains performance over time

### Overall Platform
- ✅ Backtesting validates alpha strategy profitability
- ✅ ML filtering improves win rate by 10-15 percentage points
- ✅ Users discover novel profitable strategies
- ✅ Platform handles 10,000+ backtests per day
- ✅ Real-time ML scoring adds <100ms latency

---

## Notes & Considerations

### Overfitting Risk
**Critical for ML:** The biggest risk is creating models that look amazing in backtesting but fail in live trading.

**Prevention Strategies:**
1. Always use out-of-sample testing (never test on training data)
2. Use walk-forward analysis (train on past, test on future)
3. Prefer simple models over complex (Occam's razor)
4. Require minimum number of trades (>50, ideally >100)
5. Be skeptical of >90% win rates (likely overfit)
6. Test on multiple time periods and market conditions
7. Implement A/B testing (compare old vs new models in production)

### Realistic Expectations
- **Good win rate:** 55-65% (professionals target this)
- **Great win rate:** 65-75% (achievable with ML)
- **Suspicious win rate:** >80% (probably overfit)
- **Profit factor:** 1.5-2.5 is realistic, >3 is exceptional
- **Sharpe ratio:** >1.0 is good, >2.0 is excellent

### Computational Requirements
- **Training data size:** 100K-1M labeled signals ideal
- **Training time:** Hours to days for large datasets
- **Inference time:** <100ms per signal (real-time requirement)
- **Storage:** Several GB for models and training data
- **GPU:** Optional for neural networks, not needed for XGBoost

### Data Quality Critical
- Garbage in → garbage out
- Ensure historical data is accurate (handle splits, dividends)
- Validate labels (did we calculate outcome correctly?)
- Handle survivorship bias (include delisted stocks in historical analysis)

---

## Future Exploration (Beyond Year 2)

- **Reinforcement Learning:** Agent learns optimal entry/exit timing
- **NLP for News:** Extract trading signals from news articles
- **Computer Vision:** Recognize chart patterns from images
- **Ensemble Models:** Combine multiple models for better predictions
- **Market Making:** Provide liquidity, capture bid-ask spread
- **Options Strategies:** Covered calls, spreads, iron condors
- **Portfolio Optimization:** Modern portfolio theory, mean-variance optimization
- **High-Frequency Trading:** Sub-second execution (requires different infrastructure)

---

## End of Roadmap
