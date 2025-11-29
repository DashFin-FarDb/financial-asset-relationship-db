# System Manifest

## Project Overview
- Name: financial-asset-relationship-db
- Description: CRCT-enabled project: financial-asset-relationship-db
- Created: 2025-11-06T16:31:13.737Z

## Current Status
- Current Phase: Set-up/Maintenance
- Last Updated: 2025-11-10T00:21:57.491Z

## Project Structure

- 35 py files
- 4 ts files
- 9 tsx files
- 8 js files


## Dependencies

## Project Directory Structure

- 📂 api/
  - 📄 __init__.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 __tests__/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 lib/
      - 📄 api.test.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📂 coverage/
    - 📂 lcov-report/
      - 📂 app/
        ...
      - 📄 base.css
      - 📄 block-navigation.js
      - 📄 favicon.png
      - 📄 index.html
      - 📄 prettify.css
      - 📄 prettify.js
      - 📄 sort-arrow-sprite.png
      - 📄 sorter.js
    - 📄 clover.xml
    - 📄 lcov.info
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 __init__.py
    - 📄 formulaic_analysis.py
  - 📂 data/
    - 📄 database.py
    - 📄 db_models.py
    - 📄 real_data_fetcher.py
    - 📄 repository.py
    - 📄 sample_data.py
  - 📂 logic/
    - 📄 asset_graph.py
  - 📂 models/
    - 📄 financial_models.py
  - 📂 reports/
    - 📄 schema_report.py
  - 📂 visualizations/
    - 📄 formulaic_visuals.py
    - 📄 graph_2d_visuals.py
    - 📄 graph_visuals.py
    - 📄 metric_visuals.py
- 📂 tests/
  - 📂 integration/
    - 📄 __init__.py
    - 📄 test_api_integration.py
    - 📄 test_repository.py
  - 📂 unit/
    - 📄 __init__.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 __init__.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 app.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_supabase.py


## PY Dependencies

### \test_supabase.py
Dependencies:
- logging
- os
- dotenv
- load_dotenv
- supabase
- Client,
- environment

### \test_postgres.py
Dependencies:
# Core system imports
- logging
- os

# Database dependencies
- psycopg2>=2.9.0,<3.0.0  # PostgreSQL adapter with version constraint
- psycopg2-binary>=2.9.0  # For distributed deployments

# Environment management
- python-dotenv>=1.0.0,<2.0.0  # Unified environment variable management
  # Usage: from dotenv import load_dotenv
  # load_dotenv() # Load environment variables from .env file

# Development/Testing dependencies
- pytest>=7.0.0          # Test framework
- factory-boy>=3.2.0      # Test data generation
- pytest-asyncio>=0.21.0  # Async test support

# Error handling and resilience
- tenacity>=8.0.0         # Retry logic for database operations
- backoff>=2.2.0          # Exponential backoff for failures

# Logging and monitoring
- structlog>=22.0.0       # Structured logging
- sentry-sdk>=1.20.0      # Error tracking (optional)

### \test_db_module.py
Dependencies:
- logging
- src.data.database
- get_db

### \test_api.py
Dependencies:
- sys
- fastapi.testclient
- TestClient
- api.main
- app
- traceback

### \api\__init__.py
No dependencies found

## TS Dependencies

### \frontend\__tests__\lib\api.test.ts
Dependencies:
- axios
- ../../app/types/api

### \frontend\app\types\api.ts
No dependencies found

### \frontend\app\lib\index.ts
No dependencies found

### \frontend\app\lib\api.ts
Dependencies:
- axios
- ../types/api

## TSX Dependencies

### \frontend\app\components\NetworkVisualization.tsx
Dependencies:
- react
- next/dynamic
- ../types/api

### \frontend\app\components\MetricsDashboard.tsx
Dependencies:
- react
- ../types/api

### \frontend\app\components\AssetList.tsx
Dependencies:
- react
- next/navigation
- ../lib/api
- ../types/api

### \frontend\app\page.tsx
Dependencies:
- react
- ./lib/api
- ./components/NetworkVisualization
- ./components/MetricsDashboard
- ./components/AssetList
- ./types/api

### \frontend\__tests__\components\NetworkVisualization.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api

## JS Dependencies

### \frontend\tailwind.config.js
No dependencies found

### \frontend\postcss.config.js
No dependencies found

### \frontend\next.config.js
No dependencies found

### \frontend\jest.setup.js
Dependencies:
- @testing-library/jest-dom

### \frontend\jest.config.js
Dependencies:
- next/jest



## Project Directory Structure

