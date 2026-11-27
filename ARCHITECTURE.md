# Architecture Overview

**Production Architecture:** FastAPI backend + Next.js frontend

This document describes the system architecture for the Financial Asset Relationship Database. The production architecture uses a FastAPI REST API backend with a Next.js/React frontend. Configuration is centralized through `src/config/settings.py` via `pydantic-settings`. The Gradio UI (`app.py`) is decoupled from production configuration and correctly acts strictly as a non-production demo endpoint, bounding its host explicitly to localhost (`127.0.0.1`). Auth keys like `SECRET_KEY` are deterministic in testing.

For the architectural decision rationale, see [docs/adr/0001-production-architecture.md](docs/adr/0001-production-architecture.md).

## System Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────┐     ┌──────────────────────────┐     │
│  │ Next.js UI (Port 3000)   │     │   Gradio UI (Port 7860)  │     │
│  │   ** PRODUCTION **       │     │   ** NON-PRODUCTION **   │     │
│  │  ┌────────────────────┐  │     │  ┌────────────────────┐  │     │
│  │  │ 3D Visualization   │  │     │  │ 3D Visualization   │  │     │
│  │  │ Metrics Dashboard  │  │     │  │ Metrics Dashboard  │  │     │
│  │  │ Asset Explorer     │  │     │  │ Asset Explorer     │  │     │
│  │  │ (React Components) │  │     │  │ Schema Report      │  │     │
│  │  └────────────────────┘  │     │  └────────────────────┘  │     │
│  │   (TypeScript/React)     │     │   (Python/Gradio)        │     │
│  └──────────┬───────────────┘     └──────────┬───────────────┘     │
│             │                                 │                      │
└─────────────┼─────────────────────────────────┼──────────────────────┘
              │                                 │
              │ ** PRODUCTION PATH **          │ ** DEMO/TESTING **    │
              │ HTTP REST API                  │ Direct Function Calls │
              │                                 │
┌─────────────▼─────────────────────┐   ┌────────────▼───────────────┐
│           API Layer               │   │ Core Business Logic Layer  │
├───────────────────────────────────┤   ├────────────────────────────┤
│ FastAPI Backend (Port 8000)       │   │ Gradio calls the graph and │
│ (api/app_factory.py, api/routers/)│   │ visualization stack         │
│ Endpoints:                        │   │ directly; it does not flow │
│ - /api/assets                     │   │ through the FastAPI layer. │
│ - /api/graph/metrics              │   │                            │
│ - /api/visualization              │   │                            │
│ - /api/relationships              │   │                            │
│ - /api/health & /api/health/det.. │   │                            │
└────────────┬──────────────────────┘   └────────────┬───────────────┘
             │                                        │
             └────────────────┬───────────────────────┘
                              │ Function Calls
                              │
┌─────────────────────────────▼──────────────────────────────────────┐
│                      Core Business Logic Layer                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  AssetRelationshipGraph (src/logic/asset_graph.py)           │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │   │
│  │  │ add_asset()  │  │ add_relation │  │ build_rel()  │       │   │
│  │  │              │  │              │  │              │       │   │
│  │  │ get_metrics()│  │ find_rel()   │  │ get_3d_viz() │       │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Visualization Layer (src/visualizations/)                   │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │   │
│  │  │ graph_visuals│  │ metric_vis   │  │ formulaic    │       │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────┬──────────────────────────────────────────────────────┘
              │
┌─────────────▼──────────────────────────────────────────────────────┐
│                         Data Layer                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Financial Models (src/models/financial_models.py)           │ │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │ │
│  │  │ Equity  │  │  Bond   │  │Commodity│  │Currency │        │ │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Durable Persistence & Sources (src/data/, api/database.py)  │ │
│  │  ┌────────────────┐  ┌──────────────────┐  ┌──────────────┐  │ │
│  │  │ PostgreSQL /   │  │ sample_data.py / │  │ migrate_     │  │ │
│  │  │ SQLite (ORM)   │  │ real_data_fetch  │  │ database.py  │  │ │
│  │  └────────────────┘  └──────────────────┘  └──────────────┘  │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Component Interaction Flow

