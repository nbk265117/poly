# 📖 Documentation Technique

Documentation technique détaillée du Robot de Trading Polymarket.

## 🏗️ Architecture

### Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                         MAIN.PY                             │
│                    (Trading Bot Core)                       │
└────────────┬────────────────────────────────┬───────────────┘
             │                                │
             ▼                                ▼
┌────────────────────────┐      ┌────────────────────────────┐
│   STRATEGY ENGINE      │      │   POLYMARKET EXECUTOR      │
│  (strategy.py)         │      │  (polymarket_client.py)    │
└────────┬───────────────┘      └────────────┬───────────────┘
         │                                   │
         ▼                                   ▼
┌────────────────────────┐      ┌────────────────────────────┐
│  INDICATOR PIPELINE    │      │   TELEGRAM NOTIFIER        │
│  (indicators.py)       │      │  (telegram_bot.py)         │
│  ┌──────────────────┐  │      └────────────────────────────┘
│  │ Price Action     │  │
│  │ FTFC Multi-TF    │  │
│  │ Volume Filter    │  │
│  └──────────────────┘  │
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│   DATA MANAGER         │
│  (data_manager.py)     │
│  ┌──────────────────┐  │
│  │ Binance API      │  │
│  │ CSV Cache        │  │
│  │ Multi-TF Mgmt    │  │
│  └──────────────────┘  │
└────────────────────────┘
```

### Flux de Données

```
1. DATA LOADING
   Binance API → DataManager → CSV Cache → Multi-TF DataFrames

2. INDICATOR CALCULATION
   DataFrames → IndicatorPipeline → Enriched DataFrames
   
3. SIGNAL GENERATION
   Enriched DataFrames → Strategy → BUY/SELL Signal
   
4. ORDER EXECUTION
   Signal → PolymarketExecutor → Polymarket API → Order
   
5. NOTIFICATION
   Order/Trade → TelegramNotifier → Telegram Bot → User
```

## 📦 Modules

### 1. config.py

**Rôle**: Gestionnaire de configuration centralisé

**Classes**:
- `Config`: Singleton pour accès configuration

**Méthodes Clés**:
```python
config = get_config()
config.symbols                 # List[str]
config.primary_timeframe       # str
config.position_size_usd       # float
config.telegram_enabled        # bool
```

**Sources**:
- `config.yaml`: Configuration principale
- `.env`: Variables d'environnement sensibles

### 2. data_manager.py

**Rôle**: Gestion des données OHLCV

**Classes**:
- `DataManager`: Chargement et préparation des données

**Méthodes Clés**:
```python
dm = DataManager()

# Charger données historiques
df = dm.load_historical_data('BTC/USDT', '15m', months=24)

# Données live
df = dm.get_live_data('BTC/USDT', '15m', limit=100)

# Multi-timeframe
data = dm.prepare_multi_timeframe_data('BTC/USDT', ['15m', '1h', '4h'])
```

**Format DataFrame**:
```python
{
    'timestamp': datetime,
    'open': float,
    'high': float,
    'low': float,
    'close': float,
    'volume': float
}
```

### 3. indicators.py

**Rôle**: Calcul des indicateurs techniques

**Classes**:

#### PriceActionIndicator
Détecte les patterns de bougies
```python
pa = PriceActionIndicator(min_wick_ratio=0.3, min_body_size=0.001)
df = pa.calculate(df)

# Colonnes ajoutées:
# PA_signal: 'BUY', 'SELL', None
# PA_strength: 0.0 - 1.0
# PA_type: 'hammer', 'shooting_star', etc.
# PA_direction: 'bullish', 'bearish'
```

#### FTFCIndicator
Détermine le biais directionnel multi-timeframe
```python
ftfc = FTFCIndicator(require_all_aligned=True)

# Single timeframe
df = ftfc.calculate_ftfc_single(df, period=20)

# Multi-timeframe
directions = ftfc.calculate_multi_timeframe(data_dict, timestamp)
# Returns: {'15m': 'bullish', '1h': 'bullish', '4h': 'neutral', 'global': 'neutral'}
```

#### VolumeIndicator
Filtre basé sur le volume
```python
vol = VolumeIndicator(ma_period=20, min_volume_ratio=1.2)
df = vol.calculate(df)

# Colonnes ajoutées:
# VOL_MA: Moving average
# VOL_ratio: volume / MA
# VOL_confirmed: bool
```

#### IndicatorPipeline
Orchestre tous les indicateurs
```python
pipeline = IndicatorPipeline()
df = pipeline.calculate_all(df, multi_tf_data)
signal = pipeline.generate_signal(row)  # 'BUY', 'SELL', None
```

**Logique du Signal**:
```
IF PA_signal EXISTS
  AND FTFC aligned with PA direction
  AND VOL_confirmed == True
THEN
  RETURN signal
ELSE
  RETURN None