- 📂 api/
  - 📄 __init__.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 __tests__/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 lib/
      - 📄 api.test.ts
  - 📂 app/
    - 📂 components/
      - 📂 __tests__/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 __tests__/
        ...
      - 📄 api.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📂 coverage/
    - 📂 lcov-report/
      - 📂 app/
        ...
      - 📄 base.css
      - 📄 block-navigation.js
      - 📄 favicon.png
      - 📄 index.html
      - 📄 prettify.css
      - 📄 prettify.js
      - 📄 sort-arrow-sprite.png
      - 📄 sorter.js
    - 📄 clover.xml
    - 📄 lcov.info
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 src/
  - 📂 analysis/
    - 📄 __init__.py
    - 📄 formulaic_analysis.py
  - 📂 data/
    - 📄 database.py
    - 📄 real_data_fetcher.py
    - 📄 sample_data.py
  - 📂 logic/
    - 📄 asset_graph.py
  - 📂 models/
    - 📄 financial_models.py
  - 📂 reports/
    - 📄 schema_report.py
  - 📂 visualizations/
    - 📄 formulaic_visuals.py
    - 📄 graph_2d_visuals.py
    - 📄 graph_visuals.py
    - 📄 metric_visuals.py
- 📂 tests/
  - 📂 integration/
    - 📄 __init__.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 __init__.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 __init__.py
  - 📄 conftest.py
- 📄 app.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 FINAL_REPORT.txt
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_supabase.py


## PY Dependencies

### \test_supabase.py
Dependencies:
- os
- supabase
- create_client,
- dotenv
- load_dotenv
- logging
- environment

### \test_postgres.py
Dependencies:
- os
- psycopg2
- dotenv
- load_dotenv
- logging
- environment

### \test_db_module.py
Dependencies:
- logging
- src.data.database
- get_db

### \test_api.py
Dependencies:
- sys
- api.main
- app
- fastapi.testclient
- TestClient
- traceback

### \tests\__init__.py
No dependencies found

## JS Dependencies

### \frontend\next.config.js
No dependencies found

### \frontend\jest.setup.js
Dependencies:
- @testing-library/jest-dom

### \frontend\jest.config.js
Dependencies:
- next/jest

### \frontend\postcss.config.js
No dependencies found

### \frontend\tailwind.config.js
No dependencies found

## TS Dependencies

### \frontend\__tests__\lib\api.test.ts
Dependencies:
- axios
- ../../app/lib/api
- ../../app/types/api

### \frontend\app\types\api.ts
No dependencies found

### \frontend\app\lib\index.ts
No dependencies found

### \frontend\app\lib\api.ts
Dependencies:
- axios
- ../types/api

### \frontend\app\lib\__tests__\api.test.ts
Dependencies:
- axios
- ../api

## TSX Dependencies

### \frontend\__tests__\components\NetworkVisualization.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api

### \frontend\__tests__\components\MetricsDashboard.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api

### \frontend\__tests__\components\AssetList.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/AssetList
- ../../app/lib/api

### \frontend\app\page.tsx
Dependencies:
- react
- ./lib/api
- ./components/NetworkVisualization
- ./components/MetricsDashboard
- ./components/AssetList
- ./types/api

### \frontend\app\layout.tsx
Dependencies:
- ./globals.css
- next



## Project Directory Structure

- 📂 api/
  - 📄 __init__.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 __tests__/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 lib/
      - 📄 api.test.ts
  - 📂 app/
    - 📂 components/
      - 📂 __tests__/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 __tests__/
        ...
      - 📄 api.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📂 coverage/
    - 📂 lcov-report/
      - 📂 app/
        ...
      - 📄 base.css
      - 📄 block-navigation.js
      - 📄 favicon.png
      - 📄 index.html
      - 📄 prettify.css
      - 📄 prettify.js
      - 📄 sort-arrow-sprite.png
      - 📄 sorter.js
    - 📄 clover.xml
    - 📄 lcov.info
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 src/
  - 📂 analysis/
    - 📄 __init__.py
    - 📄 formulaic_analysis.py
  - 📂 data/
    - 📄 database.py
    - 📄 real_data_fetcher.py
    - 📄 sample_data.py
  - 📂 logic/
    - 📄 asset_graph.py
  - 📂 models/
    - 📄 financial_models.py
  - 📂 reports/
    - 📄 schema_report.py
  - 📂 visualizations/
    - 📄 formulaic_visuals.py
    - 📄 graph_2d_visuals.py
    - 📄 graph_visuals.py
    - 📄 metric_visuals.py
- 📂 tests/
  - 📂 integration/
    - 📄 __init__.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 __init__.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 __init__.py
  - 📄 conftest.py
- 📄 app.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 FINAL_REPORT.txt
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_supabase.py


## PY Dependencies

