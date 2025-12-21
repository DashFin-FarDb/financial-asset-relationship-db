# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────┐     ┌──────────────────────────┐     │
│  │   Gradio UI (Port 7860)  │     │ Next.js UI (Port 3000)   │     │
│  │  ┌────────────────────┐  │     │  ┌────────────────────┐  │     │
│  │  │ 3D Visualization   │  │     │  │ 3D Visualization   │  │     │
│  │  │ Metrics Dashboard  │  │     │  │ Metrics Dashboard  │  │     │
│  │  │ Asset Explorer     │  │     │  │ Asset Explorer     │  │     │
│  │  │ Schema Report      │  │     │  │ (React Components) │  │     │
│  │  └────────────────────┘  │     │  └────────────────────┘  │     │
│  │   (Python/Gradio)        │     │   (TypeScript/React)     │     │
│  └──────────┬───────────────┘     └──────────┬───────────────┘     │
│             │                                 │                      │
└─────────────┼─────────────────────────────────┼──────────────────────┘
              │                                 │
              │ Direct Function Calls          │ HTTP REST API
              │                                 │
┌─────────────▼─────────────────────────────────▼──────────────────────┐
│                          API Layer                                    │
├───────────────────────────────────────────────────────────────────────┤
│             │                                                         │
│             │                  ┌────────────────────────────┐        │
│             │                  │  FastAPI Backend           │        │
│             │                  │  (Port 8000)               │        │
│             │                  │                            │        │
│             │                  │  Endpoints:                │        │
│             │                  │  - /api/assets             │        │
│             │                  │  - /api/metrics            │        │
│             │                  │  - /api/visualization      │        │
│             │                  │  - /api/relationships      │        │
│             │                  │  - /api/health             │        │
│             │                  │                            │        │
│             │                  └────────────┬───────────────┘        │
│             │                               │                        │
└─────────────┼───────────────────────────────┼────────────────────────┘
              │                               │
              │                               │ Function Calls
              │                               │
┌─────────────▼───────────────────────────────▼────────────────────────┐
│                      Core Business Logic Layer                        │
├───────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  AssetRelationshipGraph (src/logic/asset_graph.py)           │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │   │
│  │  │ add_asset()  │  │ add_relation │  │ build_rel()  │       │   │
│  │  │              │  │              │  │              │       │   │
│  │  │ get_metrics()│  │ find_rel()   │  │ get_3d_viz() │       │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Visualization Layer (src/visualizations/)                    │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │   │
│  │  │ graph_visuals│  │ metric_vis   │  │ formulaic    │       │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                        │
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
│  │  Data Sources (src/data/)                                    │ │
│  │  ┌────────────────┐           ┌────────────────┐            │ │
│  │  │ sample_data.py │           │real_data_fetch │            │ │
│  │  │ (Static)       │           │(Yahoo Finance) │            │ │
│  │  └────────────────┘           └────────────────┘            │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Component Interaction Flow

### Flow 1: Next.js Frontend → FastAPI → Core Logic

```
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
FastAPI Endpoint (api/main.py)
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

### Flow 2: Gradio UI → Core Logic (Direct)

```
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

```
┌─────────────────────────────────────┐
│      Next.js Frontend Stack         │
├─────────────────────────────────────┤
│ React 18      │ UI Framework        │
│ Next.js 14    │ React Framework     │
│ TypeScript    │ Type Safety         │
│ Tailwind CSS  │ Styling             │
│ Plotly.js     │ 3D Visualization    │
│ Axios         │ HTTP Client         │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│      Gradio Frontend Stack          │
├─────────────────────────────────────┤
│ Gradio 4.x    │ UI Framework        │
│ Plotly        │ Visualization       │
│ Python        │ Backend Logic       │
└─────────────────────────────────────┘
```

### Backend Technologies

```
┌─────────────────────────────────────┐
│       Backend Stack                 │
├─────────────────────────────────────┤
│ FastAPI       │ REST API Framework  │
│ Uvicorn       │ ASGI Server         │
│ Pydantic      │ Data Validation     │
│ Python 3.8+   │ Runtime             │
└─────────────────────────────────────┘

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

```
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

```
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

```
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

```
┌─────────────────────────────────────────┐
│         Security Layers                  │
├─────────────────────────────────────────┤
│                                          │
│  1. Transport Layer                     │
│     ├── HTTPS/TLS                       │
│     └── Secure WebSocket (future)       │
│                                          │
│  2. Application Layer                   │
│     ├── CORS Configuration              │
│     ├── Input Validation (Pydantic)     │
│     └── Rate Limiting (future)          │
│                                          │
│  3. Data Layer                          │
│     ├── Data validation                 │
│     └── Type checking                   │
│                                          │
└─────────────────────────────────────────┘
```

## Performance Considerations

### Caching Strategy (Future)

```
Request → Cache Check → Cache Hit?
                          │
                          ├─ Yes → Return cached data
                          │
                          └─ No → Compute → Cache → Return
```

### Load Distribution

```
High Traffic
    │
    ├─ Static Assets → CDN (Vercel Edge)
    ├─ API Requests → Serverless Functions (Auto-scale)
    └─ Graph Data → In-memory cache (Instance-level)
```

## Extensibility Points

### Adding New Features

1. **New Asset Type**
   ```
   financial_models.py → asset_graph.py → API endpoint → Frontend
   ```

2. **New Relationship Type**
   ```
   _find_relationships() → build_relationships() → Visualization
   ```

3. **New Visualization**
   ```
   Create component → Add to page.tsx → Connect to API
   ```

4. **New API Endpoint**
   ```
   api/main.py → Test → Update frontend API client → Use in components
   ```

---

For more details, see:
- [INTEGRATION_SUMMARY.md](INTEGRATION_SUMMARY.md) - Technical implementation
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment procedures
- [QUICK_START.md](QUICK_START.md) - Getting started guide
