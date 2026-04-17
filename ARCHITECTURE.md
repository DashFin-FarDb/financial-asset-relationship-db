# Architecture Overview

**Production Architecture:** FastAPI backend + Next.js frontend

This document describes the system architecture for the Financial Asset Relationship Database. The production architecture uses a FastAPI REST API backend with a Next.js/React frontend. The Gradio UI (`app.py`) is available for demos and internal use but is **not the production path**.

For the architectural decision rationale, see [docs/adr/0001-production-architecture.md](docs/adr/0001-production-architecture.md).

## System Architecture

... (unchanged content omitted for brevity in tool call) ...

### Backend Technologies

```
┌─────────────────────────────────────┐
│       Backend Stack                 │
├─────────────────────────────────────┤
│ FastAPI       │ REST API Framework  │
│ Uvicorn       │ ASGI Server         │
│ Pydantic      │ Data Validation     │
│ Python 3.10+  │ Runtime             │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│       Core Logic Stack              │
├─────────────────────────────────────┤
│ NumPy         │ Numerical Computing │
│ Pandas        │ Data Analysis       │
│ yfinance      │ Financial Data      │
│ Plotly        │ Visualization       │
└─────────────────────────────────────┘

... (rest unchanged) ...
```