### \test_supabase.py
Dependencies:
- os
- supabase
- create_client,
- dotenv
- load_dotenv
- logging
- environment

### \test_postgres.py
Dependencies:
- os
- psycopg2
- dotenv
- load_dotenv
- logging
- environment

### \test_db_module.py
Dependencies:
- logging
- src.data.database
- get_db

### \test_api.py
Dependencies:
- sys
- api.main
- app
- fastapi.testclient
- TestClient
- traceback

### \tests\__init__.py
No dependencies found

## JS Dependencies

### \frontend\tailwind.config.js
No dependencies found

### \frontend\postcss.config.js
No dependencies found

### \frontend\next.config.js
No dependencies found

### \frontend\jest.setup.js
Dependencies:
- @testing-library/jest-dom

### \frontend\jest.config.js
Dependencies:
- next/jest

## TS Dependencies

### \frontend\app\types\api.ts
No dependencies found

### \frontend\__tests__\lib\api.test.ts
Dependencies:
- axios
- ../../app/lib/api
- ../../app/types/api

### \frontend\app\lib\index.ts
No dependencies found

### \frontend\app\lib\api.ts
Dependencies:
- axios
- ../types/api

### \frontend\app\lib\__tests__\api.test.ts
Dependencies:
- axios
- ../api

## TSX Dependencies

### \frontend\app\page.tsx
Dependencies:
- react
- ./lib/api
- ./components/NetworkVisualization
- ./components/MetricsDashboard
- ./components/AssetList
- ./types/api

### \frontend\app\layout.tsx
Dependencies:
- ./globals.css
- next

### \frontend\app\components\NetworkVisualization.tsx
Dependencies:
- react
- next/dynamic
- ../types/api

### \frontend\app\components\MetricsDashboard.tsx
Dependencies:
- react
- ../types/api

### \frontend\app\components\AssetList.tsx
Dependencies:
- react
- ../lib/api
- ../types/api



## Project Directory Structure

- 📂 api/
  - 📄 __init__.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 __tests__/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 lib/
      - 📄 api.test.ts
  - 📂 app/
    - 📂 components/
      - 📂 __tests__/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 __tests__/
        ...
      - 📄 api.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📂 coverage/
    - 📂 lcov-report/
      - 📂 app/
        ...
      - 📄 base.css
      - 📄 block-navigation.js
      - 📄 favicon.png
      - 📄 index.html
      - 📄 prettify.css
      - 📄 prettify.js
      - 📄 sort-arrow-sprite.png
      - 📄 sorter.js
    - 📄 clover.xml
    - 📄 lcov.info
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 src/
  - 📂 analysis/
    - 📄 __init__.py
    - 📄 formulaic_analysis.py
  - 📂 data/
    - 📄 database.py
    - 📄 real_data_fetcher.py
    - 📄 sample_data.py
  - 📂 logic/
    - 📄 asset_graph.py
  - 📂 models/
    - 📄 financial_models.py
  - 📂 reports/
    - 📄 schema_report.py
  - 📂 visualizations/
    - 📄 formulaic_visuals.py
    - 📄 graph_2d_visuals.py
    - 📄 graph_visuals.py
    - 📄 metric_visuals.py
- 📂 tests/
  - 📂 integration/
    - 📄 __init__.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 __init__.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 __init__.py
  - 📄 conftest.py
- 📄 app.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 FINAL_REPORT.txt
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_supabase.py


## PY Dependencies

### \test_supabase.py
Dependencies:
- os
- supabase
- create_client,
- dotenv
- load_dotenv
- logging
- environment

### \test_postgres.py
Dependencies:
- os
- psycopg2
- dotenv
- load_dotenv
- logging
- environment

### \test_db_module.py
Dependencies:
- logging
- src.data.database
- get_db

### \test_api.py
Dependencies:
- sys
- api.main
- app
- fastapi.testclient
- TestClient
- traceback

### \tests\__init__.py
No dependencies found

## TS Dependencies

### \frontend\__tests__\lib\api.test.ts
Dependencies:
- axios
- ../../app/lib/api
- ../../app/types/api

### \frontend\app\types\api.ts
No dependencies found

### \frontend\app\lib\__tests__\api.test.ts
Dependencies:
- axios
- ../api

### \frontend\app\lib\index.ts
No dependencies found

### \frontend\app\lib\api.ts
Dependencies:
- axios
- ../types/api

## TSX Dependencies

### \frontend\__tests__\components\NetworkVisualization.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api

### \frontend\__tests__\components\MetricsDashboard.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api

### \frontend\__tests__\components\AssetList.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/AssetList
- ../../app/lib/api