### Production Flow: Next.js Frontend → FastAPI → Core Logic

```text
User Action (Next.js)
       │
       │ 1. Click "View 3D Graph"
       ▼
React Component (NetworkVisualization.tsx)
       │
       │ 2. API Call: GET /api/visualization
       ▼
API Client (lib/api.ts)
       │
       │ 3. HTTP Request (Axios)
       ▼
FastAPI Router (api/routers/visualization.py)
       │
       │ 4. get_visualization_data()
       ▼
AssetRelationshipGraph.get_3d_visualization_data()
       │
       │ 5. Calculate positions, colors
       ▼
Response: { nodes: [...], edges: [...] }
       │
       │ 6. JSON Response
       ▼
React Component
       │
       │ 7. Render with Plotly
       ▼
3D Visualization Displayed
```

### Non-Production Flow: Gradio UI → Core Logic (Direct)

```text
User Action (Gradio)
       │
       │ 1. Click "Refresh Visualization"
       ▼
Gradio Event Handler (app.py)
       │
       │ 2. refresh_visualization_outputs()
       ▼
visualize_3d_graph()
       │
       │ 3. Direct function call
       ▼
AssetRelationshipGraph.get_3d_visualization_data()
       │
       │ 4. Calculate positions, colors
       ▼
Plotly Figure Object
       │
       │ 5. Return figure
       ▼
Gradio Interface Update
```

## Technology Stack

### Frontend Technologies

```text
┌─────────────────────────────────────┐
│ Next.js Frontend Stack              │
│ ** PRODUCTION **                    │
├─────────────────────────────────────┤
│ React 19      │ UI Framework        │
│ Next.js 16    │ React Framework     │
│ TypeScript 5  │ Type Safety         │
│ Tailwind CSS 4│ Styling             │
│ Plotly.js     │ 3D Visualization    │
│ Axios         │ HTTP Client         │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Gradio Frontend Stack               │
│ ** NON-PRODUCTION **                │
├─────────────────────────────────────┤
│ Gradio 6.x    │ UI Framework        │
│ Plotly        │ Visualization       │
│ Python        │ Demo/Internal Logic │
└─────────────────────────────────────┘
```

### Backend Technologies

```text
┌───────────────────────────────────────────┐
│       Backend Stack                       │
├───────────────────────────────────────────┤
│ FastAPI           │ REST API Framework    │
│ Uvicorn           │ ASGI Server           │
│ Pydantic          │ Data Validation       │
│ pydantic-settings │ Config Management     │
│ SQLAlchemy 2.0    │ PostgreSQL / SQLite   │
│ slowapi           │ Rate Limiting         │
│ Python 3.12+      │ Runtime (min 3.10)    │
└───────────────────────────────────────────┘

┌─────────────────────────────────────┐
│       Core Logic Stack              │
├─────────────────────────────────────┤
│ NumPy         │ Numerical Computing │
│ Pandas        │ Data Analysis       │
│ yfinance      │ Financial Data      │
│ Plotly        │ Visualization       │
└─────────────────────────────────────┘
```

## Data Flow

### Asset Relationship Discovery

```text
1. Data Ingestion
   ├── Yahoo Finance API (yfinance)
   │   ├── Stock prices
   │   ├── Company info
   │   └── Financial metrics
   └── Static sample data
       └── Example assets

2. Asset Creation
   ├── Equity objects
   ├── Bond objects
   ├── Commodity objects
   └── Currency objects

3. Relationship Building
   ├── Same sector analysis
   ├── Corporate bond-to-equity links
   ├── Commodity exposure detection
   ├── Currency risk mapping
   └── Income comparison (dividends vs yields)

4. Graph Construction
   ├── Add assets as nodes
   ├── Add relationships as edges
   ├── Calculate edge weights (strength)
   └── Assign node attributes

5. Visualization
   ├── Calculate 3D positions (deterministic)
   ├── Assign colors by asset class
   ├── Size nodes by importance
   └── Generate edge traces

6. Output
   ├── JSON (API)
   ├── Plotly figure (Gradio)
   └── React props (Next.js)
```

