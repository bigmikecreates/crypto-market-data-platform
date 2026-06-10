COMPOSE_FILE ?= docker-compose.dev.yml

.PHONY: test report hypothesis-stats clean-reports destroy clean-images up rebuild

test:
	pytest

report:
	@mkdir -p reports
	pytest \
	  --junitxml=reports/junit.xml \
	  --cov=src/ \
	  --cov-report=term-missing \
	  --cov-report=html:reports/htmlcov \
	  --cov-report=xml:reports/coverage.xml

hypothesis-stats:
	pytest tests/properties/ --hypothesis-show-statistics -v --tb=short

clean-reports:
	rm -rf reports/

destroy:
	docker compose -f $(COMPOSE_FILE) down -v --remove-orphans

clean-images:
	docker compose -f $(COMPOSE_FILE) down --rmi all -v --remove-orphans

up:
	docker compose -f $(COMPOSE_FILE) up -d

rebuild:
	docker compose -f $(COMPOSE_FILE) up -d --build