### \frontend\__tests__\app\page.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\app\page.tsx
Dependencies:
- react
- ./lib/api
- ./components/NetworkVisualization
- ./components/MetricsDashboard
- ./components/AssetList
- ./types/api

## JS Dependencies

### \frontend\tailwind.config.js
No dependencies found

### \frontend\postcss.config.js
No dependencies found

### \frontend\next.config.js
No dependencies found

### \frontend\jest.setup.js
Dependencies:
- @testing-library/jest-dom

### \frontend\jest.config.js
Dependencies:
- next/jest



## Project Directory Structure

- 📂 api/
  - 📄 __init__.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 __tests__/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 lib/
      - 📄 api.test.ts
  - 📂 app/
    - 📂 components/
      - 📂 __tests__/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 __tests__/
        ...
      - 📄 api.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📂 coverage/
    - 📂 lcov-report/
      - 📂 app/
        ...
      - 📄 base.css
      - 📄 block-navigation.js
      - 📄 favicon.png
      - 📄 index.html
      - 📄 prettify.css
      - 📄 prettify.js
      - 📄 sort-arrow-sprite.png
      - 📄 sorter.js
    - 📄 clover.xml
    - 📄 lcov.info
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 src/
  - 📂 analysis/
    - 📄 __init__.py
    - 📄 formulaic_analysis.py
  - 📂 data/
    - 📄 database.py
    - 📄 real_data_fetcher.py
    - 📄 sample_data.py
  - 📂 logic/
    - 📄 asset_graph.py
  - 📂 models/
    - 📄 financial_models.py
  - 📂 reports/
    - 📄 schema_report.py
  - 📂 visualizations/
    - 📄 formulaic_visuals.py
    - 📄 graph_2d_visuals.py
    - 📄 graph_visuals.py
    - 📄 metric_visuals.py
- 📂 tests/
  - 📂 integration/
    - 📄 __init__.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 __init__.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 __init__.py
  - 📄 conftest.py
- 📄 app.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 FINAL_REPORT.txt
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_supabase.py


## PY Dependencies

### \test_supabase.py
Dependencies:
- os
- supabase
- create_client,
- dotenv
- load_dotenv
- logging
- environment

### \test_postgres.py
Dependencies:
- os
- psycopg2
- dotenv
- load_dotenv
- logging
- environment

### \test_db_module.py
Dependencies:
- logging
- src.data.database
- get_db

### \test_api.py
Dependencies:
- sys
- api.main
- app
- fastapi.testclient
- TestClient
- traceback

### \api\__init__.py
No dependencies found

## TSX Dependencies

### \frontend\__tests__\app\page.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\app\page.tsx
Dependencies:
- react
- ./lib/api
- ./components/NetworkVisualization
- ./components/MetricsDashboard
- ./components/AssetList
- ./types/api

### \frontend\app\components\NetworkVisualization.tsx
Dependencies:
- react
- next/dynamic
- ../types/api

### \frontend\app\components\MetricsDashboard.tsx
Dependencies:
- react
- ../types/api

### \frontend\app\components\AssetList.tsx
Dependencies:
- react
- ../lib/api
- ../types/api

## TS Dependencies

### \frontend\__tests__\lib\api.test.ts
Dependencies:
- axios
- ../../app/lib/api
- ../../app/types/api

### \frontend\app\types\api.ts
No dependencies found

### \frontend\app\lib\api.ts
Dependencies:
- axios
- ../types/api

### \frontend\app\lib\__tests__\api.test.ts
Dependencies:
- axios
- ../api

### \frontend\app\lib\index.ts
No dependencies found

## JS Dependencies

### \frontend\tailwind.config.js
No dependencies found

### \frontend\postcss.config.js
No dependencies found

### \frontend\next.config.js
No dependencies found

### \frontend\jest.setup.js
Dependencies:
- @testing-library/jest-dom

### \frontend\jest.config.js
Dependencies:
- next/jest



## Project Directory Structure

- 📂 api/
  - 📄 __init__.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 __tests__/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 lib/
      - 📄 api.test.ts
  - 📂 app/
    - 📂 components/
      - 📂 __tests__/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 __tests__/
        ...
      - 📄 api.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📂 coverage/
    - 📂 lcov-report/
      - 📂 app/
        ...
      - 📄 base.css
      - 📄 block-navigation.js
      - 📄 favicon.png
      - 📄 index.html
      - 📄 prettify.css
      - 📄 prettify.js
      - 📄 sort-arrow-sprite.png
      - 📄 sorter.js
    - 📄 clover.xml
    - 📄 lcov.info
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 src/
  - 📂 analysis/
    - 📄 __init__.py
    - 📄 formulaic_analysis.py
  - 📂 data/
    - 📄 database.py
    - 📄 real_data_fetcher.py
    - 📄 sample_data.py
  - 📂 logic/
    - 📄 asset_graph.py
  - 📂 models/
    - 📄 financial_models.py
  - 📂 reports/
    - 📄 schema_report.py
  - 📂 visualizations/
    - 📄 formulaic_visuals.py
    - 📄 graph_2d_visuals.py
    - 📄 graph_visuals.py
    - 📄 metric_visuals.py
