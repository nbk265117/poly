# Botayo Constitution
## Bot de Trading Polymarket - Predictions Crypto 15min

## Core Principles

### I. Strategie RSI + Stochastic + Filtres Temporels
- RSI(7) avec seuils 38/58 (asymetrique pour meilleur WR)
- Stochastic(5) avec seuils 30/80
- 44 combos jour+heure bloques (WR < 53%)
- Signals: UP si RSI<38 AND Stoch<30, DOWN si RSI>58 AND Stoch>80

### II. Risk Management
- Mise fixe par trade: $100 @ 52.5c
- Gain si WIN: +$90.48 (190.48 shares * $0.475 profit)
- Perte si LOSS: -$100
- Max 3 positions simultanees (1 par paire)
- 30-150 trades/jour selon marche

### III. Execution Live
- 3 bots independants: BTC (7 shares), ETH (10 shares), XRP (5 shares)
- Entry 8 secondes avant candle 15min
- Mode simulation (development) ou reel (production)
- Notifications Telegram pour chaque trade

### IV. Surveillance 24/7
- Watchdog v8.1 maintient exactement 3 bots
- Cron */5 pour watchdog, hourly pour heartbeat
- Lock file pour eviter race conditions
- Auto-restart si crash detecte

### V. Backtest Valide
- 2 ans de donnees (2024-2025)
- Win Rate: 57% moyenne
- PnL: +$17,253/mois avec $100/trade
- Pire mois: +$9,105 (avec 44 filtres)

## Infrastructure

### VPS DigitalOcean
- IP: 3.96.141.89
- User: ubuntu
- Chemin: /home/ubuntu/poly
- Python venv: /home/ubuntu/poly/venv

### Fichiers Critiques
| Fichier | Role |
|---------|------|
| bot_simple.py | Bot principal |
| watchdog.sh | Surveillance (v8.1) |
| heartbeat.sh | Status horaire |
| start_bots.sh | Demarrage manuel |
| config.yaml | Configuration strategie |

### Cron Jobs
```
*/5 * * * * /home/ubuntu/poly/watchdog.sh
0 * * * * /home/ubuntu/poly/heartbeat.sh >> /home/ubuntu/poly/logs/heartbeat.log 2>&1
0 0 * * * /home/ubuntu/poly/cleanup_logs.sh >> /home/ubuntu/poly/logs/cleanup.log 2>&1
```

## API & Services

### Polymarket CLOB API
- Endpoint: https://clob.polymarket.com
- Auth: Private key wallet
- Markets: BTC/ETH/XRP UP or DOWN 15min

### Binance Data API
- Source: Donnees historiques pour backtest
- Timeframe: 15 minutes
- Paires: BTC/USDT, ETH/USDT, XRP/USDT

### Telegram Bot
- Notifications: trade_entry, trade_exit, daily_summary, errors
- Config: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID dans .env

## Governance

- Toute modification de strategie doit etre backtestee
- Changements de config necessitent restart des bots
- Logs conserves 7 jours (cleanup quotidien)
- SSH key: /tmp/vps_key.pem (local)

**Version**: 7.0 | **Ratified**: 2025-12-30 | **Last Amended**: 2025-12-30
