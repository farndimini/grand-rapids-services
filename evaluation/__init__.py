"""
evaluation/ — Real Evaluation Harness for SEO Agent Pro
=========================================================
Provides:
  • BenchmarkRunner — full article evaluation pipeline
  • Scorers — semantic, structural, intent, readability, SERP alignment
  • Datasets — historical generation datasets and regression tracking

Usage:
    from evaluation.benchmark_runner import BenchmarkRunner
    runner = BenchmarkRunner()
    report = runner.evaluate(article_html, keyword="best CRM", serp_data={...})
"""

from .benchmark_runner import BenchmarkRunner
from .scorers import SemanticScorer, StructureScorer, SERPScorer, ReadabilityScorer
from .datasets import EvaluationDataset

__all__ = [
    "BenchmarkRunner",
    "SemanticScorer",
    "StructureScorer",
    "SERPScorer",
    "ReadabilityScorer",
    "EvaluationDataset",
]