- 📂 tests/
  - 📂 integration/
    - 📄 __init__.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 __init__.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 __init__.py
  - 📄 conftest.py
- 📄 app.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 FINAL_REPORT.txt
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_supabase.py


## PY Dependencies

### \test_supabase.py
Dependencies:
- os
- supabase
- create_client,
- dotenv
- load_dotenv
- logging
- environment

### \test_postgres.py
Dependencies:
- os
- psycopg2
- dotenv
- load_dotenv
- logging
- environment

### \test_db_module.py
Dependencies:
- logging
- src.data.database
- get_db

### \test_api.py
Dependencies:
- sys
- api.main
- app
- fastapi.testclient
- TestClient
- traceback

### \tests\__init__.py
No dependencies found

## JS Dependencies

### \frontend\tailwind.config.js
No dependencies found

### \frontend\postcss.config.js
No dependencies found

### \frontend\next.config.js
No dependencies found

### \frontend\jest.setup.js
Dependencies:
- @testing-library/jest-dom

### \frontend\jest.config.js
Dependencies:
- next/jest

## TS Dependencies

### \frontend\__tests__\lib\api.test.ts
Dependencies:
- axios
- ../../app/lib/api
- ../../app/types/api

### \frontend\app\types\api.ts
No dependencies found

### \frontend\app\lib\api.ts
Dependencies:
- axios
- ../types/api

### \frontend\app\lib\__tests__\api.test.ts
Dependencies:
- axios
- ../api

### \frontend\app\lib\index.ts
No dependencies found

## TSX Dependencies

### \frontend\__tests__\components\NetworkVisualization.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api

### \frontend\__tests__\components\MetricsDashboard.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api

### \frontend\__tests__\components\AssetList.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/AssetList
- ../../app/lib/api

### \frontend\__tests__\app\page.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\app\page.tsx
Dependencies:
- react
- ./lib/api
- ./components/NetworkVisualization
- ./components/MetricsDashboard
- ./components/AssetList
- ./types/api



## Project Directory Structure

- 📂 api/
  - 📄 __init__.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 __tests__/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 lib/
      - 📄 api.test.ts
  - 📂 app/
    - 📂 components/
      - 📂 __tests__/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 __tests__/
        ...
      - 📄 api.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📂 coverage/
    - 📂 lcov-report/
      - 📂 app/
        ...
      - 📄 base.css
      - 📄 block-navigation.js
      - 📄 favicon.png
      - 📄 index.html
      - 📄 prettify.css
      - 📄 prettify.js
      - 📄 sort-arrow-sprite.png
      - 📄 sorter.js
    - 📄 clover.xml
    - 📄 lcov.info
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 src/
  - 📂 analysis/
    - 📄 __init__.py
    - 📄 formulaic_analysis.py
  - 📂 data/
    - 📄 database.py
    - 📄 real_data_fetcher.py
    - 📄 sample_data.py
  - 📂 logic/
    - 📄 asset_graph.py
  - 📂 models/
    - 📄 financial_models.py
  - 📂 reports/
    - 📄 schema_report.py
  - 📂 visualizations/
    - 📄 formulaic_visuals.py
    - 📄 graph_2d_visuals.py
    - 📄 graph_visuals.py
    - 📄 metric_visuals.py
- 📂 tests/
  - 📂 integration/
    - 📄 __init__.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 __init__.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 __init__.py
  - 📄 conftest.py
- 📄 app.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 FINAL_REPORT.txt
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_supabase.py


## PY Dependencies

### \test_supabase.py
Dependencies:
- os
- supabase
- create_client,
- dotenv
- load_dotenv
- logging
- environment

### \test_postgres.py
Dependencies:
- os
- psycopg2
- dotenv
- load_dotenv
- logging
- environment

### \test_db_module.py
Dependencies:
- logging
- src.data.database
- get_db

### \test_api.py
Dependencies:
- sys
- api.main
- app
- fastapi.testclient
- TestClient
- traceback

### \tests\__init__.py
No dependencies found

## JS Dependencies

### \frontend\tailwind.config.js
No dependencies found

### \frontend\postcss.config.js
No dependencies found

### \frontend\next.config.js
No dependencies found

