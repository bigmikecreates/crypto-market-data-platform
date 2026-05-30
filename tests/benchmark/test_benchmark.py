import tracemalloc


from cmpd.benchmark.core import (
    BenchmarkContext,
    BenchmarkResult,
    StageMetrics,
)
from cmpd.benchmark.rules import (
    DEFAULT_RULES,
    VERBOSE_RULES,
    CrossValidationRule,
    evaluate_rules,
)
from cmpd.benchmark.runners import CandlePipelineRunner
from cmpd.config import TimestampConfig


class TestBenchmarkContext:
    def setup_method(self):
        tracemalloc.start()

    def teardown_method(self):
        tracemalloc.stop()

    def test_checkpoint_appends_stage(self):
        ctx = BenchmarkContext()
        ctx.checkpoint("stage_a")
        assert len(ctx.stages) == 1
        assert ctx.stages[0].name == "stage_a"

    def test_checkpoint_wall_ms_non_negative(self):
        ctx = BenchmarkContext()
        ctx.checkpoint("s1")
        assert ctx.stages[0].wall_ms >= 0

    def test_checkpoint_file_kb_none_by_default(self):
        ctx = BenchmarkContext()
        ctx.checkpoint("s1")
        assert ctx.stages[0].file_kb is None

    def test_checkpoint_file_kb_stored(self):
        ctx = BenchmarkContext()
        ctx.checkpoint("write", file_kb=12.5)
        assert ctx.stages[0].file_kb == 12.5

    def test_multiple_checkpoints_accumulate(self):
        ctx = BenchmarkContext()
        ctx.checkpoint("a")
        ctx.checkpoint("b")
        ctx.checkpoint("c")
        assert len(ctx.stages) == 3
        names = [s.name for s in ctx.stages]
        assert names == ["a", "b", "c"]

    def test_total_mem_delta_sums_positive_stages(self):
        ctx = BenchmarkContext()
        ctx.checkpoint("a")
        ctx.checkpoint("b")
        assert ctx.total_mem_delta_mb >= 0


class TestCandlePipelineRunnerSmoke:
    def setup_method(self):
        tracemalloc.start()

    def teardown_method(self):
        tracemalloc.stop()

    def test_coarse_runs_small_batch(self, tmp_path):
        runner = CandlePipelineRunner()
        result = runner.run_coarse(
            count=10, ts_config=TimestampConfig(), base_path=str(tmp_path)
        )
        assert result.count == 10
        assert result.runner_name == "candle"
        assert len(result.stages) > 0
        assert result.schema  # schema is populated

    def test_verbose_runs_small_batch(self, tmp_path):
        runner = CandlePipelineRunner()
        result = runner.run_verbose(
            count=10, ts_config=TimestampConfig(), base_path=str(tmp_path)
        )
        assert result.count == 10
        assert len(result.stages) > 0

    def test_zero_count_returns_early(self, tmp_path):
        runner = CandlePipelineRunner()
        result = runner.run_coarse(
            count=0, ts_config=TimestampConfig(), base_path=str(tmp_path)
        )
        assert result.count == 0

    def test_microsecond_resolution(self, tmp_path):
        runner = CandlePipelineRunner()
        result = runner.run_coarse(
            count=5, ts_config=TimestampConfig(resolution="us"), base_path=str(tmp_path)
        )
        assert result.ts_resolution == "us"
        assert result.count == 5

    def test_parquet_file_is_created(self, tmp_path):
        runner = CandlePipelineRunner()
        runner.run_coarse(count=5, ts_config=TimestampConfig(), base_path=str(tmp_path))
        parquet_files = list(tmp_path.rglob("*.parquet"))
        assert len(parquet_files) == 1

    def test_schema_contains_expected_columns(self, tmp_path):
        runner = CandlePipelineRunner()
        result = runner.run_coarse(
            count=5, ts_config=TimestampConfig(), base_path=str(tmp_path)
        )
        expected = {
            "exchange",
            "symbol",
            "timeframe",
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "source",
        }
        assert expected.issubset(result.schema.keys())


class TestRules:
    def _make_result(self, count=100, stages=None) -> BenchmarkResult:
        r = BenchmarkResult(count=count, ts_resolution="s", runner_name="test")
        if stages:
            r.stages = stages
            r.pipeline_end_index = len(stages) - 1
        return r

    def test_evaluate_default_rules_returns_one_outcome_per_rule(self):
        result = self._make_result()
        outcomes = evaluate_rules(DEFAULT_RULES, result)
        assert len(outcomes) == len(DEFAULT_RULES)

    def test_evaluate_verbose_rules_superset_of_default(self):
        result = self._make_result()
        assert len(VERBOSE_RULES) > len(DEFAULT_RULES)
        outcomes = evaluate_rules(VERBOSE_RULES, result)
        assert len(outcomes) == len(VERBOSE_RULES)

    def test_each_outcome_has_valid_rating(self):
        result = self._make_result()
        for _, rating, _ in evaluate_rules(DEFAULT_RULES, result):
            assert rating in ("PASS", "WARN", "FAIL")

    def test_empty_stages_all_pass(self):
        result = self._make_result(stages=[])
        for _, rating, _ in evaluate_rules(DEFAULT_RULES, result):
            assert rating == "PASS"

    def test_cross_validation_rule_fields(self):
        rule = DEFAULT_RULES[0]
        assert isinstance(rule, CrossValidationRule)
        assert rule.name
        assert callable(rule.evaluate)

    def test_stage_metrics_dataclass(self):
        s = StageMetrics(
            name="test",
            wall_ms=1.0,
            cpu_ms=0.9,
            mem_delta_mb=0.1,
            peak_mb=0.2,
            gc_g0=0,
            gc_g1=0,
            gc_g2=0,
            file_kb=5.0,
        )
        assert s.name == "test"
        assert s.file_kb == 5.0