```

### 4. strategy.py

**Rôle**: Moteur de stratégie de trading

**Classes**:

#### Trade
Représente un trade individuel
```python
trade = Trade(
    symbol='BTC/USDT',
    direction='BUY',
    entry_price=50000,
    entry_time=datetime.now(),
    position_size=0.002,
    stop_loss=49000,
    take_profit=51500
)

trade.close(51500, datetime.now(), 'tp')
print(trade.pnl)  # PnL en USD
```

#### TradingStrategy
Stratégie complète
```python
strategy = TradingStrategy()

# Analyser le marché
signal = strategy.analyze_market('BTC/USDT')

# Ouvrir un trade
trade = strategy.open_trade(
    symbol='BTC/USDT',
    direction='BUY',
    entry_price=50000,
    entry_time=datetime.now(),
    capital=10000
)

# Vérifier SL/TP
closed = strategy.check_stop_loss_take_profit(
    trade, 
    current_price=51500, 
    current_time=datetime.now()
)

# Statistiques
stats = strategy.get_performance_stats()
```

### 5. backtest.py

**Rôle**: Système de backtesting

**Classes**:

#### BacktestEngine
Simule le trading sur données historiques
```python
backtest = BacktestEngine(
    initial_capital=10000,
    commission=0.001,
    slippage=0.0005
)

results = backtest.run_backtest(
    symbols=['BTC/USDT', 'ETH/USDT'],
    start_date='2023-01-01',
    end_date='2024-12-31'
)

# Sauvegarder
backtest.save_results('backtest_results/')
```

**Résultats**:
```python
{
    'initial_capital': float,
    'final_capital': float,
    'total_pnl': float,
    'total_return': float,      # %
    'total_trades': int,
    'winning_trades': int,
    'losing_trades': int,
    'win_rate': float,          # %
    'avg_win': float,
    'avg_loss': float,
    'profit_factor': float,
    'max_drawdown': float,      # %
    'sharpe_ratio': float,
    'trades_per_day': float,
    'equity_curve': DataFrame,
    'trades': DataFrame
}
```

### 6. polymarket_client.py

**Rôle**: Interface avec Polymarket

**Classes**:

#### PolymarketClient
Client de base
```python
client = PolymarketClient()

# Market info
market = client.get_market_info('BTC')

# Placer un ordre
order = client.place_order(
    symbol='BTC',
    direction='BUY',
    outcome='UP',
    amount=100,
    price=None  # Market order
)

# Gestion
client.cancel_order(order_id)
positions = client.get_positions()
balance = client.get_balance()
```

#### PolymarketTradeExecutor
Exécuteur de haut niveau
```python
executor = PolymarketTradeExecutor()

# Exécuter un signal
order = executor.execute_signal('BTC/USDT', 'BUY', 50000)

# Fermer une position
order = executor.close_position('BTC', 'UP', 100)
```

**Mapping Signal → Ordre**:
```
BUY signal  → Buy YES (UP)
SELL signal → Buy NO (DOWN)
```

### 7. telegram_bot.py

**Rôle**: Notifications Telegram

**Classes**:

#### TelegramNotifier
Bot de notification
```python
notifier = TelegramNotifier()

# Notifications
notifier.notify_trade_entry(...)
notifier.notify_trade_exit(...)
notifier.notify_daily_summary(...)
notifier.notify_error(...)
notifier.notify_bot_start()
notifier.notify_bot_stop()
```

**Format Messages**:
```
📈 TRADE OUVERT

🪙 Paire: BTC/USDT
📊 Direction: BUY UP
💰 Prix d'entrée: $50,000.00
📦 Taille: 0.0020
🛑 Stop Loss: $49,000.00
🎯 Take Profit: $51,500.00

⏰ 2024-12-26 14:30:00
```

## 🔄 Workflow Complet

### 1. Initialisation

```python
# main.py
bot = TradingBot()
bot.strategy = TradingStrategy()
bot.executor = PolymarketTradeExecutor()
bot.notifier = TelegramNotifier()

# Notification démarrage
bot.notifier.notify_bot_start()
```

### 2. Cycle de Trading (Toutes les 15 min)

```python
# 1. Analyse de chaque symbole
for symbol in config.symbols:
    # 2. Charger données multi-TF
    data = data_manager.prepare_multi_timeframe_data(symbol)
    
    # 3. Calculer indicateurs
    df = indicators.calculate_all(data['15m'], data)
    
    # 4. Générer signal
    signal = indicators.generate_signal(df.iloc[-1])
    
    # 5. Si signal valide
    if signal:
        # 6. Exécuter sur Polymarket
        order = executor.execute_signal(symbol, signal, current_price)
        
        # 7. Ouvrir trade en interne
        trade = strategy.open_trade(...)
        
        # 8. Notifier
        notifier.notify_trade_entry(...)