### \frontend\jest.setup.js
Dependencies:
- @testing-library/jest-dom

### \frontend\jest.config.js
Dependencies:
- next/jest

## TS Dependencies

### \frontend\__tests__\lib\api.test.ts
Dependencies:
- axios
- ../../app/lib/api
- ../../app/types/api

### \frontend\app\types\api.ts
No dependencies found

### \frontend\app\lib\index.ts
No dependencies found

### \frontend\app\lib\api.ts
Dependencies:
- axios
- ../types/api

### \frontend\app\lib\__tests__\api.test.ts
Dependencies:
- axios
- ../api

## TSX Dependencies

### \frontend\__tests__\components\MetricsDashboard.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api

### \frontend\__tests__\components\NetworkVisualization.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api

### \frontend\__tests__\components\AssetList.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/AssetList
- ../../app/lib/api

### \frontend\__tests__\app\page.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\app\page.tsx
Dependencies:
- react
- ./lib/api
- ./components/NetworkVisualization
- ./components/MetricsDashboard
- ./components/AssetList
- ./types/api



## Project Directory Structure

- 📂 api/
  - 📄 __init__.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 __tests__/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 lib/
      - 📄 api.test.ts
  - 📂 app/
    - 📂 components/
      - 📂 __tests__/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 __tests__/
        ...
      - 📄 api.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📂 coverage/
    - 📂 lcov-report/
      - 📂 app/
        ...
      - 📄 base.css
      - 📄 block-navigation.js
      - 📄 favicon.png
      - 📄 index.html
      - 📄 prettify.css
      - 📄 prettify.js
      - 📄 sort-arrow-sprite.png
      - 📄 sorter.js
    - 📄 clover.xml
    - 📄 lcov.info
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 src/
  - 📂 analysis/
    - 📄 __init__.py
    - 📄 formulaic_analysis.py
  - 📂 data/
    - 📄 database.py
    - 📄 real_data_fetcher.py
    - 📄 sample_data.py
  - 📂 logic/
    - 📄 asset_graph.py
  - 📂 models/
    - 📄 financial_models.py
  - 📂 reports/
    - 📄 schema_report.py
  - 📂 visualizations/
    - 📄 formulaic_visuals.py
    - 📄 graph_2d_visuals.py
    - 📄 graph_visuals.py
    - 📄 metric_visuals.py
- 📂 tests/
  - 📂 integration/
    - 📄 __init__.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 __init__.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 __init__.py
  - 📄 conftest.py
- 📄 app.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 FINAL_REPORT.txt
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_supabase.py


## PY Dependencies

### \app.py
Dependencies:
- gradio
- json
- logging
- plotly.graph_objects
- typing
- Optional,
- dataclasses
- asdict
- src.logic.asset_graph
- AssetRelationshipGraph
- src.data.real_data_fetcher
- create_real_database
- src.visualizations.graph_visuals
- visualize_3d_graph,
- src.visualizations.graph_2d_visuals
- visualize_2d_graph
- src.visualizations.metric_visuals
- visualize_metrics
- src.reports.schema_report
- generate_schema_report
- src.analysis.formulaic_analysis
- FormulaicdAnalyzer
- src.visualizations.formulaic_visuals
- FormulaicVisualizer
- src.models.financial_models
- Asset
- Yahoo
- the

### \api\auth.py
Dependencies:
- datetime
- datetime,
- typing
- Optional
- fastapi
- Depends,
- fastapi.security
- OAuth2PasswordBearer,
- jose
- JWTError,
- passlib.context
- CryptContext
- pydantic
- BaseModel
- os
- database"""
- token"""

### \api\__init__.py
No dependencies found

### \api\main.py
Dependencies:
- contextlib
- asynccontextmanager
- typing
- Dict,
- logging
- os
- re
- threading
- fastapi
- FastAPI,
- fastapi.middleware.cors
- CORSMiddleware
- fastapi.security
- OAuth2PasswordRequestForm
- pydantic
- BaseModel
- .auth
- Token,
- datetime
- timedelta
- slowapi
- Limiter,
- slowapi.util
- get_remote_address
- slowapi.errors
- RateLimitExceeded
- src.logic.asset_graph
- AssetRelationshipGraph
- src.data.real_data_fetcher
- RealDataFetcher
- src.models.financial_models
- AssetClass
- fake_users_db
- environment
- e
- asset
- graph.relationships
- intermediate
- uvicorn

### \test_supabase.py
Dependencies:
- os
- supabase
- create_client,
- dotenv
- load_dotenv
- logging
- environment

## JS Dependencies

### \frontend\next.config.js
No dependencies found

### \frontend\postcss.config.js
No dependencies found

### \frontend\tailwind.config.js
No dependencies found

