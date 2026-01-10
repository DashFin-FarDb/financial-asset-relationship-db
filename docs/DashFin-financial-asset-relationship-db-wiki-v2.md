# DashFin/financial-asset-relationship-db Wiki

Version: 2

## Overview

### Home

<details>
<summary>Relevant source files</summary>
The following files were used as context for generating this wiki page:

- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
- [SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/SUMMARY.md)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)
- [frontend/README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/README.md)
</details>

# Home

The Financial Asset Relationship Database is a system designed for the 3D visualization of interconnected financial assets. It supports a wide range of major asset classes, including Equities, Bonds, Commodities, Currencies, and Regulatory Events. The core purpose is to provide a comprehensive, interactive tool for cross-asset analysis, automatic relationship discovery, and modeling the impact of corporate and regulatory events on the financial network.
Sources: [README.md:3-4]()

The project offers two distinct user interface and backend combinations: an original implementation using a Gradio UI with direct Python logic, and a newer, decoupled architecture featuring a Next.js frontend communicating with a FastAPI backend via a REST API. Both implementations leverage the same core logic for graph analysis and visualization generation.
Sources: [README.md:10-12, 30-32](), [ARCHITECTURE.md:3-23]()

## System Architecture

The system is structured into four primary layers: User Interface, API, Core Business Logic, and Data. This layered design allows for flexibility, such as supporting multiple frontend applications (Gradio and Next.js) that consume the core logic in different ways.
Sources: [ARCHITECTURE.md:3-63]()

The diagram below illustrates the high-level system architecture, showing the two parallel paths from the user interface to the core logic.

```mermaid
graph TD
    subgraph User Interface Layer
        A1[Gradio UI on Port 7860]
        A2[Next.js UI on Port 3000]
    end

    subgraph API Layer
        B1[Direct Python Calls]
        B2[FastAPI Backend on Port 8000]
    end

    subgraph Core Business Logic Layer
        C[AssetRelationshipGraph <br> src/logic/asset_graph.py]
    end

    subgraph Data Layer
        D1[Financial Models <br> src/models/financial_models.py]
        D2[Data Sources <br> yfinance, sample_data.py]
    end

    A1 --> B1
    A2 --> B2

    B1 --> C
    B2 --> C

    C --> D1
    C --> D2
```
Sources: [ARCHITECTURE.md:3-63](), [CONTRIBUTING.md:175-185]()

### Key Components

| Component | Description | Source File(s) |
| --- | --- | --- |
| **Gradio UI** | The original interactive web interface for demos and direct interaction with Python logic. | `app.py` |
| **Next.js Frontend** | A modern, responsive web application built with React and TypeScript. | `frontend/` |
| **FastAPI Backend** | A REST API server that exposes the core logic to the Next.js frontend. | `api/main.py` |
| **`AssetRelationshipGraph`** | The core engine responsible for graph algorithms, relationship discovery, and metric calculations. | `src/logic/asset_graph.py` |
| **Financial Models** | Dataclasses defining the structure for all asset types (e.g., `Equity`, `Bond`). | `src/models/financial_models.py` |
| **Data Sources** | Modules for fetching data, either from static samples or real-time sources like Yahoo Finance. | `src/data/` |

Sources: [README.md:100-112](), [ARCHITECTURE.md:70-90](), [frontend/README.md:40-52]()

## Features

The platform provides a rich set of features for financial analysis and visualization.

| Feature | Description |
| --- | --- |
| **3D Network Visualization** | An interactive 3D graph of asset relationships, rendered using Plotly. |
| **Cross-Asset Analysis** | Automatically discovers and models relationships between different asset classes. |
| **Regulatory Integration** | Models the impact of corporate events and SEC filings on the asset network. |
| **Real-time Metrics** | Provides network statistics like density, degree, and relationship strength analysis. |

Sources: [README.md:71-75]()

### Supported Asset Classes

The database is designed to handle a variety of financial instruments.

| Asset Class | Key Attributes |
| --- | --- |
| **Equities** | P/E ratios, dividend yields, EPS |
| **Fixed Income (Bonds)** | Yield, duration, credit ratings |
| **Commodities** | Futures and spot prices, contract specifications |
| **Currencies** | FX pairs, exchange rates, monetary policy links |
| **Regulatory Events** | Earnings, SEC filings, M&A activities |

Sources: [README.md:78-84]()

### Relationship Types

The system can identify and model several types of relationships between assets.

- **Sector Affinity**: Assets in the same industry sector.
- **Corporate Links**: Bonds issued by a stock company.
- **Commodity Exposure**: Equity companies exposed to commodity prices.
- **Currency Risk**: FX exposure for non-USD assets.
- **Income Comparison**: Comparing stock dividends vs. bond yields.
- **Event Impact**: A regulatory event affecting multiple assets.

Sources: [README.md:87-94]()

## Data Model and Flow

The core data model revolves around Assets, their Relationships, and the influence of Regulatory Events. Relationship strength is normalized on a 0.0 to 1.0 scale, while regulatory impact is scored from -1 (negative) to +1 (positive).
Sources: [README.md:118-120]()

The following diagram shows the basic entity relationships.

```mermaid
erDiagram
    ASSET {
        string id
        string symbol
        string name
        AssetClass asset_class
        string sector
        float price
    }
    RELATIONSHIP {
        string source_id
        string target_id
        string type
        float strength
    }
    REGULATORY_EVENT {
        string id
        string name
        date event_date
        float impact_score
    }

    ASSET ||--o{ RELATIONSHIP : "has"
    REGULATORY_EVENT ||--|{ ASSET : "impacts"
```
Sources: [README.md:114-120](), [AUDIT_REPORT.md:32-35]()

### Data Flow for Relationship Discovery

The process of building the asset graph follows a clear data flow from ingestion to visualization.

```mermaid
flowchart TD
    A[Data Ingestion <br> yfinance / sample_data.py] --> B(Asset Object Creation <br> Equity, Bond, etc.)
    B --> C{AssetRelationshipGraph}
    C --> D(Relationship Building <br> _find_relationships)
    D --> E(Graph Construction <br> Nodes and Edges)
    E --> F(3D Position Calculation <br> Deterministic seed=42)
    F --> G{Output Generation}
    G --> H[JSON for API]
    G --> I[Plotly Figure for Gradio]
```
Sources: [ARCHITECTURE.md:183-207](), [README.md:133-134]()

## Technology Stack

The project utilizes a modern Python and JavaScript/TypeScript stack. The choice of libraries is governed by a set of rules to ensure consistency.
Sources: [AI_RULES.md:5-24]()

### Backend & Core Logic

| Technology | Purpose |
| --- | --- |
| **Python 3.8+** | Foundational programming language. |
| **FastAPI** | High-performance REST API framework. |
| **Gradio** | UI framework for the original interactive demo. |
| **Pandas** | Data manipulation and analysis. |
| **NumPy** | Numerical operations and array computations. |
| **Plotly** | Generation of all interactive charts and 3D graphs. |
| **yfinance** | Fetching real-time and historical financial market data. |
| **dataclasses & enum** | Defining structured data models and enumerations. |

Sources: [AI_RULES.md:7-24](), [ARCHITECTURE.md:168-180]()

### Frontend

| Technology | Purpose |
| --- | --- |
| **Next.js 14** | React framework for the modern UI. |
| **React 18** | UI component library. |
| **TypeScript** | Type safety for JavaScript. |
| **Tailwind CSS** | Utility-first CSS framework for styling. |
| **Plotly.js** | Rendering 3D visualizations in the browser. |
| **Axios** | HTTP client for communicating with the FastAPI backend. |

Sources: [ARCHITECTURE.md:154-165](), [frontend/README.md:55-56]()

## Development and Testing

The project is equipped with a comprehensive development and testing workflow, enforced by pre-commit hooks and a CI/CD pipeline.
Sources: [CONTRIBUTING.md:65-81](), [SUMMARY.md:43-57]()

### Development Workflow

A standardized workflow is used for all contributions.

```mermaid
flowchart TD
    A(Create Branch <br> e.g., feature/your-feature) --> B(Make Changes <br> Code, Tests, Docs)
    B --> C(Run Local Checks <br> make check)
    C --> D(Commit Changes <br> Descriptive Messages)
    D --> E(Push and Create PR)
    E --> F{PR Review}
    F --> G(Merge to main)
    G --> H(Delete Branch)
```
Sources: [CONTRIBUTING.md:51-100]()

### Development Commands

A `Makefile` provides shortcuts for common development tasks.

| Command | Description |
| --- | --- |
| `make install-dev` | Install all production and development dependencies. |
| `make pre-commit` | Install pre-commit hooks for automated quality checks. |
| `make format` | Format code with `black` and `isort`. |
| `make lint` | Run linters (`flake8`, `pylint`). |
| `make type-check` | Run the `mypy` type checker. |
| `make test` | Run the `pytest` test suite with coverage. |
| `make check` | Run all checks (format, lint, type-check, test) at once. |

Sources: [SUMMARY.md:60-76](), [CONTRIBUTING.md:41-44, 72-81]()

### Testing

The project maintains a high standard of testing for both backend and frontend code.

- **Backend (Python)**: `pytest` is used for unit and integration testing. Tests are located in the `tests/` directory and are structured into `unit/` and `integration/` subdirectories.
- **Frontend (TypeScript)**: `Jest` and `React Testing Library` are used for component and utility testing. Tests are located in the `frontend/__tests__/` directory.

Sources: [README.md:140-151](), [CONTRIBUTING.md:124-161](), [frontend/README.md:27-38]()

## Conclusion

The Financial Asset Relationship Database is a well-architected system that provides powerful visualization and analysis capabilities for financial data. Its modular design supports multiple frontends and a clear separation of concerns between the UI, API, and core logic. The project is further strengthened by a robust development and testing process, ensuring code quality and maintainability.
Sources: [AUDIT_REPORT.md:21-41, 235-240]()

