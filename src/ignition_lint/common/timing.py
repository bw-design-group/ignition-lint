"""
Performance timing utilities for profiling ign-lint operations.
"""

import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TimingEntry:
	"""Represents a single timing measurement."""
	operation: str
	duration_ms: float
	context: Optional[str] = None


@dataclass
class FileTimings:
	"""Timing data for processing a single file."""
	file_path: str
	total_duration_ms: float
	file_read_ms: float
	json_flatten_ms: float
	model_build_ms: float
	rule_execution_ms: float
	rule_timings: Dict[str, float] = field(default_factory=dict)

	def to_dict(self) -> dict:
		"""Convert to dictionary for serialization."""
		return {
			'file_path': self.file_path,
			'total_duration_ms': round(self.total_duration_ms, 2),
			'file_read_ms': round(self.file_read_ms, 2),
			'json_flatten_ms': round(self.json_flatten_ms, 2),
			'model_build_ms': round(self.model_build_ms, 2),
			'rule_execution_ms': round(self.rule_execution_ms, 2),
			'rule_timings': {
				k: round(v, 2) for k, v in self.rule_timings.items()
			}
		}


class PerformanceTimer:
	"""
	Context manager and utility for timing operations.

	Usage:
		timer = PerformanceTimer()
		with timer.measure("operation_name"):
			# ... code to time
		duration_ms = timer.get_last_duration()
	"""

	def __init__(self):
		self.start_time: Optional[float] = None
		self.last_duration_ms: float = 0.0
		self.measurements: List[TimingEntry] = []

	def start(self):
		"""Start timing."""
		self.start_time = time.perf_counter()

	def stop(self, operation: str = "", context: Optional[str] = None) -> float:
		"""
		Stop timing and record the measurement.

		Returns:
			Duration in milliseconds
		"""
		if self.start_time is None:
			return 0.0

		end_time = time.perf_counter()
		duration_s = end_time - self.start_time
		duration_ms = duration_s * 1000.0

		self.last_duration_ms = duration_ms

		if operation:
			self.measurements.append(
				TimingEntry(operation=operation, duration_ms=duration_ms, context=context)
			)

		self.start_time = None
		return duration_ms

	def get_last_duration(self) -> float:
		"""Get the last measured duration in milliseconds."""
		return self.last_duration_ms

	def measure(self, operation: str, context: Optional[str] = None):
		"""
		Context manager for timing a code block.

		Usage:
			with timer.measure("my_operation"):
				# code to time
		"""
		return TimingContext(self, operation, context)

	def reset(self):
		"""Reset all timing data."""
		self.start_time = None
		self.last_duration_ms = 0.0
		self.measurements = []


class TimingContext:
	"""Context manager for timing code blocks."""

	def __init__(self, timer: PerformanceTimer, operation: str, context: Optional[str] = None):
		self.timer = timer
		self.operation = operation
		self.context = context

	def __enter__(self):
		self.timer.start()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.timer.stop(self.operation, self.context)