```

### 3. Gestion des Positions (Toutes les 1 min)

```python
for trade in strategy.open_trades:
    # 1. Prix actuel
    current_price = data_manager.get_live_data(trade.symbol).iloc[-1]['close']
    
    # 2. Vérifier SL/TP
    closed = strategy.check_stop_loss_take_profit(trade, current_price, now)
    
    # 3. Si fermé
    if closed:
        # Fermer sur Polymarket
        executor.close_position(trade.symbol, outcome, amount)
        
        # Notifier
        notifier.notify_trade_exit(...)
```

### 4. Résumé Journalier (23:55)

```python
# Calculer stats du jour
stats = calculate_daily_stats()

# Envoyer notification
notifier.notify_daily_summary(...)

# Réinitialiser compteurs
reset_daily_counters()
```

## 🧮 Calculs Importants

### Position Size

```python
position_value = min(
    config.position_size_usd,
    capital * 0.3  # Max 30% du capital
)

position_size = position_value / entry_price
```

### Stop Loss / Take Profit

```python
# BUY
stop_loss = entry_price * (1 - stop_loss_percent / 100)
take_profit = entry_price * (1 + take_profit_percent / 100)

# SELL
stop_loss = entry_price * (1 + stop_loss_percent / 100)
take_profit = entry_price * (1 - take_profit_percent / 100)
```

### PnL

```python
# BUY
pnl = (exit_price - entry_price) * position_size
pnl_percent = ((exit_price / entry_price) - 1) * 100

# SELL
pnl = (entry_price - exit_price) * position_size
pnl_percent = ((entry_price / exit_price) - 1) * 100
```

### Commission & Slippage

```python
# Appliqué à chaque ordre
cost = commission + slippage  # Ex: 0.001 + 0.0005 = 0.0015

# BUY
execution_price = market_price * (1 + cost)

# SELL
execution_price = market_price * (1 - cost)
```

## 🔧 Configuration Avancée

### Optimiser le Win Rate

```yaml
strategy:
  indicators:
    price_action:
      min_wick_ratio: 0.4      # ↑ Plus strict
      min_body_size: 0.002     # ↑ Plus strict
    
    ftfc:
      require_all_aligned: true  # Tous TF alignés
    
    volume:
      min_volume_ratio: 1.5    # ↑ Volume plus élevé
```

### Optimiser le Nombre de Trades

```yaml
strategy:
  indicators:
    price_action:
      min_wick_ratio: 0.2      # ↓ Plus permissif
      min_body_size: 0.001     # ↓ Plus permissif
    
    ftfc:
      require_all_aligned: false  # Majorité suffit
    
    volume:
      min_volume_ratio: 1.1    # ↓ Volume plus bas
```

### Optimiser le Risk/Reward

```yaml
strategy:
  risk:
    stop_loss_percent: 1.5     # ↓ SL plus serré
    take_profit_percent: 4.5   # ↑ TP plus large
```

## 🐛 Debugging

### Logs

```python
# Activer debug dans config.yaml
logging:
  level: DEBUG

# Ou dans .env
LOG_LEVEL=DEBUG
```

### Test Individuel

```python
# Tester un module
python src/indicators.py
python src/strategy.py
python src/telegram_bot.py
```

### Dry Run

```python
# Mode simulation forcé
ENVIRONMENT=development python main.py
```

## 📊 Métriques de Performance

### Calcul du Win Rate

```python
win_rate = (winning_trades / total_trades) * 100
```

### Profit Factor

```python
total_wins = sum(pnl for pnl in trades if pnl > 0)
total_losses = abs(sum(pnl for pnl in trades if pnl < 0))
profit_factor = total_wins / total_losses
```

### Sharpe Ratio

```python
returns = equity.pct_change()
sharpe = (returns.mean() / returns.std()) * sqrt(252)  # Annualisé
```

### Max Drawdown

```python
peak = equity.cummax()
drawdown = (equity - peak) / peak * 100
max_drawdown = drawdown.min()
```

## 🚀 Optimisations Futures

### 1. Machine Learning
- Prédiction de signaux avec Random Forest
- Classification des patterns avec CNN
- Optimization hyperparamètres avec Optuna

### 2. Multi-Exchange
- Support Kraken, Coinbase
- Arbitrage inter-exchange
- Meilleure liquidité

### 3. Advanced Risk Management
- Kelly Criterion pour sizing
- Portfolio optimization
- Correlation analysis

### 4. Real-time Analytics
- Dashboard Grafana
- Alertes personnalisées
- Performance tracking live

## 📚 Références

### APIs
- [Binance API](https://binance-docs.github.io/apidocs/)
- [Polymarket API](https://docs.polymarket.com/)
- [CCXT](https://docs.ccxt.com/)

### Librairies
- [pandas](https://pandas.pydata.org/)
- [numpy](https://numpy.org/)
- [python-telegram-bot](https://python-telegram-bot.org/)

### Trading
- [Investopedia](https://www.investopedia.com/)
- [TradingView](https://www.tradingview.com/)

---

**Document technique v1.0 - Dernière mise à jour: 2024-12-26**

