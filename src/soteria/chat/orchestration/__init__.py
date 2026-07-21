"""Chat orchestration: intent classification, NL->SQL generation and
validation, restricted SQL execution, and answer synthesis. pipeline.py is
the sole orchestrator — every other module here is a pure function it
calls, never calling one another directly."""