class TimingCollector:
	"""Collects and aggregates timing data across multiple files."""

	def __init__(self):
		self.file_timings: List[FileTimings] = []
		self.total_start_time: Optional[float] = None
		self.total_duration_ms: float = 0.0
		self.start_timestamp: Optional[str] = None

	def start_total_timing(self):
		"""Start timing the entire operation."""
		self.total_start_time = time.perf_counter()
		self.start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

	def stop_total_timing(self):
		"""Stop timing the entire operation."""
		if self.total_start_time:
			duration_s = time.perf_counter() - self.total_start_time
			self.total_duration_ms = duration_s * 1000.0

	def add_file_timing(self, file_timing: FileTimings):
		"""Add timing data for a processed file."""
		self.file_timings.append(file_timing)

	def get_summary(self) -> Dict:
		"""
		Get aggregated timing summary.

		Returns:
			Dictionary with summary statistics
		"""
		if not self.file_timings:
			return {}

		total_files = len(self.file_timings)

		# Aggregate totals
		total_file_read = sum(ft.file_read_ms for ft in self.file_timings)
		total_flatten = sum(ft.json_flatten_ms for ft in self.file_timings)
		total_model_build = sum(ft.model_build_ms for ft in self.file_timings)
		total_rule_exec = sum(ft.rule_execution_ms for ft in self.file_timings)

		# Calculate averages
		avg_file_read = total_file_read / total_files
		avg_flatten = total_flatten / total_files
		avg_model_build = total_model_build / total_files
		avg_rule_exec = total_rule_exec / total_files
		avg_per_file = self.total_duration_ms / total_files if total_files > 0 else 0

		# Aggregate rule timings
		all_rule_timings: Dict[str, List[float]] = {}
		for ft in self.file_timings:
			for rule_name, duration in ft.rule_timings.items():
				if rule_name not in all_rule_timings:
					all_rule_timings[rule_name] = []
				all_rule_timings[rule_name].append(duration)

		rule_summary = {}
		for rule_name, durations in all_rule_timings.items():
			rule_summary[rule_name] = {
				'total_ms': round(sum(durations), 2),
				'avg_ms': round(sum(durations) / len(durations), 2),
				'min_ms': round(min(durations), 2),
				'max_ms': round(max(durations), 2),
				'executions': len(durations)
			}

		return {
			'total_duration_ms': round(self.total_duration_ms, 2),
			'files_processed': total_files,
			'avg_per_file_ms': round(avg_per_file, 2),
			'totals': {
				'file_read_ms': round(total_file_read, 2),
				'json_flatten_ms': round(total_flatten, 2),
				'model_build_ms': round(total_model_build, 2),
				'rule_execution_ms': round(total_rule_exec, 2)
			},
			'averages': {
				'file_read_ms': round(avg_file_read, 2),
				'json_flatten_ms': round(avg_flatten, 2),
				'model_build_ms': round(avg_model_build, 2),
				'rule_execution_ms': round(avg_rule_exec, 2)
			},
			'rule_summary': rule_summary
		}

	def write_timing_report(self, output_path: Path):
		"""Write a detailed timing report to a file."""
		summary = self.get_summary()

		# Ensure parent directory exists
		output_path.parent.mkdir(parents=True, exist_ok=True)

		with open(output_path, 'w', encoding='utf-8') as f:
			f.write("=" * 80 + "\n")
			f.write("IGNITION-LINT PERFORMANCE TIMING REPORT\n")
			f.write("=" * 80 + "\n")
			if self.start_timestamp:
				f.write(f"Report Generated: {self.start_timestamp}\n")
			f.write("\n")

			# Overall summary
			f.write("OVERALL SUMMARY\n")
			f.write("-" * 80 + "\n")
			f.write(
				f"Total Duration: {summary['total_duration_ms']:.2f} ms ({summary['total_duration_ms']/1000:.2f}s)\n"
			)
			f.write(f"Files Processed: {summary['files_processed']}\n")
			f.write(f"Average Per File: {summary['avg_per_file_ms']:.2f} ms\n\n")

			# Phase breakdown
			f.write("PHASE BREAKDOWN (Totals)\n")
			f.write("-" * 80 + "\n")
			totals = summary['totals']
			f.write(f"File Reading:    {totals['file_read_ms']:>10.2f} ms\n")
			f.write(f"JSON Flattening: {totals['json_flatten_ms']:>10.2f} ms\n")
			f.write(f"Model Building:  {totals['model_build_ms']:>10.2f} ms\n")
			f.write(f"Rule Execution:  {totals['rule_execution_ms']:>10.2f} ms\n\n")

			# Phase averages
			f.write("PHASE BREAKDOWN (Averages per file)\n")
			f.write("-" * 80 + "\n")
			avgs = summary['averages']
			f.write(f"File Reading:    {avgs['file_read_ms']:>10.2f} ms\n")
			f.write(f"JSON Flattening: {avgs['json_flatten_ms']:>10.2f} ms\n")
			f.write(f"Model Building:  {avgs['model_build_ms']:>10.2f} ms\n")
			f.write(f"Rule Execution:  {avgs['rule_execution_ms']:>10.2f} ms\n\n")

			# Rule summary
			if summary['rule_summary']:
				f.write("RULE EXECUTION SUMMARY\n")
				f.write("-" * 80 + "\n")
				f.write(f"{'Rule Name':<40} {'Total (ms)':>12} {'Avg (ms)':>12} {'Executions':>12}\n")
				f.write("-" * 80 + "\n")

				# Sort by total time descending
				sorted_rules = sorted(
					summary['rule_summary'].items(), key=lambda x: x[1]['total_ms'], reverse=True
				)

				for rule_name, stats in sorted_rules:
					f.write(
						f"{rule_name:<40} {stats['total_ms']:>12.2f} {stats['avg_ms']:>12.2f} {stats['executions']:>12}\n"
					)
				f.write("\n")

			# Per-file details
			f.write("PER-FILE TIMING DETAILS\n")
			f.write("=" * 80 + "\n\n")

			for ft in self.file_timings:
				f.write(f"File: {ft.file_path}\n")
				f.write(f"Total: {ft.total_duration_ms:.2f} ms\n")
				f.write(f"  - File Read:      {ft.file_read_ms:>10.2f} ms\n")
				f.write(f"  - JSON Flatten:   {ft.json_flatten_ms:>10.2f} ms\n")
				f.write(f"  - Model Build:    {ft.model_build_ms:>10.2f} ms\n")
				f.write(f"  - Rule Execution: {ft.rule_execution_ms:>10.2f} ms\n")

				if ft.rule_timings:
					f.write("  Rule breakdown:\n")
					for rule_name, duration in sorted(
						ft.rule_timings.items(), key=lambda x: x[1], reverse=True
					):
						f.write(f"    - {rule_name}: {duration:.2f} ms\n")

				f.write("\n")

			f.write("=" * 80 + "\n")
			f.write("END OF REPORT\n")
			f.write("=" * 80 + "\n")
