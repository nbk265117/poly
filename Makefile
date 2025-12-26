# Makefile pour Robot de Trading Polymarket

.PHONY: help install download backtest run test clean

help:
	@echo "🤖 Robot de Trading Polymarket - Commandes disponibles:"
	@echo ""
	@echo "  make install      - Installer les dépendances"
	@echo "  make download     - Télécharger les données historiques"
	@echo "  make backtest     - Lancer le backtesting"
	@echo "  make run          - Lancer le robot (simulation)"
	@echo "  make test         - Tester les modules"
	@echo "  make clean        - Nettoyer les fichiers temporaires"
	@echo ""

install:
	@echo "📦 Installation des dépendances..."
	pip install -r requirements.txt
	@echo "✅ Installation terminée"

download:
	@echo "📊 Téléchargement des données historiques..."
	python scripts/download_data_15m.py
	@echo "✅ Téléchargement terminé"

backtest:
	@echo "📈 Lancement du backtesting..."
	python backtest_main.py --plot --save-results
	@echo "✅ Backtesting terminé"

run:
	@echo "🚀 Lancement du robot..."
	python main.py

test:
	@echo "🧪 Test des modules..."
	@python src/config.py
	@python src/indicators.py
	@python src/data_manager.py
	@echo "✅ Tests terminés"

clean:
	@echo "🧹 Nettoyage..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Nettoyage terminé"

.DEFAULT_GOAL := help

