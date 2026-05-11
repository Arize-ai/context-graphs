"""Test-suite-wide configuration.

Runs at pytest collection time, before any test module is imported. Two
responsibilities:

1. Clear Arize credentials so importing `src.main` (which transitively
   imports `src.instrumentation`) takes the no-op skip path instead of
   registering against the real Arize collector.

2. Install a recording `TracerProvider` so tests that exercise the
   pipeline's CHAIN root span see real span ids. OTel only allows a
   single global provider per process — setting it here once means
   individual tests don't fight each other for it.
"""

import os

os.environ.pop("ARIZE_API_KEY", None)
os.environ.pop("ARIZE_SPACE_ID", None)

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_test_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_test_exporter))
trace.set_tracer_provider(_provider)
