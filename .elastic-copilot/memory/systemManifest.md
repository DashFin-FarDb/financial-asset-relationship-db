# System Manifest

## Project Overview

- Name: financial-asset-relationship-db
- Description: CRCT-enabled project: financial-asset-relationship-db
- Created: 2025-11-06T16:31:13.737Z

## Current Status

- Current Phase: Set-up/Maintenance
- Last Updated: 2026-02-27T21:46:37.688Z

## Project Structure

- 950 py files
- 12 ts files
- 10 tsx files
- 10 js files
- 18 h files

## Project Directory Structure

- 📂 api/
  - 📄 init.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 tests/
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
      - 📂 tests/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 tests/
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
    - 📄 init.py
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
    - 📄 init.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 init.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 init.py
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

### \tests\_\_init\_\_.py

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

### \frontend\_\_tests\_\_\lib\api.test.ts

Dependencies:

- axios
- ../../app/lib/api
- ../../app/types/api

### \frontend\app\types\api.ts

No dependencies found

### \frontend\app\lib\_\_tests\_\_\api.test.ts

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

### \frontend\_\_tests\_\_\components\NetworkVisualization.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api

### \frontend\_\_tests\_\_\components\MetricsDashboard.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api

### \frontend\_\_tests\_\_\components\AssetList.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/AssetList
- ../../app/lib/api

### \frontend\_\_tests\_\_\app\page.test.tsx

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

## Key Components

- TBD

## Integration Points

- TBD

## Technical Considerations

- TBD

## Implementation Notes

- TBD