## Deployment Architecture

### Local Development

```text
┌──────────────────────────────────────────┐
│         Developer Machine                 │
├──────────────────────────────────────────┤
│                                           │
│  ┌────────────┐      ┌────────────┐     │
│  │ Frontend   │      │  Backend   │     │
│  │ npm run dev│      │  uvicorn   │     │
│  │ Port 3000  │◄────►│  Port 8000 │     │
│  └────────────┘      └────────────┘     │
│                                           │
│  ┌──────────────────────────────┐       │
│  │  Gradio (Optional)            │       │
│  │  python app.py                │       │
│  │  Port 7860                    │       │
│  └──────────────────────────────┘       │
│                                           │
└──────────────────────────────────────────┘
```

### Vercel Deployment

```text
┌──────────────────────────────────────────────────────────┐
│                    Vercel Platform                        │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────────────┐  ┌────────────────────┐  │
│  │  Next.js Frontend        │  │  Python Backend    │  │
│  │  (Vercel Edge)           │  │  (Serverless Func) │  │
│  │  - Static pages          │  │  - FastAPI app     │  │
│  │  - API routes            │  │  - Auto-scaling    │  │
│  │  - Auto-deploy from Git  │  │  - Cold start      │  │
│  └──────────┬───────────────┘  └──────────┬─────────┘  │
│             │                              │             │
│             │    Internal Network          │             │
│             └──────────────────────────────┘             │
│                                                           │
└──────────────────────────────────────────────────────────┘
                         │
                         │ HTTPS
                         ▼
                    Internet Users
```

## Security Architecture

```text
┌─────────────────────────────────────────┐
│         Security Layers                  │
├─────────────────────────────────────────┤
│                                          │
│  1. Transport Layer                     │
│     ├── HTTPS/TLS                       │
│     └── Secure WebSocket (future)       │
│                                          │
│  2. Application Layer                   │
│     ├── CORS Policy (api/cors_policy.py)│
│     ├── JWT Auth & Operator RBAC        │
│     ├── Input Validation (Pydantic)     │
│     └── Rate Limiting (slowapi)         │
│                                          │
│  3. Data Layer                          │
│     ├── Least-privilege DB roles        │
│     ├── Parameterized SQLAlchemy ORM    │
│     └── Schema migrations CLI           │
│                                          │
└─────────────────────────────────────────┘
```

## Performance Considerations

### Caching Strategy (Future)

```text
Request → Cache Check → Cache Hit?
                          │
                          ├─ Yes → Return cached data
                          │
                          └─ No → Compute → Cache → Return
```

### Load Distribution

```text
High Traffic
    │
    ├─ Static Assets → CDN (Vercel Edge)
    ├─ API Requests → Serverless Functions (Auto-scale)
    └─ Graph Data → In-memory cache (Instance-level)
```

## Extensibility Points

### Adding New Features

1. **New Asset Type**

   ```text
   financial_models.py → asset_graph.py → API endpoint → Frontend
   ```

2. **New Relationship Type**

   ```text
   _find_relationships() → build_relationships() → Visualization
   ```

3. **New Visualization**

   ```text
   Create component → Add to page.tsx → Connect to API
   ```

4. **New API Endpoint**
   ```text
   api/routers/ → api/app_factory.py → Test → Update frontend API client → Use in components
   ```

---

For more details, see:

- [AGENTS.md](AGENTS.md) - Repository orientation and architecture overview
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment procedures
- [QUICK_START.md](QUICK_START.md) - Getting started guide
