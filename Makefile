.PHONY: test report hypothesis-stats clean-reports

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