### \frontend\jest.setup.js
Dependencies:
- @testing-library/jest-dom

### \frontend\jest.config.js
Dependencies:
- next/jest

## TSX Dependencies

### \frontend\app\page.tsx
Dependencies:
- react
- ./lib/api
- ./components/NetworkVisualization
- ./components/MetricsDashboard
- ./components/AssetList
- ./types/api

### \frontend\app\layout.tsx
Dependencies:
- ./globals.css
- next

### \frontend\__tests__\components\NetworkVisualization.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api

### \frontend\__tests__\components\MetricsDashboard.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api

### \frontend\__tests__\components\AssetList.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/AssetList
- ../../app/lib/api

## TS Dependencies

### \frontend\app\lib\index.ts
No dependencies found

### \frontend\app\lib\api.ts
Dependencies:
- axios
- ../types/api

### \frontend\__tests__\lib\api.test.ts
Dependencies:
- axios
- ../../app/lib/api
- ../../app/types/api

### \frontend\app\types\api.ts
No dependencies found

### \frontend\app\lib\__tests__\api.test.ts
Dependencies:
- axios
- ../api



## Project Directory Structure

- 📂 api/
  - 📄 __init__.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 __tests__/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 lib/
      - 📄 api.test.ts
  - 📂 app/
    - 📂 components/
      - 📂 __tests__/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 __tests__/
        ...
      - 📄 api.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📂 coverage/
    - 📂 lcov-report/
      - 📂 app/
        ...
      - 📄 base.css
      - 📄 block-navigation.js
      - 📄 favicon.png
      - 📄 index.html
      - 📄 prettify.css
      - 📄 prettify.js
      - 📄 sort-arrow-sprite.png
      - 📄 sorter.js
    - 📄 clover.xml
    - 📄 lcov.info
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 src/
  - 📂 analysis/
    - 📄 __init__.py
    - 📄 formulaic_analysis.py
  - 📂 data/
    - 📄 database.py
    - 📄 real_data_fetcher.py
    - 📄 sample_data.py
  - 📂 logic/
    - 📄 asset_graph.py
  - 📂 models/
    - 📄 financial_models.py
  - 📂 reports/
    - 📄 schema_report.py
  - 📂 visualizations/
    - 📄 formulaic_visuals.py
    - 📄 graph_2d_visuals.py
    - 📄 graph_visuals.py
    - 📄 metric_visuals.py
- 📂 tests/
  - 📂 integration/
    - 📄 __init__.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 __init__.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 __init__.py
  - 📄 conftest.py
- 📄 app.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 FINAL_REPORT.txt
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_supabase.py


## PY Dependencies

### \app.py
Dependencies:
- gradio
- json
- logging
- plotly.graph_objects
- typing
- Optional,
- dataclasses
- asdict
- src.logic.asset_graph
- AssetRelationshipGraph
- src.data.real_data_fetcher
- create_real_database
- src.visualizations.graph_visuals
- visualize_3d_graph,
- src.visualizations.graph_2d_visuals
- visualize_2d_graph
- src.visualizations.metric_visuals
- visualize_metrics
- src.reports.schema_report
- generate_schema_report
- src.analysis.formulaic_analysis
- FormulaicdAnalyzer
- src.visualizations.formulaic_visuals
- FormulaicVisualizer
- src.models.financial_models
- Asset
- Yahoo
- starting.
- the

### \api\__init__.py
No dependencies found

### \api\main.py
Dependencies:
- contextlib
- asynccontextmanager
- typing
- Dict,
- logging
- os
- re
- threading
- fastapi
- FastAPI,
- fastapi.middleware.cors
- CORSMiddleware
- fastapi.security
- OAuth2PasswordRequestForm
- pydantic
- BaseModel
- .auth
- Token,
- datetime
- timedelta
- slowapi
- Limiter,
- slowapi.util
- get_remote_address
- slowapi.errors
- RateLimitExceeded
- src.logic.asset_graph
- AssetRelationshipGraph
- src.data.real_data_fetcher
- RealDataFetcher
- src.models.financial_models
- AssetClass
- fake_users_db
- environment
- e
- asset
- graph.relationships
- intermediate
- uvicorn

### \api\auth.py
Dependencies:
- datetime
- datetime,
- typing
- Optional
- fastapi
- Depends,
- fastapi.security
- OAuth2PasswordBearer,
- jose
- JWTError,
- passlib.context
- CryptContext
- pydantic
- BaseModel
- os
- database"""
- token"""

### \src\models\financial_models.py
Dependencies:
- dataclasses
- dataclass,
- enum
- Enum
- typing
- List,
- re

## JS Dependencies

