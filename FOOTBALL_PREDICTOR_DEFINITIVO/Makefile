.PHONY: run test docker-build docker-run update-data

run:
	streamlit run football_predictor_pro.py

test:
	pytest tests/

docker-build:
	docker build -t football-predictor .

docker-run:
	docker-compose up -d

update-data:
	python data/api_fetcher.py
	python data/fbref_scraper.py