### Quick Start Guide

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [run-dev.sh](https://github.com/DashFin/financial-asset-relationship-db/blob/main/run-dev.sh)
- [run-dev.bat](https://github.com/DashFin/financial-asset-relationship-db/blob/main/run-dev.bat)
- [docker-compose.yml](https://github.com/DashFin/financial-asset-relationship-db/blob/main/docker-compose.yml)
- [QUICK_START.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/QUICK_START.md)
- [DOCKER.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/DOCKER.md)
- [frontend/README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/README.md)

</details>

# Quick Start Guide

This guide provides instructions to quickly set up and run the Financial Asset Relationship Database application. It covers three primary methods: the modern Next.js/FastAPI stack (recommended), the original Gradio interface, and a containerized Docker deployment. Each method is designed to get a developer running in under 5 minutes.

The project offers a comprehensive 3D visualization system for interconnected financial assets, including equities, bonds, commodities, and currencies. For more detailed deployment information, refer to the [Vercel deployment guide](#deploymentmd) or the [system architecture overview](#architecturemd).

Sources: [README.md:3-4](), [QUICK_START.md:3-4]()

## Prerequisites

Before you begin, ensure you have the following software installed on your system.

| Software | Minimum Version |
| :--- | :--- |
| Python | 3.10+ |
| Node.js | 18+ |

Sources: [README.md:7-9](), [QUICK_START.md:5-7]()

## Option 1: Next.js Frontend + FastAPI Backend (Recommended)

This is the modern approach, providing a rich web interface powered by a REST API. You can use automated scripts for a one-command setup or follow the manual steps for more control.

Sources: [README.md:28-30]()

### Automated Setup (Scripts)

The repository includes convenience scripts to start both the backend and frontend servers simultaneously.

This diagram illustrates the process initiated by the `run-dev` scripts.
```mermaid
flowchart TD
    A[Start Script] --> B{Check OS};
    B -->|Linux/macOS| C[run-dev.sh];
    B -->|Windows| D[run-dev.bat];
    C --> E[Start FastAPI Backend on Port 8000];
    D --> E;
    E --> F[Start Next.js Frontend on Port 3000];
    F --> G[Application Ready];
```
Sources: [run-dev.sh](), [run-dev.bat]()

To run the automated setup:

**Linux/macOS**
```bash
./run-dev.sh
```

**Windows**
```cmd
run-dev.bat
```

These scripts will perform the necessary setup, including installing dependencies and launching the servers.

Sources: [README.md:33-39](), [QUICK_START.md:9-19]()

### Manual Setup

If you prefer to run the services separately, follow these steps.

#### 1. Start the FastAPI Backend

```bash
# Activate virtual environment (e.g., source .venv/bin/activate)
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --port 8000
```
Sources: [README.md:44-46](), [QUICK_START.md:25-33]()

#### 2. Start the Next.js Frontend

Open a new terminal for this step.

```bash
cd frontend
npm install
npm run dev
```
Sources: [README.md:49-51](), [QUICK_START.md:36-44]()

### Accessing the Application

Once running, the different parts of the application are accessible at the following URLs.

| Service | URL |
| :--- | :--- |
| Next.js Frontend | `http://localhost:3000` |
| FastAPI Backend | `http://localhost:8000` |
| API Documentation (Swagger) | `http://localhost:8000/docs` |

Sources: [README.md:54-56](), [QUICK_START.md:20-22]()

## Option 2: Gradio UI (Original)

This method runs the original Python-based Gradio interface.

1.  **Clone the repository and set up a Python virtual environment.**
    ```bash
    git clone <repository-url>
    cd financial-asset-relationship-db
    python -m venv .venv
    ```
    Sources: [README.md:12-15]()

2.  **Activate the environment.**
    -   macOS/Linux: `source .venv/bin/activate`
    -   Windows: `.venv\Scripts\activate.bat`
    Sources: [README.md:18-26]()

3.  **Install dependencies.**
    ```bash
    pip install -r requirements.txt
    ```
    Sources: [README.md:29-31]()

4.  **Run the application.**
    ```bash
    python app.py
    ```
    The application will be available at `http://localhost:7860`.
    Sources: [README.md:34-36]()

## Option 3: Docker Installation

For a containerized setup that encapsulates all dependencies, use Docker.

### Docker Compose (Recommended)

The `docker-compose.yml` file defines the application service.

This diagram shows the services defined in the Docker Compose configuration.
```mermaid
graph TD
    subgraph Docker Environment
        A(app_service)
    end

    A -->|Exposes Port 7860| B(Host Machine);
    B --> C(User);

    style A fill:#f9f,stroke:#333,stroke-width:2px
```
Sources: [docker-compose.yml]()

To build and run the application using Docker Compose:
```bash
docker-compose up --build
```
This command builds the image for the `app` service and starts the container, making the Gradio UI available on `http://localhost:7860`.

The `docker-compose.yml` defines a single service named `app`.
```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports:
      - "7860:7860"
    volumes:
      - ./src:/app/src
```
Sources: [README.md:61-63](), [DOCKER.md:5-9](), [docker-compose.yml:2-8]()

### Direct Docker Commands

Alternatively, you can build and run the Docker image directly without Docker Compose.

1.  **Build the image:**
    ```bash
    docker build -t financial-asset-db .
    ```
2.  **Run the container:**
    ```bash
    docker run -p 7860:7860 financial-asset-db
    ```
Sources: [README.md:66-69](), [DOCKER.md:12-15]()

## Summary

This guide has outlined three distinct methods for running the application. For modern web development, the **Next.js + FastAPI** stack is recommended and can be started with a single script. The **Gradio UI** offers a simpler, Python-only alternative. Finally, **Docker** provides a consistent, isolated environment ideal for both development and deployment.

Sources: [README.md](), [QUICK_START.md]()

### Project Goals and Vision

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [IMPROVEMENTS.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/IMPROVEMENTS.md)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)

</details>

# Project Goals and Vision

The Financial Asset Relationship Database project is envisioned as a comprehensive system for visualizing and analyzing the intricate relationships between financial assets. Its core purpose is to provide an interactive 3D network graph that models the connections across major asset classes, including equities, bonds, commodities, currencies, and regulatory events. This allows for cross-asset analysis and understanding the impact of corporate and regulatory activities on the financial ecosystem.

The project's vision extends to being a modern, scalable, and extensible platform. It supports dual user interfaces—a classic Gradio UI for rapid prototyping and a modern Next.js frontend with a FastAPI backend for a production-grade user experience. The architecture is designed to be modular, separating data models, business logic, and presentation layers to facilitate future enhancements and maintainability.

Sources: [README.md:3-4](), [ARCHITECTURE.md:3-19](), [INTEGRATION_SUMMARY.md:3-6]()

## Core Mission: Visualizing Financial Networks

The primary goal is to transform complex, abstract financial data into an intuitive, interactive 3D visualization. This helps users discover and analyze relationships that are not immediately obvious from tabular data.

### Key Features

| Feature | Description | Source |
| :--- | :--- | :--- |
| **3D Network Visualization** | An interactive 3D graph of asset relationships, rendered using Plotly. | [README.md:52](), [frontend/README.md:43]() |
| **Cross-Asset Analysis** | Automatically discovers and models relationships between different asset classes. | [README.md:53]() |
| **Regulatory Integration** | Models the impact of corporate events and SEC filings on the asset network. | [README.md:54]() |
| **Real-time Metrics** | Provides a dashboard with network statistics and relationship strength analysis. | [README.md:55](), [frontend/README.md:44]() |

Sources: [README.md:51-55](), [frontend/README.md:42-45]()

### Data Model Vision

The project's data model is centered around three core entities: Assets, Relationships, and Regulatory Events. The vision is to create a rich, interconnected graph where these entities influence each other.

The diagram below illustrates the conceptual data model.

```mermaid
erDiagram
    ASSET {
        string id PK
        string symbol
        string name
        AssetClass asset_class
        string sector
        float price
    }

    RELATIONSHIP {
        string source_id FK
        string target_id FK
        string type
        float strength
        bool is_bidirectional
    }

    REGULATORY_EVENT {
        string id PK
        string name
        RegulatoryActivity activity_type
        date event_date
        float impact_score
    }

    ASSET ||--o{ RELATIONSHIP : "has"
    REGULATORY_EVENT ||--|{ ASSET : "impacts"
```
*Sources: [README.md:73-80](), [src/models/financial_models.py (inferred from project structure)]()*

## Supported Asset Ecosystem

The project aims to cover all major financial asset classes to provide a holistic view of the market.

| Asset Class | Key Attributes | Source |
| :--- | :--- | :--- |
| **Equities** | P/E Ratios, Dividend Yields, EPS, Sector | [README.md:58]() |
| **Fixed Income (Bonds)** | Yield, Duration, Credit Ratings | [README.md:59]() |
| **Commodities** | Futures and Spot Prices, Contract Specifications | [README.md:60]() |
| **Currencies** | FX Pairs, Exchange Rates, Monetary Policy Links | [README.md:61]() |
| **Regulatory Events** | Earnings, SEC Filings, M&A Activities, Impact Score | [README.md:62]() |

*Sources: [README.md:57-62](), [AI_RULES.md:16]()*

### Relationship Discovery

A core goal is the automatic discovery of relationships between assets. This logic is encapsulated in the `AssetRelationshipGraph` and is designed to be extensible.

The following diagram shows the process of building relationships.

```mermaid
flowchart TD
    A[Start: Ingest Assets] --> B{Iterate All Asset Pairs};
    B --> C{Find Relationship Type};
    C --> D{Is Relationship Found?};
    D -- Yes --> E[Create Relationship Edge];
    E --> F[Calculate Strength (0.0-1.0)];
    F --> G[Add to Graph];
    G --> B;
    D -- No --> B;
    B -- Done --> H[Graph Complete];
```
*Sources: [ARCHITECTURE.md:104-122](), [README.md:95]()*

The system identifies several types of relationships:

| Relationship Type | Description | Source |
| :--- | :--- | :--- |
| **Sector Affinity** | Assets belonging to the same industry sector. | [README.md:65]() |
| **Corporate Links** | Bonds issued by a publicly traded company (equity). | [README.md:66]() |
| **Commodity Exposure** | Equity companies whose business is tied to commodity prices. | [README.md:67]() |
| **Currency Risk** | FX exposure for assets not denominated in USD. | [README.md:68]() |
| **Income Comparison** | Comparing stock dividends against bond yields. | [README.md:69]() |
| **Event Impact** | A single regulatory event affecting multiple assets. | [README.md:70]() |

*Sources: [README.md:64-70]()*

## Technical Vision and Architecture

The project's technical vision emphasizes modernity, scalability, and developer experience. This is achieved through a dual-frontend architecture and a clear separation of concerns.

This diagram shows the high-level system architecture.

```mermaid
graph TD
    subgraph User_Interfaces
        UI_Next[Next.js UI on Port 3000]
        UI_Gradio[Gradio UI on Port 7860]
    end

    subgraph API_Layer
        API[FastAPI Backend on Port 8000]
    end

    subgraph Core_Logic
        GraphEngine[AssetRelationshipGraph]
        Viz[Visualization Logic]
        DataModels[Financial Data Models]
    end

    subgraph Data_Sources
        RealData[Real-time Data Fetcher]
        SampleData[Static Sample Data]
    end

    UI_Next -- REST API --> API;
    API -- Function Calls --> GraphEngine;
    UI_Gradio -- Direct Function Calls --> GraphEngine;
    GraphEngine --> Viz;
    GraphEngine --> DataModels;
    GraphEngine --> RealData;
    GraphEngine --> SampleData;
```
*Sources: [ARCHITECTURE.md:3-82](), [INTEGRATION_SUMMARY.md:64-90]()*

### API-First Approach

The introduction of a FastAPI backend signifies a move towards an API-first design. This decouples the frontend from the backend logic, allowing for more flexible and scalable development.

The sequence diagram below shows a typical data flow for the Next.js frontend.

```mermaid
sequenceDiagram
    participant User as "User Browser"
    participant NextApp as "Next.js Frontend"
    participant FastAPI as "FastAPI Backend"
    participant GraphEngine as "Core Graph Logic"

    User->>NextApp: Load page
    NextApp->>FastAPI: GET /api/visualization
    FastAPI->>GraphEngine: get_3d_visualization_data()
    GraphEngine-->>FastAPI: Return {nodes, edges}
    FastAPI-->>NextApp: JSON Response
    NextApp-->>User: Render 3D Graph with Plotly
```
*Sources: [ARCHITECTURE.md:85-102](), [INTEGRATION_SUMMARY.md:20-33]()*

## Development Philosophy and Quality

The project vision includes a strong emphasis on high-quality code, robust testing, and a streamlined development workflow. This is supported by a suite of modern development tools and clear contribution guidelines.

*Sources: [CONTRIBUTING.md](), [AUDIT_REPORT.md:10-14]()*

### Development Tooling

| Tool | Purpose | Source |
| :--- | :--- | :--- |
| `pytest` | Backend testing framework. | [README.md:102](), [CONTRIBUTING.md:129]() |
| `Jest` | Frontend testing framework. | [frontend/README.md:30]() |
| `black`, `isort` | Automatic code formatting for Python. | [CONTRIBUTING.md:103](), [AUDIT_REPORT.md:150]() |
| `flake8`, `pylint` | Python linting to enforce code style. | [CONTRIBUTING.md:106](), [AUDIT_REPORT.md:149]() |
| `mypy` | Static type checking for Python. | [CONTRIBUTING.md:109](), [AUDIT_REPORT.md:151]() |
| `pre-commit` | Runs automated quality checks before each commit. | [CONTRIBUTING.md:44-47](), [AUDIT_REPORT.md:183-191]() |
| `GitHub Actions` | Continuous Integration (CI) to run checks automatically. | [AUDIT_REPORT.md:158-166]() |

*Sources: [CONTRIBUTING.md](), [AUDIT_REPORT.md](), [README.md]()*

### Guiding Principles

- **Modularity**: Code is organized into small, focused files with a clear separation of concerns (`src/models`, `src/logic`, etc.).
- **Readability**: Emphasis on clean, well-commented code with meaningful names.
- **Testing**: A high standard for test coverage is expected, with a goal of over 80%. New features and bug fixes must include tests.
- **Consistency**: Adherence to defined coding styles (PEP 8, Black) and project conventions.
- **Documentation**: Public functions and classes require docstrings, and key architectural decisions are documented in Markdown files.

*Sources: [AI_RULES.md:43-53](), [CONTRIBUTING.md:80-127](), [AUDIT_REPORT.md:20-40]()*

## Future Vision and Extensibility

The project is designed to be a foundation for more advanced financial analysis tools. The architectural choices and documented improvement areas point to a clear vision for future growth.

### Potential Future Features

| Feature Area | Description | Source |
| :--- | :--- | :--- |
| **Data Persistence** | Storing asset and relationship data in a database like SQLite or PostgreSQL. | [IMPROVEMENTS.md:200-207]() |
| **Real-time Updates** | Using WebSockets to stream live data and automatically refresh visualizations. | [IMPROVEMENTS.md:268-273]() |
| **Advanced Analytics** | Integrating machine learning for relationship prediction, anomaly detection, and trend analysis. | [IMPROVEMENTS.md:262-266]() |
| **Service-Oriented Architecture** | Abstracting logic into a service layer with repositories for better testability and maintenance. | [IMPROVEMENTS.md:194-216]() |
| **Enhanced Monitoring** | Adding health check endpoints, Prometheus metrics, and structured logging for observability. | [IMPROVEMENTS.md:237-259]() |

*Sources: [IMPROVEMENTS.md](), [INTEGRATION_SUMMARY.md:181-188]()*

## Conclusion

The project's goal is to be more than just a visualization tool; it aims to be an extensible, high-quality, and modern platform for financial data analysis. The vision combines a powerful analytical engine with a user-friendly interface, supported by a robust and scalable technical architecture. By prioritizing clean code, comprehensive testing, and clear documentation, the project is well-positioned for future growth and community contribution.

*Sources: [AUDIT_REPORT.md:275-281](), [README.md:3-4]()*


## System Architecture

### Architecture Overview

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [docker-compose.yml](https://github.com/DashFin/financial-asset-relationship-db/blob/main/docker-compose.yml)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
</details>

# Architecture Overview

This document provides a comprehensive overview of the system architecture for the Financial Asset Relationship Database. The project is designed to visualize the complex interconnections between financial assets across various classes, including equities, bonds, commodities, and currencies. The architecture supports two distinct user interfaces—a modern Next.js web application and an original Gradio-based demo—both powered by a robust Python backend.

The system is structured into four primary layers: a User Interface Layer, an API Layer, a Core Business Logic Layer, and a Data Layer. This separation of concerns allows for modularity and scalability, enabling different frontend experiences to consume the same underlying relationship discovery engine. For more information on deployment and integration, see [DEPLOYMENT.md](#deployment-md) and [INTEGRATION_SUMMARY.md](#integration-summary-md).

Sources: [README.md:3-4](), [ARCHITECTURE.md:3-33](), [AUDIT_REPORT.md:15-17]()

## System Architecture

The system is composed of four distinct layers, facilitating a clean separation of concerns between data, logic, and presentation.

This diagram illustrates the high-level system architecture, showing the two UI options and their connection to the backend logic.

```mermaid
graph TD
    subgraph User_Interface_Layer
        Gradio_UI["Gradio UI (Port 7860)"]
        NextJS_UI["Next.js UI (Port 3000)"]
    end

    subgraph API_Layer
        FastAPI["FastAPI Backend (Port 8000)"]
    end

    subgraph Core_Business_Logic_Layer
        AssetGraph["AssetRelationshipGraph (src/logic/asset_graph.py)"]
        Visualizations["Visualization Layer (src/visualizations/)"]
    end

    subgraph Data_Layer
        Models["Financial Models (src/models/financial_models.py)"]
        DataSources["Data Sources (src/data/)"]
    end

    NextJS_UI -- "HTTP REST API" --> FastAPI
    Gradio_UI -- "Direct Function Calls" --> AssetGraph
    FastAPI -- "Function Calls" --> AssetGraph
    AssetGraph --> Visualizations
    AssetGraph --> Models
    AssetGraph --> DataSources
```
Sources: [ARCHITECTURE.md:5-48](), [README.md:104-118]()

### Key Components

| Component | Description | Source File |
| --- | --- | --- |
| `app.py` | The main application entry point for the Gradio web interface and its event handlers. | `README.md:105` |
| `api/main.py` | The FastAPI backend that serves the REST API for the Next.js frontend. | `ARCHITECTURE.md:20-29` |
| `src/logic/asset_graph.py` | Contains the core graph algorithms and the relationship discovery engine. | `README.md:106` |
| `src/models/financial_models.py` | Defines the domain model dataclasses (e.g., `Asset`, `Equity`) and enums. | `README.md:107` |
| `src/data/sample_data.py` | Responsible for creating the sample dataset used in the application. | `README.md:108` |
| `src/visualizations/` | Contains modules for generating Plotly-based charts and 3D graphs. | `README.md:109` |
| `src/reports/` | Includes logic for generating schema and business rules documentation. | `README.md:110` |

Sources: [README.md:104-118](), [CONTRIBUTING.md:197-203]()

## Component Interaction Flow

The system supports two primary interaction flows depending on the user interface being used.

### Next.js Frontend Flow

The Next.js frontend communicates with the backend via a REST API, providing a decoupled and modern web experience.

The following sequence diagram shows a typical user interaction to view the 3D graph from the Next.js UI.

```mermaid
sequenceDiagram
    participant User as "User"
    participant NextJS as "Next.js UI (Port 3000)"
    participant FastAPI as "FastAPI Backend (Port 8000)"
    participant CoreLogic as "Core Logic (AssetRelationshipGraph)"

    User->>NextJS: Clicks "View 3D Graph"
    NextJS->>FastAPI: GET /api/visualization
    activate FastAPI
    FastAPI->>CoreLogic: get_3d_visualization_data()
    activate CoreLogic
    CoreLogic-->>FastAPI: {nodes: [...], edges: [...]}
    deactivate CoreLogic
    FastAPI-->>NextJS: 200 OK (JSON Response)
    deactivate FastAPI
    NextJS->>User: Renders 3D Visualization
```
Sources: [ARCHITECTURE.md:52-71]()

### Gradio UI Flow

The Gradio UI, being a Python-native framework, interacts directly with the core logic functions without an intermediate API layer.

This sequence diagram illustrates how the Gradio UI refreshes the visualization through direct function calls.

```mermaid
sequenceDiagram
    participant User as "User"
    participant Gradio as "Gradio UI (Port 7860)"
    participant CoreLogic as "Core Logic (AssetRelationshipGraph)"

    User->>Gradio: Clicks "Refresh Visualization"
    Gradio->>CoreLogic: refresh_visualization_outputs()<br/>(Direct function call)
    activate CoreLogic
    CoreLogic-->>Gradio: Plotly Figure Object
    deactivate CoreLogic
    Gradio->>User: Updates Visualization in UI
```
Sources: [ARCHITECTURE.md:73-89]()

## Technology Stack

The project utilizes a combination of Python for the backend and core logic, and a choice between Python (Gradio) or a TypeScript/React (Next.js) stack for the frontend.

Sources: [AI_RULES.md:5-20](), [ARCHITECTURE.md:92-120]()

### Backend & Core Logic

| Technology | Role |
| --- | --- |
| **Python 3.8+** | Foundational programming language for all backend and logic. |
| **FastAPI** | High-performance REST API framework for the Next.js frontend. |
| **Uvicorn** | ASGI server to run the FastAPI application. |
| **Pydantic** | Data validation and settings management. |
| **NumPy** | High-performance numerical operations and graph algorithms. |
| **Pandas** | Data manipulation and analysis. |
| **yfinance** | Fetching real-time and historical financial market data. |
| **dataclasses & enum** | Defining structured data models and enumerations. |

Sources: [AI_RULES.md:7-20](), [ARCHITECTURE.md:109-120]()

### Frontend

| Technology | Role |
| --- | --- |
| **Next.js 14** | React framework for the modern web UI. |
| **React 18** | UI component library. |
| **TypeScript** | Type safety for the frontend codebase. |
| **Gradio** | Framework for the original Python-based interactive UI. |
| **Plotly / Plotly.js** | Exclusive library for all interactive charts and 3D visualizations. |
| **Axios** | HTTP client for the Next.js frontend to communicate with the API. |
| **Tailwind CSS** | Styling for the Next.js frontend. |

Sources: [ARCHITECTURE.md:94-107](), [AI_RULES.md:8](), [AI_RULES.md:13]()

## Data Layer

The data layer is responsible for defining the structure of financial assets and sourcing the data.

### Data Models

The core data models are defined using Python's `dataclasses` for clarity and type safety. The base `Asset` class is inherited by more specific asset types.

This class diagram shows the inheritance structure of the financial asset models.

```mermaid
classDiagram
    class Asset {
        +id: str
        +symbol: str
        +name: str
        +asset_class: AssetClass
        +price: float
        +currency: str
    }
    class Equity {
        +sector: str
        +pe_ratio: float
    }
    class Bond {
        +yield: float
        +duration: float
    }
    class Commodity {
        +contract_size: float
    }
    class Currency {
        +country: str
    }
    class RegulatoryEvent {
        +activity: RegulatoryActivity
        +impact_score: float
    }

    Asset <|-- Equity
    Asset <|-- Bond
    Asset <|-- Commodity
    Asset <|-- Currency
```
Sources: [AUDIT_REPORT.md:19-22](), [README.md:93-97]()

### Data Sources

Data is ingested from two primary sources:
1.  **Static Sample Data**: A predefined set of assets located in `src/data/sample_data.py` for demonstration and testing.
2.  **Yahoo Finance**: Real-time and historical market data is fetched using the `yfinance` library, as defined in `src/data/real_data_fetcher.py`.

Sources: [ARCHITECTURE.md:42-46](), [AI_RULES.md:14]()

## Deployment Architecture

The application is designed for both local development and cloud deployment on Vercel.

### Local Development & Docker

For local development, developers can run the FastAPI backend and Next.js frontend as separate processes. Alternatively, Docker provides a containerized environment. The `docker-compose.yml` file defines the service for running the application.

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports:
      - "7860:7860"
    volumes:
      - .:/app
    environment:
      - GRADIO_SERVER_NAME=0.0.0.0
```
This configuration builds a Docker image from the local Dockerfile and maps port 7860 for the Gradio application.

Sources: [README.md:65-76](), [docker-compose.yml:1-9]()

### Vercel Deployment

The Next.js application is optimized for deployment on Vercel. The frontend is served from Vercel's Edge Network, while the Python backend (FastAPI) is deployed as a Vercel Serverless Function. This provides auto-scaling capabilities and a seamless deployment experience integrated with Git.

This diagram shows the Vercel deployment model.
```mermaid
graph TD
    User["Internet Users"] -->|HTTPS| Vercel
    subgraph Vercel Platform
        NextJS["Next.js Frontend (Edge Network)"]
        FastAPI["Python Backend (Serverless Function)"]
        NextJS -- "Internal Network" --> FastAPI
    end
```
Sources: [ARCHITECTURE.md:158-176]()

## Conclusion

The architecture of the Financial Asset Relationship Database is designed to be modular, scalable, and flexible. By separating the core relationship engine from the presentation layer, the system can support multiple user experiences (Gradio and Next.js) and is well-suited for future expansion. The use of a decoupled API layer for the Next.js application follows modern web development best practices, while the direct-call mechanism for the Gradio app provides a simpler, Python-native alternative. The clear project structure and defined technology stack create a solid foundation for collaborative development and future feature enhancements.

Sources: [AUDIT_REPORT.md:410-413](), [ARCHITECTURE.md]()

### Backend Architecture

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [api/main.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/api/main.py)
- [src/logic/asset_graph.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/logic/asset_graph.py)
- [src/models/financial_models.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/models/financial_models.py)
- [app.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/app.py)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [src/data/real_data_fetcher.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/data/real_data_fetcher.py)

</details>

# Backend Architecture

The backend architecture of the Financial Asset Relationship Database is designed to support two distinct user interfaces: a modern Next.js web application and the original Gradio-based interactive demo. This is achieved through a dual-pathway system where a FastAPI server provides a RESTful API for the Next.js frontend, while the Gradio app interacts directly with the core business logic.

At the heart of the system is the `AssetRelationshipGraph`, a Python class that encapsulates all logic for managing financial assets, discovering their relationships, calculating network metrics, and preparing data for 3D visualization. The data layer is defined by a set of `dataclasses` representing various financial instruments and is populated using either sample data or real-time information fetched via the `yfinance` library.

Sources: [ARCHITECTURE.md](), [README.md:80-88](), [api/main.py](), [app.py]()

## System Components

The backend is composed of three primary layers: the API Layer, the Core Business Logic Layer, and the Data Layer. This modular design allows different frontends to consume the same underlying functionality.

This diagram illustrates the high-level system architecture, showing the two frontend applications and how they interface with the backend components.

```mermaid
graph TD
    subgraph User_Interface_Layer
        A[Next.js UI on Port 3000]
        B[Gradio UI on Port 7860]
    end

    subgraph API_Layer
        C[FastAPI Backend on Port 8000]
    end

    subgraph Core_Business_Logic
        D[AssetRelationshipGraph]
        E[Visualization Logic]
    end

    subgraph Data_Layer
        F[Financial Models]
        G[Data Fetchers]
    end

    A -- "HTTP REST API" --> C
    C -- "Function Calls" --> D
    B -- "Direct Function Calls" --> D
    D -- "Uses" --> F
    D -- "Uses" --> G
    D -- "Uses" --> E

```
Sources: [ARCHITECTURE.md](), [README.md:19-33]()

## API Layer (FastAPI)

The FastAPI application, defined in `api/main.py`, serves as the primary interface for the Next.js frontend. It exposes a set of RESTful endpoints to query the financial asset graph. A singleton pattern is used to initialize and reuse a single `AssetRelationshipGraph` instance, which is populated with real data on the first request.

Sources: [api/main.py:34-48](), [INTEGRATION_SUMMARY.md]()

### Key Endpoints

The API provides endpoints for retrieving assets, relationships, metrics, and visualization data.

| Method | Endpoint                      | Description                                                                 | Core Logic Called                               |
| :----- | :---------------------------- | :-------------------------------------------------------------------------- | :---------------------------------------------- |
| `GET`  | `/api/health`                 | Health check for the service.                                               | N/A                                             |
| `GET`  | `/api/assets`                 | Retrieves a list of all assets, with optional filtering by class and sector.  | `graph.assets`                                  |
| `GET`  | `/api/assets/{asset_id}`      | Fetches detailed information for a single asset.                            | `graph.get_asset_by_id()`                       |
| `GET`  | `/api/relationships`          | Returns all relationships in the graph.                                     | `graph.relationships`                           |
| `GET`  | `/api/metrics`                | Calculates and returns key network metrics.                                 | `graph.calculate_metrics()`                     |
| `GET`  | `/api/visualization`          | Generates node and edge data for 3D visualization.                          | `graph.get_3d_visualization_data()`             |
| `GET`  | `/api/asset-classes`          | Lists all available asset classes.                                          | `graph.get_all_asset_classes()`                 |
| `GET`  | `/api/sectors`                | Lists all unique sectors present in the data.                               | `graph.get_all_sectors()`                       |

Sources: [api/main.py:51-168]()

### Request Flow (Next.js)

This sequence diagram shows a typical request from the Next.js frontend to the FastAPI backend to retrieve visualization data.

```mermaid
sequenceDiagram
    participant User as "User (Browser)"
    participant NextApp as "Next.js Frontend"
    participant FastAPI as "FastAPI Backend"
    participant Graph as "AssetRelationshipGraph"

    User->>NextApp: Load 3D Visualization Page
    NextApp->>FastAPI: GET /api/visualization
    activate FastAPI
    Note over FastAPI: get_graph() singleton is called
    FastAPI->>Graph: get_3d_visualization_data()
    activate Graph
    Graph-->>FastAPI: {nodes: [...], edges: [...]}
    deactivate Graph
    FastAPI-->>NextApp: 200 OK with JSON data
    deactivate FastAPI
    NextApp->>User: Render Plotly.js graph
```
Sources: [api/main.py:133-140](), [ARCHITECTURE.md]()

## Core Business Logic Layer

The core logic is centralized in the `AssetRelationshipGraph` class. This class is responsible for the in-memory representation and manipulation of the financial asset network.

Sources: [src/logic/asset_graph.py]()

### `AssetRelationshipGraph` Class

This class manages the lifecycle of assets and their relationships.

```mermaid
classDiagram
    class AssetRelationshipGraph {
        +List~Asset~ assets
        +List~Relationship~ relationships
        +add_asset(asset: Asset)
        +add_relationship(source_id, target_id, type, strength)
        +build_relationships()
        +calculate_metrics() : dict
        +get_3d_visualization_data() : dict
        +get_asset_by_id(asset_id) : Asset
        -_find_relationships(asset1, asset2)
    }
```
Sources: [src/logic/asset_graph.py:21-255]()

### Relationship Discovery

The `build_relationships()` method orchestrates the discovery of connections between assets. It iterates through all unique pairs of assets and calls `_find_relationships()` to identify potential links based on predefined rules.

This flowchart shows the logic for building relationships.

```mermaid
flowchart TD
    A[Start build_relationships] --> B{Iterate through all unique pairs of assets (asset1, asset2)}
    B --> C[Call _find_relationships(asset1, asset2)]
    C --> D{Relationship found?}
    D -- Yes --> E[Create Relationship object]
    E --> F[Add to graph.relationships]
    F --> B
    D -- No --> B
    B -- Loop finished --> G[End]
```
Sources: [src/logic/asset_graph.py:100-120]()

The `_find_relationships` method contains the specific business rules, such as identifying assets in the same sector or linking a corporate bond to its parent equity.

Sources: [src/logic/asset_graph.py:122-171]()

## Data Layer

The data layer consists of data models that define the structure of financial assets and the logic for fetching data from external or internal sources.

### Data Models

The project uses Python's `dataclasses` to create strongly-typed and structured data models for all financial assets. A base `Asset` class defines common attributes, and specific classes like `Equity`, `Bond`, and `Commodity` inherit from it.

Sources: [src/models/financial_models.py]()

This diagram shows the inheritance hierarchy of the financial asset models.

```mermaid
classDiagram
    direction LR
    class Asset {
        <<dataclass>>
        +id: str
        +symbol: str
        +name: str
        +asset_class: AssetClass
        +price: float
        +currency: str
    }
    class Equity {
        <<dataclass>>
        +sector: str
        +market_cap: float
    }
    class Bond {
        <<dataclass>>
        +issuer: str
        +credit_rating: str
    }
    class Commodity {
        <<dataclass>>
        +unit: str
    }
    class Currency {
        <<dataclass>>
        +country: str
    }

    Asset <|-- Equity
    Asset <|-- Bond
    Asset <|-- Commodity
    Asset <|-- Currency
```
Sources: [src/models/financial_models.py:25-108]()

### Data Fetching

Data is primarily sourced from `yfinance` for real-time and historical market data, as specified in the project's rules. The function `populate_graph_with_real_data` in `src/data/real_data_fetcher.py` is responsible for fetching data for a predefined list of tickers and populating the graph.

Sources: [src/data/real_data_fetcher.py:15-115](), [AI_RULES.md]()

## Gradio Integration

The original `app.py` provides a Gradio-based user interface. Unlike the Next.js application, it does not use the FastAPI layer. Instead, its event handlers make direct synchronous calls to the `AssetRelationshipGraph` instance and associated visualization functions.

This architecture demonstrates a simpler, direct-coupling approach suitable for rapid prototyping and interactive demos.

This diagram shows the direct interaction between the Gradio UI and the core logic.

```mermaid
graph TD
    GradioUI[Gradio UI Components] -- "User Interaction" --> EventHandler[Gradio Event Handler in app.py]
    EventHandler -- "Direct Function Call" --> CoreLogic[AssetRelationshipGraph]
    CoreLogic -- "Returns Data/Figure" --> EventHandler
    EventHandler -- "Updates UI" --> GradioUI
```
Sources: [app.py:117-158]()

## Summary

The backend architecture is flexible, supporting both a modern, decoupled frontend via a FastAPI REST API and a legacy, tightly-coupled Gradio UI through direct function calls. The system is centered around the `AssetRelationshipGraph` class, which serves as the single source of truth for business logic, ensuring consistency across both interfaces. The use of `dataclasses` for modeling and a dedicated data-fetching layer creates a clear separation of concerns, making the system modular and extensible.

Sources: [ARCHITECTURE.md](), [README.md](), [api/main.py](), [app.py]()

### Frontend Architecture

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [frontend/app/page.tsx](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/app/page.tsx)
- [frontend/app/lib/api.ts](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/app/lib/api.ts)
- [frontend/next.config.js](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/next.config.js)
- [frontend/README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/README.md)
- [frontend/package.json](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/package.json)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
</details>

# Frontend Architecture

The frontend for the Financial Asset Relationship Database is a modern web application built with Next.js and React. Its primary purpose is to provide an interactive user interface for visualizing and exploring complex financial asset relationships. The application fetches data from a separate FastAPI backend and presents it through three main features: an interactive 3D network graph, a dashboard of key metrics, and a filterable table of assets.

The architecture emphasizes a clear separation of concerns, with dedicated components for each feature, a centralized API client for backend communication, and type safety enforced by TypeScript. This design makes the application responsive, scalable, and maintainable. For more information on the overall system, see the [System Architecture](#).

Sources: [frontend/README.md](), [INTEGRATION_SUMMARY.md](), [ARCHITECTURE.md]()

## Technology Stack

The frontend leverages a modern technology stack centered around the React ecosystem. The core technologies and their roles are detailed below.

| Technology | Version | Role |
| :--- | :--- | :--- |
| **Next.js** | `14.2.35` | The React framework for server-side rendering, routing, and building the application. |
| **React** | `^18.2.0` | The UI library for building components. |
| **TypeScript** | `^5.3.0` | Provides static typing for the entire codebase, ensuring type safety. |
| **Tailwind CSS** | `^3.3.0` | A utility-first CSS framework for styling the application. |
| **Plotly.js** | `^2.27.0` | The core library for creating the interactive 3D network visualization. |
| **react-plotly.js** | `^2.6.0` | A React wrapper for Plotly.js, integrating it into the component model. |
| **Recharts** | `^2.10.0` | A composable charting library used for the metrics dashboard. |
| **Axios** | `^1.13.2` | A promise-based HTTP client for communicating with the backend REST API. |
| **Jest** | `^29.7.0` | The testing framework used for unit and component tests. |
| **React Testing Library** | `^14.1.2` | Provides utilities for testing React components in a user-centric way. |

Sources: [frontend/package.json](), [frontend/README.md]()

## Project Structure

The frontend project is organized into a standard Next.js App Router structure. This layout separates concerns, making the codebase easy to navigate and maintain.

```
frontend/
├── app/
│   ├── components/      # React components
│   │   ├── AssetList.tsx
│   │   ├── MetricsDashboard.tsx
│   │   └── NetworkVisualization.tsx
│   ├── lib/            # Utility libraries
│   │   ├── api.ts      # API client
│   │   └── index.ts    # Barrel exports
│   ├── types/          # TypeScript type definitions
│   │   └── api.ts
│   ├── globals.css     # Global styles
│   ├── layout.tsx      # Root layout
│   └── page.tsx        # Main page
├── public/             # Static assets
├── next.config.js      # Next.js configuration
├── package.json        # Dependencies and scripts
├── tsconfig.json       # TypeScript configuration
└── tailwind.config.js  # Tailwind CSS configuration
```
*Source: [frontend/README.md]()*

- **`app/`**: The core of the application, following the Next.js App Router convention.
  - **`components/`**: Contains reusable React components that form the building blocks of the UI.
  - **`lib/`**: Houses utility functions, with `api.ts` being the most critical for backend communication.
  - **`types/`**: Defines TypeScript interfaces for data structures, particularly for API responses.
  - **`page.tsx`**: The main entry point and page component, which orchestrates the layout and data fetching for the different tabs.
- **`public/`**: Stores static assets like images and fonts.
- **`next.config.js`**: Configuration file for the Next.js framework.
- **`package.json`**: Defines project metadata, dependencies, and scripts.

Sources: [frontend/README.md](), [INTEGRATION_SUMMARY.md]()

## Core Components

The UI is built from a set of modular React components, each responsible for a specific feature. The main page (`page.tsx`) uses a tabbed interface to switch between these components.

- **`NetworkVisualization.tsx`**: Renders the interactive 3D network graph using `react-plotly.js`. It takes node and edge data as props and configures the 3D scene, camera, and layout.
- **`MetricsDashboard.tsx`**: Displays key network statistics and analytics, such as total assets, relationships, and network density. It uses `Recharts` to render charts like the asset class distribution.
- **`AssetList.tsx`**: Presents a filterable and searchable table of all financial assets. It allows users to filter assets by class and sector.

These components are managed by the main `HomePage` component in `app/page.tsx`, which handles data fetching and passes the required data down as props.

Sources: [frontend/app/page.tsx](), [INTEGRATION_SUMMARY.md](), [frontend/README.md]()

## Data Flow and API Communication

The frontend is decoupled from the backend and communicates exclusively through a REST API. All API logic is encapsulated within the API client module.

### API Client (`lib/api.ts`)

This module uses `axios` to create a pre-configured client for making HTTP requests to the backend. The base URL is determined by the `NEXT_PUBLIC_API_URL` environment variable.

The following diagram illustrates the data fetching sequence when the application loads.

```mermaid
sequenceDiagram
    participant User
    participant Page as "HomePage (page.tsx)"
    participant APIClient as "API Client (api.ts)"
    participant Backend as "FastAPI Backend"

    User->>Page: Loads application
    activate Page
    Page->>APIClient: Calls getVisualizationData(), getMetrics(), getAssets()
    activate APIClient
    Note over Page,Backend: Parallel data fetching on mount

    APIClient->>Backend: GET /api/visualization
    APIClient->>Backend: GET /api/metrics
    APIClient->>Backend: GET /api/assets

    Backend-->>APIClient: { nodes: [...], edges: [...] }
    Backend-->>APIClient: { total_assets: ..., ... }
    Backend-->>APIClient: [ { id: ..., symbol: ... }, ... ]

    deactivate Backend
    APIClient-->>Page: Returns fetched data
    deactivate APIClient

    Page->>Page: Sets data in state (e.g., setVizData)
    Page-->>User: Renders UI with data
    deactivate Page
```
This diagram shows the initial parallel data fetching when the main page component mounts.
*Sources: [frontend/app/page.tsx](), [frontend/app/lib/api.ts](), [ARCHITECTURE.md]()*

### Key API Functions

The `api.ts` module exposes several functions to interact with the backend endpoints.

| Function Name | HTTP Method | Endpoint | Description |
| :--- | :--- | :--- | :--- |
| `healthCheck` | `GET` | `/api/health` | Checks the health of the backend API. |
| `getAssets` | `GET` | `/api/assets` | Fetches a list of all assets, with optional filtering by class or sector. |
| `getAssetDetail` | `GET` | `/api/assets/{id}` | Retrieves details for a single asset. |
| `getAllRelationships` | `GET` | `/api/relationships` | Fetches all relationships in the graph. |
| `getMetrics` | `GET` | `/api/metrics` | Retrieves network-wide metrics. |
| `getVisualizationData` | `GET` | `/api/visualization` | Fetches the node and edge data required for the 3D graph. |
| `getAssetClasses` | `GET` | `/api/asset-classes` | Gets a list of all available asset classes. |
| `getSectors` | `GET` | `/api/sectors` | Gets a list of all available industry sectors. |

Sources: [frontend/app/lib/api.ts](), [INTEGRATION_SUMMARY.md]()

## State Management

State management within the frontend is handled primarily by React hooks (`useState`, `useEffect`) inside the `HomePage` component (`app/page.tsx`). There is no external state management library like Redux or Zustand.

The main page component manages several state variables:
- Data for each component (`vizData`, `metrics`, `assets`).
- Loading status (`loading`).
- Error status (`error`).
- The currently active tab.

The following flowchart illustrates the state transitions during the initial data load.

```mermaid
flowchart TD
    A[Component Mount] --> B{Set loading = true};
    B --> C[Fetch Data from API];
    C --> D{API Call Successful?};
    D -- Yes --> E[Set data in state];
    E --> F[Set loading = false];
    D -- No --> G[Set error message];
    G --> F;
```
This diagram shows the simple loading, success, and error state flow managed within the main page component.
*Source: [frontend/app/page.tsx]()*

## Configuration and Scripts

Project configuration and build scripts are managed through standard Next.js and Node.js files.

### Environment Variables
The frontend requires a single environment variable to be set in a `.env.local` file to connect to the backend API.
- `NEXT_PUBLIC_API_URL`: The base URL for the FastAPI backend (e.g., `http://localhost:8000`).

Sources: [frontend/README.md](), [QUICK_START.md]()

### `package.json` Scripts
The `package.json` file defines scripts for development, building, and testing.

| Script | Command | Description |
| :--- | :--- | :--- |
| `dev` | `next dev` | Starts the Next.js development server. |
| `build` | `next build` | Creates a production-optimized build of the application. |
| `start` | `next start` | Starts the production server after a build. |
| `lint` | `next lint` | Runs ESLint to find and fix problems in the code. |
| `test` | `jest --silent` | Runs the Jest test suite in silent mode. |
| `test:coverage` | `jest --coverage --silent` | Runs tests and generates a code coverage report. |

Source: [frontend/package.json:5-12]()

## Testing

The project is configured for testing using Jest and React Testing Library. The `package.json` includes scripts to run tests, generate coverage reports, and run in watch mode. The testing setup is configured in `jest.config.js` and `jest.setup.js` (not included in context, but implied by `package.json` and `TESTING_GUIDE.md`). Tests cover components, API utilities, and user interactions.

Sources: [frontend/package.json](), [TESTING_GUIDE.md](), [README.md]()

### Financial Data Models

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [src/models/financial_models.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/models/financial_models.py)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [IMPROVEMENTS.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/IMPROVEMENTS.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)

</details>

# Financial Data Models

The financial data models are the structural foundation of the Financial Asset Relationship Database. They define the core entities, their attributes, and their relationships, ensuring data integrity, type safety, and a clear, extensible domain model. These models are implemented as Python `dataclasses`, providing a structured and maintainable way to represent complex financial instruments and events.

Sources: [AI_RULES.md](), [AUDIT_REPORT.md](), [src/models/financial_models.py]()

The models are located in the `src/models/` directory and are a key component of the Data Layer, feeding into the Core Business Logic Layer where relationships are processed and visualizations are generated.

Sources: [ARCHITECTURE.md](), [CONTRIBUTING.md]()

## Core Concepts

### Dataclasses and Enums
The project exclusively uses Python's built-in `dataclasses` and `enum` modules for data modeling. This approach ensures type safety, clarity, and maintainability without introducing heavy external dependencies for data definition.

- **`dataclasses`**: Used to define all structured data objects like `Asset`, `Equity`, and `Bond`.
- **`enum`**: Used for fixed sets of choices, such as `AssetClass` and `RegulatoryActivity`.

Sources: [AI_RULES.md](), [AUDIT_REPORT.md]()

### Inheritance Model
The system employs a clear inheritance hierarchy, with a base `Asset` class defining common properties. Specific asset types like `Equity`, `Bond`, `Commodity`, and `Currency` inherit from this base class and add their own unique attributes. This promotes code reuse and a consistent structure across all asset types.

Sources: [AUDIT_REPORT.md](), [src/models/financial_models.py]()

This diagram illustrates the inheritance structure of the financial asset models.

```mermaid
classDiagram
    direction LR
    class Asset {
        +str id
        +str symbol
        +str name
        +AssetClass asset_class
        +str currency
        +float price
        +str sector
        +dict additional_fields
    }
    class Equity {
        +float pe_ratio
        +float dividend_yield
        +float eps
    }
    class Bond {
        +float yield_to_maturity
        +float duration
        +str credit_rating
    }
    class Commodity {
        +str contract_size
        +str unit_of_measure
    }
    class Currency {
        +str country
    }

    Asset <|-- Equity
    Asset <|-- Bond
    Asset <|-- Commodity
    Asset <|-- Currency
```
Sources: [src/models/financial_models.py](), [AUDIT_REPORT.md]()

## Data Model Schema

### Enumerations
Enumerations are used to standardize categorical data within the models.

#### AssetClass
Defines the supported types of financial assets.

| Member      | Description                |
|-------------|----------------------------|
| `EQUITY`    | Represents stocks.         |
| `BOND`      | Represents fixed income.   |
| `COMMODITY` | Represents commodities.    |
| `CURRENCY`  | Represents foreign exchange. |
| `DERIVATIVE`| Represents derivatives.    |

Sources: [src/models/financial_models.py](), [README.md]()

#### RegulatoryActivity
Defines the types of regulatory or corporate events.

| Member        | Description                               |
|---------------|-------------------------------------------|
| `EARNINGS`    | Corporate earnings announcement.          |
| `SEC_FILING`  | Filing with the Securities and Exchange Commission. |
| `MERGER_ACQUISITION` | Merger or acquisition activity. |

Sources: [src/models/financial_models.py](), [README.md]()

### Core Data Models

#### Asset (Base Class)
The `Asset` class is the abstract base for all financial instruments in the system.

| Field               | Type                  | Description                                      |
|---------------------|-----------------------|--------------------------------------------------|
| `id`                | `str`                 | Unique identifier for the asset.                 |
| `symbol`            | `str`                 | Ticker symbol or unique code.                    |
| `name`              | `str`                 | Full name of the asset.                          |
| `asset_class`       | `AssetClass`          | The type of the asset (e.g., EQUITY, BOND).      |
| `currency`          | `str`                 | The currency of the asset's price (ISO 4217 code). |
| `price`             | `float`               | The current market price.                        |
| `sector`            | `str` (Optional)      | Industry sector the asset belongs to.            |
| `additional_fields` | `dict` (Optional)     | A dictionary for any extra, non-standard data.   |

Sources: [src/models/financial_models.py]()

#### Equity
Inherits from `Asset` and adds fields specific to stocks.

| Field            | Type    | Description                   |
|------------------|---------|-------------------------------|
| `pe_ratio`       | `float` | Price-to-Earnings ratio.      |
| `dividend_yield` | `float` | Annual dividend per share as a percentage of the share's price. |
| `eps`            | `float` | Earnings Per Share.           |

Sources: [src/models/financial_models.py](), [README.md]()

#### Bond
Inherits from `Asset` and adds fields specific to fixed-income securities.

| Field               | Type    | Description                               |
|---------------------|---------|-------------------------------------------|
| `yield_to_maturity` | `float` | The total return anticipated on a bond if held until it matures. |
| `duration`          | `float` | A measure of the bond's price sensitivity to interest rate changes. |
| `credit_rating`     | `str`   | A rating of the bond issuer's creditworthiness. |

Sources: [src/models/financial_models.py](), [README.md]()

#### Commodity
Inherits from `Asset` and adds fields for commodities.

| Field             | Type    | Description                               |
|-------------------|---------|-------------------------------------------|
| `contract_size`   | `str`   | The amount of the commodity in one contract. |
| `unit_of_measure` | `str`   | The unit for the contract size (e.g., barrels, bushels). |

Sources: [src/models/financial_models.py](), [README.md]()

#### Currency
Inherits from `Asset` and adds fields for currencies.

| Field     | Type  | Description                               |
|-----------|-------|-------------------------------------------|
| `country` | `str` | The primary country associated with the currency. |

Sources: [src/models/financial_models.py](), [README.md]()

#### RegulatoryEvent
Represents a corporate or regulatory event that can impact assets.

| Field          | Type                 | Description                                      |
|----------------|----------------------|--------------------------------------------------|
| `id`           | `str`                | Unique identifier for the event.                 |
| `event_type`   | `RegulatoryActivity` | The type of event (e.g., EARNINGS).              |
| `date`         | `str`                | The date of the event (ISO 8601 format).         |
| `description`  | `str`                | A description of the event.                      |
| `impact_score` | `float`              | A score from -1.0 to 1.0 indicating the event's impact. |
| `related_assets` | `list[str]`        | A list of asset IDs affected by this event.      |

Sources: [src/models/financial_models.py]()

#### AssetRelationship
Defines a connection between two assets.

| Field          | Type      | Description                                      |
|----------------|-----------|--------------------------------------------------|
| `source`       | `str`     | The ID of the source asset.                      |
| `target`       | `str`     | The ID of the target asset.                      |
| `type`         | `str`     | The nature of the relationship (e.g., `same_sector`). |
| `strength`     | `float`   | The strength of the relationship, normalized from 0.0 to 1.0. |
| `is_bidirectional` | `bool`| Whether the relationship is symmetric.           |

Sources: [src/models/financial_models.py]()

### Entity Relationship Diagram
This diagram shows the relationships between the main data entities. An `AssetRelationship` connects two `Asset` entities, and a `RegulatoryEvent` can be linked to multiple `Asset` entities.

```mermaid
erDiagram
    ASSET {
        string id PK
        string symbol
        string name
        AssetClass asset_class
    }

    ASSET_RELATIONSHIP {
        string source_id FK
        string target_id FK
        string type
        float strength
    }

    REGULATORY_EVENT {
        string id PK
        RegulatoryActivity event_type
        string date
        float impact_score
    }

    ASSET ||--o{ ASSET_RELATIONSHIP : "has source"
    ASSET ||--o{ ASSET_RELATIONSHIP : "has target"
    ASSET }o--o{ REGULATORY_EVENT : "is affected by"
```
Sources: [src/models/financial_models.py](), [README.md]()

## Data Validation
Data integrity is enforced through validation logic within the `__post_init__` method of the dataclasses. This ensures that all created objects adhere to predefined business rules.

Key validation rules include:
- Asset `price` must be non-negative.
- `currency` codes must be 3-letter ISO format strings.
- `RegulatoryEvent` `impact_score` must be within the range of -1.0 to 1.0.
- `RegulatoryEvent` `date` must be in ISO 8601 format.

Sources: [AUDIT_REPORT.md](), [IMPROVEMENTS.md](), [src/models/financial_models.py]()

## Conclusion
The financial data models provide a robust and well-structured schema for the application's core data. By leveraging Python's native `dataclasses` and a clear inheritance structure, the models are both easy to understand and simple to extend. The built-in validation ensures a high level of data quality, which is critical for the accuracy of the relationship analysis and visualizations that form the core of the project.


## Core Features

### Feature: 3D Network Visualization

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [src/visualizations/graph_visuals.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/visualizations/graph_visuals.py)
- [src/visualizations/graph_2d_visuals.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/visualizations/graph_2d_visuals.py)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
- [frontend/app/components/NetworkVisualization.tsx](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/app/components/NetworkVisualization.tsx)
- [frontend/__tests__/components/NetworkVisualization.test.tsx](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/__tests__/components/NetworkVisualization.test.tsx)
- [frontend/__tests__/test-utils.test.ts](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/__tests__/test-utils.test.ts)
- [api/main.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/api/main.py)
- [src/logic/asset_graph.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/logic/asset_graph.py)

</details>

# Feature: 3D Network Visualization

The 3D Network Visualization is the core feature of the Financial Asset Relationship Database, providing an interactive 3D graph to explore the interconnectedness of financial assets. It supports various asset classes, including Equities, Bonds, Commodities, and Currencies, and models the relationships between them. This visualization is available through both the original Gradio UI and the newer Next.js web application.

The system is designed to automatically discover relationships and display them in a deterministic 3D layout, ensuring a consistent and analyzable view of the asset network. The visualization is powered by Plotly on both the Python backend and the React frontend.

Sources: [README.md](), [ARCHITECTURE.md]()

## Architecture and Data Flow

The 3D visualization feature spans the full stack, from the backend data logic to the frontend rendering component. The modern implementation uses a Next.js frontend communicating with a FastAPI backend via a REST API.

The diagram below illustrates the data flow for the Next.js application to render the 3D graph.

```mermaid
sequenceDiagram
    participant User as "User Browser"
    participant NextJS as "Next.js Frontend (Port 3000)"
    participant FastAPI as "FastAPI Backend (Port 8000)"
    participant CoreLogic as "Python Core Logic"

    User->>NextJS: Loads main page
    NextJS->>FastAPI: GET /api/visualization
    Note right of NextJS: API call made from NetworkVisualization.tsx
    FastAPI->>CoreLogic: get_3d_visualization_data()
    Note right of FastAPI: Calls method on AssetRelationshipGraph instance
    CoreLogic-->>FastAPI: Returns {nodes: [...], edges: [...]}
    Note right of CoreLogic: Data includes 3D positions and colors
    FastAPI-->>NextJS: JSON Response with visualization data
    NextJS-->>User: Renders interactive 3D graph using Plotly.js
```
This sequence shows the clear separation of concerns: the frontend handles rendering, the backend provides a dedicated API endpoint, and the core logic is responsible for generating the visualization data structure.

Sources: [ARCHITECTURE.md](), [INTEGRATION_SUMMARY.md](), [frontend/app/components/NetworkVisualization.tsx](), [api/main.py]()

## Backend Implementation

The backend is responsible for creating the data structure that the frontend uses to render the graph. This logic is encapsulated within the `AssetRelationshipGraph` class and exposed via a FastAPI endpoint.

### Data Generation

The core method for generating visualization data is `AssetRelationshipGraph.get_3d_visualization_data()`. This method is called by the API endpoint and returns a dictionary containing nodes and edges.

A key feature of the backend is the use of a fixed random seed (`seed=42`) to ensure that the 3D layout of the assets is deterministic and consistent across page loads and application restarts. This is crucial for comparative analysis.

The overall process is as follows:

```mermaid
flowchart TD
    A[API Request: GET /api/visualization] --> B{Call get_3d_visualization_data};
    B --> C[Get Assets and Relationships];
    C --> D[Calculate 3D Positions (seed=42)];
    D --> E[Assign Colors by Asset Class];
    E --> F[Assign Node Sizes];
    F --> G[Format Node and Edge Data];
    G --> H[Return JSON: {nodes, edges}];
```
Sources: [README.md](), [src/logic/asset_graph.py](), [src/visualizations/graph_visuals.py]()

### API Endpoint: `/api/visualization`

The FastAPI backend exposes a dedicated endpoint to serve the 3D graph data.

- **Endpoint**: `GET /api/visualization`
- **File**: `api/main.py`
- **Description**: Retrieves the complete data structure required to render the 3D network graph. It calls the core logic and returns the data in a JSON format.

The response from this endpoint contains two main keys: `nodes` and `edges`.

#### Response Data Structure

| Key | Type | Description |
| --- | --- | --- |
| `nodes` | `Array<Node>` | An array of objects, where each object represents an asset in the graph. |
| `edges` | `Array<Edge>` | An array of objects, where each object represents a relationship between two assets. |

**Node Object Structure**
| Field | Type | Description |
| --- | --- | --- |
| `id` | `string` | Unique identifier for the asset (e.g., "ASSET_1"). |
| `name` | `string` | Full name of the asset (e.g., "Apple Inc."). |
| `symbol` | `string` | Ticker symbol or short identifier (e.g., "AAPL"). |
| `asset_class` | `string` | The class of the asset (e.g., "EQUITY"). |
| `x`, `y`, `z` | `number` | The 3D coordinates for the node's position in the graph. |
| `color` | `string` | Hex color code for the node, determined by its asset class. |
| `size` | `number` | The size of the node in the visualization. |

**Edge Object Structure**
| Field | Type | Description |
| --- | --- | --- |
| `source` | `string` | The `id` of the source asset. |
| `target` | `string` | The `id` of the target asset. |
| `relationship_type` | `string` | The type of relationship (e.g., "SAME_SECTOR"). |
| `strength` | `number` | The strength of the relationship, typically a value between 0 and 1. |

Sources: [api/main.py](), [frontend/__tests__/test-utils.test.ts](), [INTEGRATION_SUMMARY.md]()

## Frontend Implementation

The frontend uses a React component, `NetworkVisualization.tsx`, to render the 3D graph. This component fetches data from the `/api/visualization` endpoint and uses `react-plotly.js` to create the interactive visualization.

Sources: [frontend/app/components/NetworkVisualization.tsx](), [INTEGRATION_SUMMARY.md]()

### Component: `NetworkVisualization.tsx`

This component is responsible for:
1.  Receiving the `nodes` and `edges` data as props.
2.  Processing this data into a format compatible with Plotly.
3.  Configuring the layout and appearance of the 3D graph.
4.  Handling loading and empty states.

The component's logic involves mapping the `nodes` array to Plotly's `scatter3d` trace for the assets and mapping the `edges` array to another `scatter3d` trace for the relationship lines.

The component's rendering logic is validated by unit tests that check for correct processing of node/edge data and proper Plotly configuration.

```mermaid
graph TD
    subgraph NetworkVisualization.tsx
        A[Props: {data: {nodes, edges}}] --> B{Process Data};
        B --> C[Create Node Trace (scatter3d)];
        B --> D[Create Edge Trace (scatter3d)];
        C --> E[Plotly Chart];
        D --> E[Plotly Chart];
        E --> F[Render Interactive 3D Graph];
    end
```
Sources: [frontend/app/components/NetworkVisualization.tsx](), [frontend/__tests__/components/NetworkVisualization.test.tsx]()

### Visualization Libraries

The frontend relies on two key libraries for rendering:
- **`plotly.js`**: The core JavaScript charting library that provides the 3D graphing capabilities.
- **`react-plotly.js`**: A React wrapper for `plotly.js` that simplifies its integration into React components.

These dependencies are declared in `frontend/package.json`.

Sources: [frontend/README.md](), [frontend/__tests__/config/package-validation.test.ts]()

## Conclusion

The 3D Network Visualization feature is a well-architected, full-stack implementation that serves as the centerpiece of the application. It effectively separates backend data processing from frontend rendering, using a clean REST API for communication. The use of Plotly on both ends ensures powerful visualization capabilities, while the deterministic layout on the backend provides analytical consistency. The entire feature is designed to be interactive, informative, and extensible for future analytical needs.

Sources: [README.md](), [ARCHITECTURE.md]()

### Feature: Asset Relationship Engine

<details>
<summary>Relevant source files</summary>
The following files were used as context for generating this wiki page:

- [src/logic/asset_graph.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/logic/asset_graph.py)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)
</details>

# Feature: Asset Relationship Engine

The Asset Relationship Engine is the core business logic component of the Financial Asset Relationship Database. Its primary purpose is to automatically discover, quantify, and represent the complex relationships between various financial assets. The engine is encapsulated within the `AssetRelationshipGraph` class, which serves as the central brain for processing financial data models and generating outputs for visualization and analysis.

This engine powers both the original Gradio user interface and the modern Next.js frontend (via a FastAPI backend). It ingests asset data, builds a network graph of their interconnections, calculates key performance metrics, and prepares data structures for 3D visualization. The entire system is designed to be deterministic, ensuring consistent graph layouts and analysis results.

Sources: [src/logic/asset_graph.py](), [README.md:60-61](), [ARCHITECTURE.md:28-36]()

## Core Architecture

The Asset Relationship Engine sits at the heart of the application, acting as a bridge between the data layer and the presentation (UI) layers. It consumes financial data models and is, in turn, called by the API/UI layers to provide processed graph data and analytics.

The diagram below illustrates the engine's central position within the system architecture.

```mermaid
graph TD
    subgraph Data_Layer
        A[Financial Models <br> src/models/financial_models.py]
        B[Data Sources <br> src/data/]
    end

    subgraph Core_Business_Logic
        C[AssetRelationshipGraph <br> <b>(The Engine)</b> <br> src/logic/asset_graph.py]
    end

    subgraph API_Layer
        D[FastAPI Backend <br> api/main.py]
    end

    subgraph UI_Layer
        E[Next.js UI]
        F[Gradio UI <br> app.py]
    end

    A --> C
    B --> C
    C --> D
    C --> F
    D --> E
```
*This diagram shows the data flow from data sources and models into the Asset Relationship Engine, which then serves both the FastAPI backend and the Gradio UI.*

Sources: [ARCHITECTURE.md:5-75](), [README.md:58-65]()

## Data Models

The engine operates on a set of well-defined data structures defined in `src/models/financial_models.py`. The fundamental building block is the `Asset` dataclass, which is inherited by specific asset types.

Sources: [README.md:60](), [AI_RULES.md:15-17]()

### Asset Class Hierarchy

The engine processes different classes of assets, each with its own specific attributes. The main supported classes are `Equity`, `Bond`, `Commodity`, and `Currency`.

```mermaid
classDiagram
    direction LR
    class Asset {
        +id: str
        +symbol: str
        +name: str
        +asset_class: AssetClass
        +price: float
    }
    class Equity {
        +sector: str
        +pe_ratio: float
    }
    class Bond {
        +issuer: str
        +yield: float
    }
    class Commodity {
        +unit: str
    }
    class Currency {
        +country: str
    }

    Asset <|-- Equity
    Asset <|-- Bond
    Asset <|-- Commodity
    Asset <|-- Currency
```
*This diagram shows the inheritance structure of the financial data models.*

Sources: [README.md:40-45](), [AI_RULES.md:15-17](), [CONTRIBUTING.md:183]()

## Relationship Discovery

The core function of the engine is to automatically discover relationships between assets. This is handled by the `build_relationships()` method, which iterates through all unique pairs of assets and calls `_find_relationships()` to identify specific connections.

Sources: [README.md:82-83](), [src/logic/asset_graph.py]()

### Discovery Process

The following flowchart outlines the logic for building the relationship graph.

```mermaid
flowchart TD
    start[Start build_relationships()] --> A{Iterate all asset pairs (asset1, asset2)}
    A --> B[Call _find_relationships(asset1, asset2)]
    B --> C{Check for relationship types}
    C -- Same Sector --> D[Create 'same_sector' relationship]
    C -- Corporate Bond --> E[Create 'corporate_bond_to_equity' relationship]
    C -- Other types... --> F[...]
    D --> G[Add relationship to graph]
    E --> G
    F --> G
    G --> A
    A -- Loop finished --> stop[End]
```
*This flowchart shows the process of iterating through assets to find and add relationships to the graph.*

Sources: [src/logic/asset_graph.py](), [README.md:82-83]()

### Relationship Types

The engine can identify several types of relationships, each with a predefined strength score.

| Relationship Type | Condition | Default Strength | Source File |
|-------------------|-----------|------------------|-------------|
| `same_sector` | Two equities are in the same industry sector. | 0.7 | `README.md:48` |
| `corporate_bond_to_equity` | A bond is issued by the same company as an equity. | 0.9 | `README.md:49`, `IMPROVEMENTS.md:31` |
| `commodity_exposure` | An equity company is exposed to commodity prices. | Varies | `README.md:50` |
| `currency_risk` | An asset has exposure to foreign exchange risk. | 0.8 | `README.md:51`, `IMPROVEMENTS.md:30` |
| `income_comparison` | Comparing an equity's dividend yield to a bond's yield. | Varies | `README.md:52` |
| `event_impact` | A regulatory event affects multiple assets. | Varies | `README.md:53` |

Sources: [README.md:47-54](), [IMPROVEMENTS.md:28-32]()

## Analytics and Metrics

The engine provides analytical capabilities through the `calculate_metrics()` method. This function computes various network statistics that offer insights into the structure and density of the asset relationship graph.

### Calculated Metrics

| Metric | Description |
|---|---|
| `total_assets` | The total number of assets (nodes) in the graph. |
| `total_relationships` | The total number of connections (edges) in the graph. |
| `network_density` | A measure of how interconnected the assets are, on a scale from 0 to 1. |
| `avg_degree` | The average number of relationships per asset. |
| `max_degree` | The highest number of relationships held by a single asset. |
| `asset_classes` | A dictionary counting the number of assets in each class (e.g., Equity, Bond). |

Sources: [src/logic/asset_graph.py](), [TEST_SUMMARY.md:48](), [INTEGRATION_SUMMARY.md:22]()

## Visualization Data Generation

A key feature of the engine is its ability to generate data formatted for 3D visualization with Plotly. The `get_3d_visualization_data()` method produces a dictionary containing lists of nodes and edges with positional and styling information.

- **Deterministic Layout**: The 3D positions of the assets are calculated using a fixed random seed (`seed=42`) to ensure the visualization is consistent and reproducible across sessions.
- **Node Sizing and Coloring**: Nodes are colored based on their `AssetClass` and sized based on their importance or connectivity within the graph.
- **Edge Styling**: Edges can be styled based on relationship `strength`.

Sources: [README.md:70, 81](), [src/logic/asset_graph.py]()

## API Exposure

The engine's functionalities are exposed to the Next.js frontend via a REST API built with FastAPI. The API endpoints in `api/main.py` instantiate and interact with the `AssetRelationshipGraph` to serve data to the client.

### API Interaction Flow

This sequence diagram shows how a frontend request for visualization data is processed.

```mermaid
sequenceDiagram
    participant User as "Next.js UI"
    participant API as "FastAPI Backend"
    participant Engine as "AssetRelationshipGraph"

    User->>API: GET /api/visualization
    activate API
    API->>Engine: get_graph() (singleton)
    activate Engine
    Engine-->>API: Graph instance
    deactivate Engine
    API->>Engine: get_3d_visualization_data()
    activate Engine
    Engine-->>API: {nodes: [...], edges: [...]}
    deactivate Engine
    API-->>User: JSON Response
    deactivate API
```
*This diagram shows the sequence of calls from the UI to the API and finally to the Asset Relationship Engine to fetch visualization data.*

Sources: [ARCHITECTURE.md:80-97](), [INTEGRATION_SUMMARY.md:15-23]()

### Key API Endpoints

The following endpoints directly leverage the Asset Relationship Engine:

| Endpoint | Method | Description |
|---|---|---|
| `/api/assets` | GET | Lists all assets from the graph. |
| `/api/relationships` | GET | Returns all discovered relationships. |
| `/api/metrics` | GET | Calculates and returns network metrics. |
| `/api/visualization` | GET | Generates and returns data for the 3D graph. |

Sources: [INTEGRATION_SUMMARY.md:15-23](), [TESTING_GUIDE.md:43-51]()

## Summary

The Asset Relationship Engine is the foundational component that enables the project's core value proposition. By encapsulating the logic for asset modeling, relationship discovery, analytics, and visualization data preparation, it provides a powerful and reusable service for multiple frontends. Its deterministic nature and clear separation from the UI and data layers make it a robust and central piece of the system architecture.

Sources: [AUDIT_REPORT.md:20-27](), [README.md:58-61]()

### Feature: Supported Asset Classes

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [src/models/financial_models.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/models/financial_models.py)
- [src/data/sample_data.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/data/sample_data.py)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [CHANGELOG.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CHANGELOG.md)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [src/logic/asset_graph.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/logic/asset_graph.py)

</details>

# Feature: Supported Asset Classes

The Financial Asset Relationship Database is designed to model and visualize connections between a variety of financial instruments. The system supports five primary asset classes: Equities, Bonds, Commodities, Currencies, and Regulatory Events. This structured approach allows for cross-asset analysis and automatic discovery of relationships.

The core of this feature is a well-defined data model using Python's `dataclasses` and `enum` modules. A base `Asset` class provides common attributes, and specific subclasses extend it with fields relevant to each asset type. This object-oriented hierarchy is fundamental to the system's architecture, enabling consistent handling and analysis across different financial instruments.

*Sources: [README.md:31-37](), [AI_RULES.md:14-16](), [ARCHITECTURE.md:83-89]()*

## Core Data Model

The foundation of the asset representation is built upon a base `Asset` dataclass and an `AssetClass` enumeration to categorize each instrument.

*Sources: [src/models/financial_models.py]()*

### AssetClass Enum

The `AssetClass` enum provides a controlled vocabulary for classifying assets. This ensures type safety and consistency throughout the application, from data creation to visualization.

*Sources: [src/models/financial_models.py:11-19](), [AI_RULES.md:34-35]()*

| Member | Description |
| --- | --- |
| `EQUITY` | Represents stocks or shares in a company. |
| `BOND` | Represents fixed-income instruments. |
| `COMMODITY` | Represents raw materials or primary agricultural products. |
| `CURRENCY` | Represents foreign exchange pairs. |
| `REGULATORY_EVENT` | Represents corporate or regulatory events affecting assets. |

### Asset Class Hierarchy

All specific asset models inherit from a common `Asset` base class. This design ensures that all assets share a fundamental set of properties, while allowing for specialized attributes in subclasses. The diagram below illustrates this inheritance structure.

*Sources: [src/models/financial_models.py:22-101](), [ARCHITECTURE.md:83-89]()*

```mermaid
classDiagram
    direction LR
    class Asset {
        <<Abstract>>
        +str id
        +str symbol
        +str name
        +AssetClass asset_class
        +str sector
        +str currency
        +float price
        +float market_cap
        +dict additional_fields
        +__post_init__()
    }

    class Equity {
        +float pe_ratio
        +float dividend_yield
        +float eps
    }

    class Bond {
        +float yield_
        +float duration
        +str credit_rating
    }

    class Commodity {
        +str futures_contract_specs
        +float spot_price
    }

    class Currency {
        +str country
        +float interest_rate
        +str central_bank
    }

    class RegulatoryEvent {
        +RegulatoryActivity activity_type
        +date event_date
        +float impact_score
        +str description
    }

    Asset <|-- Equity
    Asset <|-- Bond
    Asset <|-- Commodity
    Asset <|-- Currency
    Asset <|-- RegulatoryEvent
```

### Base Asset Model

The `Asset` dataclass defines the common attributes shared by all financial instruments in the system. It includes validation in its `__post_init__` method to ensure data integrity, such as checking for non-negative prices.

*Sources: [src/models/financial_models.py:22-47](), [AUDIT_REPORT.md:21-23]()*

| Attribute | Type | Description | Constraints |
| --- | --- | --- | --- |
| `id` | `str` | A unique identifier for the asset. | |
| `symbol` | `str` | The ticker symbol or other short identifier. | |
| `name` | `str` | The full name of the asset. | |
| `asset_class` | `AssetClass` | The type of the asset, from the `AssetClass` enum. | |
| `sector` | `str` | The industry sector the asset belongs to. | |
| `currency` | `str` | The currency of the asset's price (3-letter ISO code). | Must be 3 uppercase letters. |
| `price` | `float` | The current market price of the asset. | Must be non-negative. |
| `market_cap` | `float` | The total market capitalization. | |
| `additional_fields` | `dict` | A dictionary for any extra, non-standard data. | |

## Detailed Asset Classes

The system supports five specialized asset classes, each inheriting from the base `Asset` model and adding its own unique attributes. These were introduced in version 1.0.0 of the project.

*Sources: [CHANGELOG.md:52-56](), [README.md:32-37]()*

### Equities

Represents ownership stakes in a public company. The `Equity` class adds standard financial metrics used for stock valuation.

*Sources: [src/models/financial_models.py:50-57]()*

| Attribute | Type | Description |
| --- | --- | --- |
| `pe_ratio` | `float` | Price-to-Earnings ratio. |
| `dividend_yield`| `float` | The ratio of the annual dividend to the share price. |
| `eps` | `float` | Earnings Per Share. |

### Fixed Income (Bonds)

Represents debt instruments. The `Bond` class includes attributes related to yield and credit risk.

*Sources: [src/models/financial_models.py:60-67]()*

| Attribute | Type | Description |
| --- | --- | --- |
| `yield_` | `float` | The yield to maturity of the bond. |
| `duration`| `float` | A measure of the bond's interest rate sensitivity. |
| `credit_rating` | `str` | The credit rating from an agency (e.g., AAA, BB+). |

### Commodities

Represents physical goods or raw materials. The `Commodity` class includes details about futures contracts and spot pricing.

*Sources: [src/models/financial_models.py:70-75]()*

| Attribute | Type | Description |
| --- | --- | --- |
| `futures_contract_specs` | `str` | Specifications for the futures contract. |
| `spot_price`| `float` | The current market price for immediate delivery. |

### Currencies

Represents foreign exchange instruments. The `Currency` class adds macroeconomic indicators relevant to a currency's value.

*Sources: [src/models/financial_models.py:78-84]()*

| Attribute | Type | Description |
| --- | --- | --- |
| `country` | `str` | The primary country associated with the currency. |
| `interest_rate`| `float` | The central bank's benchmark interest rate. |
| `central_bank` | `str` | The name of the central bank issuing the currency. |

### Regulatory Events

Represents significant events that can impact other assets. The `RegulatoryEvent` model includes an impact score and a type classification.

*Sources: [src/models/financial_models.py:87-101]()*

| Attribute | Type | Description | Constraints |
| --- | --- | --- | --- |
| `activity_type` | `RegulatoryActivity` | The type of event (e.g., Earnings, M&A). | |
| `event_date`| `date` | The date the event occurred. | Must be a valid ISO 8601 date. |
| `impact_score` | `float` | A score from -1.0 (negative) to 1.0 (positive). | Must be within [-1.0, 1.0]. |
| `description` | `str` | A brief description of the event. | |

## Extensibility

The system is designed to be extensible, allowing for the addition of new asset types. To add a new asset class, a developer can create a new dataclass that inherits from the base `Asset` class. This pattern is encouraged for future expansion.

The example below, taken from the project's documentation, shows how a `Derivative` asset could be added.

*Sources: [README.md:73-84]()*

```python
from src.models.financial_models import Asset, AssetClass

# Extend Asset for new types
@dataclass
class Derivative(Asset):
    underlying_asset: str
    expiration_date: str
    strike_price: Optional[float] = None
```

## Conclusion

The project's support for diverse asset classes is built on a robust and extensible object-oriented data model. By using a common base class and specialized subclasses, the system can consistently manage, analyze, and visualize a wide range of financial instruments and the complex relationships between them. This structured approach is central to the application's ability to provide meaningful cross-asset insights.

### Feature: Metrics and Analytics

<details>
<summary>Relevant source files</summary>
The following files were used as context for generating this wiki page:

- [src/visualizations/metric_visuals.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/visualizations/metric_visuals.py)
- [frontend/app/components/MetricsDashboard.tsx](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/app/components/MetricsDashboard.tsx)
- [src/logic/asset_graph.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/logic/asset_graph.py)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [TESTING_GUIDE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/TESTING_GUIDE.md)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [IMPROVEMENTS.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/IMPROVEMENTS.md)

</details>

# Feature: Metrics and Analytics

The Metrics and Analytics feature provides a quantitative overview of the financial asset network's structure and complexity. It calculates key statistical metrics from the underlying graph data and presents them through two distinct user interfaces: a modern Next.js dashboard and the original Gradio UI. This functionality is crucial for users to quickly assess the density, composition, and overall scale of the interconnected assets.

The system is designed to provide real-time metrics that are recalculated whenever the asset graph is updated, ensuring that the analytics always reflect the current state of the data. This feature is central to the project's goal of offering comprehensive analysis of asset relationships.

Sources: [README.md](), [ARCHITECTURE.md]()

## Architecture and Data Flow

The metrics and analytics functionality spans from the core business logic layer, through the API, to the user interface. The `AssetRelationshipGraph` class is the single source of truth for all metric calculations. This data is then exposed via a FastAPI endpoint to the Next.js frontend or consumed directly by the Gradio UI.

This diagram illustrates the data flow for the metrics feature across both frontend implementations.

```mermaid
graph TD
    subgraph Core Logic
        A[src/logic/asset_graph.py] -->|calculate_metrics()| B(Metrics Dictionary)
    end

    subgraph API and Frontend
        subgraph Gradio UI
            B -->|Direct Call| C[src/visualizations/metric_visuals.py]
            C --> D[Plotly Gauge & Pie Charts]
            D --> E[Gradio Dashboard]
        end

        subgraph Next.js UI
            B -->|FastAPI Endpoint| F(GET /api/metrics)
            F -->|Axios Request| G[frontend/app/lib/api.ts]
            G --> H[frontend/app/components/MetricsDashboard.tsx]
            H --> I[React Component Rendering]
        end
    end
```
Sources: [ARCHITECTURE.md](), [TESTING_GUIDE.md]()

## Backend: Metric Calculation

All network metrics are computed within the `AssetRelationshipGraph` class, specifically in the `calculate_metrics` method. This method aggregates data about the nodes (assets) and edges (relationships) to produce a dictionary of key statistics.

Sources: [src/logic/asset_graph.py](), [README.md]()

### Core Method: `calculate_metrics`

This method is responsible for calculating all network statistics. It raises a `ValueError` if the graph is empty.

The following table details the metrics calculated by this method.

| Metric Key | Description | Calculation Logic |
| :--- | :--- | :--- |
| `total_assets` | The total number of assets (nodes) in the graph. | `len(self.assets)` |
| `total_relationships` | The total number of relationships (edges) in the graph. | `len(self.relationships)` |
| `average_relationship_strength` | The mean strength of all relationships, clamped between 0 and 1. | `np.mean([r['strength'] for r in self.relationships])` |
| `network_density` | A measure of how interconnected the graph is. A value of 1 means all possible connections exist. | `(2 * num_relationships) / (num_assets * (num_assets - 1))` |
| `asset_classes` | A breakdown of assets by their class (e.g., Equity, Bond). | Counts assets for each `AssetClass` enum member. |
| `average_degree` | The average number of connections per asset. | `(2 * num_relationships) / num_assets` |
| `max_degree` | The highest number of connections for any single asset in the network. | `max(degrees)` where `degrees` is a list of connection counts per asset. |

Sources: [src/logic/asset_graph.py:218-268](), [IMPROVEMENTS.md]()

## API Layer: Exposing Metrics

The calculated metrics are exposed to the Next.js frontend via a dedicated REST API endpoint managed by FastAPI.

Sources: [ARCHITECTURE.md](), [TESTING_GUIDE.md]()

### Endpoint: `GET /api/metrics`

This endpoint retrieves the calculated metrics from the singleton `AssetRelationshipGraph` instance and returns them as a JSON object.

The data flow for a frontend request is as follows:

```mermaid
sequenceDiagram
    participant User as "User Interface"
    participant NextApp as "Next.js Frontend"
    participant API as "FastAPI Backend"
    participant Graph as "AssetRelationshipGraph"

    User->>NextApp: Loads Metrics Dashboard
    NextApp->>API: GET /api/metrics
    activate API
    API->>Graph: get_graph()
    Graph-->>API: Singleton instance
    API->>Graph: calculate_metrics()
    Graph-->>API: Metrics Dictionary
    API-->>NextApp: 200 OK (JSON Response)
    deactivate API
    NextApp-->>User: Renders Metric Cards
```
This sequence shows the Next.js application fetching metrics from the FastAPI backend, which in turn calls the core logic to perform the calculation.

Sources: [ARCHITECTURE.md](), [TESTING_GUIDE.md]()

### Data Model: `MetricsResponse`

The API response is validated using a Pydantic model to ensure type safety and consistency.

| Field | Type | Description |
| :--- | :--- | :--- |
| `total_assets` | `int` | Total number of assets. |
| `total_relationships` | `int` | Total number of relationships. |
| `average_relationship_strength` | `float` | Average strength of relationships. |
| `network_density` | `float` | Density of the network graph. |
| `asset_classes` | `Dict[str, int]` | Count of assets per class. |
| `average_degree` | `float` | Average connections per asset. |
| `max_degree` | `int` | Maximum connections for a single asset. |

Sources: [TESTING_GUIDE.md](), [TEST_SUMMARY.md]()

## Frontend: Displaying Metrics

The project provides two different UIs for displaying the calculated metrics, each with its own implementation.

### Next.js Metrics Dashboard

The Next.js frontend features a `MetricsDashboard` React component that fetches data from the `/api/metrics` endpoint and displays it in a series of cards.

Sources: [frontend/app/components/MetricsDashboard.tsx](), [TESTING_GUIDE.md]()

#### Component: `MetricsDashboard.tsx`

This component is responsible for:
1.  Receiving metrics data as props.
2.  Rendering individual "metric cards" for each key statistic.
3.  Formatting numerical data for readability (e.g., percentages, large numbers).
4.  Displaying the asset class breakdown.

Key features of the component include:
- **Data Formatting**: Values like `network_density` are formatted as percentages.
- **Edge Case Handling**: Correctly displays `0` for metrics when the data is empty or null, preventing `NaN` errors.
- **Visual Consistency**: Ensures a uniform look and feel for all displayed metrics.

The following metrics are displayed on the dashboard:

| Metric Displayed | Data Source | Formatting |
| :--- | :--- | :--- |
| Total Assets | `metrics.total_assets` | Raw integer |
| Total Relationships | `metrics.total_relationships` | Raw integer |
| Network Density | `metrics.network_density` | Percentage (2 decimal places) |
| Average Degree | `metrics.average_degree` | Number (2 decimal places) |
| Max Degree | `metrics.max_degree` | Raw integer |
| Asset Classes | `metrics.asset_classes` | List of class names and counts |

Sources: [frontend/app/components/MetricsDashboard.tsx:11-80](), [TESTING_GUIDE.md]()

### Gradio Metrics Dashboard

The original Gradio UI uses Plotly to create a more visual representation of the metrics, including gauge and pie charts.

Sources: [src/visualizations/metric_visuals.py]()

#### Functions

- **`create_metrics_dashboard(metrics)`**: The main function that orchestrates the creation of the entire dashboard layout in Gradio. It calls other helper functions to generate individual plots.
- **`create_gauge_chart(value, title, reference)`**: Generates a Plotly gauge chart, used for displaying metrics like "Network Density" and "Avg. Relationship Strength".
- **`create_asset_class_pie_chart(asset_classes)`**: Creates a Plotly pie chart to visualize the distribution of different asset classes.

The Gradio dashboard provides a different visual take on the same underlying data, emphasizing visual indicators over raw numbers for some metrics.

Sources: [src/visualizations/metric_visuals.py:11-103]()

## Summary

The Metrics and Analytics feature is a cornerstone of the application, providing essential insights into the structure of the financial asset graph. By centralizing the calculation logic in `AssetRelationshipGraph` and offering flexible display options through both a modern Next.js/FastAPI stack and a classic Gradio interface, the system ensures data consistency while catering to different presentation needs. The clear separation of concerns—from calculation to API exposure to frontend rendering—makes the feature robust, testable, and extensible.

Sources: [README.md](), [ARCHITECTURE.md](), [IMPROVEMENTS.md]()

### Feature: Regulatory Event Integration

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [src/models/financial_models.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/models/financial_models.py)
- [src/logic/asset_graph.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/logic/asset_graph.py)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
- [CHANGELOG.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CHANGELOG.md)
</details>

# Feature: Regulatory Event Integration

The Regulatory Event Integration feature allows the system to model the impact of corporate and regulatory activities, such as SEC filings or M&A announcements, on financial assets. This is achieved by representing these events as distinct nodes within the asset relationship graph. These event nodes create directional relationships with the assets they affect, with the relationship's strength determined by a predefined impact score. This adds a layer of qualitative, event-driven analysis to the quantitative market data.

Sources: [README.md](), [CHANGELOG.md](), [ARCHITECTURE.md]()

## Data Models for Regulatory Events

The feature is built upon two primary data structures defined in the `financial_models.py` module: the `RegulatoryActivity` enum and the `RegulatoryEvent` dataclass.

Sources: [src/models/financial_models.py](), [AI_RULES.md]()

### RegulatoryActivity Enum

This enumeration defines the types of regulatory activities that can be modeled. It provides a fixed set of choices for categorizing events.

Sources: [src/models/financial_models.py](), [AI_RULES.md]()

### RegulatoryEvent Dataclass

The `RegulatoryEvent` is a specialized type of `Asset` that encapsulates all information about a specific event. It includes a list of impacted asset symbols and an `impact_score` to quantify the event's effect.

The diagram below shows the structure of the `RegulatoryEvent` class and its relation to the base `Asset` class and `RegulatoryActivity` enum.

```mermaid
classDiagram
    direction LR
    class Asset {
        +str id
        +str symbol
        +str name
        +AssetClass asset_class
    }
    class RegulatoryEvent {
        +str date
        +RegulatoryActivity activity_type
        +list[str] impacted_symbols
        +float impact_score
        +str description
        +__post_init__() void
    }
    class RegulatoryActivity {
        <<enumeration>>
        EARNINGS_RELEASE
        SEC_FILING
        MERGER_ACQUISITION
        PRODUCT_LAUNCH
        LEGAL_RULING
    }

    Asset <|-- RegulatoryEvent
    RegulatoryEvent o-- RegulatoryActivity
```
Sources: [src/models/financial_models.py]()

The fields of the `RegulatoryEvent` dataclass are detailed in the table below.

| Field              | Type                     | Description                                                                                             | Constraints                                  |
| ------------------ | ------------------------ | ------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| `id`               | `str`                    | Unique identifier for the event.                                                                        | Inherited from `Asset`.                      |
| `name`             | `str`                    | A descriptive name for the event.                                                                       | Inherited from `Asset`.                      |
| `date`             | `str`                    | The date of the event in ISO 8601 format.                                                               | Must be a valid ISO 8601 date string.        |
| `activity_type`    | `RegulatoryActivity`     | The type of regulatory activity (e.g., `EARNINGS_RELEASE`).                                             | Must be a member of the `RegulatoryActivity` enum. |
| `impacted_symbols` | `List[str]`              | A list of asset symbols (e.g., stock tickers) that are affected by this event.                          | -                                            |
| `impact_score`     | `float`                  | A normalized score from -1.0 (negative impact) to +1.0 (positive impact) quantifying the event's effect. | Must be between -1.0 and 1.0, inclusive.     |
| `description`      | `str`                    | A detailed text description of the event.                                                               | -                                            |

The `__post_init__` method in the `RegulatoryEvent` dataclass performs validation to ensure the `impact_score` is within its valid range and that the `date` conforms to the ISO 8601 standard.

Sources: [src/models/financial_models.py](), [AUDIT_REPORT.md]()

## Integration into the Asset Relationship Graph

Regulatory events are integrated into the graph during the relationship-building phase, which is handled by the `AssetRelationshipGraph` class. The system identifies assets that are `RegulatoryEvent` instances and creates directional relationships to the assets listed in their `impacted_symbols` field.

Sources: [src/logic/asset_graph.py](), [ARCHITECTURE.md]()

### Relationship Discovery Logic

The core logic resides within the `_find_relationships` method of the `AssetRelationshipGraph`. The process for handling regulatory events is as follows:

1.  The method iterates through all pairs of assets in the graph.
2.  It checks if one of the assets in a pair is an instance of `RegulatoryEvent`.
3.  If an event is found, the logic iterates through the `impacted_symbols` defined within that event object.
4.  For each `impacted_symbol`, it checks if the other asset in the pair has a matching symbol.
5.  If a match is found, a new directional relationship of type `event_impact` is created from the event to the impacted asset.

The following flowchart illustrates this discovery process.

```mermaid
flowchart TD
    A[Start _find_relationships] --> B{Iterate through asset pairs (asset1, asset2)};
    B --> C{Is asset1 a RegulatoryEvent?};
    C -- Yes --> D{Iterate through impacted_symbols in asset1};
    D --> E{Does asset2.symbol match an impacted_symbol?};
    E -- Yes --> F[Create 'event_impact' relationship from asset1 to asset2];
    F --> D;
    E -- No --> D;
    D -- End of symbols --> B;
    C -- No --> B;
    B -- End of pairs --> G[End];
```
Sources: [src/logic/asset_graph.py]()

## The 'Event Impact' Relationship

The integration of regulatory events introduces a unique, directional relationship type called `event_impact`.

-   **Directionality**: The relationship is always directed *from* the `RegulatoryEvent` *to* the impacted financial asset (e.g., an `Equity`). This signifies that the event causes an effect on the asset.
-   **Strength**: The strength of the `event_impact` relationship is directly derived from the `impact_score` of the `RegulatoryEvent`. This allows the graph to model both the existence and the magnitude of an event's influence.

This diagram shows an example of an `event_impact` relationship.

```mermaid
graph TD
    subgraph "Asset Relationship Graph"
        direction LR
        Event[("Regulatory Event<br>M&A Announcement<br>impact_score: 0.8")]
        Asset[("Equity<br>AAPL")]

        Event -- "event_impact<br>strength: 0.8" --> Asset
    end
```
Sources: [src/logic/asset_graph.py](), [README.md]()

## Validation and Testing

The system ensures the integrity of regulatory event data through validation and comprehensive testing.

-   **Data Validation**: As noted in the audit report, the `RegulatoryEvent` model includes `__post_init__` validation for the `impact_score` (must be between -1 and 1) and the date format (must be ISO 8601). This prevents malformed event data from entering the system.
-   **Unit Testing**: The test suite includes fixtures like `sample_regulatory_event` in `tests/conftest.py` to create valid event objects for testing. Unit tests in `tests/unit/test_financial_models.py` and `tests/unit/test_asset_graph.py` verify both the model's validation logic and the graph's ability to correctly build relationships from these events.

Sources: [AUDIT_REPORT.md]()

## Summary

The Regulatory Event Integration feature is a key component for adding qualitative depth to the financial asset graph. By modeling external events as nodes and creating directional, weighted relationships, the system can represent how non-market activities influence specific assets. This is supported by a robust data model with built-in validation and is a core part of the relationship discovery engine.

Sources: [README.md](), [CHANGELOG.md]()


## Data Management and Flow

### Database Schema

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- `ARCHITECTURE.md`
- `IMPROVEMENTS.md`
- `AI_RULES.md`
- `README.md`
- `SECURITY.md`
- `AUDIT_REPORT.md`
- `DEPENDENCY_IMPROVEMENTS.md`

</details>

# Database Schema

The Financial Asset Relationship Database system is designed to model and visualize complex relationships between various financial assets. The data architecture is evolving from an in-memory model to a persistent database system to ensure scalability, data integrity, and support for advanced analytics. This document outlines both the current in-memory data models and the planned future database schema.

The core of the data layer is built around Python `dataclasses` which define the structure for assets and their relationships. The future architecture will translate these models into a relational database schema, likely using PostgreSQL, and will be accessed via a Repository Pattern to decouple business logic from data storage.

Sources: [`AI_RULES.md`](), [`IMPROVEMENTS.md`](), [`ARCHITECTURE.md`]()

## Data Models (In-Memory)

The application currently relies on a set of well-defined Python `dataclasses` to represent financial entities. This approach ensures type safety and clear data definitions for the in-memory graph structure. The primary models are defined for different asset classes, all inheriting from a base `Asset` class.

Sources: [`AI_RULES.md`](), [`README.md:65-73`]()

### Model Inheritance Diagram

The following diagram illustrates the inheritance hierarchy of the financial data models.

```mermaid
classDiagram
    direction LR
    class Asset {
        +str id
        +str symbol
        +str name
        +AssetClass asset_class
        +str sector
        +float price
        +str currency
        +dict additional_fields
    }
    class Equity {
        +float pe_ratio
        +float dividend_yield
    }
    class Bond {
        +float yield
        +float duration
        +str credit_rating
    }
    class Commodity {
        +str contract_size
    }
    class Currency {
        +str country
    }
    class RegulatoryEvent {
        +str event_type
        +float impact_score
    }

    Asset <|-- Equity
    Asset <|-- Bond
    Asset <|-- Commodity
    Asset <|-- Currency

```
Sources: [`README.md:65-73`](), [`AI_RULES.md`]()

### Core Asset Models

The system supports several asset classes, each with specific attributes.

#### Asset (Base Class)

This is the foundational data class from which all specific asset types inherit.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `str` | Unique identifier for the asset. |
| `symbol` | `str` | The ticker or symbol for the asset. |
| `name` | `str` | The full name of the asset. |
| `asset_class` | `Enum` | The type of asset (e.g., EQUITY, BOND). |
| `sector` | `str` | The industry sector the asset belongs to. |
| `price` | `float` | The current market price. |
| `currency` | `str` | The currency of the price (3-letter ISO code). |
| `additional_fields` | `dict` | A dictionary for any extra attributes. |

Sources: [`README.md:65-73`](), [`AUDIT_REPORT.md`]()

#### Other Asset Types
- **Equity**: Represents stocks and includes fields like `pe_ratio` and `dividend_yield`.
- **Bond**: Represents fixed-income securities with fields like `yield`, `duration`, and `credit_rating`.
- **Commodity**: Represents physical goods or raw materials.
- **Currency**: Represents foreign exchange pairs.
- **Regulatory Events**: Models corporate events like SEC filings or M&A activities that can impact assets. It includes an `impact_score` from -1 to +1.

Sources: [`README.md:65-73`]()

## Planned Database Architecture

To support data persistence, real-time updates, and advanced analytics, the project architecture is planned to incorporate a relational database. The recommended approach involves using a **Repository Pattern** to abstract data access and a **Service Layer** for business logic.

Sources: [`IMPROVEMENTS.md`](), [`AUDIT_REPORT.md`]()

### Architectural Layers

This diagram shows the proposed layers for interacting with the database.

```mermaid
graph TD
    A[API Layer / UI] --> B[Service Layer];
    B --> C[Repository Interface];
    C --> D[PostgresRepository];
    D --> E[PostgreSQL Database];
    C --> F[InMemoryRepository];
    F --> G[In-Memory Graph];

    subgraph "Business Logic"
        B
    end

    subgraph "Data Access Abstraction"
        C
    end

    subgraph "Data Access Implementation"
        D
        F
    end

    subgraph "Data Storage"
        E
        G
    end
```
This architecture allows the application to switch between an in-memory store and a persistent PostgreSQL database by simply changing the repository implementation injected into the service layer.

Sources: [`IMPROVEMENTS.md`]()

### Proposed Entity-Relationship Diagram (ERD)

The following ERD represents a possible database schema based on the existing in-memory data models. It includes tables for assets, their specific attributes, and the relationships between them.

```mermaid
erDiagram
    ASSET {
        varchar(255) id PK
        varchar(255) symbol
        varchar(255) name
        varchar(50) asset_class
        varchar(100) sector
        decimal price
        varchar(3) currency
        jsonb additional_fields
    }

    EQUITY {
        varchar(255) asset_id PK, FK
        decimal pe_ratio
        decimal dividend_yield
    }

    BOND {
        varchar(255) asset_id PK, FK
        decimal yield
        decimal duration
        varchar(10) credit_rating
    }

    REGULATORY_EVENT {
        varchar(255) id PK
        varchar(255) event_type
        text description
        date event_date
        decimal impact_score
    }

    ASSET_RELATIONSHIP {
        varchar(255) source_asset_id PK, FK
        varchar(255) target_asset_id PK, FK
        varchar(100) relationship_type PK
        decimal strength
        boolean is_directional
    }

    EVENT_ASSET_LINK {
        varchar(255) event_id PK, FK
        varchar(255) asset_id PK, FK
    }

    ASSET ||--o{ EQUITY : "is a"
    ASSET ||--o{ BOND : "is a"
    ASSET ||--o{ ASSET_RELATIONSHIP : "has source"
    ASSET ||--o{ ASSET_RELATIONSHIP : "has target"
    REGULATORY_EVENT ||--|{ EVENT_ASSET_LINK : "affects"
    ASSET ||--|{ EVENT_ASSET_LINK : "is affected by"

```
This schema normalizes asset-specific data into separate tables (`EQUITY`, `BOND`) linked back to the main `ASSET` table. Relationships are stored in a dedicated `ASSET_RELATIONSHIP` table.

Sources: [`README.md:65-73`](), [`IMPROVEMENTS.md`]()

## Database Security

When implementing the database, several security best practices are recommended to protect sensitive financial data.

| Practice | Description |
| :--- | :--- |
| **Parameterized Queries** | Use parameterized queries or ORMs to prevent SQL injection attacks. |
| **Secrets Management** | Store database credentials securely using environment variables or a secrets manager (e.g., AWS Secrets Manager, Azure Key Vault), not in code. |
| **Connection Pooling** | Use connection pooling to manage database connections efficiently and securely. |
| **Encryption** | Enable encryption at rest for stored data and encryption in transit (TLS/SSL) for data moving between the application and the database. |
| **Role-Based Access** | Configure specific database user roles with the minimum required permissions. |
| **Audit Logging** | Enable audit logging on the database to track access and changes to data. |

Sources: [`SECURITY.md`](), [`DEPENDENCY_IMPROVEMENTS.md`]()

### Example: Secure Query

The following code snippet illustrates the use of parameterized queries to prevent SQL injection.

```python
# GOOD - Use parameterized queries
from sqlalchemy import text
query = text("SELECT * FROM assets WHERE id = :asset_id")
result = session.execute(query, {"asset_id": asset_id})
```
Sources: [`SECURITY.md`]()

## Conclusion

The project's data architecture is strategically designed for evolution. It starts with a flexible, in-memory `dataclass`-based model that is ideal for rapid development and visualization. The clear and well-documented plan to migrate to a persistent PostgreSQL database using a repository pattern ensures that the system can scale to handle larger datasets, support more complex queries, and provide a robust foundation for future features like real-time analytics and machine learning integration. Adherence to security best practices during this transition will be critical for protecting data integrity.

### Data Repository Pattern

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [IMPROVEMENTS.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/IMPROVEMENTS.md)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [TESTING_GUIDE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/TESTING_GUIDE.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
</details>

# Data Repository Pattern

The Data Repository Pattern is a recommended architectural improvement for the Financial Asset Relationship Database project. Its purpose is to abstract the data access layer from the core business logic. This decouples the application from a specific data storage implementation, enhances testability, and prepares the system for future enhancements like database persistence.

Currently, the project's data management is tightly coupled with the business logic inside the `AssetRelationshipGraph` class. The proposed pattern introduces a dedicated `AssetRepository` to handle all data operations, creating a more scalable and maintainable layered architecture.

Sources: [IMPROVEMENTS.md:123-135](), [README.md:65-68]()

## Current Data Management Architecture

In the existing architecture, the `AssetRelationshipGraph` class serves as both the core logic engine and an in-memory data store. The API layer (FastAPI) or UI layer (Gradio) interacts directly with this class to manage assets and relationships.

Sources: [README.md:65-68](), [TESTING_GUIDE.md:38-46]()

The diagram below illustrates the current tightly-coupled data flow.

```mermaid
graph TD
    subgraph API/UI Layer
        A[FastAPI Endpoints]
        B[Gradio Interface]
    end

    subgraph Core Logic
        C[AssetRelationshipGraph]
    end

    subgraph In-Memory Storage
        D{Assets & Relationships}
    end

    A --> C
    B --> C
    C -- Manages --> D

    style C fill:#f9f,stroke:#333,stroke-width:2px
```
*Diagram showing the API/UI layers directly calling `AssetRelationshipGraph`, which manages in-memory data.*

Sources: [README.md:65-68](), [TESTING_GUIDE.md:38-46]()

## Proposed Repository Pattern Architecture

The `IMPROVEMENTS.md` document recommends refactoring the architecture to introduce a formal Repository Pattern. This involves creating a dedicated repository layer that sits between the business logic (Service Layer) and the data source.

Sources: [IMPROVEMENTS.md:123-125]()

### Key Components

The proposed architecture consists of three main components:

| Component | Description | Source File |
| :--- | :--- | :--- |
| **AssetRepository** | An interface or class that defines data access methods like `get_by_id`, `get_all`, and `save`. It abstracts the underlying data storage mechanism. | `IMPROVEMENTS.md` |
| **AssetService** | A business logic layer that consumes the `AssetRepository`. It contains the core application logic, such as calculating portfolio risk, without knowing how data is stored. | `IMPROVEMENTS.md` |
| **Dependency Injection** | A mechanism to provide the `AssetService` with a concrete implementation of the `AssetRepository`, facilitating easier testing and decoupling. | `IMPROVEMENTS.md` |

Sources: [IMPROVEMENTS.md:123-150]()

### Proposed Data Flow

The new data flow would be layered, promoting a clean separation of concerns.

```mermaid
flowchart TD
    A[API Layer] --> B[Service Layer (e.g., AssetService)]
    B --> C[Repository Interface (e.g., AssetRepository)]
    C --> D[Data Source (In-Memory or DB)]

    subgraph "Business Logic"
        B
    end

    subgraph "Data Access Layer"
        C
    end
```
*Diagram illustrating the proposed layered architecture where the API interacts with a Service Layer, which in turn uses a Repository to access data.*

Sources: [IMPROVEMENTS.md:123-150]()

### `AssetRepository` Interface

The `IMPROVEMENTS.md` document suggests the following structure for the `AssetRepository`. This interface defines the contract for all data access operations related to assets.

```python
# Proposed in: src/repositories/asset_repository.py
class AssetRepository:
    def get_by_id(self, asset_id: str) -> Optional[Asset]:
        pass

    def get_all(self) -> List[Asset]:
        pass

    def save(self, asset: Asset) -> None:
        pass
```
*Source: [IMPROVEMENTS.md:126-135]()*

The following class diagram shows the proposed `AssetRepository` and its relationship with the `Asset` model.

```mermaid
classDiagram
    class AssetRepository {
        <<Interface>>
        +get_by_id(asset_id: str) Optional[Asset]
        +get_all() List[Asset]
        +save(asset: Asset) None
    }
    class Asset {
        +id: str
        +symbol: str
        +name: str
    }
    AssetRepository ..> Asset : "manages"
```
*Class diagram for the proposed `AssetRepository` interface.*

Sources: [IMPROVEMENTS.md:126-135](), [AI_RULES.md:12-13]()

## Integration with a Service Layer

The repository is designed to be consumed by a service layer, which will house the business logic currently in `AssetRelationshipGraph`. The `IMPROVEMENTS.md` document provides an example of an `AssetService` that uses dependency injection to receive a repository instance.

```python
# Proposed in: src/services/asset_service.py
class AssetService:
    def __init__(self, repository: AssetRepository):
        self.repository = repository

    def calculate_portfolio_risk(self, assets: List[Asset]) -> float:
        # Business logic here
        pass
```
*Source: [IMPROVEMENTS.md:139-147]()*

### Sequence of Operations

This sequence diagram shows how a request to fetch an asset would flow through the proposed architecture.

```mermaid
sequenceDiagram
    participant API as "API Endpoint"
    participant Service as "AssetService"
    participant Repo as "AssetRepository"
    participant DS as "Data Source"

    API->>Service: get_asset_details("AAPL")
    activate Service
    Service->>Repo: get_by_id("AAPL")
    activate Repo
    Repo->>DS: Retrieve asset data for "AAPL"
    DS-->>Repo: Asset data
    Repo-->>Service: Asset object
    deactivate Repo
    Service-->>API: Asset JSON response
    deactivate Service
```
*Sequence diagram showing an API request being handled by the Service, which uses the Repository to fetch data.*

Sources: [IMPROVEMENTS.md:123-150]()

## Benefits of Adopting the Repository Pattern

Implementing this pattern offers several advantages for the project's long-term health and scalability:

- **Separation of Concerns**: Isolates data access logic from business logic, making the code easier to understand and maintain.
- **Improved Testability**: Business logic can be tested independently of the data layer by mocking the repository interface. This is a key part of the project's testing strategy.
- **Data Source Agnosticism**: The underlying data storage can be changed (e.g., from in-memory to a SQL database like PostgreSQL) without affecting the business logic, as long as the new data source class implements the `AssetRepository` interface.
- **Enables Persistence**: It is a prerequisite for adding a persistent data storage layer, a suggested future feature.

Sources: [IMPROVEMENTS.md:123-125, 148-150](), [TESTING_GUIDE.md:19-25]()

## Conclusion

The Data Repository Pattern is a strategic architectural improvement recommended for the `financial-asset-relationship-db` project. By transitioning from the current monolithic `AssetRelationshipGraph` to a layered architecture with a dedicated `AssetRepository` and `AssetService`, the project will become more modular, testable, and prepared for future features like database persistence. This change aligns with modern software design principles and is crucial for the application's evolution.

Sources: [IMPROVEMENTS.md](), [README.md]()

### Real Data Fetching

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [src/data/real\_data\_fetcher.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/data/real_data_fetcher.py)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
- [IMPROVEMENTS.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/IMPROVEMENTS.md)
- [CHANGELOG.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CHANGELOG.md)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
</details>

# Real Data Fetching

The Real Data Fetching module is responsible for acquiring live and historical financial market data from external sources. Its primary function is to populate the application's financial models with real-world data, which is essential for both the 3D visualization and the underlying analysis. This functionality is a core component of the system, supporting both the original Gradio interface and the newer FastAPI/Next.js architecture.

The system is standardized to use the `yfinance` library for all public financial market data acquisition, ensuring a consistent and reliable data source. This module acts as the bridge between the external Yahoo Finance API and the application's internal logic.

Sources: [AI_RULES.md](), [CHANGELOG.md](), [INTEGRATION_SUMMARY.md]()

## Core Technology

The project mandates the use of a specific library for financial data acquisition to ensure consistency and maintainability.

### yfinance Library

The `yfinance` library is the sole approved tool for retrieving public financial market data, including stock prices, company information, and news. This rule prevents the implementation of custom web scrapers or the use of other external financial APIs unless explicitly approved.

Sources: [AI_RULES.md](), [README.md]()

## Architecture and Data Flow

The data fetching mechanism is centralized within the `src/data/` directory and is called by higher-level application layers like the API backend.

This diagram illustrates the data flow from the API layer to the external data source.
```mermaid
flowchart TD
    A[API Layer / App Logic] --> B[real_data_fetcher.py];
    B --> C{yfinance Library};
    C --> D[(Yahoo Finance API)];
    D -->> C;
    C -->> B;
    B -->> A[Returns Populated Asset Models];
```
Sources: [ARCHITECTURE.md](), [AI_RULES.md]()

### Sequence of Operations

The sequence diagram below shows how the FastAPI backend interacts with the data fetching module to retrieve asset information.

```mermaid
sequenceDiagram
    participant Next_js as "Next.js Frontend"
    participant FastAPI as "FastAPI Backend"
    participant Fetcher as "real_data_fetcher.py"
    participant YFinance as "yfinance Library"
    participant YahooAPI as "Yahoo Finance API"

    Next_js->>FastAPI: GET /api/assets
    activate FastAPI
    Note over FastAPI: Uses real data from real_data_fetcher.py
    FastAPI->>Fetcher: fetch_data()
    activate Fetcher
    Fetcher->>YFinance: Ticker(symbol).info
    activate YFinance
    YFinance->>YahooAPI: HTTP GET Request
    YahooAPI-->>YFinance: JSON Response
    YFinance-->>Fetcher: Data Dictionary
    deactivate YFinance
    Fetcher-->>FastAPI: Populated Asset Objects
    deactivate Fetcher
    FastAPI-->>Next_js: JSON Response with Asset Data
    deactivate FastAPI
```
This flow demonstrates the clear separation of concerns, where the API layer delegates data acquisition to the specialized fetcher module.

Sources: [INTEGRATION_SUMMARY.md](), [IMPROVEMENTS.md]()

## System Integration

The real data fetching capability is integrated into multiple parts of the application.

### FastAPI Backend

The FastAPI backend, located in `api/main.py`, utilizes `src/data/real_data_fetcher.py` to serve real-time data to the Next.js frontend. This is a key part of the modern web interface, allowing it to display up-to-date financial information in the asset explorer and visualizations.

Sources: [INTEGRATION_SUMMARY.md]()

### Gradio Application

The initial version of the application, built with Gradio, also relies on `yfinance` for real-time data fetching to power its interactive visualizations and analytics dashboard. This was a feature from the first major release.

Sources: [CHANGELOG.md]()

## Error Handling and Improvements

The `IMPROVEMENTS.md` document highlights an area for enhancement within the `real_data_fetcher.py` module concerning its error handling strategy.

### Broad Exception Handling

The current implementation in `real_data_fetcher.py` uses broad `except Exception` clauses. This pattern is discouraged because it can catch unexpected exceptions, making debugging more difficult.

| Current (Discouraged) | Recommended |
| :--- | :--- |
| Catches all exceptions, including system-level ones. | Catches specific, expected exceptions like `ValueError` or `ConnectionError`. |
| Can hide bugs by catching errors that should have been propagated. | Allows unexpected errors to propagate for easier debugging. |
| Makes it hard to distinguish between different error types (e.g., data vs. network). | Provides distinct handling for different error scenarios. |

**Recommendation:**
Refactor the `try...except` blocks to catch more specific exceptions first, with a final `except Exception` to log and re-raise any truly unexpected errors.

```python
# Instead of:
try:
    data = fetch_data()
except Exception as e:
    logger.error(f"Error: {e}")

# Use specific exceptions:
try:
    data = fetch_data()
except (ValueError, KeyError, TypeError) as e:
    logger.error(f"Data error: {e}")
except ConnectionError as e:
    logger.error(f"Network error: {e}")
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    raise  # Re-raise unexpected errors
```
Sources: [IMPROVEMENTS.md]()

## Conclusion

The Real Data Fetching module is a critical, standardized component for sourcing live financial data using the `yfinance` library. It serves as the data backbone for both the original Gradio application and the newer FastAPI/Next.js stack. While functionally complete, its robustness can be improved by refining its error-handling logic to be more specific, as outlined in the project's improvement recommendations.

### Sample Data Generation

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [src/data/sample_data.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/data/sample_data.py)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
- [IMPROVEMENTS.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/IMPROVEMENTS.md)
- [SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/SUMMARY.md)
- [TESTING_GUIDE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/TESTING_GUIDE.md)
</details>

# Sample Data Generation

The sample data generation module is a core component responsible for creating a static, in-memory dataset of financial assets and regulatory events. Its primary purpose is to allow the application to run and demonstrate its visualization capabilities without requiring live data fetching, making it essential for development, testing, and quick demonstrations.

This module, primarily located in `src/data/sample_data.py`, populates the system with a variety of asset classes, including equities, bonds, commodities, and currencies. This pre-defined dataset ensures a consistent and reproducible state for the application's 3D network graph, as the visualization's layout is deterministic.

Sources: [README.md](), [CONTRIBUTING.md](), [AUDIT_REPORT.md]()

## Architecture and Generation Flow

The sample data generation process is straightforward. A central function orchestrates the creation of various asset objects and collects them into a list. This process is deterministic, partly due to the use of a fixed random seed for any operations involving randomness, ensuring the 3D graph layout remains consistent across application runs.

Sources: [AUDIT_REPORT.md](), [IMPROVEMENTS.md]()

### Core Function

The main entry point for data generation is the `create_sample_assets()` function (inferred name). This function instantiates hardcoded `dataclasses` for each asset and returns them as a list to be consumed by other parts of the application, such as the `AssetRelationshipGraph`.

Sources: [README.md](), [CONTRIBUTING.md]()

### Generation Process Flow

The following diagram illustrates the logical flow of creating the sample dataset.

```mermaid
flowchart TD
    A[Start: create_sample_assets()] --> B{Initialize empty asset list};
    B --> C[Create Equity objects];
    C --> D[Create Bond objects];
    D --> E[Create Commodity objects];
    E --> F[Create Currency objects];
    F --> G[Create Regulatory Event objects];
    subgraph Asset Creation
        C
        D
        E
        F
        G
    end
    G --> H{Append all objects to list};
    H --> I[Return list of Assets];
    I --> J[End];
```
This diagram shows the sequential creation of different asset types, which are then aggregated and returned.

Sources: [README.md](), [AI_RULES.md]()

## Data Models

The sample data generation relies on a set of well-defined data models defined in `src/models/financial_models.py`. These models are implemented using Python's `dataclasses` and `enum` modules to ensure type safety, clarity, and maintainability. The core model is a base `Asset` class from which specific asset types inherit.

Sources: [AI_RULES.md](), [AUDIT_REPORT.md]()

### Asset Class Hierarchy

The system uses a clear inheritance hierarchy for its financial models. This structure allows for both shared attributes and specialized fields for each asset class.

```mermaid
classDiagram
    direction LR
    class Asset {
        +id: str
        +symbol: str
        +name: str
        +asset_class: AssetClass
        +price: float
        +currency: str
        +sector: str
    }

    class Equity {
        +pe_ratio: float
        +dividend_yield: float
    }

    class Bond {
        +yield: float
        +duration: float
        +credit_rating: str
    }

    class Commodity {
        +contract_size: str
    }

    class Currency {
        +country: str
    }

    class RegulatoryEvent {
        +event_type: RegulatoryActivity
        +impact_score: float
    }

    Asset <|-- Equity
    Asset <|-- Bond
    Asset <|-- Commodity
    Asset <|-- Currency
    Asset <|-- RegulatoryEvent
```
This diagram shows the base `Asset` class and the specialized classes for `Equity`, `Bond`, `Commodity`, `Currency`, and `RegulatoryEvent`.

Sources: [AUDIT_REPORT.md](), [AI_RULES.md](), [README.md]()

### Enumerations

To enforce a fixed set of choices for categories, the system uses `enum`.

| Enum Name | Purpose |
| --- | --- |
| `AssetClass` | Defines the major types of assets (e.g., EQUITY, BOND). |
| `RegulatoryActivity` | Defines the types of regulatory events (e.g., EARNINGS, SEC_FILING). |

Sources: [AI_RULES.md](), [AUDIT_REPORT.md]()

## Generated Asset Types

The `sample_data.py` module creates instances for all supported asset classes. The hardcoded values provide a rich and interconnected dataset for visualization.

Sources: [README.md](), [IMPROVEMENTS.md]()

### Equities

Sample stocks are created with financial metrics like P/E ratio and dividend yield.

| Symbol | Name | Sector |
| --- | --- | --- |
| AAPL | Apple Inc. | Technology |
| MSFT | Microsoft Corp. | Technology |
| JPM | JPMorgan Chase & Co. | Financials |
| XOM | Exxon Mobil Corp. | Energy |

Sources: [README.md](), [TESTING_GUIDE.md]()

### Bonds

Corporate bonds are included, often linked to the equities of the issuing company.

| Symbol | Name | Issuer |
| --- | --- | --- |
| AAPL25 | Apple 2.4% 2025 | Apple Inc. |
| MSFT30 | Microsoft 3.1% 2030 | Microsoft Corp. |

Sources: [README.md](), [TESTING_GUIDE.md]()

### Other Asset Classes

The sample dataset also includes:
- **Commodities**: Such as Gold (GC=F) and Crude Oil (CL=F).
- **Currencies**: FX pairs like EUR/USD and GBP/USD.
- **Regulatory Events**: SEC filings or earnings reports linked to specific assets.

Sources: [README.md](), [AUDIT_REPORT.md]()

## Usage in the Application

The data generated by this module is fundamental to the application's ability to display a graph upon startup. The main application file (`app.py` or `api/main.py`) fetches this data and uses it to initialize the `AssetRelationshipGraph`.

Sources: [README.md](), [CONTRIBUTING.md](), [TESTING_GUIDE.md]()

### Data Flow on Application Start

This sequence diagram shows how the sample data is loaded and processed when the application starts.

```mermaid
sequenceDiagram
    participant User
    participant App as "Application (app.py/api.main.py)"
    participant SampleData as "sample_data.py"
    participant AssetGraph as "AssetRelationshipGraph"

    User->>App: Starts Application
    activate App
    App->>SampleData: create_sample_assets()
    activate SampleData
    SampleData-->>App: Returns list of Asset objects
    deactivate SampleData
    App->>AssetGraph: new AssetRelationshipGraph()
    activate AssetGraph
    deactivate AssetGraph
    App->>AssetGraph: add_asset() for each asset
    App->>AssetGraph: build_relationships()
    App->>AssetGraph: get_3d_visualization_data()
    activate AssetGraph
    AssetGraph-->>App: Returns visualization data
    deactivate AssetGraph
    App-->>User: Renders 3D Graph
    deactivate App
```
This flow demonstrates the critical role of `sample_data.py` in bootstrapping the application's primary feature.

Sources: [README.md](), [CONTRIBUTING.md](), [TEST_SUMMARY.md]()

## Role in Testing

The sample data provides a reliable and consistent baseline for the project's comprehensive test suite. Test fixtures, defined in `tests/conftest.py`, are heavily inspired by or are direct subsets of the data generated in `sample_data.py`. These fixtures are then used across unit and integration tests to validate the behavior of the `AssetRelationshipGraph`, API endpoints, and data models.

For example, tests for relationship discovery in `tests/unit/test_asset_graph.py` use fixtures representing sample equities and bonds to assert that the correct relationships are created. This ensures that the core logic of the application is sound and behaves as expected with a known dataset.

Sources: [SUMMARY.md](), [AUDIT_REPORT.md](), [TESTING_GUIDE.md]()

## Conclusion

The sample data generation module is a cornerstone of the `financial-asset-relationship-db` project. It provides a self-contained, deterministic, and representative dataset that enables immediate visualization and robust testing. By decoupling the application's core logic from live data sources, it enhances developer productivity, ensures consistent demonstrations, and provides a stable foundation for the entire test suite.


## Backend Systems

### FastAPI API Reference

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [api/main.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/api/main.py)
- [tests/unit/test_api_main.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/tests/unit/test_api_main.py)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [DEPLOYMENT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/DEPLOYMENT.md)
- [QUICK_START.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/QUICK_START.md)

</details>

# FastAPI API Reference

The FastAPI backend serves as the primary data provider for the modern Next.js frontend. Its main purpose is to expose the functionalities of the core `AssetRelationshipGraph` logic through a high-performance, RESTful API. The API handles requests for asset data, relationship information, network metrics, and visualization data, returning it in a structured JSON format.

This API is designed to be run as a serverless function on platforms like Vercel, working in tandem with the Next.js application. It includes automatic OpenAPI documentation, which can be accessed at the `/docs` endpoint during local development.

*Sources: [INTEGRATION_SUMMARY.md](), [ARCHITECTURE.md](), [QUICK_START.md]()*

## Architecture

The API is built using the FastAPI framework and runs on a Uvicorn ASGI server. It acts as a wrapper around the existing Python business logic, primarily interacting with a singleton instance of the `AssetRelationshipGraph` class. This design separates the web-serving layer from the core data processing engine.

*Sources: [ARCHITECTURE.md](), [api/main.py:18-24]()*

The following diagram illustrates the high-level architecture and data flow from the user to the core logic via the FastAPI layer.

```mermaid
graph TD
    subgraph User_Interface
        A[Next.js Frontend]
    end

    subgraph API_Layer
        B[FastAPI Backend]
    end

    subgraph Core_Logic
        C[AssetRelationshipGraph]
        D[Data Sources e.g., yfinance]
    end

    A -- "REST API Calls" --> B
    B -- "Function Calls" --> C
    C -- "Fetches Data" --> D
```
*Sources: [ARCHITECTURE.md](), [INTEGRATION_SUMMARY.md]()*

### Core Logic Integration

To ensure efficiency and maintain state, the API uses a thread-safe singleton pattern to manage the `AssetRelationshipGraph` instance. The graph is initialized only once on the first request and is then reused for all subsequent calls. This avoids the costly process of re-fetching and rebuilding the graph for every API hit.

A `threading.Lock` is used to prevent race conditions during the initial creation of the graph, making it safe for concurrent requests.

*Sources: [api/main.py:31-48](), [tests/unit/test_api_main.py:70-93]()*

This diagram shows the logic for initializing the singleton graph instance.

```mermaid
flowchart TD
    A[Request Received] --> B{graph is None?};
    B -- Yes --> C{Acquire Lock};
    C --> D{graph is None?};
    D -- Yes --> E[Initialize AssetRelationshipGraph];
    E --> F[Set global graph instance];
    F --> G[Release Lock];
    D -- No --> G;
    B -- No --> H[Return Existing Graph];
    G --> H;
    H --> I[Process Request];
```
*Sources: [api/main.py:31-48]()*

### CORS Configuration

The API is configured with CORS (Cross-Origin Resource Sharing) middleware to allow requests from the Next.js frontend, which runs on a different port during local development (`http://localhost:3000`) and on Vercel deployment domains (`https://*.vercel.app`).

*Sources: [api/main.py:220-229](), [DEPLOYMENT.md]()*

## API Endpoints

The API is available under the `/api/` prefix.

*Sources: [api/main.py](), [DEPLOYMENT.md](), [INTEGRATION_SUMMARY.md]()*

### Health & Metadata

#### `GET /api/health`
Returns the operational status of the API.

- **Response:**
  ```json
  {
    "status": "healthy",
    "graph_initialized": true
  }
  ```
*Sources: [api/main.py:100-106](), [tests/unit/test_api_main.py:130-135]()*

#### `GET /api/asset-classes`
Returns a list of all available asset classes.

- **Response:**
  ```json
  [
    "EQUITY",
    "BOND",
    "COMMODITY",
    "CURRENCY"
  ]
  ```
*Sources: [api/main.py:189-194](), [tests/unit/test_api_main.py:302-307]()*

#### `GET /api/sectors`
Returns a list of all unique sectors available in the asset graph.

- **Response:**
  ```json
  [
    "Technology",
    "Financial Services",
    "Consumer Cyclical"
  ]
  ```
*Sources: [api/main.py:197-202](), [tests/unit/test_api_main.py:309-314]()*

### Assets

#### `GET /api/assets`
Retrieves a list of all assets, with optional filtering.

| Parameter | Type | Description |
|---|---|---|
| `asset_class` | `str` | (Optional) Filter assets by a specific asset class (e.g., `EQUITY`). |
| `sector` | `str` | (Optional) Filter assets by a specific sector (e.g., `Technology`). |

- **Response:** An array of `AssetResponse` objects.
*Sources: [api/main.py:110-129](), [tests/unit/test_api_main.py:151-189]()*

#### `GET /api/assets/{asset_id}`
Retrieves detailed information for a single asset by its ID.

- **Response:** A single `AssetResponse` object or a 404 error if not found.
*Sources: [api/main.py:132-143](), [tests/unit/test_api_main.py:191-203]()*

#### `GET /api/assets/{asset_id}/relationships`
Retrieves all relationships for a specific asset.

- **Response:** An array of `RelationshipResponse` objects.
*Sources: [api/main.py:146-157](), [tests/unit/test_api_main.py:221-233]()*

### Relationships

#### `GET /api/relationships`
Retrieves all relationships in the graph.

- **Response:** An array of `RelationshipResponse` objects.
*Sources: [api/main.py:160-166](), [tests/unit/test_api_main.py:235-241]()*

### Metrics & Visualization

#### `GET /api/metrics`
Calculates and returns key metrics about the network graph.

- **Response:** A `MetricsResponse` object.
*Sources: [api/main.py:169-175](), [tests/unit/test_api_main.py:243-256]()*

#### `GET /api/visualization`
Returns the data required for the frontend to render the 3D network graph.

- **Response:** A `VisualizationDataResponse` object containing nodes and edges.
*Sources: [api/main.py:178-186](), [tests/unit/test_api_main.py:258-279]()*

The following sequence diagram shows a typical request to the visualization endpoint.
```mermaid
sequenceDiagram
    participant Client as "Next.js Frontend"
    participant API as "FastAPI Backend"
    participant Graph as "AssetRelationshipGraph"

    Client->>API: GET /api/visualization
    API->>Graph: get_graph()
    Note right of API: Get singleton instance
    Graph-->>API: graph_instance
    API->>Graph: get_3d_visualization_data()
    Graph-->>API: {nodes: [...], links: [...]}
    API-->>Client: 200 OK with JSON payload
```
*Sources: [api/main.py:178-186](), [ARCHITECTURE.md]()*

## Data Models

The API uses Pydantic models to define and validate the structure of JSON responses.

*Sources: [api/main.py:51-97](), [tests/unit/test_api_main.py:95-128]()*

```mermaid
classDiagram
    class AssetResponse {
        +str id
        +str symbol
        +str name
        +str asset_class
        +str sector
        +str currency
        +float price
        +float market_cap
        +dict additional_fields
    }

    class RelationshipResponse {
        +str source
        +str target
        +str relationship_type
        +float strength
    }

    class MetricsResponse {
        +int total_assets
        +int total_relationships
        +float network_density
        +float average_degree
        +int max_degree
        +dict asset_class_distribution
    }

    class VisualizationNode {
        +str id
        +str name
        +str asset_class
        +str sector
        +float val
        +list~float~ x, y, z
    }

    class VisualizationLink {
        +str source
        +str target
        +str type
        +float strength
    }

    class VisualizationDataResponse {
        +list~VisualizationNode~ nodes
        +list~VisualizationLink~ links
    }

    AssetResponse "1" -- "0..*" RelationshipResponse : (source/target)
    MetricsResponse ..> AssetResponse : (counts)
    VisualizationDataResponse o-- "many" VisualizationNode
    VisualizationDataResponse o-- "many" VisualizationLink
    VisualizationNode ..> AssetResponse : (derived from)
    VisualizationLink ..> RelationshipResponse : (derived from)
```
*Sources: [api/main.py:51-97]()*

### AssetResponse
| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique identifier for the asset. |
| `symbol` | `str` | Ticker symbol or identifier. |
| `name` | `str` | Full name of the asset. |
| `asset_class` | `str` | The class of the asset (e.g., `EQUITY`). |
| `sector` | `str` | The industry sector. |
| `currency` | `str` | The currency of the asset price. |
| `price` | `float` | The current price. |
| `market_cap` | `float` | The market capitalization. |
| `additional_fields` | `dict` | A dictionary of asset-specific fields. |
*Sources: [api/main.py:52-63]()*

### MetricsResponse
| Field | Type | Description |
|---|---|---|
| `total_assets` | `int` | Total number of assets in the graph. |
| `total_relationships` | `int` | Total number of relationships. |
| `network_density` | `float` | The density of the network graph. |
| `average_degree` | `float` | The average number of connections per node. |
| `max_degree` | `int` | The highest number of connections for any single node. |
| `asset_class_distribution` | `dict` | A count of assets per asset class. |
*Sources: [api/main.py:72-80]()*

## Error Handling

The API includes a generic exception handler that catches any unhandled server-side errors. This prevents internal stack traces from being exposed to the client and returns a standard `500 Internal Server Error` response. Specific errors, such as a non-existent asset, result in a `404 Not Found` status code.

*Sources: [api/main.py:205-217](), [tests/unit/test_api_main.py:316-332]()*

## Summary

The FastAPI application provides a robust and modern API layer that decouples the frontend from the core Python logic. It leverages a thread-safe singleton pattern for efficient data management and uses Pydantic for reliable data validation. The well-defined endpoints supply all necessary data for the Next.js frontend to deliver a rich, interactive user experience for exploring financial asset relationships.

### API Authentication

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [api/auth.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/api/auth.py)
- [api/main.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/api/main.py)
- [tests/integration/test_api_integration.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/tests/integration/test_api_integration.py)
- [SECURITY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/SECURITY.md)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
</details>

# API Authentication

The Financial Asset Relationship Database API employs an OAuth2 Password Flow with JSON Web Tokens (JWT) to secure its endpoints. This system ensures that only authenticated users can access protected resources. The implementation is built using FastAPI's security utilities, providing a standardized and robust authentication mechanism.

The core logic is encapsulated within `api/auth.py`, which handles user verification, token creation, and decoding. The main API application, defined in `api/main.py`, integrates this authentication module to expose a token issuance endpoint and protect specific routes. The entire flow is validated through integration tests found in `tests/integration/test_api_integration.py`.

## Architecture and Core Components

The authentication system is composed of several key parts: data models for users and tokens, functions for handling the authentication logic, and API endpoints for user interaction.

Sources: [api/auth.py](), [api/main.py]()

### Data Models

Pydantic models are used to define the data structures for users and tokens, ensuring type safety and validation.

This diagram illustrates the Pydantic models used for authentication.

```mermaid
classDiagram
    class Token {
        +access_token: str
        +token_type: str
    }
    class TokenData {
        +username: str | None
    }
    class User {
        +username: str
        +email: str | None
        +full_name: str | None
        +disabled: bool | None
    }
    class UserInDB {
        +hashed_password: str
    }
    User <|-- UserInDB

    Token --|> TokenData : "Decodes to"
    UserInDB --|> User : "Extends"
```
Sources: [api/auth.py:28-51]()

| Model | Description | Fields | Source File |
|---|---|---|---|
| `User` | Basic user model. | `username`, `email`, `full_name`, `disabled` | `api/auth.py:43-47` |
| `UserInDB` | Extends `User` to include the hashed password for storage. | Inherits from `User`, adds `hashed_password` | `api/auth.py:50-51` |
| `Token` | Represents the access token returned to the client. | `access_token`, `token_type` | `api/auth.py:28-30` |
| `TokenData` | Represents the data encoded within the JWT. | `username` | `api/auth.py:33-34` |

### Configuration

Authentication behavior is configured through environment variables. A hardcoded user database is present for simplicity, with credentials also loaded from the environment.

| Variable | Description | Default Value | Source File |
|---|---|---|---|
| `SECRET_KEY` | A secret string for encoding and decoding JWTs. | "a_very_secret_key" | `api/auth.py:18` |
| `ALGORITHM` | The algorithm used for JWT signing. | "HS256" | `api/auth.py:19` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | The token's validity period in minutes. | 30 | `api/auth.py:20` |
| `ADMIN_USERNAME` | Username for the default admin user. | "admin" | `api/auth.py:57` |
| `ADMIN_PASSWORD` | Password for the default admin user. | "admin" | `api/auth.py:58` |
| `ADMIN_EMAIL` | Email for the default admin user. | "admin@example.com" | `api/auth.py:59` |
| `ADMIN_FULL_NAME` | Full name for the default admin user. | "Admin User" | `api/auth.py:60` |

The use of these environment variables is confirmed in the integration tests.
Sources: [api/auth.py:17-21, 56-61](), [tests/integration/test_api_integration.py:139-142]()

### Key Functions

The authentication logic is handled by a set of functions in `api/auth.py`.

| Function | Description | Source File |
|---|---|---|
| `authenticate_user()` | Verifies a user's credentials (username and password) against the user database. | `api/auth.py:70-79` |
| `create_access_token()` | Generates a new JWT for a given username and expiration time. | `api/auth.py:82-90` |
| `get_current_active_user()` | A FastAPI dependency that decodes the JWT from the request header and retrieves the corresponding active user. | `api/auth.py:93-111` |

## Authentication Flow

The process of obtaining and using an access token follows the standard OAuth2 Password Flow.

### 1. Token Issuance

A client requests an access token by sending its credentials to the `/token` endpoint.

The following sequence diagram shows the token issuance process.
```mermaid
sequenceDiagram
    participant Client
    participant API as "FastAPI App"
    participant Auth as "Auth Module"

    Client->>API: POST /token (username, password)
    activate API
    API->>Auth: authenticate_user(username, password)
    activate Auth
    Note right of Auth: Verifies password hash
    Auth-->>API: UserInDB object or False
    deactivate Auth
    alt Credentials are valid
        API->>Auth: create_access_token(data={"sub": username})
        activate Auth
        Note right of Auth: Encodes JWT with SECRET_KEY
        Auth-->>API: access_token
        deactivate Auth
        API-->>Client: 200 OK { "access_token": "...", "token_type": "bearer" }
    else Credentials are invalid
        API--xClient: 401 Unauthorized
    end
    deactivate API
```
This flow is initiated by the `login_for_access_token` function in `api/main.py`, which handles the `/token` endpoint.
Sources: [api/main.py:129-142](), [api/auth.py:70-90](), [tests/integration/test_api_integration.py:137-150]()

### 2. Accessing Protected Endpoints

Once the client has an access token, it can access protected endpoints by including the token in the `Authorization` header.

This flowchart shows how a request to a protected endpoint is validated.
```mermaid
flowchart TD
    A[Client sends request with 'Authorization: Bearer TOKEN'] --> B{Protected Endpoint};
    B --> C{Depends(get_current_active_user)};
    C --> D[Decode JWT from header];
    D --> E{Token valid and not expired?};
    E -- Yes --> F[Retrieve username from token payload];
    F --> G[Fetch user from DB];
    G --> H{User exists and is active?};
    H -- Yes --> I[Execute endpoint logic];
    I --> J[Return response];
    E -- No --> K[HTTPException 401 Unauthorized];
    H -- No --> K;
```
The `get_current_active_user` function serves as the FastAPI dependency that enforces this validation. Any endpoint that includes `Depends(get_current_active_user)` in its signature is automatically protected.
Sources: [api/auth.py:93-111](), [api/main.py:145-149]()

## API Endpoints

### Authentication Endpoints

| Endpoint | Method | Description | Parameters (form-data) | Response | Source File |
|---|---|---|---|---|---|
| `/token` | `POST` | Issues a JWT access token upon successful authentication. | `username: str`, `password: str` | `Token` model | `api/main.py:129-142` |
| `/api/users/me` | `GET` | Returns the details of the currently authenticated user. Protected endpoint. | None | `User` model | `api/main.py:145-149` |

### Example Usage

To obtain a token, a client sends a POST request with form data.

```bash
curl -X POST "http://localhost:8000/token" \
-H "Content-Type: application/x-www-form-urlencoded" \
-d "username=admin&password=admin"
```
The response will be a JSON object containing the access token.

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```
This token is then used to access protected endpoints.

```bash
curl -X GET "http://localhost:8000/api/users/me" \
-H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```
Sources: [tests/integration/test_api_integration.py:137-165]()

## Security Considerations

The current implementation uses a simple, in-memory user database defined in `api/auth.py`. This is suitable for development and demonstration but is not secure for a production environment. The `SECURITY.md` document recommends implementing JWT authentication, which has been done, but a production system should replace the hardcoded user store with a proper database.

- **User Storage**: The user database is hardcoded. For production, this should be migrated to a secure database system.
- **Secret Management**: The `SECRET_KEY` should be managed securely via environment variables or a secrets management service, not hardcoded or left as the default.
- **HTTPS**: In production, the API should be served over HTTPS to protect credentials and tokens in transit.

Sources: [api/auth.py:54-68](), [SECURITY.md:53-70]()

## Summary

The API authentication system provides a secure and standard way to protect endpoints using OAuth2 and JWT. It is configured via environment variables and relies on a core `auth` module for its logic. While the current user management is basic, the overall structure is robust and follows modern security practices recommended for web APIs. The integration tests confirm that the token issuance and validation flow works as expected.

### Gradio Application (Legacy)

<details>
<summary>Relevant source files</summary>
The following files were used as context for generating this wiki page:

- [app.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/app.py)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
- [UI_COMPARISON.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/UI_COMPARISON.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [pyproject.toml](https://github.com/DashFin/financial-asset-relationship-db/blob/main/pyproject.toml)
</details>

# Gradio Application (Legacy)

The Gradio application, defined in `app.py`, serves as the original, Python-native user interface for the Financial Asset Relationship Database. It provides an interactive web-based demo for visualizing the complex network of financial assets, exploring their relationships, and analyzing key metrics. Built using the Gradio library, it allows for rapid prototyping and direct interaction with the backend Python logic.

This application runs as a standalone web server and is launched via the command `python app.py`. While it remains fully functional, it is considered the legacy UI in comparison to the newer [Next.js Frontend](#), which offers a more modern and scalable architecture. The Gradio app is particularly suited for data scientists and Python developers who need a quick way to visualize and interact with the asset graph without requiring a separate frontend development environment.

*Sources: [app.py](), [UI_COMPARISON.md](), [README.md](), [ARCHITECTURE.md]()*

## Architecture and Core Components

The application's logic is encapsulated within the `FinancialAssetApp` class in `app.py`. This class manages the application state, handles data initialization, and defines the methods that respond to user interactions in the UI.

*Sources: [app.py:141-144]()*

### `FinancialAssetApp` Class

The `FinancialAssetApp` class is the central controller for the Gradio interface. It initializes the core `AssetRelationshipGraph` and connects UI components to backend data processing and visualization functions.

The diagram below shows the key methods within the `FinancialAssetApp` class.
```mermaid
classDiagram
    class FinancialAssetApp {
        +graph: AssetRelationshipGraph
        +__init__()
        -_initialize_graph()
        +ensure_graph() AssetRelationshipGraph
        +create_interface() Blocks
        +refresh_all_outputs() Tuple
        +refresh_visualization(...) Tuple
        +update_asset_info(asset_id) Tuple
        +generate_formulaic_analysis() Tuple
        +show_formula_details(formula_name) Tuple
        -_update_metrics_text() str
        -_format_formula_summary() str
    }
```
*Sources: [app.py:141-419]()*

### Key Methods

| Method | Description | Source |
| --- | --- | --- |
| `_initialize_graph()` | Initializes the `AssetRelationshipGraph` by calling `create_real_database()` to fetch data from Yahoo Finance. | `app.py:146-156` |
| `create_interface()` | Constructs the entire Gradio UI, defining all tabs, components, and their layouts. | `app.py:421-638` |
| `refresh_all_outputs()` | A master function that refreshes all visualizations and reports across all tabs simultaneously. | `app.py:206-236` |
| `refresh_visualization()` | Updates the 2D/3D network graph based on user-selected filters (e.g., view mode, relationship types). | `app.py:238-280` |
| `update_asset_info()` | Fetches and displays detailed JSON data for a selected asset in the "Asset Explorer" tab. | `app.py:189-204` |
| `generate_formulaic_analysis()` | Runs the `FormulaicdAnalyzer` and uses `FormulaicVisualizer` to create and display plots in the "Formulaic Analysis" tab. | `app.py:282-336` |

## Application Startup Flow

When the application is started with `python app.py`, it follows a clear initialization sequence before launching the web interface.

The following flowchart illustrates the startup process.
```mermaid
flowchart TD
    A[Start `python app.py`] --> B{`if __name__ == "__main__"`};
    B --> C[Instantiate `FinancialAssetApp`];
    C --> D[Call `app._initialize_graph()`];
    D --> E[Call `create_real_database()` from `real_data_fetcher.py`];
    E --> F[Fetch data from yfinance];
    F --> G[Create `AssetRelationshipGraph` instance];
    G --> H[Store graph in `app.graph`];
    H --> I[Call `app.create_interface()`];
    I --> J[Build Gradio UI components];
    J --> K[Call `demo.launch()`];
    K --> L[Gradio UI available at http://localhost:7860];
    E -- On Error --> M{Log Error & Raise};
```
*Sources: [app.py:641-648](), [app.py:146-156](), [README.md]()*

## User Interface Tabs

The UI is organized into several tabs, each serving a distinct purpose for exploring the financial asset data. The interface is built using Gradio and Plotly for visualizations.

*Sources: [app.py:424-533](), [AI_RULES.md]()*

| Tab Name | Purpose | Key Functions |
| --- | --- | --- |
| **Network Visualization (2D/3D)** | The main interactive view of the asset network. Supports 2D and 3D modes with extensive filtering. | `refresh_visualization`, `visualize_3d_graph_with_filters`, `visualize_2d_graph` |
| **Metrics & Analytics** | Displays quantitative statistics and charts about the network, such as asset distribution and relationship types. | `update_all_metrics_outputs`, `visualize_metrics` |
| **Schema & Rules** | Shows a generated report of the database schema, data models, and business rules for relationships. | `refresh_all_outputs`, `generate_schema_report` |
| **Asset Explorer** | Allows users to select a specific asset from a dropdown and view its detailed attributes and connections in JSON format. | `update_asset_info` |
| **Formulaic Analysis** | Provides advanced mathematical analysis, extracting and visualizing formulas and correlations between financial variables. | `generate_formulaic_analysis`, `show_formula_details` |
| **Documentation** | A static tab containing help text and a quick start guide on how to use the application. | N/A (Static Markdown) |

### Network Visualization Tab

This is the primary tab for visual exploration. It provides numerous controls to filter and customize the graph view.

#### Visualization Controls

| Control | Type | Options | Description | Source |
| --- | --- | --- | --- | --- |
| Visualization Mode | Radio | `3D`, `2D` | Toggles between 2D and 3D graph layouts. | `app.py:437` |
| 2D Layout Type | Radio | `spring`, `circular`, `grid` | Selects the algorithm for the 2D graph layout. Visible only in 2D mode. | `app.py:441` |
| Relationship Filters | Checkbox | (Multiple) | A series of checkboxes to toggle the visibility of different relationship types (e.g., "Same Sector", "Regulatory Impact"). | `app.py:451-465` |
| Show Direction Arrows | Checkbox | `True`, `False` | Toggles the visibility of arrows indicating relationship direction in the 3D view. | `app.py:466` |

*Sources: [app.py:432-466]()*

## Event Handling and Data Flow

User interactions in the Gradio UI trigger specific Python methods in the `FinancialAssetApp` class. The `gr.State` component is used to maintain the `AssetRelationshipGraph` object between events.

The sequence diagram below shows a typical user interaction: changing a filter and refreshing the 3D visualization.

```mermaid
sequenceDiagram
    participant User
    participant Gradio_UI as "Gradio UI"
    participant FinancialAssetApp as "app.py"
    participant GraphVisuals as "graph_visuals.py"

    User->>Gradio_UI: Clicks 'Show Regulatory' checkbox
    Gradio_UI->>FinancialAssetApp: Calls refresh_visualization()
    Note over FinancialAssetApp: Passes current state of all filter checkboxes

    FinancialAssetApp->>FinancialAssetApp: ensure_graph()
    FinancialAssetApp->>GraphVisuals: visualize_3d_graph_with_filters(graph, filters)
    GraphVisuals-->>FinancialAssetApp: Returns Plotly Figure object

    FinancialAssetApp-->>Gradio_UI: Returns Figure and error state
    Gradio_UI-->>User: Updates 3D Plot component
```
*Sources: [app.py:596-601](), [app.py:238-280]()*

## Dependencies

The Gradio application relies on several key Python libraries defined in the project's configuration.

| Library | Usage | Source |
| --- | --- | --- |
| `gradio` | The core framework for building the web UI. | `pyproject.toml:16` |
| `plotly` | The exclusive library used for all 2D and 3D visualizations. | `pyproject.toml:17` |
| `pandas` | Used for data manipulation before visualization. | `pyproject.toml:22` |
| `yfinance` | Fetches real-time financial data to populate the graph. | `pyproject.toml:20` |

*Sources: [pyproject.toml:15-23](), [AI_RULES.md]()*

## Conclusion

The `app.py` file provides a powerful, self-contained, and interactive tool for financial data analysis. As the original UI, it demonstrates the core value of the project by enabling direct, visual interaction with the asset relationship graph. While the project has evolved to include a more modern Next.js frontend, the Gradio application remains a valuable asset for rapid development, debugging, and Python-centric data exploration.

*Sources: [app.py](), [UI_COMPARISON.md]()*


## Frontend Components

### Next.js Frontend Overview

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [frontend/README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/README.md)
- [frontend/package.json](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/package.json)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
- [QUICK_START.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/QUICK_START.md)
- [TESTING_GUIDE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/TESTING_GUIDE.md)
- [frontend/__tests__/config/package-validation.test.ts](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/__tests__/config/package-validation.test.ts)
- [UI_COMPARISON.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/UI_COMPARISON.md)
</details>

# Next.js Frontend Overview

The Next.js frontend is a modern, responsive, and type-safe web application that serves as the primary user interface for the Financial Asset Relationship Database. It is built with Next.js 14, React 18, and TypeScript, offering a more feature-rich and customizable experience compared to the original Gradio UI. The application communicates with a dedicated FastAPI backend via a REST API to fetch and display complex financial data, including interactive 3D network graphs, analytical metrics, and a filterable asset explorer.

This frontend is designed for scalability and can be deployed on serverless platforms like Vercel. It provides a clear separation between the user interface and the core business logic, which is handled by the Python backend. For more information on the backend, see the [Architecture Overview](#architecture-overview).

Sources: [frontend/README.md](), [INTEGRATION_SUMMARY.md](), [UI_COMPARISON.md]()

## Architecture and Technology Stack

The frontend application is a client-side Next.js/React application that interacts with a Python-based FastAPI server. This architecture decouples the presentation layer from the data processing and business logic, enabling independent development and scaling.

Sources: [ARCHITECTURE.md:4-43](), [INTEGRATION_SUMMARY.md:65-95]()

This diagram illustrates the high-level system architecture, showing the interaction between the Next.js frontend, the FastAPI backend, and the core Python logic.
```mermaid
graph TD
    subgraph User_Browser
        A[Next.js UI on Port 3000]
    end

    subgraph Vercel_Platform
        B[FastAPI Backend on Port 8000]
        C[Core Business Logic<br>(asset_graph.py)]
    end

    A -- "REST API Calls (Axios)" --> B
    B -- "Direct Function Calls" --> C

    style A fill:#cde4ff
    style B fill:#d5f0d5
```
Sources: [ARCHITECTURE.md:120-136](), [INTEGRATION_SUMMARY.md:65-95]()

### Technology Stack

The frontend leverages a modern web development stack to deliver a high-quality user experience.

| Technology | Version | Purpose |
| --- | --- | --- |
| **Next.js** | `14.2.35` | React framework for server-side rendering, routing, and build optimization. |
| **React** | `^18.2.0` | UI library for building components. |
| **TypeScript** | `^5.3.0` | Provides static typing for code quality and maintainability. |
| **Tailwind CSS** | `^3.3.0` | A utility-first CSS framework for styling. |
| **Plotly.js** | `^2.27.0` | Library for creating interactive 2D and 3D visualizations. |
| **Recharts** | `^2.10.0` | A composable charting library built on React components. |
| **Axios** | `^1.13.2` | HTTP client for making REST API requests to the backend. |
| **Jest** | `^29.7.0` | Testing framework for unit and component tests. |
| **React Testing Library** | `^14.1.2` | Utilities for testing React components in a user-centric way. |

Sources: [frontend/package.json:15-39](), [frontend/README.md:63-69](), [ARCHITECTURE.md:100-107]()

## Project Structure

The `frontend` directory is organized to follow Next.js conventions, separating UI components, business logic, type definitions, and static assets.

This diagram shows the layout of the key directories within the `frontend` folder.
```mermaid
graph TD
    A(frontend/) --> B(app/)
    A --> C(public/)
    A --> D(package.json)
    A --> E(next.config.js)
    A --> F(tailwind.config.js)
    A --> G(__tests__/)

    B --> B1(components/)
    B --> B2(lib/)
    B --> B3(types/)
    B --> B4(page.tsx)
    B --> B5(layout.tsx)
    B --> B6(globals.css)

    B1 --> B1a(NetworkVisualization.tsx)
    B1 --> B1b(MetricsDashboard.tsx)
    B1 --> B1c(AssetList.tsx)

    B2 --> B2a(api.ts)
```
Sources: [frontend/README.md:38-53](), [INTEGRATION_SUMMARY.md:30-46]()

### Key Directories and Files

| Path | Description |
| --- | --- |
| `app/` | Contains all application routes, components, and logic, following the Next.js App Router convention. |
| `app/components/` | Houses reusable React components like `NetworkVisualization.tsx`, `MetricsDashboard.tsx`, and `AssetList.tsx`. |
| `app/lib/api.ts` | The API client module responsible for all communication with the backend. It uses `axios`. |
| `app/types/api.ts` | Contains TypeScript type definitions for API request and response objects. |
| `app/page.tsx` | The main entry point page for the application, which integrates all the major components into a tabbed interface. |
| `app/layout.tsx` | The root layout component for the application. |
| `public/` | Stores static assets like images and fonts. |
| `__tests__/` | Contains all Jest tests for components, libraries, and configuration. |
| `package.json` | Defines project metadata, dependencies, and npm scripts. |
| `next.config.js` | Configuration file for the Next.js framework. |
| `tailwind.config.js` | Configuration file for Tailwind CSS. |

Sources: [frontend/README.md:38-53](), [INTEGRATION_SUMMARY.md:30-46](), [TESTING_GUIDE.md:121-122]()

## Core Components

The UI is built from a set of modular React components, each responsible for a specific feature.

| Component | Description | Features |
| --- | --- | --- |
| **NetworkVisualization.tsx** | Renders the interactive 3D network graph of financial assets. | Uses Plotly.js, supports zoom/pan/rotate, displays node and edge details on hover. |
| **MetricsDashboard.tsx** | Displays key statistics and analytics about the asset network. | Shows total assets, relationships, network density, and asset class distribution. |
| **AssetList.tsx** | Provides a filterable and searchable table of all financial assets. | Allows filtering by asset class and sector. |

These components are integrated into the main page (`app/page.tsx`) and organized within a tabbed layout, allowing users to switch between different views of the data.

Sources: [frontend/README.md:40-43](), [INTEGRATION_SUMMARY.md:49-63](), [TESTING_GUIDE.md:121-122, 178-185]()

## Data Flow

User interactions in the frontend trigger API calls to the FastAPI backend to fetch data, which is then rendered by the React components. The `app/lib/api.ts` module centralizes all data-fetching logic.

The following sequence diagram shows the data flow for loading the 3D visualization.
```mermaid
sequenceDiagram
    participant User as User
    participant ReactComponent as "NetworkVisualization.tsx"
    participant ApiClient as "api.ts (Axios)"
    participant FastAPIServer as "FastAPI Backend"
    participant CoreLogic as "asset_graph.py"

    User->>ReactComponent: Navigates to Visualization Tab
    activate ReactComponent
    ReactComponent->>ApiClient: getVisualizationData()
    activate ApiClient
    ApiClient->>FastAPIServer: GET /api/visualization
    activate FastAPIServer
    FastAPIServer->>CoreLogic: get_3d_visualization_data()
    activate CoreLogic
    CoreLogic-->>FastAPIServer: { nodes: [...], edges: [...] }
    deactivate CoreLogic
    FastAPIServer-->>ApiClient: 200 OK with JSON data
    deactivate FastAPIServer
    ApiClient-->>ReactComponent: Returns visualization data
    deactivate ApiClient
    ReactComponent->>ReactComponent: Renders data with Plotly.js
    deactivate ReactComponent
```
Sources: [ARCHITECTURE.md:73-95](), [INTEGRATION_SUMMARY.md:10-23, 37-38]()

## Setup and Development

To run the frontend locally, a few setup steps are required.

### Prerequisites
- Node.js 18 or higher
- npm or yarn

Sources: [frontend/README.md:8-9]()

### Installation and Execution
1.  **Install dependencies** from the `frontend` directory:
    ```bash
    npm install
    ```
2.  **Configure environment variables**. Create a `.env.local` file in the `frontend` directory with the URL of the running backend API:
    ```env
    NEXT_PUBLIC_API_URL=http://localhost:8000
    ```
3.  **Run the development server**:
    ```bash
    npm run dev
    ```
The application will be available at `http://localhost:3000`.

Sources: [frontend/README.md:12-24](), [QUICK_START.md:41-52]()

### NPM Scripts

The `package.json` file defines several scripts for managing the development lifecycle.

| Script | Description |
| --- | --- |
| `dev` | Starts the Next.js development server with hot-reloading. |
| `build` | Creates an optimized production build of the application. |
| `start` | Starts the production server (requires a build first). |
| `lint` | Runs ESLint to check for code quality and style issues. |
| `test` | Runs the Jest test suite. |
| `test:watch` | Runs tests in interactive watch mode. |
| `test:coverage` | Runs tests and generates a code coverage report. |
| `test:ci` | Runs tests in a CI-friendly mode. |

Sources: [frontend/package.json:5-12](), [frontend/__tests__/config/package-validation.test.ts:88-95]()

## Testing

The frontend includes a comprehensive test suite using Jest and React Testing Library. Tests cover components, the API client, and configuration files.

- **Component Tests**: Verify that components render correctly, handle user interactions, and manage data states (loading, error, success). Key files tested include `AssetList.test.tsx`, `MetricsDashboard.test.tsx`, and `NetworkVisualization.test.tsx`.
- **API Client Tests**: The `api.test.ts` file ensures that the API client correctly calls backend endpoints, handles parameters, and manages success and error responses.
- **Configuration Tests**: The `package-validation.test.ts` file validates the `package.json` for correct dependencies, scripts, and versioning.

To run the tests, use the following commands from the `frontend` directory:
- `npm test`: Run all tests.
- `npm test -- --coverage`: Run tests with a coverage report.
- `npm test -- --watch`: Run tests in watch mode.

Sources: [frontend/README.md:28-36](), [TESTING_GUIDE.md:92-192]()

## Conclusion

The Next.js frontend provides a robust, modern, and maintainable interface for the Financial Asset Relationship Database. Its component-based architecture, separation from the backend API, and comprehensive testing strategy make it a scalable solution suitable for production deployment. It stands as a powerful alternative to the original Gradio UI, offering superior customization, user experience, and alignment with modern web development practices.

Sources: [UI_COMPARISON.md:13-33, 142-150](), [INTEGRATION_SUMMARY.md]()

### Frontend API Integration

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [frontend/app/lib/api.ts](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/app/lib/api.ts)
- [frontend/app/types/api.ts](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/app/types/api.ts)
- [frontend/__tests__/lib/api.test.ts](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/__tests__/lib/api.test.ts)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [TEST_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/TEST_SUMMARY.md)
- [frontend/README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/README.md)

</details>

# Frontend API Integration

The Frontend API integration layer is a TypeScript module that serves as the exclusive communication bridge between the Next.js frontend application and the backend FastAPI server. Its primary purpose is to provide a centralized, type-safe, and testable interface for all data-fetching operations. This module abstracts the underlying HTTP communication, handled by Axios, and exposes a set of asynchronous functions tailored to the application's data requirements, such as fetching assets, relationships, network metrics, and visualization data.

This system is a core part of the modern web interface, which runs parallel to the original Gradio UI. The architecture ensures a clean separation between the frontend presentation logic and the backend business logic, with this API client acting as the intermediary. For more information on the overall system design, see the [Architecture Overview](#architecture-overview).

Sources: [frontend/app/lib/api.ts](), [INTEGRATION_SUMMARY.md](), [ARCHITECTURE.md]()

## Architecture and Configuration

The API client is built around a pre-configured Axios instance. This instance sets the base URL for all API requests, which is dynamically sourced from an environment variable. This approach allows the application to seamlessly switch between different backend environments (e.g., local development, staging, production) without code changes.

Sources: [frontend/app/lib/api.ts:7-11](), [frontend/README.md]()

### Client Initialization

An Axios instance is created with the `baseURL` set to the value of `NEXT_PUBLIC_API_URL`. If this environment variable is not set, it defaults to `http://localhost:8000`, ensuring functionality in a standard local development setup.

```typescript
// Source: frontend/app/lib/api.ts:7-11
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 10000, // Example timeout
});
```
Sources: [frontend/app/lib/api.ts:7-11](), [frontend/README.md]()

The following diagram illustrates the configuration flow for the API client.

```mermaid
graph TD
    A[Environment] -- reads --> B(process.env.NEXT_PUBLIC_API_URL);
    B -- "Is it defined?" --> C{Use Value};
    B -- "Is it undefined?" --> D[Use Default 'http://localhost:8000'];
    C --> E[axios.create({ baseURL })];
    D --> E;
    E --> F(apiClient Instance);
```
This diagram shows how the `apiClient` instance is configured with the correct base URL.
Sources: [frontend/app/lib/api.ts:7-11](), [frontend/README.md]()

## API Client Functions

The module exports a collection of functions, each corresponding to a specific backend API endpoint. These functions encapsulate the logic for making the request, handling the response data, and managing potential errors.

Sources: [frontend/app/lib/api.ts](), [TEST_SUMMARY.md]()

### Endpoint Summary

The table below maps the client functions to their respective backend API endpoints.

| Function Name | HTTP Method | Endpoint Path | Description |
| :--- | :--- | :--- | :--- |
| `healthCheck` | `GET` | `/api/health` | Checks the health of the backend API. |
| `getAssets` | `GET` | `/api/assets` | Fetches a list of assets, with optional filtering. |
| `getAssetDetail` | `GET` | `/api/assets/{id}` | Fetches detailed information for a single asset. |
| `getAssetRelationships` | `GET` | `/api/assets/{id}/relationships` | Fetches relationships for a specific asset. |
| `getAllRelationships` | `GET` | `/api/relationships` | Fetches all relationships in the graph. |
| `getMetrics` | `GET` | `/api/metrics` | Fetches network-wide metrics. |
| `getVisualizationData` | `GET` | `/api/visualization` | Fetches data required for the 3D network graph. |
| `getAssetClasses` | `GET` | `/api/asset-classes` | Fetches the list of available asset classes. |
| `getSectors` | `GET` | `/api/sectors` | Fetches the list of available industry sectors. |

Sources: [frontend/app/lib/api.ts](), [INTEGRATION_SUMMARY.md](), [TEST_SUMMARY.md]()

### Function Details

#### `getAssets`
This function retrieves a list of financial assets. It supports optional filtering by `assetClass` and `sector`.

- **Parameters**:
  - `assetClass` (optional, `string`): The asset class to filter by.
  - `sector` (optional, `string`): The sector to filter by.
- **Returns**: `Promise<Asset[]>`

The function constructs query parameters dynamically based on the provided arguments.

Sources: [frontend/app/lib/api.ts:25-36]()

### API Call Flow Example

The following sequence diagram illustrates a typical flow when a frontend component calls the `getAssets` function.

```mermaid
sequenceDiagram
    participant Component as "React Component"
    participant APIClient as "api.ts"
    participant Axios as "Axios Instance"
    participant Backend as "FastAPI Backend"

    Component->>APIClient: getAssets({ assetClass: 'Equity' })
    activate APIClient
    APIClient->>Axios: apiClient.get('/api/assets', { params: { asset_class: 'Equity' } })
    activate Axios
    Axios->>Backend: GET /api/assets?asset_class=Equity
    activate Backend
    Backend-->>Axios: 200 OK (JSON: Asset[])
    deactivate Backend
    Axios-->>APIClient: Promise resolves with response
    deactivate Axios
    APIClient-->>Component: return response.data
    deactivate APIClient
```
This diagram shows the journey of a request from a React component to the backend and back.
Sources: [frontend/app/lib/api.ts:25-36](), [ARCHITECTURE.md]()

## Data Models and Types

To ensure type safety across the application, all data structures returned by the API are strictly typed using TypeScript interfaces defined in `frontend/app/types/api.ts`. These types are used as generics in the API client functions to provide compile-time checks and editor autocompletion.

Sources: [frontend/app/types/api.ts](), [TEST_SUMMARY.md]()

### Core Data Models

The diagram below shows the main data entities and their relationships.

```mermaid
classDiagram
    class Asset {
        +id: string
        +symbol: string
        +name: string
        +asset_class: string
        +sector: string
        +currency: string
        +market_cap: number
        +price: number
        +additional_fields: object
    }

    class Relationship {
        +source: string
        +target: string
        +type: string
        +strength: number
    }

    class Metrics {
        +total_assets: number
        +total_relationships: number
        +network_density: number
        +average_degree: number
        +max_degree: AssetDegree
        +asset_class_distribution: object
    }

    class VisualizationData {
        +nodes: Node[]
        +edges: Edge[]
    }

    class Node {
      +id: string
      +label: string
      +color: string
      +size: number
      +details: Asset
    }

    class Edge {
      +source: string
      +target: string
      +strength: number
    }

    VisualizationData "1" -- "0..*" Node
    VisualizationData "1" -- "0..*" Edge
    Node "1" -- "1" Asset : contains
    Edge "1" -- "1" Relationship : represents
```
This class diagram outlines the structure of the primary data types used in the API communication.
Sources: [frontend/app/types/api.ts](), [TEST_SUMMARY.md]()

### `Asset` Interface

| Property | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique identifier for the asset. |
| `symbol` | `string` | The ticker symbol or identifier. |
| `name` | `string` | The full name of the asset. |
| `asset_class` | `string` | The class of the asset (e.g., 'Equity', 'Bond'). |
| `sector` | `string` | The industry sector. |
| `currency` | `string` | The currency the asset is priced in (ISO code). |
| `market_cap`| `number` | The market capitalization. |
| `price` | `number` | The current price of the asset. |
| `additional_fields` | `Record<string, any>` | A key-value map for asset-specific data. |

Sources: [frontend/app/types/api.ts:1-11]()

## Error Handling

Error handling is implemented using `try...catch` blocks within each API function. The client is designed to catch errors thrown by Axios, which are typically instances of `AxiosError`. The caught error is logged to the console, and the function re-throws the error to allow the calling component to implement its own UI-specific error handling logic (e.g., displaying a notification or a fallback UI).

The test suite validates this behavior by mocking various error scenarios, including network errors, timeouts, and HTTP status codes like 404 and 500.

Sources: [frontend/app/lib/api.ts](), [frontend/__tests__/lib/api.test.ts]()

### Error Handling Flow

```mermaid
flowchart TD
    A[Component calls API function] --> B{try...catch block};
    B -- "try" --> C[apiClient makes HTTP request];
    C --> D{Request Successful?};
    D -- Yes --> E[Return response.data];
    D -- No --> F[Axios throws error];
    F --> G[catch (error) block];
    G --> H[Log error to console];
    H --> I[Re-throw error];
    I --> J[Calling component handles error];
    E --> J;
```
This flowchart shows the standardized error handling process for all API calls.
Sources: [frontend/app/lib/api.ts:13-23](), [frontend/__tests__/lib/api.test.ts]()

## Testing

The API client is extensively tested using Jest. The tests cover every exported function and validate multiple scenarios:
- **Configuration**: Ensures the Axios instance is created correctly.
- **Successful Responses**: Verifies that data is returned in the expected format.
- **Filtering**: Confirms that query parameters are correctly passed for functions like `getAssets`.
- **Error Handling**: Mocks network errors, HTTP 404/500 errors, and timeouts to ensure they are handled gracefully.
- **Type Safety**: The tests are written in TypeScript, implicitly validating the data models.

These tests provide a safety net against regressions and ensure the API client remains reliable and consistent with the backend contract.

Sources: [frontend/__tests__/lib/api.test.ts](), [TEST_SUMMARY.md](), [TESTING_GUIDE.md]()

### Component: NetworkVisualization

<details>
<summary>Relevant source files</summary>
The following files were used as context for generating this wiki page:

- [frontend/app/components/NetworkVisualization.tsx](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/app/components/NetworkVisualization.tsx)
- [frontend/__tests__/components/NetworkVisualization.test.tsx](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/__tests__/components/NetworkVisualization.test.tsx)
- [frontend/app/types/api.ts](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/app/types/api.ts)
- [frontend/app/page.tsx](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/app/page.tsx)
- [api/main.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/api/main.py)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
</details>

# Component: NetworkVisualization

The `NetworkVisualization` component is a client-side React component responsible for rendering an interactive 3D graph of financial assets and their relationships. It utilizes the `react-plotly.js` library to create the visualization based on data fetched from the backend API. This component is a core feature of the Next.js frontend, providing a visual representation of the interconnected financial network.

The component is designed to be integrated into a tabbed interface on the main application page, where it receives processed data and handles its own rendering logic, including loading and empty states.

Sources: [frontend/app/components/NetworkVisualization.tsx](), [frontend/app/page.tsx:16](), [ARCHITECTURE.md]()

## Component Architecture

The component receives visualization data as a prop and processes it into a format suitable for Plotly.js. Its internal logic handles different states: loading, empty data, and successful data rendering.

### Component Props

The component accepts a single prop:

| Prop  | Type                      | Description                               |
| :---- | :------------------------ | :---------------------------------------- |
| `data`  | `VisualizationData | null` | An object containing node and edge data for the graph, or `null` if data is loading. |

Sources: [frontend/app/components/NetworkVisualization.tsx:11]()

### State Management

The component is stateless and derives its entire view from the `data` prop. It implements conditional rendering based on the state of this prop:
1.  If `data` is `null`, it displays a "Loading visualization..." message.
2.  If `data` is present but `data.nodes` is an empty array, it displays a "No visualization data available." message.
3.  If `data` and `data.nodes` are populated, it renders the Plotly graph.

Sources: [frontend/app/components/NetworkVisualization.tsx:14-19]()

### Rendering Flow

The following diagram illustrates the component's rendering logic.

```mermaid
flowchart TD
    A[Component Renders] --> B{Is `data` prop null?};
    B -- Yes --> C[Display "Loading visualization..."];
    B -- No --> D{Is `data.nodes` empty?};
    D -- Yes --> E[Display "No visualization data available."];
    D -- No --> F[Process Nodes and Edges];
    F --> G[Configure Plotly Data and Layout];
    G --> H[Render Plotly 3D Graph];
```
*This diagram shows the conditional rendering path based on the `data` prop.*

Sources: [frontend/app/components/NetworkVisualization.tsx:13-89]()

## Data Processing

The component receives data structured according to the `VisualizationData` type and transforms it into traces for Plotly.

### Input Data Structure

The `data` prop conforms to the `VisualizationData` interface, which is defined in `frontend/app/types/api.ts`.

```mermaid
classDiagram
    class VisualizationData {
        +Node[] nodes
        +Edge[] edges
    }
    class Node {
        +string id
        +string label
        +string color
        +number size
        +number x
        +number y
        +number z
    }
    class Edge {
        +string source
        +string target
        +string color
        +number width
    }
    VisualizationData "1" *-- "0..*" Node
    VisualizationData "1" *-- "0..*" Edge
```
*This diagram shows the structure of the `VisualizationData` object, including its `Node` and `Edge` arrays.*

Sources: [frontend/app/types/api.ts:25-41]()

### Node and Edge Transformation

The component processes the `nodes` and `edges` arrays to create separate traces for the Plotly chart.

1.  **Node Processing**: It iterates through `data.nodes` to create a `scatter3d` trace. The `x`, `y`, `z`, `text`, `marker.color`, and `marker.size` properties are populated from the corresponding fields in each `Node` object.
    Sources: [frontend/app/components/NetworkVisualization.tsx:23-32]()

2.  **Edge Processing**: It constructs a `scatter3d` trace for the edges. For each edge, it finds the coordinates of the source and target nodes and adds them to `x`, `y`, and `z` arrays, with a `null` value in between to create separate lines for each edge.
    Sources: [frontend/app/components/NetworkVisualization.tsx:34-52]()

## Plotly Configuration

The visualization is configured through `data` (traces) and `layout` objects passed to the `Plot` component from `react-plotly.js`.

### Plotly Traces

Two `scatter3d` traces are generated: one for nodes and one for edges.

#### Node Trace (`nodeTrace`)

| Property        | Value                                         | Description                               |
| :-------------- | :-------------------------------------------- | :---------------------------------------- |
| `x`, `y`, `z`   | Arrays of coordinates from `data.nodes`       | Positions the nodes in 3D space.          |
| `text`          | Array of labels from `data.nodes`             | Text to display on hover.                 |
| `mode`          | `'markers'`                                   | Renders nodes as markers (points).        |
| `hoverinfo`     | `'text'`                                      | Shows only the `text` field on hover.     |
| `marker.color`  | Array of colors from `data.nodes`             | Sets the color for each node.             |
| `marker.size`   | Array of sizes from `data.nodes`              | Sets the size for each node.              |
| `marker.sizemode` | `'diameter'`                                | Interprets `size` as the marker diameter. |

Sources: [frontend/app/components/NetworkVisualization.tsx:21-33]()

#### Edge Trace (`edgeTrace`)

| Property      | Value                                                              | Description                               |
| :------------ | :----------------------------------------------------------------- | :---------------------------------------- |
| `x`, `y`, `z` | Arrays of interleaved source/target coordinates separated by `null` | Defines the start and end points for each edge line. |
| `mode`        | `'lines'`                                                          | Renders edges as lines.                   |
| `hoverinfo`   | `'none'`                                                           | Disables hover interactions for edges.    |
| `line.color`  | `'#888'`                                                           | Sets a default gray color for all edges.  |
| `line.width`  | `1`                                                                | Sets a default width for all edges.       |

Sources: [frontend/app/components/NetworkVisualization.tsx:34-53]()

### Plotly Layout

The `layout` object configures the overall appearance and behavior of the 3D scene.

| Property              | Value                                     | Description                                       |
| :-------------------- | :---------------------------------------- | :------------------------------------------------ |
| `title`               | `'Financial Asset Relationship Network'`  | The title of the graph.                           |
| `autosize`            | `true`                                    | Allows the plot to fill its container.            |
| `showlegend`          | `false`                                   | Hides the plot legend.                            |
| `scene.xaxis.visible` | `false`                                   | Hides the x-axis lines, labels, and grid.         |
| `scene.yaxis.visible` | `false`                                   | Hides the y-axis lines, labels, and grid.         |
| `scene.zaxis.visible` | `false`                                   | Hides the z-axis lines, labels, and grid.         |
| `margin`              | `{ l: 0, r: 0, b: 0, t: 40 }`             | Removes margins around the plot area.             |
| `paper_bgcolor`       | `'#f0f2f5'` (light) or `'#1a202c'` (dark) | Sets the background color of the plot container.  |
| `plot_bgcolor`        | `'#f0f2f5'` (light) or `'#1a202c'` (dark) | Sets the background color of the plotting area.   |

*Note: Background colors are conditionally set based on the theme, but the provided file only shows one set of values.*
Sources: [frontend/app/components/NetworkVisualization.tsx:55-73]()

## Integration

The `NetworkVisualization` component is used within the main application page, `frontend/app/page.tsx`.

```mermaid
sequenceDiagram
    participant Page as "app/page.tsx"
    participant API as "FastAPI Backend"
    participant Viz as "NetworkVisualization"

    Page->>API: GET /api/visualization
    API-->>Page: { nodes: [...], edges: [...] }
    Page->>Viz: Renders <NetworkVisualization data={vizData} />
    Note over Viz: Component processes data and renders Plotly graph
```
*This diagram shows how the main page fetches data and passes it to the `NetworkVisualization` component.*

In `page.tsx`, it is rendered inside a `TabsContent` container, making it visible when the "3D Visualization" tab is active. The `vizData` state from the page is passed directly to the component's `data` prop.

Sources: [frontend/app/page.tsx:16, 68-70](), [ARCHITECTURE.md]()

## Testing

The component is tested in `frontend/__tests__/components/NetworkVisualization.test.tsx`. The tests cover several key areas:

- **Rendering States**:
  - It correctly displays a loading message when `data` is `null`.
  - It correctly displays an empty state message when `data.nodes` is an empty array.
  - It renders the `Plot` component when valid data is provided.
- **Data Processing**:
  - It processes node data correctly into Plotly-compatible `x`, `y`, `z`, `color`, and `size` arrays.
  - It processes edge data correctly, ensuring source and target nodes are connected.
- **Plotly Configuration**:
  - It verifies that the `data` and `layout` props passed to the `Plot` component have the correct structure and values.
- **Edge Cases**:
  - Handles scenarios with a single node and no edges.
  - Handles empty data gracefully.

Sources: [frontend/__tests__/components/NetworkVisualization.test.tsx]()

## Summary

The `NetworkVisualization` component is a specialized, presentation-focused component that encapsulates the logic for displaying a complex 3D financial network graph. It effectively decouples the visualization logic from the data-fetching and state management concerns, which are handled by its parent component (`page.tsx`). By relying on a well-defined `VisualizationData` structure, it serves as a robust and testable module for the application's primary visual feature.

### Component: AssetList

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [frontend/app/components/AssetList.tsx](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/app/components/AssetList.tsx)
- [frontend/__tests__/components/AssetList.test.tsx](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/__tests__/components/AssetList.test.tsx)
- [frontend/app/lib/api.ts](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/app/lib/api.ts)
- [frontend/app/types/api.ts](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/app/types/api.ts)
- [TESTING_GUIDE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/TESTING_GUIDE.md)
- [frontend/README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/README.md)

</details>

# Component: AssetList

The `AssetList` is a stateful React component responsible for displaying a filterable and paginated list of financial assets. It fetches data from the backend API, manages loading and error states, and updates the view based on user interactions with filter and pagination controls. The component's state is synchronized with the URL query parameters, allowing for shareable and bookmarkable views.

Sources: [frontend/app/components/AssetList.tsx](), [frontend/README.md:30-34]()

## Architecture and Data Flow

The component's logic is centered around a `useEffect` hook that triggers data fetching whenever URL search parameters change. It uses hooks from `next/navigation` to read and write to the URL, creating a single source of truth for the component's state.

Sources: [frontend/app/components/AssetList.tsx:41-69]()

### Component Lifecycle and State Management

The following diagram illustrates the data flow from component mount to rendering the asset list.

```mermaid
flowchart TD
    subgraph AssetList Component
        A[Mount] --> B{Read URL Search Params};
        B --> C[Set Initial State (page, filters)];
        C --> D[useEffect Trigger];
        D --> E{Fetch Data from API};
        E -- Success --> F[Set Assets & Pagination Data];
        E -- Error --> G[Set Error State];
        F --> H[Render Asset Table & Filters];
        G --> I[Render Error Message];
    end

    subgraph User Interaction
        J[User changes filter/page] --> K[Update URL Search Params];
    end

    K --> D;
```
This diagram shows the reactive loop where changes to URL parameters trigger a data refetch.
Sources: [frontend/app/components/AssetList.tsx:28-69]()

### API Interaction

`AssetList` interacts with three main functions from the API client library (`app/lib/api.ts`):
1.  `api.getAssetClasses()`: To populate the "Asset Class" filter dropdown.
2.  `api.getSectors()`: To populate the "Sector" filter dropdown.
3.  `api.getAssets()`: To fetch the paginated list of assets based on current filters.

Sources: [frontend/app/components/AssetList.tsx:44-50](), [frontend/__tests__/components/AssetList.test.tsx:43-45]()

The following sequence diagram details the process of fetching assets.

```mermaid
sequenceDiagram
    participant User
    participant AssetList as "AssetList.tsx"
    participant APIClient as "api.ts"
    participant Backend as "Backend API"

    User->>AssetList: Changes filter (e.g., selects 'EQUITY')
    activate AssetList
    AssetList->>AssetList: handleFilterChange()
    AssetList->>AssetList: Updates URL with new search param
    Note over AssetList: useEffect hook is triggered by URL change
    AssetList->>APIClient: api.getAssets({ asset_class: 'EQUITY', ... })
    deactivate AssetList
    activate APIClient
    APIClient->>Backend: GET /api/assets?asset_class=EQUITY
    activate Backend
    Backend-->>APIClient: PaginatedAssetsResponse
    deactivate Backend
    APIClient-->>AssetList: Promise resolves with asset data
    deactivate APIClient
    activate AssetList
    AssetList->>AssetList: Updates state with new assets
    AssetList-->>User: Renders updated asset table
    deactivate AssetList
```
This diagram illustrates how a user filter change propagates through the component to the backend API and back to the UI.
Sources: [frontend/app/components/AssetList.tsx:41-69](), [frontend/app/lib/api.ts:20-33]()

### `getAssets` API Parameters

The `getAssets` function accepts several parameters to filter and paginate the results.

| Parameter | Type | Description | Source |
| :--- | :--- | :--- | :--- |
| `page` | `number` | The page number to retrieve. | `[frontend/app/lib/api.ts:21]()` |
| `per_page` | `number` | The number of assets to retrieve per page. | `[frontend/app/lib/api.ts:21]()` |
| `asset_class` | `string` | Filters assets by their class (e.g., 'EQUITY'). | `[frontend/app/lib/api.ts:21]()` |
| `sector` | `string` | Filters assets by their sector (e.g., 'Technology'). | `[frontend/app/lib/api.ts:21]()` |

## UI Components

### Filters

The "Filters" section contains two dropdown menus: "Asset Class" and "Sector".
- The options for these dropdowns are fetched from the `getAssetClasses` and `getSectors` API endpoints on component mount.
- Changing a filter's value triggers the `handleFilterChange` function, which updates the corresponding URL search parameter and resets the page to 1. This change automatically triggers a data refetch via the `useEffect` hook.

Sources: [frontend/app/components/AssetList.tsx:75-111](), [frontend/__tests__/components/AssetList.test.tsx:81-96]()

### Asset Table

The main content area is a table that displays the fetched assets. If the data is loading or an error occurs, a message is displayed instead.

| Column | Description | Data Type |
| :--- | :--- | :--- |
| **Symbol** | The asset's ticker symbol. | `string` |
| **Name** | The full name of the asset. | `string` |
| **Asset Class** | The class of the asset (e.g., EQUITY, BOND). | `string` |
| **Sector** | The industry sector of the asset. | `string` |
| **Price** | The current price of the asset. | `number` |
| **Market Cap** | The market capitalization of the asset. | `number` |
| **Currency** | The currency of the price and market cap. | `string` |

The data for this table corresponds to the `Asset` type definition.
Sources: [frontend/app/components/AssetList.tsx:125-163](), [frontend/app/types/api.ts:1-10]()

### Pagination

Pagination controls are rendered below the table.
- They include "Previous" and "Next" buttons.
- The component calculates whether to disable these buttons based on the current `page` and the `total` number of assets returned from the API.
- Clicking a button updates the `page` search parameter in the URL, triggering a refetch for the new page.

Sources: [frontend/app/components/AssetList.tsx:165-186](), [frontend/__tests__/components/AssetList.test.tsx:128-143]()

## Error Handling and Loading States

The component manages its state through `useState` hooks for `loading` and `error`.
- **Loading**: The `loading` state is `true` while an API request is in progress. The UI displays a "Loading results..." message.
- **Error**: If an API call fails, the `error` state is set with an error message. The UI displays an alert with the error, and the error is logged to the console via `console.error`.
- **Empty State**: If the API returns no assets, a "No assets found" message is displayed.

Sources: [frontend/app/components/AssetList.tsx:23-24, 60-64, 113-124](), [frontend/__tests__/components/AssetList.test.tsx:116-127]()

## Testing

The component is tested comprehensively in `AssetList.test.tsx`. The tests cover:
- Initial component rendering.
- Data loading and display from a mocked API.
- Functionality of asset class and sector filters.
- Pagination logic (next/previous page requests).
- Correct handling of loading, empty, and error states.
- Respecting initial state from URL query parameters on mount.

The tests use `jest.mock` to mock the `api` client and `next/navigation` hooks, ensuring the component's logic is tested in isolation.

Sources: [frontend/__tests__/components/AssetList.test.tsx](), [TESTING_GUIDE.md:73-93]()

## Summary

The `AssetList` component serves as a robust and interactive data browser for financial assets. By leveraging URL parameters for state management, it provides a clean, shareable, and bookmarkable user experience. Its clear separation of concerns—fetching data, managing state, and rendering UI—makes it a maintainable and central part of the application's frontend.


## Deployment and Infrastructure

### Local Development Setup

<details>
<summary>Relevant source files</summary>
The following files were used as context for generating this wiki page:
- [run-dev.sh](https://github.com/DashFin/financial-asset-relationship-db/blob/main/run-dev.sh)
- [run-dev.bat](https://github.com/DashFin/financial-asset-relationship-db/blob/main/run-dev.bat)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/SUMMARY.md)
- [frontend/README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/README.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
</details>

# Local Development Setup

The project supports multiple local development environments, including a modern Next.js frontend with a FastAPI backend, an original Gradio-based UI, and a containerized Docker setup. This guide provides instructions for setting up and running the application locally for development and testing purposes. The recommended setup for most developers is the Next.js and FastAPI combination, which can be launched with a single script.

For more information on the system's components and how they interact, refer to the [Architecture Overview](#architecture.md). For contribution guidelines, including coding standards and pull request processes, see the [Contributing Guide](#contributing.md).

## Prerequisites

Before starting, ensure you have the following tools installed on your system.

| Tool | Minimum Version | Source |
| --- | --- | --- |
| Python | 3.8+ | `CONTRIBUTING.md` |
| Node.js | 18+ | `README.md` |
| Git | N/A | `CONTRIBUTING.md` |
| Virtual Env Tool | `venv`, `virtualenv`, or `conda` | `CONTRIBUTING.md` |

Sources: [CONTRIBUTING.md:16-20](), [README.md:8-9]()

## Core Environment Setup

This initial setup is required for all development options except Docker. It involves creating a Python virtual environment and installing all necessary dependencies.

### 1. Clone the Repository

First, clone your fork of the repository to your local machine.
Sources: [CONTRIBUTING.md:25-28]()

### 2. Create and Activate Virtual Environment

It is crucial to use a virtual environment to isolate project dependencies.

**Create the environment:**
```bash
python -m venv .venv
```

**Activate the environment:**
-   **Windows (PowerShell):** `.\.venv\Scripts\Activate.ps1`
-   **Windows (Command Prompt):** `.venv\Scripts\activate.bat`
-   **macOS/Linux:** `source .venv/bin/activate`

Sources: [CONTRIBUTING.md:40-56](), [README.md:17-29]()

### 3. Install Dependencies

The project separates production and development dependencies. The `install-dev` Makefile command installs both.

```bash
# Install all dependencies using the Makefile
make install-dev
```
Alternatively, you can install them manually:
```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```
Sources: [CONTRIBUTING.md:58-68](), [SUMMARY.md:32-33]()

## Development Environment Options

The project can be run in three different modes for local development.

### Option 1: Next.js Frontend + FastAPI Backend (Recommended)

This setup runs the modern web frontend and the REST API backend. It is the recommended approach for most development tasks.

#### Automated Quick Start

The easiest way to start is by using the provided run scripts, which launch both the backend and frontend servers concurrently.

-   **Linux/macOS:** `./run-dev.sh`
-   **Windows:** `run-dev.bat`

This will start the FastAPI backend on `http://localhost:8000` and the Next.js frontend on `http://localhost:3000`.

The following diagram illustrates the process executed by the `run-dev` scripts.
```mermaid
flowchart TD
    A[Start run-dev.sh / run-dev.bat] --> B{Terminal 1};
    A --> C{Terminal 2};
    B --> D[Start FastAPI Backend];
    D --> E["uvicorn api.main:app --reload --port 8000"];
    C --> F[Start Next.js Frontend];
    F --> G["cd frontend && npm run dev"];
    E --> H[Backend running on port 8000];
    G --> I[Frontend running on port 3000];
```
Sources: [README.md:35-42](), [INTEGRATION_SUMMARY.md:129-137](), [run-dev.sh](), [run-dev.bat]()

#### Manual Setup

You can also start the servers manually in two separate terminals.

1.  **Start the FastAPI Backend (Terminal 1):**
    Ensure your Python virtual environment is activated.
    ```bash
    python -m uvicorn api.main:app --reload --port 8000
    ```
    The API and its auto-generated documentation will be available at `http://localhost:8000` and `http://localhost:8000/docs` respectively.

2.  **Start the Next.js Frontend (Terminal 2):**
    ```bash
    cd frontend
    npm install
    npm run dev
    ```
    The frontend application will be accessible at `http://localhost:3000`.

The local development architecture for this option is shown below.
```mermaid
graph TD
    subgraph "Developer Machine"
        Frontend["Next.js (npm run dev)<br>Port 3000"]
        Backend["FastAPI (uvicorn)<br>Port 8000"]
        Frontend -- "HTTP REST API" --> Backend
    end
```
Sources: [README.md:44-58](), [frontend/README.md:15-21](), [ARCHITECTURE.md:204-217]()

### Option 2: Gradio UI (Original)

This option runs the original Python-based Gradio interface. This is useful for tasks directly related to the `app.py` logic.

1.  Ensure your Python virtual environment is activated and dependencies are installed.
2.  Run the application:
    ```bash
    python app.py
    ```
3.  The application will be available at `http://localhost:7860`.

Sources: [README.md:11-33]()

### Option 3: Docker Installation (Alternative)

For a containerized environment that encapsulates all dependencies, you can use Docker.

1.  **Using Docker Compose (Recommended):**
    This command builds the necessary images and starts the services defined in `docker-compose.yml`.
    ```bash
    docker-compose up --build
    ```
    You can also use the Makefile shortcut:
    ```bash
    make docker-compose-up
    ```

2.  **Using Docker Directly:**
    This method builds a single image and runs the Gradio application.
    ```bash
    docker build -t financial-asset-db .
    docker run -p 7860:7860 financial-asset-db
    ```

Sources: [README.md:62-77]()

## Development Tools and Workflow

The repository is configured with a suite of tools to ensure code quality and consistency. These are managed via `pre-commit` hooks and `Makefile` commands.

### Pre-commit Hooks

Pre-commit hooks automatically run checks before each commit. It is highly recommended to install them.

```bash
# Install hooks
pre-commit install

# Or use the Makefile
make pre-commit
```

The hooks are configured in `.pre-commit-config.yaml` and run tools like `black`, `isort`, `flake8`, and `mypy`.
Sources: [CONTRIBUTING.md:70-76](), [SUMMARY.md:35-36](), [AUDIT_REPORT.md:195-204]()

### Makefile Commands

The `Makefile` provides shortcuts for common development tasks.

| Command | Description | Source |
| --- | --- | --- |
| `make help` | Show all available commands. | `SUMMARY.md` |
| `make install-dev` | Install both production and development dependencies. | `CONTRIBUTING.md` |
| `make check` | Run all checks: format, lint, type-check, and test. | `CONTRIBUTING.md` |
| `make format` | Format code with `black` and `isort`. | `CONTRIBUTING.md` |
| `make lint` | Run linters (`flake8` and `pylint`). | `CONTRIBUTING.md` |
| `make type-check` | Run `mypy` type checker. | `CONTRIBUTING.md` |
| `make test` | Run `pytest` with coverage. | `CONTRIBUTING.md` |
| `make test-fast` | Run `pytest` without coverage. | `CONTRIBUTING.md` |
| `make run` | Run the application (likely `python app.py`). | `SUMMARY.md` |

Sources: [SUMMARY.md:47-62](), [CONTRIBUTING.md:95-112]()

### Running Tests

The project has separate test suites for the backend and frontend.

#### Backend Testing (Python)

Use `pytest` to run the backend tests.
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src
```
Makefile shortcuts are also available: `make test` or `make test-fast`.
Sources: [CONTRIBUTING.md:173-189](), [README.md:188-196]()

#### Frontend Testing (TypeScript)

The frontend tests use Jest.
```bash
cd frontend

# Run all tests
npm test

# Run tests with coverage
npm test -- --coverage
```
Sources: [README.md:198-206](), [frontend/README.md:25-31]()

## Summary

The local development setup is flexible, offering a modern dual-server environment with Next.js and FastAPI, a legacy Gradio UI, and a containerized Docker option. The recommended path for most developers is the Next.js/FastAPI setup, which is easily launched using the `run-dev` scripts. The project is also equipped with a robust set of development tools, managed through `pre-commit` hooks and a `Makefile`, to streamline development and maintain high code quality.

### Docker Deployment

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [DOCKER.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/DOCKER.md)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [SECURITY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/SECURITY.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)

</details>

# Docker Deployment

The Financial Asset Relationship Database application can be deployed and run within Docker containers, providing a consistent and isolated environment. This approach simplifies dependency management and ensures the application runs the same way regardless of the host machine. Deployment can be managed using Docker Compose for multi-container setups (including an optional database) or by building and running the application container directly with Docker.

While automated CI/CD workflows for publishing Docker images were removed to streamline the build process, local Docker-based deployment remains a supported and documented method for running the application.

Sources: [DOCKER.md](), [README.md:49-62](), [AUDIT_REPORT.md:83-85]()

## Quick Start

There are two primary methods for launching the application with Docker.

### Using Docker Compose (Recommended)

This method builds and starts the application service defined in `docker-compose.yml`.

```bash
# Build and start the application
docker-compose up --build
```
The application will be accessible at `http://localhost:7860`.

Sources: [DOCKER.md:6-11](), [README.md:52-54]()

### Using Docker Directly

This method involves manually building the Docker image from the `Dockerfile` and then running it as a container.

```bash
# 1. Build the image
docker build -t financial-asset-db .

# 2. Run the container, mapping port 7860
docker run -p 7860:7860 financial-asset-db
```
The application will be accessible at `http://localhost:7860`.

Sources: [DOCKER.md:13-20](), [README.md:56-58]()

## Deployment Architecture

The Docker deployment isolates the application and its dependencies. The `docker-compose.yml` file orchestrates the services, including the main application and an optional PostgreSQL database.

Sources: [ARCHITECTURE.md:10-47](), [DOCKER.md:36-46]()

### Service Interaction

The following diagram illustrates the services defined in the Docker Compose setup.

```mermaid
graph TD
    subgraph Docker Environment
        App_Service[app: financial-asset-db]
        Postgres_Service[postgres (Optional)]
    end

    User[User] -->|HTTP Request on localhost:7860| App_Service
    App_Service -->|Connects via internal network| Postgres_Service

    style App_Service fill:#d4f0fd
    style Postgres_Service fill:#fcf3cf
```
This diagram shows the user accessing the `app` service, which can optionally connect to a `postgres` database service within the same Docker network.

Sources: [DOCKER.md:36-46]()

## Configuration

### Docker Compose Services

The `docker-compose.yml` file describes the services, networks, and volumes. Although the file is not present, `DOCKER.md` outlines its key components: an `app` service for the Gradio application and an optional `postgres` service for data persistence. The `app` service mounts the local `src/` directory for live development.

Sources: [DOCKER.md:24-28, 36-38]()

### Environment Variables

Application behavior is configured via environment variables set in `docker-compose.yml`.

| Variable | Description | Default Value |
| :--- | :--- | :--- |
| `GRADIO_SERVER_NAME` | The host address the Gradio server binds to. `0.0.0.0` makes it accessible externally. | `0.0.0.0` |
| `GRADIO_SERVER_PORT` | The port the Gradio server listens on inside the container. | `7860` |
| `DATABASE_URL` | The connection string for the PostgreSQL database. | `postgresql://finuser:changeme@postgres:5432/financial_assets` |

Sources: [DOCKER.md:48-53]()

### Port Mapping

To avoid conflicts, the host port can be changed in `docker-compose.yml`. The following example maps host port `8080` to the container's port `7860`.

```yaml
ports:
  - "8080:7860"  # Use port 8080 on the host
```
Sources: [DOCKER.md:100-103]()

## Dockerfile and Security

The project emphasizes security in its Docker configuration, following several best practices.

Sources: [SECURITY.md:13-18, 209-229](), [DOCKER.md:115-118]()

### Key Security Practices

- **Non-Root User**: The `Dockerfile` creates and switches to a non-root user named `appuser` to reduce potential security risks.
- **Minimal Base Image**: The image is based on `python:3.11-slim` to minimize the attack surface by excluding unnecessary packages.
- **No Hardcoded Secrets**: Secrets and passwords should be managed through environment variables or a secrets management tool, not hardcoded in the image.
- **Health Checks**: The application includes health checks that Docker can use to verify the container's status.

This diagram shows the flow for checking container health.
```mermaid
flowchart TD
    A[Docker Daemon] -- Periodically runs --> B{Health Check Command}
    B -- Success --> C[State: healthy]
    B -- Failure --> D[State: unhealthy]
```

Sources: [SECURITY.md:15, 212-213](), [DOCKER.md:88-93, 116]()

### Multi-Stage Build (Advanced)

For smaller production images, a multi-stage build is recommended. This separates the build environment from the runtime environment, ensuring the final image contains only the necessary artifacts.

```dockerfile
# Build stage
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["python", "app.py"]
```
Sources: [DOCKER.md:128-141]()

## Command Reference

The `DOCKER.md` file provides a comprehensive list of commands for managing the application with both Docker and Docker Compose.

### Docker Commands

| Command | Description |
| :--- | :--- |
| `docker build -t financial-asset-db .` | Build the Docker image. |
| `docker run -p 7860:7860 financial-asset-db` | Run the container and map ports. |
| `docker ps` | List running containers. |
| `docker logs -f <container_name>` | Follow the logs of a container. |
| `docker stop <container_name>` | Stop a running container. |
| `docker rm <container_name>` | Remove a stopped container. |
| `docker rmi <image_name>` | Remove a Docker image. |

Sources: [DOCKER.md:55-86]()

### Docker Compose Commands

| Command | Description |
| :--- | :--- |
| `docker-compose up` | Start services in the foreground. |
| `docker-compose up -d` | Start services in detached (background) mode. |
| `docker-compose down` | Stop and remove containers, networks. |
| `docker-compose down -v` | Stop and remove containers, networks, and volumes. |
| `docker-compose build` | Rebuild service images. |
| `docker-compose up --build` | Rebuild images and then start services. |
| `docker-compose logs -f app` | Follow logs for the `app` service. |

Sources: [DOCKER.md:88-113]()

## Summary

Docker provides a powerful and flexible way to run the Financial Asset Relationship Database locally. Using Docker Compose is the recommended approach as it simplifies the management of the application and its optional database service. The project incorporates security best practices into its Docker setup, such as using a non-root user and minimal base images, to provide a secure runtime environment.

Sources: [DOCKER.md](), [README.md:49-62]()

### Vercel Deployment

<details>
<summary>Relevant source files</summary>
The following files were used as context for generating this wiki page:

- [vercel.json](https://github.com/DashFin/financial-asset-relationship-db/blob/main/vercel.json)
- [DEPLOYMENT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/DEPLOYMENT.md)
- [VERCEL_DEPLOYMENT_CHECKLIST.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/VERCEL_DEPLOYMENT_CHECKLIST.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
- [tests/unit/test_dev_scripts.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/tests/unit/test_dev_scripts.py)
</details>

# Vercel Deployment

This project utilizes Vercel for deploying its integrated frontend and backend components. The deployment architecture consists of a Next.js frontend application and a Python-based FastAPI backend, which runs as a Vercel Serverless Function. This setup allows for a scalable, modern web application with a powerful Python backend for data processing and API services.

The Vercel deployment is configured to handle both the Next.js application and the Python API within a single project, routing requests appropriately based on the URL path. This guide provides a comprehensive overview of the deployment architecture, configuration, processes, and troubleshooting steps. For more details on the overall system design, see the [Architecture Overview](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md).

Sources: [DEPLOYMENT.md](), [ARCHITECTURE.md](), [INTEGRATION_SUMMARY.md]()

## Architecture on Vercel

The application is deployed on Vercel as a monorepo containing two primary components: the Next.js frontend and the FastAPI backend. Vercel automatically handles the build and deployment of both.

- **Next.js Frontend**: Served by Vercel's Edge Network, providing fast delivery of static assets and server-side rendered pages.
- **Python Backend**: The FastAPI application located in the `/api` directory is deployed as a Vercel Serverless Function. This function handles all API requests.

The diagram below illustrates the Vercel deployment architecture.

```mermaid
graph TD
    subgraph User
        A[Internet Users]
    end

    subgraph Vercel Platform
        A -- HTTPS --> B{Vercel Edge Network};
        B -- / (root) --> C[Next.js Frontend];
        B -- /api/... --> D[Python Serverless Function];

        subgraph Frontend
            C(Static Pages & React Components)
        end

        subgraph Backend
            D(FastAPI App)
        end

        C -.-> D;
    end

    style C fill:#f9f,stroke:#333,stroke-width:2px
    style D fill:#ccf,stroke:#333,stroke-width:2px
```
This diagram shows that user requests are routed by Vercel's Edge Network. Requests to the root path (`/`) are served by the Next.js frontend, while requests to `/api/...` are directed to the Python Serverless Function running the FastAPI application.

Sources: [ARCHITECTURE.md](), [DEPLOYMENT.md]()

## Deployment Configuration

The core of the Vercel deployment is managed by the `vercel.json` file located in the project root. This file instructs Vercel on how to build and route the different parts of the application.

Sources: [vercel.json](), [tests/unit/test_dev_scripts.py:15-23]()

### `vercel.json` Structure

The configuration is split into two main sections: `builds` and `routes`.

```json
{
  "builds": [
    {
      "src": "api/main.py",
      "use": "@vercel/python",
      "config": {
        "maxLambdaSize": "50mb"
      }
    },
    {
      "src": "frontend/package.json",
      "use": "@vercel/next"
    }
  ],
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "api/main.py"
    },
    {
      "src": "/(.*)",
      "dest": "frontend/$1"
    }
  ]
}
```
Sources: [vercel.json](), [VERCEL_DEPLOYMENT_CHECKLIST.md:126-135]()

#### Builds Configuration

The `builds` array defines how Vercel should compile the project source code.

| `src` | `use` | `config` | Description |
| :--- | :--- | :--- | :--- |
| `api/main.py` | `@vercel/python` | `{"maxLambdaSize": "50mb"}` | Specifies that the Python API entrypoint is `api/main.py` and should be built using the Vercel Python runtime. The `maxLambdaSize` is increased to 50MB to accommodate dependencies. |
| `frontend/package.json` | `@vercel/next` | N/A | Specifies that the `frontend` directory contains a Next.js application, identified by its `package.json` file. It will be built using the Vercel Next.js runtime. |

Sources: [vercel.json:2-15](), [VERCEL_DEPLOYMENT_CHECKLIST.md:126-135](), [tests/unit/test_dev_scripts.py:25-35]()

#### Routes Configuration

The `routes` array defines how incoming requests are routed to the built outputs.

The following diagram illustrates the routing logic defined in `vercel.json`.

```mermaid
flowchart TD
    A[Incoming Request] --> B{Path Matching};
    B -- "/api/..." --> C[Route to api/main.py];
    B -- "/..." --> D[Route to frontend];
```

| `src` | `dest` | Description |
| :--- | :--- | :--- |
| `/api/(.*)` | `api/main.py` | Any request path starting with `/api/` is rewritten and handled by the Python serverless function defined in `api/main.py`. |
| `/(.*)` | `frontend/$1` | All other requests are routed to the Next.js application in the `frontend` directory. |

Sources: [vercel.json:16-26](), [tests/unit/test_dev_scripts.py:37-45]()

## Deployment Process

There are two recommended methods for deploying the application to Vercel: GitHub Integration and the Vercel CLI.

Sources: [DEPLOYMENT.md:63-84](), [VERCEL_DEPLOYMENT_CHECKLIST.md:43-108]()

### GitHub Integration (Recommended)

This method provides continuous deployment, automatically deploying changes pushed to the repository.

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GitHub
    participant Vercel

    Dev->>GitHub: git push origin main
    activate GitHub
    GitHub->>Vercel: Webhook: Code pushed
    deactivate GitHub
    activate Vercel
    Vercel-->>Vercel: Auto-detects Next.js & Python
    Vercel-->>Vercel: Runs builds based on vercel.json
    Vercel-->>Vercel: Deploys to production URL
    deactivate Vercel
```
**Steps:**
1.  **Push to GitHub**: Ensure all code is committed and pushed to the `main` branch.
2.  **Connect to Vercel**: In the Vercel dashboard, create a "New Project" and import the GitHub repository.
3.  **Configure Project**: Vercel will auto-detect the Next.js framework. The root directory should be left as the default.
4.  **Set Environment Variables**: Add `NEXT_PUBLIC_API_URL` in the project settings.
5.  **Deploy**: Click "Deploy". Vercel will build and deploy the application.

Sources: [VERCEL_DEPLOYMENT_CHECKLIST.md:43-78](), [DEPLOYMENT.md:72-84]()

### Vercel CLI

This method is useful for manual deployments from your local machine.

1.  **Install Vercel CLI**:
    ```bash
    npm install -g vercel
    ```
2.  **Login**:
    ```bash
    vercel login
    ```
3.  **Deploy**: From the project root, run the deployment command and follow the prompts.
    ```bash
    # Deploy to production
    vercel --prod
    ```
Sources: [VERCEL_DEPLOYMENT_CHECKLIST.md:80-108](), [DEPLOYMENT.md:63-70]()

## Environment Variables

The frontend requires an environment variable to know the URL of the backend API.

| Variable | Description | Example Value (Production) |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | The absolute URL of the deployed backend API. The `NEXT_PUBLIC_` prefix makes it available in the browser. | `https://your-project.vercel.app` |

This variable must be set in the Vercel project settings under "Environment Variables". After the first deployment, you must update this variable with the actual Vercel project URL and redeploy if necessary.

Sources: [VERCEL_DEPLOYMENT_CHECKLIST.md:63-78, 100-103, 149-155](), [DEPLOYMENT.md:120-126]()

## Post-Deployment and Troubleshooting

After each deployment, it is crucial to verify that the application is functioning correctly. A checklist is provided for this purpose.

### Verification Checklist
- [ ] Open the deployed URL and check that the frontend loads without errors.
- [ ] Verify the API health by visiting `https://your-project.vercel.app/api/health`.
- [ ] Test the interactive API documentation at `https://your-project.vercel.app/docs`.
- [ ] Test all major features: 3D visualization, metrics, and the asset explorer.
- [ ] Check the browser console for any CORS or JavaScript errors.

Sources: [VERCEL_DEPLOYMENT_CHECKLIST.md:110-124]()

### Common Issues and Solutions

| Issue | Solution |
| :--- | :--- |
| **Build Failed** | Check build logs in the Vercel dashboard. Verify all dependencies are listed in `requirements.txt` and `frontend/package.json`. Run the build locally (`cd frontend && npm run build`) to debug. |
| **API Not Found (404)** | Ensure `vercel.json` is in the project root and correctly configured. Verify that `api/main.py` exists and is the correct entry point. |
| **CORS Errors** | The FastAPI backend must be configured to allow origins from your Vercel domain. Update the `allow_origins` list in `api/main.py`. |
| **Lambda Size Exceeded** | The Python serverless function has a size limit. This is pre-configured to `50mb` in `vercel.json`. If this error occurs, remove unused dependencies or consider lighter alternatives. |

Sources: [VERCEL_DEPLOYMENT_CHECKLIST.md:137-183]()

A code snippet for configuring CORS in `api/main.py`:
```python
# In api/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://*.vercel.app", "https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
Sources: [VERCEL_DEPLOYMENT_CHECKLIST.md:160-168]()

### Configuration

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [pyproject.toml](https://github.com/DashFin/financial-asset-relationship-db/blob/main/pyproject.toml)
- [api/main.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/api/main.py)
- [frontend/next.config.js](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/next.config.js)
- [Makefile](https://github.com/DashFin/financial-asset-relationship-db/blob/main/Makefile)
- [frontend/package.json](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/package.json)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/SUMMARY.md)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
- [.pre-commit-config.yaml](https://github.com/DashFin/financial-asset-relationship-db/blob/main/.pre-commit-config.yaml)
- [.flake8](https://github.com/DashFin/financial-asset-relationship-db/blob/main/.flake8)
- [requirements-dev.txt](https://github.com/DashFin/financial-asset-relationship-db/blob/main/requirements-dev.txt)

</details>

# Configuration

Configuration for the `financial-asset-relationship-db` project is managed through a combination of files that define the development environment, tool settings, application behavior, and deployment processes. The project uses a monorepo-like structure with distinct configurations for the Python backend and the Next.js frontend, unified by top-level tooling and scripts.

Key configuration files like `pyproject.toml`, `Makefile`, and `package.json` orchestrate a suite of development tools for testing, linting, and formatting, ensuring code quality and consistency. Application-level settings, such as API CORS policies and frontend build options, are handled within their respective codebases.

## Project-Level Configuration

Project-level configuration centralizes development tooling and provides a consistent interface for developers through `Makefile` commands.

Sources: [SUMMARY.md](), [CONTRIBUTING.md](), [AUDIT_REPORT.md]()

### Development Tooling (`pyproject.toml`)

The `pyproject.toml` file is the central configuration hub for Python development tools, standardizing settings for testing, formatting, and static analysis.

The diagram below shows the tools configured in `pyproject.toml`.

```mermaid
graph TD
    A[pyproject.toml] --> B[pytest]
    A --> C[coverage]
    A --> D[black]
    A --> E[isort]
    A --> F[mypy]
    A --> G[pylint]

    subgraph Testing
        B
        C
    end

    subgraph Formatting
        D
        E
    end

    subgraph Static Analysis
        F
        G
    end
```
Sources: [pyproject.toml](), [SUMMARY.md:83-90]()

| Tool | Purpose | Key Configurations |
| --- | --- | --- |
| `pytest` | Test runner | Verbose output, test markers (`unit`, `integration`, `slow`). |
| `coverage` | Code coverage | Generates HTML and XML reports, sets a failure threshold of 80%. |
| `black` | Code formatter | Line length set to 120, targets Python 3.8+. |
| `isort` | Import sorter | Uses a `black`-compatible profile. |
| `mypy` | Static type checker | Checks untyped definitions, warns on return issues. |
| `pylint` | Linter | Fails on a score below 8.0, ignores docstring warnings. |

Sources: [pyproject.toml](), [SUMMARY.md:83-90](), [AUDIT_REPORT.md:121-127]()

### Linter Configuration (`.flake8`)

While most tools are configured in `pyproject.toml`, `flake8` uses a dedicated `.flake8` file.

| Option | Value | Description |
| --- | --- | --- |
| `max-line-length` | 120 | Sets the maximum line length to 120 characters. |
| `max-complexity` | 15 | Sets the maximum cyclomatic complexity for functions. |
| `ignore` | E203, E501, W503 | Ignores specific error codes that conflict with `black`. |

Sources: [.flake8](), [SUMMARY.md:84](), [AUDIT_REPORT.md:129-134]()

### Development Commands (`Makefile`)

The `Makefile` provides a set of shortcut commands to simplify common development tasks, orchestrating the configured tools.

This diagram illustrates the workflow of the `make check` command.

```mermaid
flowchart TD
    Start(make check) --> Format{make format-check}
    Format --> Lint{make lint}
    Lint --> TypeCheck{make type-check}
    TypeCheck --> Test{make test}
    Test --> End(All Checks Pass)

    Format -- Fails --> Stop_Format(Stop & Report Error)
    Lint -- Fails --> Stop_Lint(Stop & Report Error)
    TypeCheck -- Fails --> Stop_Type(Stop & Report Error)
    Test -- Fails --> Stop_Test(Stop & Report Error)
```
Sources: [Makefile:54-55](), [SUMMARY.md:65-79]()

| Command | Description |
| --- | --- |
| `install-dev` | Installs both production and development dependencies. |
| `pre-commit` | Installs pre-commit hooks. |
| `format` | Formats code using `black` and `isort`. |
| `lint` | Runs linters (`flake8` and `pylint`). |
| `type-check` | Runs `mypy` for static type analysis. |
| `test` | Runs `pytest` with code coverage. |
| `check` | Runs all checks: format check, lint, type-check, and test. |

Sources: [Makefile](), [CONTRIBUTING.md:73-90]()

### Pre-commit Hooks

The `.pre-commit-config.yaml` file configures hooks that run automatically before each commit to ensure code quality.

The sequence diagram below shows the pre-commit process.
```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Git as Git Client
    participant Hooks as Pre-commit Hooks

    Dev->>Git: git commit -m "..."
    Git->>Hooks: Execute hooks on staged files
    activate Hooks
    Hooks->>Hooks: Run trailing-whitespace
    Hooks->>Hooks: Run end-of-file-fixer
    Hooks->>Hooks: Run check-yaml
    Hooks->>Hooks: Run black (formatter)
    Hooks->>Hooks: Run isort (importer sorter)
    Hooks->>Hooks: Run flake8 (linter)
    Hooks->>Hooks: Run mypy (type checker)
    alt All hooks pass
        Hooks-->>Git: Success
        Git-->>Dev: Commit successful
    else At least one hook fails
        Hooks--xGit: Failure
        Git--xDev: Commit failed, fix errors
    end
    deactivate Hooks
```
Sources: [.pre-commit-config.yaml](), [AUDIT_REPORT.md:154-164]()

## Backend API Configuration (`api/main.py`)

The FastAPI server configuration is defined directly within `api/main.py`.

### CORS Middleware

The API uses `CORSMiddleware` to control cross-origin requests from the frontend.

| Configuration | Description |
| --- | --- |
| `allow_origins` | A list of allowed origins, including localhost for development and Vercel deployment URLs. |
| `allow_credentials` | `True`, allows cookies to be included in cross-origin requests. |
| `allow_methods` | `["*"]`, allows all standard HTTP methods. |
| `allow_headers` | `["*"]`, allows all request headers. |

The allowed origins are dynamically generated based on the `VERCEL_URL` environment variable for production/preview deployments on Vercel, with localhost ports for local development.

Sources: [api/main.py:27-49]()

### Application Startup

The FastAPI application is launched using Uvicorn. The recommended command for development starts the server with auto-reloading on port 8000.

```bash
python -m uvicorn api.main:app --reload --port 8000
```
Sources: [README.md:52](), [QUICK_START.md:43]()

## Frontend Configuration

The Next.js frontend configuration is split between `package.json` for scripts and dependencies, and `next.config.js` for framework-specific settings.

### Scripts (`frontend/package.json`)

The `scripts` section in `package.json` defines commands for building, running, and testing the frontend application.

| Script | Command | Description |
| --- | --- | --- |
| `dev` | `next dev` | Starts the Next.js development server. |
| `build` | `next build` | Creates an optimized production build. |
| `start` | `next start` | Starts a production server. |
| `lint` | `next lint` | Runs the Next.js linter (ESLint). |
| `test` | `jest --silent` | Runs Jest tests. |
| `test:coverage` | `jest --coverage --silent` | Runs Jest tests and generates a coverage report. |

Sources: [frontend/package.json](), [frontend/__tests__/config/package-validation.test.ts:90-128]()

### Next.js Build (`frontend/next.config.js`)

The `next.config.js` file contains settings for the Next.js build process. The current configuration is minimal, enabling React's Strict Mode.

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

module.exports = nextConfig;
```
This setting helps identify potential problems in the application by running effects and checks twice in development mode.

Sources: [frontend/next.config.js:1-6]()

### Environment Variables

The frontend relies on an environment variable to locate the backend API.

| Variable | Description | Example |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | The base URL for the FastAPI backend. | `http://localhost:8000` |

This is configured in a `.env.local` file in the `frontend` directory, based on the `.env.example` template in the project root.

Sources: [INTEGRATION_SUMMARY.md:200-203](), [QUICK_START.md:49-51]()

## Deployment Configuration (`vercel.json`)

Deployment to Vercel is configured via `vercel.json`. This file defines how the project is built and how incoming requests are routed to either the Next.js frontend or the Python API.

The diagram below shows Vercel's request routing.

```mermaid
graph TD
    subgraph Vercel Platform
        A[Incoming Request] --> B{Request Path}
        B -- /api/* --> C[Python/FastAPI Backend]
        B -- else --> D[Next.js Frontend]
    end
```
This configuration ensures that API calls are correctly forwarded to the serverless Python function, while all other paths are handled by the Next.js application.

Sources: [INTEGRATION_SUMMARY.md:104-108](), [TESTING_GUIDE.md:65-68]()


## Extensibility and Customization

### How-To: Add a New Asset Type

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [src/models/financial_models.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/models/financial_models.py)
- [src/data/sample_data.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/data/sample_data.py)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [ARCHITECTURE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/ARCHITECTURE.md)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
- [INTEGRATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/INTEGRATION_SUMMARY.md)
</details>

# How-To: Add a New Asset Type

This guide provides a step-by-step process for extending the financial asset relationship database with a new asset type. The system is designed to be extensible, allowing developers to incorporate new financial instruments beyond the core classes of Equities, Bonds, Commodities, and Currencies.

Adding a new asset type primarily involves defining its data structure, adding it to the system's enumeration of asset classes, and implementing the logic that governs its relationships with other assets. Following these steps will ensure the new asset is properly integrated into the graph visualization, metrics calculation, and API responses.

Sources: [README.md](), [ARCHITECTURE.md]()

## Process Overview

The overall process for adding a new asset type involves modifications to the data, logic, and potentially the presentation layers.

This flowchart shows the high-level workflow for integrating a new asset type.
```mermaid
flowchart TD
    A[Step 1: Extend Data Model<br/>Create new dataclass] --> B[Step 2: Update AssetClass Enum<br/>Add new type to enum]
    B --> C[Step 3: Add Sample Data<br/>(Optional) Create sample instances]
    C --> D[Step 4: Define Relationship Rules<br/>Update AssetRelationshipGraph]
    D --> E[Step 5: Update Frontend<br/>(If needed) Modify types and components]
    E --> F[Step 6: Add Tests<br/>Unit and integration tests]
```
Sources: [README.md:112-122](), [CONTRIBUTING.md:195-203]()

## Step 1: Extend the Data Model

The first step is to define the data structure for the new asset. All asset types are Python dataclasses that inherit from the base `Asset` class defined in `src/models/financial_models.py`.

Sources: [AI_RULES.md:14](), [CONTRIBUTING.md:201]()

### Create a New Dataclass

Create a new Python file or add to the existing `financial_models.py` a new dataclass that inherits from `Asset`. This new class should include fields specific to the new asset type. The project standard is to use Python's `dataclasses` module for all structured data objects.

For example, to add a `Derivative` asset type:
```python
from src.models.financial_models import Asset, AssetClass

@dataclass
class Derivative(Asset):
    underlying_asset: str
    expiration_date: str
    strike_price: Optional[float] = None
```
Sources: [README.md:112-118](), [AI_RULES.md:37-38]()

The base `Asset` class provides a set of common fields that all asset types must have.

This class diagram illustrates how a new `Derivative` class inherits from the base `Asset` class, alongside other existing asset types.
```mermaid
classDiagram
    class Asset {
        +str id
        +str symbol
        +str name
        +AssetClass asset_class
        +str sector
        +str currency
        +float price
        +dict additional_fields
    }
    class Equity {
        +float pe_ratio
        +float dividend_yield
    }
    class Bond {
        +float yield
        +float duration
    }
    class Derivative {
        +str underlying_asset
        +str expiration_date
        +float strike_price
    }

    Asset <|-- Equity
    Asset <|-- Bond
    Asset <|-- Derivative
```
Sources: [README.md:112-118](), [src/models/financial_models.py]()

## Step 2: Update the `AssetClass` Enum

The `AssetClass` enumeration in `src/models/financial_models.py` is used to categorize and identify different types of assets throughout the application. You must add your new asset type to this enum.

```python
# In src/models/financial_models.py
from enum import Enum

class AssetClass(Enum):
    EQUITY = "Equity"
    BOND = "Fixed Income"
    COMMODITY = "Commodity"
    CURRENCY = "Currency"
    REGULATORY_EVENT = "Regulatory Event"
    DERIVATIVE = "Derivative" # Add the new type here
```
Sources: [AI_RULES.md:39-40](), [src/models/financial_models.py]()

## Step 3: Add Sample Data (Optional)

To test and visualize the new asset type, it is recommended to add sample instances to `src/data/sample_data.py`. This file is responsible for creating the initial dataset used in the application.

You would instantiate your new dataclass and add it to the list of assets that are loaded into the `AssetRelationshipGraph`.

Sources: [CONTRIBUTING.md:202](), [ARCHITECTURE.md:79-85]()

## Step 4: Define New Relationship Rules

The core of the system is the `AssetRelationshipGraph` in `src/logic/asset_graph.py`, which automatically discovers relationships between assets. To make the system aware of how your new asset type interacts with others, you must update the `_find_relationships` method within this class.

This method iterates through pairs of assets and appends relationship tuples `(type, strength, is_bidirectional)` based on custom logic.

The following flowchart shows the logic inside the `_find_relationships` method.
```mermaid
flowchart TD
    start[Start _find_relationships] --> loop{For each pair of assets (asset1, asset2)}
    loop --> check_type{Check asset types}
    check_type --> rule1{Is asset1 a Derivative and asset2 an Equity?}
    rule1 -- Yes --> check_underlying{Is asset1.underlying_asset == asset2.symbol?}
    check_underlying -- Yes --> add_rel[Add ("derivative_underlying", 0.95, False)]
    add_rel --> loop
    check_underlying -- No --> loop
    rule1 -- No --> other_rules(...)
    other_rules --> loop
    loop --> finish[End]
```
Sources: [README.md:120-122](), [ARCHITECTURE.md:46-53]()

Add a new conditional block to implement the logic for your new asset type. For example, to link a `Derivative` to its underlying `Equity`:
```python
# Add to _find_relationships() in AssetRelationshipGraph
if isinstance(asset1, Derivative) and isinstance(asset2, Equity):
    if asset1.underlying_asset == asset2.symbol:
        relationships.append(("derivative_underlying", 0.95, False))
```
Sources: [README.md:120-122]()

## Step 5: Update the Frontend (If Applicable)

If the new asset type has unique fields that need to be displayed in the user interface, you may need to update the frontend code. The project has a Next.js frontend that communicates with a FastAPI backend.

Key files to update include:
-   **`frontend/app/types/api.ts`**: Add the new asset type and its specific fields to the TypeScript interfaces to ensure type safety.
-   **`frontend/app/components/AssetList.tsx`**: Modify the component to display the new fields in the asset explorer table.
-   **`api/main.py`**: Ensure the FastAPI endpoint serializes the new asset's fields correctly.

Sources: [INTEGRATION_SUMMARY.md:41-58](), [frontend/README.md:41-51]()

## Step 6: Add Tests

Finally, it is crucial to add tests for the new functionality. The project uses `pytest` for backend testing.

-   **Unit Tests**: Add tests to `tests/unit/test_models.py` to validate the new dataclass, including any custom validation in `__post_init__`.
-   **Integration Tests**: Add tests to `tests/unit/test_graph.py` to verify that the new relationship rules are correctly identified and that metrics are calculated properly with the new asset type included.

Follow the guidelines in `CONTRIBUTING.md` for writing and running tests. New features must be accompanied by tests.

Sources: [CONTRIBUTING.md:129-170](), [AUDIT_REPORT.md:111-128]()

## Summary

Adding a new asset type is a structured process that touches multiple layers of the application architecture. By extending the data model, updating enums, defining relationship logic, and adding tests, you can seamlessly integrate new financial instruments into the system. This modular design is a core strength of the `financial-asset-relationship-db` project, enabling it to evolve and support a wider range of financial analysis scenarios.

Sources: [ARCHITECTURE.md:173-182](), [README.md:109-110]()

### How-To: Create Custom Relationship Rules

<details>
<summary>Relevant source files</summary>
The following files were used as context for generating this wiki page:
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [src/logic/asset_graph.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/src/logic/asset_graph.py)
- [AI_RULES.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AI_RULES.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [IMPROVEMENTS.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/IMPROVEMENTS.md)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)
</details>

# How-To: Create Custom Relationship Rules

The financial asset relationship database is designed to automatically discover connections between different financial assets. This guide explains how developers can extend the system by defining and implementing custom relationship rules. The core of this functionality resides in the `AssetRelationshipGraph` class, which processes assets and identifies relationships based on a predefined set of rules.

Creating a custom rule involves defining the conditions under which two assets are considered related, the type of relationship, and its relative strength. This process typically requires modifying the core relationship discovery engine and may involve extending the existing data models to support new asset types or attributes.

Sources: [README.md:82-85](), [src/logic/asset_graph.py]()

## Understanding Core Components

Before creating a new rule, it's essential to understand the primary components that govern asset relationships.

Sources: [README.md:65-76](), [AI_RULES.md:31-34]()

### Asset Data Models

All assets in the system are defined using Python `dataclasses`. There is a base `Asset` class, and specific asset types like `Equity`, `Bond`, and `Commodity` inherit from it. To create rules for a new type of asset, you must first define its model.

The diagram below shows the inheritance structure of the core financial models.

```mermaid
classDiagram
    direction LR
    class Asset {
        +id: str
        +symbol: str
        +name: str
        +asset_class: AssetClass
        +price: float
    }
    class Equity {
        +sector: str
        +market_cap: float
    }
    class Bond {
        +issuer: str
        +credit_rating: str
    }
    class Commodity {
        +unit: str
    }
    class Currency {
        +country: str
    }

    Asset <|-- Equity
    Asset <|-- Bond
    Asset <|-- Commodity
    Asset <|-- Currency
```
This class diagram illustrates the inheritance hierarchy for financial asset models.

Sources: [AUDIT_REPORT.md:21-25](), [AI_RULES.md:31-34]()

### The Relationship Discovery Engine

The `AssetRelationshipGraph` class is the engine for relationship management. The automatic discovery process is handled by the `build_relationships()` method, which in turn calls the private `_find_relationships()` method. This is the primary location for adding custom rule logic.

The `_find_relationships()` method iterates through all possible pairs of assets in the graph and applies a series of conditional checks to identify relationships.

The following sequence diagram shows the high-level flow when discovering relationships.

```mermaid
sequenceDiagram
    participant App as "Application"
    participant Graph as "AssetRelationshipGraph"
    App->>Graph: build_relationships()
    activate Graph
    Graph->>Graph: _find_relationships()
    Note over Graph: Iterates through all asset pairs
    Graph->>Graph: add_relationship(source, target, type, strength)
    deactivate Graph
    App-->>App: Relationships built
```
This diagram shows the method calls involved in the automatic relationship discovery process.

Sources: [README.md:85](), [src/logic/asset_graph.py]()

## Step-by-Step Guide to Creating a Custom Rule

Follow these steps to add a new relationship rule to the system.

### 1. Define or Extend Asset Models (If Necessary)

If your new rule involves a new type of financial instrument, you must first define it as a `dataclass` that inherits from `Asset`. The project standards mandate the use of `dataclasses` for all structured data objects.

For example, to add a rule for derivatives, you would first define a `Derivative` class.

```python
from dataclasses import dataclass
from typing import Optional
from src.models.financial_models import Asset, AssetClass

@dataclass
class Derivative(Asset):
    underlying_asset: str
    expiration_date: str
    strike_price: Optional[float] = None
```
*Source: [README.md:88-96]()*

Sources: [README.md:88-96](), [AI_RULES.md:31-34]()

### 2. Modify the Relationship Discovery Logic

The logic for all relationship rules is centralized in the `_find_relationships()` method within `src/logic/asset_graph.py`. This method contains a nested loop that compares every asset with every other asset.

The general flow of this method is as follows:
1.  Iterate through each asset (`asset1`).
2.  Iterate through each subsequent asset (`asset2`) to form a pair.
3.  Apply a series of `if` statements to check the types and attributes of `asset1` and `asset2`.
4.  If a condition is met, create a relationship tuple and append it to a list.
5.  After checking all conditions for the pair, add the identified relationships to the graph.

The flowchart below visualizes this process.

```mermaid
flowchart TD
    A[Start _find_relationships] --> B{Loop through all asset pairs};
    B --> C[Get asset1, asset2];
    C --> D{Check Rule 1: Same Sector?};
    D -- Yes --> E[Append 'same_sector' relationship];
    D -- No --> F{Check Rule 2: Corporate Bond?};
    E --> F;
    F -- Yes --> G[Append 'corp_bond_to_equity' relationship];
    F -- No --> H{...Check other rules...};
    G --> H;
    H -- Yes --> I[Append custom relationship];
    H -- No --> J[End of checks for pair];
    I --> J;
    J --> B;
    B -- All pairs checked --> K[Add all found relationships to graph];
    K --> L[End];
```
This diagram shows the logical flow for checking relationship rules between asset pairs.

Sources: [src/logic/asset_graph.py](), [README.md:85]()

### 3. Implement the Rule Logic

To implement your custom rule, add a new `if` block inside the nested loop in `_find_relationships()`. This block should check the asset types and the specific attributes that define the relationship.

When a relationship is found, you must create a tuple with the following structure and append it to the `relationships` list.

| Element         | Type    | Description                                                                 |
| --------------- | ------- | --------------------------------------------------------------------------- |
| `type`          | `str`   | A unique name for the relationship (e.g., `derivative_underlying`).         |
| `strength`      | `float` | A normalized value from 0.0 to 1.0 indicating the relationship's strength.  |
| `bidirectional` | `bool`  | `True` if the relationship is symmetric (A->B and B->A), `False` otherwise. |

*Source: [src/logic/asset_graph.py]()*

Here is an example of adding a rule to link a `Derivative` to its underlying `Equity`.

```python
# Add to _find_relationships() in AssetRelationshipGraph
if isinstance(asset1, Derivative) and isinstance(asset2, Equity):
    if asset1.underlying_asset == asset2.symbol:
        relationships.append(("derivative_underlying", 0.95, False))
```
*Source: [README.md:99-102]()*

This code checks if one asset is a `Derivative` and the other is an `Equity`. If the derivative's underlying asset symbol matches the equity's symbol, it creates a directional relationship with a strength of 0.95.

## Best Practices and Configuration

### Managing Relationship Strengths

The codebase has been identified as having hardcoded "magic numbers" for relationship strengths (e.g., `0.7` for `same_sector`). It is recommended to extract these values into a centralized configuration file, such as `src/config.py`, to improve maintainability.

| Relationship Type          | Hardcoded Strength | Recommended Constant         |
| -------------------------- | ------------------ | ---------------------------- |
| `same_sector`              | `0.7`              | `SAME_SECTOR_STRENGTH`       |
| `corporate_bond_to_equity` | `0.9`              | `CORPORATE_BOND_STRENGTH`    |
| `currency_exposure`        | `0.8`              | `CURRENCY_EXPOSURE_STRENGTH` |

*Source: [IMPROVEMENTS.md:23-39]()*

### Testing Your New Rule

All new features and bug fixes must be accompanied by tests. When you add a new relationship rule, you should also add a corresponding unit test to validate its behavior.

1.  **Test Structure**: Tests for the graph logic are located in `tests/unit/test_asset_graph.py`.
2.  **Fixtures**: Use shared fixtures from `tests/conftest.py` to create sample assets for your test cases.
3.  **Test Case**: Write a test function that:
    *   Creates an `AssetRelationshipGraph`.
    *   Adds the specific assets needed to trigger your new rule.
    *   Calls `build_relationships()`.
    *   Asserts that the new relationship was created correctly with the expected type and strength.

*Sources: [CONTRIBUTING.md:129-161](), [AUDIT_REPORT.md:105-118]()*

## Summary

Creating a custom relationship rule is a straightforward process that extends the core functionality of the application. The key steps are to define the necessary asset models, add conditional logic to the `_find_relationships` method in `AssetRelationshipGraph`, and provide comprehensive tests to ensure the rule functions as expected. By centralizing rule strengths and following the established testing patterns, you can contribute new, maintainable, and robust features to the relationship discovery engine.


## Development and Testing

### Testing Strategy

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [TESTING_GUIDE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/TESTING_GUIDE.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)
- [tests/unit/test_documentation_validation.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/tests/unit/test_documentation_validation.py)
- [tests/integration/test_workflow_documentation.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/tests/integration/test_workflow_documentation.py)
- [COMPREHENSIVE_TEST_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/COMPREHENSIVE_TEST_SUMMARY.md)
- [TEST_DOCUMENTATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/TEST_DOCUMENTATION_SUMMARY.md)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [TESTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/TESTING.md)

</details>

# Testing Strategy

The project employs a comprehensive testing strategy that covers both the Python backend and the TypeScript/React frontend. The approach emphasizes unit and integration tests to ensure code quality, data integrity, and prevent regressions. The strategy also includes unique validation for documentation and configuration files, treating them as critical project artifacts. The core frameworks are `pytest` for the backend and `Jest` with `@testing-library/react` for the frontend.

The testing infrastructure was a significant addition to the project, which initially had no tests. The current suite includes over 140 test cases across backend and frontend, validating everything from API endpoints and component rendering to Markdown file structure and dependency consistency.

*Sources: [TESTING_GUIDE.md](), [AUDIT_REPORT.md:21-26](), [CONTRIBUTING.md:113-145]()*

## Test Architecture

The testing architecture is segregated by application layer (backend, frontend) and test type (unit, integration). This separation ensures clarity and maintainability.

This diagram illustrates the high-level organization of the test suites.
```mermaid
graph TD
    subgraph Testing
        A[Test Suites] --> B[Backend Tests];
        A --> C[Frontend Tests];
        A --> D[Documentation & Config Tests];
    end

    subgraph Backend
        B --> B1[Pytest];
        B1 --> B2[Unit Tests: `tests/unit`];
        B1 --> B3[Integration Tests: `tests/integration`];
    end

    subgraph Frontend
        C --> C1[Jest];
        C1 --> C2[Component Tests: `frontend/__tests__/components`];
        C1 --> C3[API Client Tests: `frontend/__tests__/lib`];
    end

    subgraph Docs_and_Config
        D --> D1[Pytest];
        D1 --> D2[Markdown Validation: `test_documentation_validation.py`];
        D1 --> D3[Config Validation: `test_config_validation.py`];
        D1 --> D4[Requirements Validation: `test_requirements.py`];
    end
```
*Sources: [AUDIT_REPORT.md:104-112](), [CONTRIBUTING.md:114-120](), [TESTING_GUIDE.md:18, 59]()*

### Directory Structure

The project organizes test files into dedicated directories:

| Path | Description |
| --- | --- |
| `tests/` | Root directory for all backend Python tests. |
| `tests/unit/` | Contains unit tests for isolated backend components like API endpoints and data models. |
| `tests/integration/` | Contains integration tests for backend components, such as documentation and workflow validation. |
| `tests/conftest.py` | Provides shared `pytest` fixtures for backend tests. |
| `frontend/__tests__/` | Root directory for all frontend TypeScript/React tests. |

*Sources: [AUDIT_REPORT.md:104-112](), [CONTRIBUTING.md:114-120]()*

## Backend Testing (Python)

Backend testing is performed using `pytest` and focuses on the FastAPI application, data models, and core logic. The suite covers API endpoints, CORS configuration, Pydantic model validation, and error handling.

*Sources: [TESTING_GUIDE.md:18-58](), [TEST_SUMMARY.md:10-56]()*

### Key Test Areas

- **API Endpoints**: All REST endpoints are tested for correct responses, query parameter handling, and filtering logic.
- **CORS and Security**: `TestValidateOrigin` ensures that Cross-Origin Resource Sharing (CORS) rules correctly validate origins from localhost and Vercel deployments, preventing unauthorized access.
- **Concurrency**: Tests verify that the core `AssetRelationshipGraph` is initialized in a thread-safe manner.
- **Model Validation**: Pydantic response models are validated to ensure data integrity and correct structure.
- **Error Handling**: The system is tested against invalid requests, server errors, and 404 not-found scenarios.

This class diagram shows some of the key test classes for the backend.
```mermaid
classDiagram
    direction LR
    class TestValidateOrigin {
        +test_http_localhost_dev()
        +test_vercel_url()
        +test_invalid_domain()
    }
    class TestAPIEndpoints {
        +test_get_all_assets()
        +test_filter_by_asset_class()
        +test_asset_detail_retrieval()
        +test_network_metrics()
    }
    class TestErrorHandling {
        +test_server_error_handling()
        +test_404_responses()
    }
    class TestConcurrency {
        +test_thread_safe_double_check_locking()
    }
```
*Sources: [TESTING_GUIDE.md:37-54](), [TEST_SUMMARY.md:16-56]()*

### Test Fixtures
Shared test data and setup are managed using fixtures in `tests/conftest.py`. This includes sample assets (`sample_equity`, `sample_bond`) and graph instances (`empty_graph`, `populated_graph`), promoting test isolation and reusability.

*Sources: [AUDIT_REPORT.md:114-122]()*

## Frontend Testing (TypeScript)

Frontend testing uses `Jest` and `@testing-library/react` to validate React components, the API client, and user interactions. Tests are located in the `frontend/__tests__` directory.

*Sources: [TESTING_GUIDE.md:59-130](), [README.md:191-199]()*

### Key Test Areas

- **API Client (`api.test.ts`)**: The Axios-based API client is extensively tested to verify correct endpoint calls, parameter handling, and response data parsing. All API methods, including `getAssets`, `getAssetDetail`, and `getVisualizationData`, are covered.
- **React Components**: Components like `AssetList`, `MetricsDashboard`, and `NetworkVisualization` are tested for rendering, data loading, user interactions (e.g., filtering), and handling of empty or error states.
- **Mock Data Validation**: A dedicated test file, `frontend/__tests__/test-utils.test.ts`, validates all mock data objects used in the test suite to ensure they conform to TypeScript interfaces and maintain data integrity.
- **Page-Level Integration**: The main application page is tested to ensure correct component integration, tab switching, and data loading flows.

This diagram shows the structure of the frontend test suites.
```mermaid
graph TD
    subgraph Frontend_Tests
        FT[Jest Test Suites] --> API[API Client: api.test.ts];
        FT --> Comp[Component Tests];
        FT --> Mock[Mock Data Validation: test-utils.test.ts];
        FT --> Page[Page Integration: page.test.tsx];
    end

    subgraph Components
        Comp --> AL[AssetList.test.tsx];
        Comp --> MD[MetricsDashboard.test.tsx];
        Comp --> NV[NetworkVisualization.test.tsx];
    end
```
*Sources: [TESTING_GUIDE.md:61-130](), [COMPREHENSIVE_TEST_SUMMARY.md:20-44]()*

## Documentation and Configuration Testing

A unique aspect of this project's testing strategy is the validation of non-code artifacts like Markdown documentation and configuration files. These tests run within the `pytest` framework and ensure that project metadata and documentation remain accurate and well-formatted.

*Sources: [TEST_DOCUMENTATION_SUMMARY.md](), [tests/unit/test_documentation_validation.py]()*

### Documentation Validation
Tests in `tests/unit/test_documentation_validation.py` and `tests/integration/test_workflow_documentation.py` validate `.md` files for:
- **Structure**: Presence of required titles and sections (e.g., `## Overview`).
- **Formatting**: Correct Markdown syntax, no trailing whitespace, and proper code block closure.
- **Content Accuracy**: Mentions of key files and technologies (e.g., `pytest`, `pr-agent.yml`).
- **Consistency**: Cross-validation between different documentation files to ensure file counts and other metrics match.
- **Security**: Checks for hardcoded secrets like GitHub tokens.

The following class diagram outlines the test classes responsible for documentation validation.
```mermaid
classDiagram
    class TestDependencyMatrix {
        +test_file_counts_match()
        +test_dependency_format()
    }
    class TestSystemManifest {
        +test_has_project_overview()
        +test_directory_structure_format()
    }
    class TestDocumentationConsistency {
        +test_file_counts_match_between_documents()
        +test_timestamps_are_recent()
    }
    class TestDocumentationRealisticContent {
        +test_documented_files_exist()
        +test_documented_dependencies_are_real_packages()
    }
    class TestSecurityAndBestPractices {
        +test_no_hardcoded_secrets()
    }

    TestDependencyMatrix --|> DocumentationValidation
    TestSystemManifest --|> DocumentationValidation
    TestDocumentationConsistency --|> DocumentationValidation
    TestDocumentationRealisticContent --|> DocumentationValidation
    TestSecurityAndBestPractices --|> DocumentationValidation
```
*Sources: [TEST_DOCUMENTATION_SUMMARY.md:21-65](), [tests/unit/test_documentation_validation.py](), [tests/integration/test_documentation_validation.py:228-244]()*

### Configuration and Dependency Testing
Tests like `tests/unit/test_config_validation.py` and `tests/integration/test_requirements.py` validate:
- **JSON/YAML Syntax**: Ensures configuration files like `vercel.json` and `.github/workflows/pr-agent.yml` are well-formed.
- **Dependency Integrity**: `requirements.txt` and `package.json` are checked for required packages, consistent versioning, and security pins.

*Sources: [TESTING_GUIDE.md:40-58](), [TEST_GENERATION_SUMMARY.md:10-31](), [COMPREHENSIVE_TEST_SUMMARY.md:83-85]()*

## Execution and CI/CD

Tests are designed to be run locally by developers and automatically in a CI/CD pipeline.

*Sources: [CONTRIBUTING.md:99-111](), [TESTING_GUIDE.md:132-171]()*

### Local Execution

| Environment | Command | Description |
| --- | --- | --- |
| **Backend** | `pytest` | Runs all Python tests. |
| | `pytest --cov=api --cov=src` | Runs tests with a coverage report. |
| **Frontend** | `cd frontend && npm test` | Runs all TypeScript/React tests. |
| | `cd frontend && npm test -- --coverage` | Runs frontend tests with coverage. |
| **All Checks** | `make check` | A utility command to run formatting, linting, type-checking, and all tests. |

*Sources: [CONTRIBUTING.md:104, 133-145](), [TESTING_GUIDE.md:134-158](), [README.md:185-212]()*

### CI/CD Integration

Tests are integrated into a GitHub Actions workflow (`.github/workflows/ci.yml`), which runs on every push and pull request.

This flowchart shows the CI testing pipeline.
```mermaid
flowchart TD
    A[Push or PR] --> B{CI Workflow};
    B --> C[Backend Job];
    B --> D[Frontend Job];

    subgraph C [Backend Job]
        C1[Setup Python] --> C2[Install Dependencies];
        C2 --> C3[Lint & Format Check];
        C3 --> C4[Run Pytest];
    end

    subgraph D [Frontend Job]
        D1[Setup Node.js] --> D2[Install Dependencies];
        D2 --> D3[Run Jest Tests];
    end
```
*Sources: [TESTING_GUIDE.md:239-268](), [AUDIT_REPORT.md:144-155]()*

### Pre-commit Hooks
To ensure code quality before commits, the project uses `pre-commit` hooks. These hooks automatically run formatters (`black`, `isort`), linters (`flake8`), and type checkers (`mypy`), catching issues early.

*Sources: [CONTRIBUTING.md:86-92](), [AUDIT_REPORT.md:159-168]()*

## Conclusion

The testing strategy for the Financial Asset Relationship Database is robust and multi-faceted. It provides comprehensive coverage for backend logic, frontend components, and critical project artifacts like documentation and configuration. By integrating automated checks into both pre-commit hooks and the CI/CD pipeline, the strategy enforces high standards of quality and stability, enabling developers to contribute with confidence.

*Sources: [AUDIT_REPORT.md:255-265](), [SUMMARY.md:167-171]()*

### Running Tests

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [pyproject.toml](https://github.com/DashFin/financial-asset-relationship-db/blob/main/pyproject.toml)
- [conftest.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/conftest.py)
- [frontend/jest.config.js](https://github.com/DashFin/financial-asset-relationship-db/blob/main/frontend/jest.config.js)
- [test_scripts.sh](https://github.com/DashFin/financial-asset-relationship-db/blob/main/test_scripts.sh)
- [TESTING_GUIDE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/TESTING_GUIDE.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [tests/integration/test_documentation_validation.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/tests/integration/test_documentation_validation.py)
- [COMPREHENSIVE_TEST_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/COMPREHENSIVE_TEST_SUMMARY.md)
- [TEST_DOCUMENTATION_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/TEST_DOCUMENTATION_SUMMARY.md)
</details>

# Running Tests

The project employs a comprehensive testing strategy that covers both the Python backend and the Next.js frontend, ensuring code quality, stability, and correctness. The testing infrastructure is built around industry-standard tools: `pytest` for the backend and `Jest` with `React Testing Library` for the frontend. With over 140 test cases, the suite validates everything from API endpoints and component rendering to configuration files and documentation integrity.

This guide provides a detailed overview of the testing architecture, command-line execution, and the different types of tests available in the repository. For more information on development workflows, see the [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md) guide.

Sources: [TESTING_GUIDE.md:5-8](), [CONTRIBUTING.md:100-103](), [README.md:144-146]()

## Test Architecture Overview

The project maintains two parallel testing stacks, one for the Python backend and one for the TypeScript/React frontend. This separation allows for isolated, framework-specific testing while ensuring complete coverage of the application.

The following diagram illustrates the high-level testing architecture.

```mermaid
graph TD
    subgraph Backend Testing [Python]
        B1[Pytest] --> B2{Test Runner};
        B3[tests/unit] --> B1;
        B4[tests/integration] --> B1;
        B5[conftest.py] --> B1;
        B6[pyproject.toml] -- config --> B1;
    end

    subgraph Frontend Testing [TypeScript/React]
        F1[Jest] --> F2{Test Runner};
        F3[frontend/__tests__] --> F1;
        F4[React Testing Library] --> F1;
        F5[jest.config.js] -- config --> F1;
        F6[package.json] -- scripts --> F1;
    end

    subgraph CI/CD [GitHub Actions]
        G1[Push/PR] --> G2{Run Tests};
        G2 --> B2;
        G2 --> F2;
    end

    B2 --> B7[Coverage Report];
    F2 --> F7[Coverage Report];
```
This diagram shows the separate testing stacks for the backend (Pytest) and frontend (Jest), both of which are executed during the CI/CD process.

Sources: [TESTING_GUIDE.md:10-21](), [CONTRIBUTING.md:105-112](), [AUDIT_REPORT.md:104-107]()

## Backend Testing (Python)

The backend test suite uses `pytest` to validate the FastAPI application, core logic, data models, and configuration files. Tests are organized into `unit` and `integration` directories.

Sources: [TESTING_GUIDE.md:23-25](), [CONTRIBUTING.md:105-112]()

### Structure and Configuration

-   **Test Runner**: `pytest`
-   **Configuration**: `pyproject.toml` defines pytest settings, including test paths and markers.
-   **Fixtures**: Shared test fixtures, such as `sample_equity` and `populated_graph`, are defined in `tests/conftest.py` to provide reusable data for tests.
-   **Directory Structure**:
    -   `tests/unit/`: For isolated tests of individual components, such as API endpoints or data models.
    -   `tests/integration/`: For tests that verify interactions between multiple components or validate entire files (e.g., documentation, requirements).

Sources: [CONTRIBUTING.md:105-112](), [AUDIT_REPORT.md:113-122](), [TEST_DOCUMENTATION_SUMMARY.md:11]()

### Test Coverage

The backend tests provide extensive coverage, including:
-   API endpoints, query parameters, and filtering.
-   CORS configuration and security validation.
-   Pydantic model validation and error handling.
-   Thread-safe graph initialization.
-   Configuration file validation (`vercel.json`, `requirements.txt`).
-   Documentation file integrity and formatting.

Sources: [TESTING_GUIDE.md:31-59](), [TEST_DOCUMENTATION_SUMMARY.md:15-49]()

### Running Backend Tests

The following table summarizes the commands used to run backend tests. These can be executed directly or via the `Makefile`.

| Command | Description | Source |
| :--- | :--- | :--- |
| `pytest` | Runs all tests in the `tests/` directory. | [CONTRIBUTING.md:126]() |
| `pytest -v` | Runs all tests with verbose output. | [TESTING_GUIDE.md:121]() |
| `pytest --cov=api --cov=src` | Runs tests and generates a coverage report. | [TESTING_GUIDE.md:124]() |
| `pytest -m unit` | Runs only tests marked with the `unit` marker. | [CONTRIBUTING.md:132]() |
| `make test` | Makefile shortcut to run tests with coverage. | [CONTRIBUTING.md:87]() |
| `make lint` | Runs linters like `flake8` and `pylint`. | [CONTRIBUTING.md:84]() |

## Frontend Testing (TypeScript)

The frontend test suite uses `Jest` and `React Testing Library` to validate React components, the API client, and configuration files.

Sources: [TESTING_GUIDE.md:61-66](), [README.md:157-159]()

### Structure and Configuration

-   **Test Runner**: `Jest`, configured via `frontend/jest.config.js`.
-   **Utilities**: `React Testing Library` is used for rendering components and simulating user interactions.
-   **Setup**: `frontend/jest.setup.js` configures the test environment, including mocks for browser APIs like `window.matchMedia`.
-   **Test Location**: All test files are located within the `frontend/__tests__` directory, mirroring the structure of the `app` directory.

Sources: [TESTING_GUIDE.md:61-66](), [TEST_SUMMARY.md:88-96]()

### Test Coverage

Frontend tests validate:
-   The API client library (`app/lib/api.ts`), including all endpoint functions and error handling.
-   React components, covering rendering, data loading, user interactions (filtering), and empty/error states.
-   The main application page, including tab switching and component integration.
-   Configuration files like `package.json` and `package-lock.json` for dependency integrity.

Sources: [TESTING_GUIDE.md:68-117](), [TEST_GENERATION_REPORT.md:21-46]()

### Running Frontend Tests

The following commands are run from the `frontend/` directory.

| Command | Description | Source |
| :--- | :--- | :--- |
| `npm test` | Runs all frontend tests. | [TESTING_GUIDE.md:133]() |
| `npm run test:watch` | Runs tests in interactive watch mode. | [TESTING_GUIDE.md:136]() |
| `npm run test:coverage` | Runs tests and generates a coverage report. | [TESTING_GUIDE.md:139]() |
| `npm test -- AssetList.test.tsx` | Runs tests for a specific file. | [TESTING_GUIDE.md:94]() |

## Specialized Test Suites

Beyond typical unit and integration tests, the project includes specialized suites to ensure the quality of documentation and configuration.

Sources: [COMPREHENSIVE_TEST_SUMMARY.md:92-109](), [TEST_DOCUMENTATION_SUMMARY.md]()

### Documentation Validation

A unique feature of this project's test suite is the validation of Markdown documentation files. These tests ensure that documentation remains accurate, well-formatted, and maintainable.

The following diagram shows the validation flow for a documentation file.

```mermaid
flowchart TD
    A[pytest runs test_documentation_validation.py] --> B{Load .md File};
    B --> C[Check Existence & Readability];
    B --> D[Validate Structure];
    D --> D1[Has H1 Title];
    D --> D2[Has Required Sections];
    B --> E[Validate Formatting];
    E --> E1[No Trailing Whitespace];
    E --> E2[Code Blocks Closed];
    B --> F[Validate Content];
    F --> F1[Mentions Key Files];
    F --> F2[No Hardcoded Secrets];
    C & D & E & F --> G[Test Passed/Failed];
```

These tests are located in files like `tests/integration/test_documentation_validation.py` and `tests/unit/test_documentation_validation.py`. They check for:
-   Correct Markdown syntax and heading structure.
-   Presence of required sections like "Overview".
-   Absence of hardcoded secrets.
-   Consistency of information between different documentation files.

Sources: [tests/integration/test_documentation_validation.py](), [TEST_DOCUMENTATION_SUMMARY.md:15-49]()

### Configuration File Validation

Tests are in place to validate various configuration files, preventing common errors related to dependencies and deployment settings.

-   **`requirements.txt` / `requirements-dev.txt`**: Tests ensure required packages are present, versions are correctly specified, and security pins are in place.
-   **`package.json` / `package-lock.json`**: Tests validate dependency versions, script availability, and integrity between the two files.
-   **`vercel.json` / `tsconfig.json`**: Deployment and TypeScript compiler settings are validated for correctness.

Sources: [TEST_GENERATION_SUMMARY.md:14-35](), [TESTING_GUIDE.md:47-59](), [TEST_GENERATION_REPORT.md:21-72]()

## CI/CD Integration

All tests are designed to run automatically in the CI/CD pipeline using GitHub Actions. The workflow is configured to execute both backend and frontend test suites on every push and pull request, ensuring that no failing tests are merged into the main branch.

The CI pipeline performs the following steps:
1.  Checks out the code.
2.  Sets up Python and Node.js environments.
3.  Installs backend and frontend dependencies.
4.  Runs the respective test suites, often with coverage reporting.

Sources: [TESTING_GUIDE.md:169-194](), [AUDIT_REPORT.md:138-148]()

### CI/CD Workflows

<details>
<summary>Relevant source files</summary>
The following files were used as context for generating this wiki page:

- [tests/integration/test_github_workflows.py](https://github.com/DashFin/financial-asset-relationship-db/blob/main/tests/integration/test_github_workflows.py)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)
- [SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/SUMMARY.md)
- [CHANGELOG.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CHANGELOG.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [BRANCH_CLEANUP_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/BRANCH_CLEANUP_SUMMARY.md)
- [README.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/README.md)
- [COMPREHENSIVE_TEST_SUMMARY.md](httpshttps://github.com/DashFin/financial-asset-relationship-db/blob/main/COMPREHENSIVE_TEST_SUMMARY.md)

</details>

# CI/CD Workflows

The project employs a streamlined and robust set of CI/CD workflows managed through GitHub Actions. The system was significantly refactored to remove 23 irrelevant workflow files for technologies not used in the project (like .NET, Docker, and Node.js), consolidating the pipeline into a few focused, Python-centric workflows. This cleanup reduced CI/CD resource usage and improved maintainability. The core of the CI strategy is a consolidated pipeline (`ci.yml`) for testing and quality checks, supplemented by automated PR management (`pr-agent.yml`), security scanning, and branch maintenance.

A key feature of this repository is that the workflows themselves are subject to comprehensive integration testing using `pytest`. These tests validate YAML syntax, structure, security best practices, and action configurations, ensuring the CI/CD infrastructure remains reliable and secure. This approach prevents common workflow errors like duplicate keys or invalid syntax from being merged.

Sources: [AUDIT_REPORT.md:40-47, 102-113](), [SUMMARY.md:12-20](), [tests/integration/test_github_workflows.py]()

## Workflow Architecture

The project utilizes several GitHub Actions workflows, each triggered by different events, to automate testing, security scanning, PR management, and repository maintenance. The main workflows are `ci.yml`, `pr-agent.yml`, `codeql.yml`, `dependency-review.yml`, and `branch-cleanup.yml`.

This diagram illustrates the high-level architecture of the GitHub Actions workflows, their triggers, and their primary functions.
```mermaid
graph TD
    subgraph Triggers
        A[Push to main]
        B[Pull Request]
        C[PR Comment / Review]
        D[Weekly Schedule]
    end

    subgraph Workflows
        W1[ci.yml]
        W2[pr-agent.yml]
        W3[codeql.yml]
        W4[dependency-review.yml]
        W5[branch-cleanup.yml]
    end

    subgraph Actions
        J1[Run Tests & Quality Checks]
        J2[Automated PR Review & Merge]
        J3[Static Code Analysis (Security)]
        J4[Dependency Vulnerability Scan]
        J5[Identify Stale Branches]
    end

    A --> W1
    B --> W1
    B --> W4
    C --> W2
    D --> W3
    D --> W5

    W1 --> J1
    W2 --> J2
    W3 --> J3
    W4 --> J4
    W5 --> J5
```
Sources: [SUMMARY.md:104-109](), [AUDIT_REPORT.md:109-113](), [BRANCH_CLEANUP_SUMMARY.md:21-28](), [tests/integration/test_github_workflows.py:215-220]()

## Consolidated CI Pipeline (`ci.yml`)
Sources: [SUMMARY.md:104-119](), [AUDIT_REPORT.md:102-113]()

The `ci.yml` workflow is the primary CI/CD pipeline, responsible for running a suite of quality and security checks on every push and pull request to the `main` branch. It replaced several redundant Python-specific workflows like `python-app.yml` and `pylint.yml`. The pipeline is structured into two main jobs: `test` and `security`.

The flow diagram below shows the sequence of jobs and steps within the `ci.yml` pipeline.
```mermaid
flowchart TD
    Start[Trigger: Push/PR] --> TestJob{Test Job};

    subgraph TestJob [Python Matrix: 3.8, 3.9, 3.10, 3.11, 3.12]
        direction LR
        T1[Install Deps] --> T2[Lint] --> T3[Format Check] --> T4[Type Check] --> T5[Run Pytest]
    end

    TestJob --> SecurityJob{Security Job};
    subgraph SecurityJob
        direction LR
        S1[Scan with bandit] --> S2[Scan with safety]
    end

    SecurityJob --> Finish[End]
```
Sources: [SUMMARY.md:107-119](), [AUDIT_REPORT.md:105-108]()

### Test Job
The `test` job runs in a matrix across multiple Python versions to ensure compatibility. It performs a sequence of checks, and a failure in any step will fail the job.

| Python Versions Tested |
| :--------------------- |
| 3.8                    |
| 3.9                    |
| 3.10                   |
| 3.11                   |
| 3.12                   |

Sources: [SUMMARY.md:108-109]()

The steps executed in the `test` job are:
1.  **Install Dependencies**: Installs production and development dependencies from `requirements.txt` and `requirements-dev.txt`, using a cache to speed up builds.
2.  **Lint**: Runs `flake8` and `pylint` to check for code style and errors.
3.  **Format Check**: Runs `black` and `isort` to ensure code is formatted correctly.
4.  **Type Check**: Runs `mypy` for static type checking.
5.  **Test**: Executes the `pytest` suite with coverage reporting. Coverage reports are uploaded as artifacts.

Sources: [SUMMARY.md:109-112](), [CONTRIBUTING.md:79-92]()

### Security Job
The `security` job runs after the `test` job completes successfully. It uses two tools to scan for potential security vulnerabilities:
*   **`safety`**: Checks for known vulnerabilities in installed Python dependencies.
*   **`bandit`**: Performs static security analysis on the Python codebase to find common security issues.

Sources: [SUMMARY.md:115-118](), [AUDIT_REPORT.md:108]()

## PR Agent Workflow (`pr-agent.yml`)
Sources: [tests/integration/test_github_workflows.py:207-404]()

The `pr-agent.yml` workflow automates pull request reviews, comments, and merging based on specific triggers like PR review comments. It is designed to respond to commands like `@copilot` in comments. The workflow is composed of three distinct jobs.

### Jobs
| Job Name             | Description                                                                                             |
| :------------------- | :------------------------------------------------------------------------------------------------------ |
| `pr-agent-trigger`   | The main job that runs on PR comments or reviews. It lints, tests, and posts results back to the PR.      |
| `auto-merge-check`   | Checks if a PR can be auto-merged based on approval status and successful checks.                         |
| `dependency-update`  | Auto-approves and merges dependency updates from trusted bots like Dependabot and Renovate.               |

Sources: [tests/integration/test_github_workflows.py:414-424]()

### Trigger and Logic Flow
The workflow uses conditional logic (`if`) to execute jobs based on the event context.

This diagram shows the conditional logic for the `pr-agent.yml` jobs.
```mermaid
flowchart TD
    subgraph Triggers
        T1[PR Comment with '@copilot']
        T2[PR Review 'CHANGES_REQUESTED']
        T3[PR Sync with 'approved' review]
        T4[PR from Dependabot/Renovate]
    end

    subgraph Jobs
        J1[pr-agent-trigger]
        J2[auto-merge-check]
        J3[dependency-update]
    end

    T1 --> J1
    T2 --> J1
    T3 --> J2
    T4 --> J3

    J1 --> J1_S1[Setup Env] --> J1_S2[Install Deps] --> J1_S3[Lint & Test] --> J1_S4[Post Comment to PR]
```
Sources: [tests/integration/test_github_workflows.py:440-447, 532-542, 550-556]()

### Permissions
The workflow requests specific, limited permissions to follow the principle of least privilege.
- **Top-Level**: `contents: read`
- **`pr-agent-trigger`**: `issues: write` (to comment on PRs)
- **`auto-merge-check`**: `issues: write`, `pull-requests: write` (to merge)
- **`dependency-update`**: `pull-requests: write` (to approve and merge)

Sources: [tests/integration/test_githubworkflows.py:426-439]()

## Branch Management Workflow (`branch-cleanup.yml`)
Sources: [BRANCH_CLEANUP_SUMMARY.md:21-28]()

To maintain repository hygiene, the `branch-cleanup.yml` workflow runs automatically on a weekly schedule. Its purpose is to identify and report on stale branches that have not been updated recently.

**Key Features:**
- **Schedule**: Runs weekly to detect stale branches.
- **Manual Trigger**: Can be run on-demand from the GitHub Actions UI.
- **Reporting**: Generates a report of stale branches in the workflow run summary.

This automation helps prevent the accumulation of unnecessary branches, as detailed in the [Branch Cleanup Analysis](#).

Sources: [BRANCH_CLEANUP_SUMMARY.md:21-28]()

## Security Workflows
The repository uses standard, GitHub-provided security workflows to proactively identify vulnerabilities.

| Workflow File           | Purpose                                                              |
| :---------------------- | :------------------------------------------------------------------- |
| `codeql.yml`            | Performs deep static code analysis to find security vulnerabilities. |
| `dependency-review.yml` | Scans for vulnerabilities in dependencies added or changed in a PR.  |

Sources: [SUMMARY.md:104-109](), [AUDIT_REPORT.md:109-113]()

## Workflow Validation Testing
A unique aspect of this project is its comprehensive integration test suite for the GitHub Actions workflows themselves, located in `tests/integration/test_github_workflows.py`. These tests use `pytest` to parse the workflow YAML files and validate them against a series of rules, ensuring their correctness and security before they are even run by GitHub Actions.

This diagram shows the structure of the workflow test suite.
```mermaid
graph TD
    subgraph Pytest Suite
        A[test_github_workflows.py]
    end

    subgraph Test Classes
        C1[TestWorkflowSyntax]
        C2[TestWorkflowStructure]
        C3[TestWorkflowActions]
        C4[TestPrAgentWorkflow]
        C5[TestWorkflowSecurity]
        C6[TestWorkflowMaintainability]
        C7[TestWorkflowEdgeCases]
    end

    A --> C1
    A --> C2
    A --> C3
    A --> C4
    A --> C5
    A --> C6
    A --> C7
```
Sources: [tests/integration/test_github_workflows.py]()

### Test Coverage
The test suite is organized into multiple classes, each targeting a specific aspect of workflow validation.

| Test Class                    | Validation Checks                                                                                             |
| :---------------------------- | :------------------------------------------------------------------------------------------------------------ |
| `TestWorkflowSyntax`          | Valid YAML syntax, no duplicate keys, file is readable.                                                       |
| `TestWorkflowStructure`       | Presence of `name`, `on`, and `jobs` fields. Ensures jobs have steps.                                         |
| `TestWorkflowActions`         | Actions use version tags (e.g., `@v2`), steps have `name` or `uses`.                                          |
| `TestPrAgentWorkflow`         | Specific checks for `pr-agent.yml`, including triggers, job structure, and step configurations.               |
| `TestWorkflowSecurity`        | No hardcoded secrets, sensitive data uses the `secrets` context.                                              |
| `TestWorkflowMaintainability` | Steps have descriptive names, file size is reasonable.                                                        |
| `TestWorkflowEdgeCases`       | Correct file extensions (`.yml`/`.yaml`), UTF-8 encoding, no tabs for indentation.                              |
| `TestWorkflowPerformance`     | Recommends use of caching to improve performance.                                                             |
| `TestWorkflowAdvancedSecurity`| Checks for potential environment variable injection and secrets being logged.                                   |
| `TestWorkflowJobConfiguration`| Jobs specify a standard runner (`runs-on`).                                                                    |

Sources: [tests/integration/test_github_workflows.py:79, 134, 183, 207, 313, 357, 386, 406, 611, 706](), [COMPREHENSIVE_TEST_SUMMARY.md:120-129]()

This proactive testing of the CI/CD configuration itself is a critical practice that enhances the stability and security of the entire development lifecycle.

## Conclusion

The CI/CD system for this project is a modern, consolidated, and robust implementation. By removing legacy clutter and focusing on a single, well-tested pipeline, the project benefits from faster, more reliable, and more secure automated checks. The inclusion of automated PR management, branch cleanup, and comprehensive self-testing of the workflows demonstrates a mature approach to DevOps, ensuring high-quality code and a clean, maintainable repository.

Sources: [AUDIT_REPORT.md:231-239](), [SUMMARY.md:144-148]()

### Developer Scripts and Tooling

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/SUMMARY.md)
- [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md)
- [BRANCH_CLEANUP_SUMMARY.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/BRANCH_CLEANUP_SUMMARY.md)
- [BRANCH_CLEANUP_ANALYSIS.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/BRANCH_CLEANUP_ANALYSIS.md)
- [BRANCH_CLEANUP_QUICK_REFERENCE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/BRANCH_CLEANUP_QUICK_REFERENCE.md)
- [AUDIT_REPORT.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/AUDIT_REPORT.md)
- [TESTING_GUIDE.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/TESTING_GUIDE.md)
</details>

# Developer Scripts and Tooling

The project is equipped with a comprehensive suite of developer scripts and tooling designed to streamline development, enforce code quality, and maintain repository hygiene. The primary entry point for developers is a `Makefile` that provides shortcuts for common tasks like installation, testing, and formatting. This is supplemented by shell scripts for specialized tasks like branch cleanup and automated quality checks via pre-commit hooks.

This tooling ensures a consistent development environment and automates quality assurance, allowing developers to focus on building features. For detailed setup instructions and workflow, refer to the [CONTRIBUTING.md](https://github.com/DashFin/financial-asset-relationship-db/blob/main/CONTRIBUTING.md) guide.

Sources: [SUMMARY.md](), [CONTRIBUTING.md](), [AUDIT_REPORT.md]()

## Makefile Commands

The `Makefile` serves as the central command interface for developers, abstracting away the specifics of various tools. It provides a set of simple, memorable commands for all essential development lifecycle tasks.

Sources: [SUMMARY.md:37-55](), [CONTRIBUTING.md:65-71]()

### Command Reference

The following table summarizes the available `make` commands and their functions.

| Command | Description |
| :--- | :--- |
| `make help` | Shows all available commands. |
| `make install` | Installs production dependencies from `requirements.txt`. |
| `make install-dev` | Installs all development and production dependencies. |
| `make test` | Runs the test suite with `pytest` and generates a coverage report. |
| `make test-fast` | Runs the test suite without coverage for quicker feedback. |
| `make lint` | Runs linters, specifically `flake8` and `pylint`. |
| `make format` | Formats code using `black` and sorts imports with `isort`. |
| `make format-check` | Checks formatting with `black` and `isort` without making changes. |
| `make type-check` | Runs static type checking using `mypy`. |
| `make pre-commit` | Installs the pre-commit hooks. |
| `make pre-commit-run` | Runs the pre-commit hooks on all files in the repository. |
| `make clean` | Cleans up generated files like `.pytest_cache`, `.coverage`, and `htmlcov/`. |
| `make run` | Runs the main application (`app.py`). |
| `make check` | A comprehensive check that runs `format-check`, `lint`, `type-check`, and `test`. |

Sources: [SUMMARY.md:60-75](), [CONTRIBUTING.md:94-113]()

### `make check` Workflow

The `make check` command is a crucial part of the local development workflow, ensuring code meets quality standards before it is committed. The following diagram illustrates the sequence of checks it performs.

```mermaid
flowchart TD
    A[Start: make check] --> B{Format Check};
    B -- Pass --> C{Linting};
    B -- Fail --> F[End: Failure];
    C -- Pass --> D{Type Checking};
    C -- Fail --> F;
    D -- Pass --> E{Testing};
    D -- Fail --> F;
    E -- Pass --> G[End: Success];
    E -- Fail --> F;
```
This diagram shows the sequential execution of format checking, linting, type checking, and testing when `make check` is run.

Sources: [SUMMARY.md:75](), [CONTRIBUTING.md:112-113]()

## Branch Management and Cleanup

The repository has a structured approach to branch management to maintain a clean and understandable git history. This includes strict naming conventions, policies for short-lived branches, and automated tooling to identify and clean up stale or merged branches.

Sources: [BRANCH_CLEANUP_ANALYSIS.md](), [CONTRIBUTING.md:120-140](), [BRANCH_CLEANUP_SUMMARY.md]()

### Branch Naming Conventions

To keep branches organized, the project follows a descriptive naming convention based on the type of work being done.

| Prefix | Purpose | Example |
| :--- | :--- | :--- |
| `feature/` | New feature development | `feature/add-api-endpoint` |
| `bugfix/` | Bug fixes | `bugfix/database-connection` |
| `docs/` | Documentation updates | `docs/update-readme` |
| `refactor/` | Code refactoring | `refactor/simplify-graph-logic` |
| `test/` | Test additions or improvements | `test/add-model-validation-tests` |
| `chore/` | Maintenance tasks | `chore/upgrade-dependencies` |

Sources: [CONTRIBUTING.md:124-132](), [BRANCH_CLEANUP_QUICK_REFERENCE.md:83-91]()

### Cleanup Tools

Two primary tools are provided to assist with branch cleanup: an automated GitHub Actions workflow and an interactive local script.

1.  **Automated Workflow (`branch-cleanup.yml`)**: This GitHub Actions workflow runs on a weekly schedule to identify stale branches (inactive for 90+ days) and generates a report. It can also be triggered manually.
    Sources: [BRANCH_CLEANUP_SUMMARY.md:30-38]()

2.  **Interactive Script (`cleanup-branches.sh`)**: A shell script for developers to run locally. It provides an interactive menu to identify and safely delete merged or stale branches, both locally and remotely.
    Sources: [BRANCH_CLEANUP_SUMMARY.md:40-47](), [BRANCH_CLEANUP_QUICK_REFERENCE.md:5-9]()

The flow of the interactive `cleanup-branches.sh` script is as follows:

```mermaid
flowchart TD
    subgraph Interactive Script Flow
        A[Run ./cleanup-branches.sh] --> B{Select Action};
        B --> C[List Merged Branches];
        B --> D[List Stale Branches];
        B --> E[List Remote Branches not Local];
        C --> C1{Confirm Deletion};
        D --> D1{Confirm Deletion};
        E --> E1[No Action];
        C1 -- Yes --> C2[Delete Branches];
        D1 -- Yes --> D2[Delete Branches];
        C1 -- No --> B;
        D1 -- No --> B;
        C2 --> F[End];
        D2 --> F;
    end
```
This diagram outlines the user's journey through the `cleanup-branches.sh` script, from selecting an action to confirming and executing branch deletion.

Sources: [BRANCH_CLEANUP_SUMMARY.md:40-47](), [BRANCH_CLEANUP_QUICK_REFERENCE.md]()

## Quality Assurance Tooling

The project integrates several tools to automate code quality checks, which are run both locally via pre-commit hooks and in the CI/CD pipeline.

Sources: [AUDIT_REPORT.md:121-145](), [CONTRIBUTING.md:100-113]()

### Pre-commit Hooks

Pre-commit hooks are configured in `.pre-commit-config.yaml` to run a series of checks automatically before a commit is created. This prevents common issues and ensures code adheres to project standards.

The configured hooks perform the following actions:
-   Trailing whitespace removal
-   End-of-file fixing
-   Validation of YAML, JSON, and TOML files
-   Code formatting with `black`
-   Import sorting with `isort`
-   Linting with `flake8`
-   Static type checking with `mypy`

To install the hooks, a developer runs `make pre-commit` or `pre-commit install`.

Sources: [AUDIT_REPORT.md:200-211](), [CONTRIBUTING.md:73-79]()

### Developer Workflow with QA Tools

The following diagram shows a typical developer workflow, incorporating the automated tooling.

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Local as Local Machine
    participant Remote as GitHub Repository

    Dev->>Local: git checkout -b feature/new-thing
    Dev->>Local: Write code and tests
    Dev->>Local: git commit -m "feat: new thing"
    activate Local
    Local->>Local: Run pre-commit hooks (format, lint, etc.)
    Note right of Local: Hooks run automatically
    alt Hooks Pass
        Local-->>Dev: Commit successful
    else Hooks Fail
        Local-->>Dev: Commit failed, fix issues
    end
    deactivate Local

    Dev->>Remote: git push origin feature/new-thing
    Dev->>Remote: Create Pull Request
    activate Remote
    Remote->>Remote: Run CI Workflow (ci.yml)
    Note right of Remote: Includes lint, type-check, test, security
    Remote-->>Dev: PR checks pass/fail
    deactivate Remote
```
This sequence diagram illustrates how a developer's actions trigger automated quality checks both locally (pre-commit) and remotely (CI workflow).

Sources: [CONTRIBUTING.md:81-118](), [AUDIT_REPORT.md:148-160]()

## Testing Scripts

Testing is managed through `pytest` and can be invoked using simple `Makefile` commands.

-   `make test`: Runs all tests with coverage reporting. This is the standard command for full validation.
-   `make test-fast`: Runs tests without coverage, which is faster and useful for quick checks during development.
-   `pytest -m <marker>`: Allows running specific test groups, such as `unit` tests.

The project contains a comprehensive test suite, including unit tests for models and logic, and integration tests for configurations and workflows.

Sources: [TESTING_GUIDE.md:231-259](), [CONTRIBUTING.md:188-199](), [SUMMARY.md:66-67]()