### \frontend\tailwind.config.js
No dependencies found

### \frontend\postcss.config.js
No dependencies found

### \frontend\next.config.js
No dependencies found

### \frontend\jest.setup.js
Dependencies:
- @testing-library/jest-dom

### \frontend\jest.config.js
Dependencies:
- next/jest

## TS Dependencies

### \frontend\__tests__\lib\api.test.ts
Dependencies:
- axios
- ../../app/lib/api
- ../../app/types/api

### \frontend\app\types\api.ts
No dependencies found

### \frontend\app\lib\index.ts
No dependencies found

### \frontend\app\lib\api.ts
Dependencies:
- axios
- ../types/api

### \frontend\app\lib\__tests__\api.test.ts
Dependencies:
- axios
- ../api

## TSX Dependencies

### \frontend\__tests__\components\NetworkVisualization.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api

### \frontend\__tests__\components\MetricsDashboard.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api

### \frontend\__tests__\components\AssetList.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/AssetList
- ../../app/lib/api

### \frontend\app\page.tsx
Dependencies:
- react
- ./lib/api
- ./components/NetworkVisualization
- ./components/MetricsDashboard
- ./components/AssetList
- ./types/api

### \frontend\app\layout.tsx
Dependencies:
- ./globals.css
- next



## Project Directory Structure

- 📂 api/
  - 📄 __init__.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 __tests__/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 lib/
      - 📄 api.test.ts
  - 📂 app/
    - 📂 components/
      - 📂 __tests__/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 __tests__/
        ...
      - 📄 api.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📂 coverage/
    - 📂 lcov-report/
      - 📂 app/
        ...
      - 📄 base.css
      - 📄 block-navigation.js
      - 📄 favicon.png
      - 📄 index.html
      - 📄 prettify.css
      - 📄 prettify.js
      - 📄 sort-arrow-sprite.png
      - 📄 sorter.js
    - 📄 clover.xml
    - 📄 lcov.info
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 src/
  - 📂 analysis/
    - 📄 __init__.py
    - 📄 formulaic_analysis.py
  - 📂 data/
    - 📄 database.py
    - 📄 real_data_fetcher.py
    - 📄 sample_data.py
  - 📂 logic/
    - 📄 asset_graph.py
  - 📂 models/
    - 📄 financial_models.py
  - 📂 reports/
    - 📄 schema_report.py
  - 📂 visualizations/
    - 📄 formulaic_visuals.py
    - 📄 graph_2d_visuals.py
    - 📄 graph_visuals.py
    - 📄 metric_visuals.py
- 📂 tests/
  - 📂 integration/
    - 📄 __init__.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 __init__.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 __init__.py
  - 📄 conftest.py
- 📄 app.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 FINAL_REPORT.txt
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_supabase.py


## PY Dependencies

### \test_supabase.py
Dependencies:
- os
- supabase
- create_client,
- dotenv
- load_dotenv
- logging
- environment

### \test_postgres.py
Dependencies:
- os
- psycopg2
- dotenv
- load_dotenv
- logging
- environment

### \test_db_module.py
Dependencies:
- logging
- src.data.database
- get_db

### \test_api.py
Dependencies:
- sys
- api.main
- app
- fastapi.testclient
- TestClient
- traceback

### \tests\__init__.py
No dependencies found

## TS Dependencies

### \frontend\__tests__\lib\api.test.ts
Dependencies:
- axios
- ../../app/lib/api
- ../../app/types/api

### \frontend\app\types\api.ts
No dependencies found

### \frontend\app\lib\__tests__\api.test.ts
Dependencies:
- axios
- ../api

### \frontend\app\lib\index.ts
No dependencies found

### \frontend\app\lib\api.ts
Dependencies:
- axios
- ../types/api

## TSX Dependencies

### \frontend\__tests__\components\NetworkVisualization.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api

### \frontend\__tests__\components\MetricsDashboard.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api

### \frontend\__tests__\components\AssetList.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/AssetList
- ../../app/lib/api

### \frontend\__tests__\app\page.test.tsx
Dependencies:
- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\app\page.tsx
Dependencies:
- react
- ./lib/api
- ./components/NetworkVisualization
- ./components/MetricsDashboard
- ./components/AssetList
- ./types/api

## JS Dependencies

### \frontend\tailwind.config.js
No dependencies found

### \frontend\postcss.config.js
No dependencies found

### \frontend\next.config.js
No dependencies found

### \frontend\jest.setup.js
Dependencies:
- @testing-library/jest-dom

### \frontend\jest.config.js
Dependencies:
- next/jest



## Key Components
- TBD

## Integration Points
- TBD

## Technical Considerations
- TBD

## Implementation Notes
- TBD
