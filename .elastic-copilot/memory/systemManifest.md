# System Manifest

## Project Overview

- Name: financial-asset-relationship-db
- Description: CRCT-enabled project: financial-asset-relationship-db
- Created: 2025-11-06T16:31:13.737Z

## Current Status

- Current Phase: Set-up/Maintenance
- Last Updated: 2026-02-16T07:57:42.656Z

## Project Structure

- 84 py files
- 5 js files
- 12 ts files
- 10 tsx files

## Dependencies

## Project Directory Structure

- 📂 api/
  - 📄 __init__.py
  - 📄 auth.py
  - 📄 database.py
  - 📄 main.py
- 📂 branch_reviews/
- 📂 docs/
- 📂 frontend/
  - 📂 **tests**/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 config/
      - 📄 package-integration.test.ts
      - 📄 package-lock-validation.test.ts
      - 📄 package-validation.test.ts
    - 📂 integration/
      - 📄 component-integration.test.tsx
    - 📂 lib/
      - 📄 api-axios-compatibility.test.ts
      - 📄 api-upgrade-integration.test.ts
      - 📄 api.test.ts
    - 📄 test-utils.test.ts
    - 📄 test-utils.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 assetHelpers.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 **init**.py
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
  - 📄 workflow_validator.py
- 📂 tests/
  - 📂 integration/
    - 📄 **init**.py
    - 📄 conftest.py
    - 📄 test_api_integration.py
    - 📄 test_bearer_workflow.py
    - 📄 test_branch_integration.py
    - 📄 test_debricked_workflow.py
    - 📄 test_documentation_files_validation.py
    - 📄 test_documentation_validation.py
    - 📄 test_github_workflows_helpers.py
    - 📄 test_github_workflows.py
    - 📄 test_github_workflows.py.backup
    - 📄 test_modified_config_files_validation.py
    - 📄 test_pr_agent_config_validation.py
    - 📄 test_pr_agent_workflow_specific.py
    - 📄 test_repository.py
    - 📄 test_requirements_dev.py
    - 📄 test_requirements_pyyaml.py
    - 📄 test_requirements_validation.py
    - 📄 test_requirements.py
    - 📄 test_workflow_changes_validation.py
    - 📄 test_workflow_config_changes.py
    - 📄 test_workflow_documentation.py
    - 📄 test_workflow_requirements_integration.py
    - 📄 test_workflow_security_advanced.py
    - 📄 test_workflow_yaml_validation.py
    - 📄 test_yaml_config_validation.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_database_memory.py
    - 📄 test_database.py
    - 📄 test_db_models.py
    - 📄 test_dev_scripts.py
    - 📄 test_documentation_validation.py
    - 📄 test_financial_models.py
    - 📄 test_formulaic_analysis.py
    - 📄 test_formulaic_visuals.py
    - 📄 test_graph_2d_visuals.py
    - 📄 test_graph_visuals.py
    - 📄 test_metric_visuals.py
    - 📄 test_microagent_validation.py
    - 📄 test_real_data_fetcher.py
    - 📄 test_repository_comprehensive.py
    - 📄 test_repository.py
    - 📄 test_root_conftest_comprehensive.py
    - 📄 test_root_conftest.py
    - 📄 test_sample_data.py
    - 📄 test_schema_report.py
    - 📄 test_summary_documentation.py
    - 📄 test_workflow_validator.py
  - 📄 **init**.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 add_test_files.sh
- 📄 analyze_pr_mergeability.sh
- 📄 app.py
- 📄 asset_graph.db
- 📄 cleanup-branches.sh
- 📄 close_unmergeable_prs_script.sh
- 📄 close_unmergeable_prs.sh
- 📄 CNAME
- 📄 compass.yml
- 📄 conftest.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 mcp_server.py
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 s
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_scripts.sh
- 📄 test_supabase.py
- 📄 validate_new_tests.sh

## PY Dependencies

### \test_supabase.py

Dependencies:

- __future__
- annotations
- os
- typing
- Final,
- pytest
- supabase
- Client,

### \test_postgres.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- psycopg2
- connect
- env

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

### \tests\_\_init\_\_.py

Dependencies:

- os
- pathlib
- Path
- it.

## JS Dependencies

### \frontend\jest.config.js

Dependencies:

- next/jest

### \frontend\jest.setup.js

Dependencies:

- @testing-library/jest-dom

### \frontend\next.config.js

No dependencies found

### \frontend\tailwind.config.js

No dependencies found

### \frontend\postcss.config.js

No dependencies found

## TS Dependencies

### \frontend\_\_tests\_\_\test-utils.ts

No dependencies found

### \frontend\_\_tests\_\_\test-utils.test.ts

Dependencies:

- ../app/types/api

### \frontend\_\_tests\_\_\lib\api-axios-compatibility.test.ts

Dependencies:

- ../../app/types/api
- ../test-utils

### \frontend\_\_tests\_\_\lib\api.test.ts

Dependencies:

- axios
- ../../app/types/api

### \frontend\_\_tests\_\_\lib\api-upgrade-integration.test.ts

Dependencies:

- axios
- ../test-utils

## TSX Dependencies

### \frontend\_\_tests\_\_\integration\component-integration.test.tsx

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

### \frontend\_\_tests\_\_\components\NetworkVisualization.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api
- ../test-utils

### \frontend\_\_tests\_\_\app\page.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\_\_tests\_\_\components\MetricsDashboard.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api
- ../test-utils

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 database.py
  - 📄 main.py
- 📂 branch_reviews/
- 📂 docs/
- 📂 frontend/
  - 📂 **tests**/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 config/
      - 📄 package-integration.test.ts
      - 📄 package-lock-validation.test.ts
      - 📄 package-validation.test.ts
    - 📂 integration/
      - 📄 component-integration.test.tsx
    - 📂 lib/
      - 📄 api-axios-compatibility.test.ts
      - 📄 api-upgrade-integration.test.ts
      - 📄 api.test.ts
    - 📄 test-utils.test.ts
    - 📄 test-utils.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 assetHelpers.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 **init**.py
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
  - 📄 workflow_validator.py
- 📂 tests/
  - 📂 integration/
    - 📄 **init**.py
    - 📄 conftest.py
    - 📄 test_api_integration.py
    - 📄 test_bearer_workflow.py
    - 📄 test_branch_integration.py
    - 📄 test_debricked_workflow.py
    - 📄 test_documentation_files_validation.py
    - 📄 test_documentation_validation.py
    - 📄 test_github_workflows_helpers.py
    - 📄 test_github_workflows.py
    - 📄 test_github_workflows.py.backup
    - 📄 test_modified_config_files_validation.py
    - 📄 test_pr_agent_config_validation.py
    - 📄 test_pr_agent_workflow_specific.py
    - 📄 test_repository.py
    - 📄 test_requirements_dev.py
    - 📄 test_requirements_pyyaml.py
    - 📄 test_requirements_validation.py
    - 📄 test_requirements.py
    - 📄 test_workflow_changes_validation.py
    - 📄 test_workflow_config_changes.py
    - 📄 test_workflow_documentation.py
    - 📄 test_workflow_requirements_integration.py
    - 📄 test_workflow_security_advanced.py
    - 📄 test_workflow_yaml_validation.py
    - 📄 test_yaml_config_validation.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_database_memory.py
    - 📄 test_database.py
    - 📄 test_db_models.py
    - 📄 test_dev_scripts.py
    - 📄 test_documentation_validation.py
    - 📄 test_financial_models.py
    - 📄 test_formulaic_analysis.py
    - 📄 test_formulaic_visuals.py
    - 📄 test_graph_2d_visuals.py
    - 📄 test_graph_visuals.py
    - 📄 test_metric_visuals.py
    - 📄 test_microagent_validation.py
    - 📄 test_real_data_fetcher.py
    - 📄 test_repository_comprehensive.py
    - 📄 test_repository.py
    - 📄 test_root_conftest_comprehensive.py
    - 📄 test_root_conftest.py
    - 📄 test_sample_data.py
    - 📄 test_schema_report.py
    - 📄 test_summary_documentation.py
    - 📄 test_workflow_validator.py
  - 📄 **init**.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 add_test_files.sh
- 📄 analyze_pr_mergeability.sh
- 📄 app.py
- 📄 asset_graph.db
- 📄 cleanup-branches.sh
- 📄 close_unmergeable_prs_script.sh
- 📄 close_unmergeable_prs.sh
- 📄 CNAME
- 📄 compass.yml
- 📄 conftest.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 mcp_server.py
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 s
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_scripts.sh
- 📄 test_supabase.py
- 📄 validate_new_tests.sh

## PY Dependencies

### \test_postgres.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- psycopg2
- connect
- env

### \mcp_server.py

Dependencies:

- argparse
- copy
- json
- threading
- src.logic.asset_graph
- AssetRelationshipGraph
- src.models.financial_models
- AssetClass,
- mcp.server.fastmcp
- FastMCP
- (lazy)
- e

### \main.py

Dependencies:

- os
- socket
- psycopg2
- dotenv
- load_dotenv
- supabase
- Client,
- .env
- DATABASE_URL

### \test_api.py

Dependencies:

- sys
- fastapi.testclient
- TestClient
- api.main
- app
- traceback

### \conftest.py

Dependencies:

- **future**
- annotations
- collections.abc
- Callable,
- pathlib
- Path
- pytest
- sqlalchemy.engine
- Engine
- sqlalchemy.orm
- Session,
- src.data.database
- (
- within

## JS Dependencies

### \frontend\jest.config.js

Dependencies:

- next/jest

### \frontend\tailwind.config.js

No dependencies found

### \frontend\postcss.config.js

No dependencies found

### \frontend\next.config.js

No dependencies found

### \frontend\jest.setup.js

Dependencies:

- @testing-library/jest-dom

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
- @vercel/speed-insights/next

### \frontend\app\components\NetworkVisualization.tsx

Dependencies:

- react
- next/dynamic
- ../types/api
- plotly.js

### \frontend\app\components\MetricsDashboard.tsx

Dependencies:

- react
- ../types/api

### \frontend\app\components\AssetList.tsx

Dependencies:

- react
- next/navigation
- ../types/api

## TS Dependencies

### \frontend\app\types\api.ts

No dependencies found

### \frontend\app\lib\api.ts

Dependencies:

- axios

### \frontend\_\_tests\_\_\test-utils.ts

No dependencies found

### \frontend\_\_tests\_\_\test-utils.test.ts

Dependencies:

- ../app/types/api

### \frontend\_\_tests\_\_\lib\api-axios-compatibility.test.ts

Dependencies:

- ../../app/types/api
- ../test-utils

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 database.py
  - 📄 main.py
- 📂 branch_reviews/
- 📂 docs/
- 📂 frontend/
  - 📂 **tests**/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 config/
      - 📄 package-integration.test.ts
      - 📄 package-lock-validation.test.ts
      - 📄 package-validation.test.ts
    - 📂 integration/
      - 📄 component-integration.test.tsx
    - 📂 lib/
      - 📄 api-axios-compatibility.test.ts
      - 📄 api-upgrade-integration.test.ts
      - 📄 api.test.ts
    - 📄 test-utils.test.ts
    - 📄 test-utils.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 assetHelpers.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 **init**.py
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
  - 📄 workflow_validator.py
- 📂 tests/
  - 📂 integration/
    - 📄 **init**.py
    - 📄 conftest.py
    - 📄 test_api_integration.py
    - 📄 test_bearer_workflow.py
    - 📄 test_branch_integration.py
    - 📄 test_debricked_workflow.py
    - 📄 test_documentation_files_validation.py
    - 📄 test_documentation_validation.py
    - 📄 test_github_workflows_helpers.py
    - 📄 test_github_workflows.py
    - 📄 test_github_workflows.py.backup
    - 📄 test_modified_config_files_validation.py
    - 📄 test_pr_agent_config_validation.py
    - 📄 test_pr_agent_workflow_specific.py
    - 📄 test_repository.py
    - 📄 test_requirements_dev.py
    - 📄 test_requirements_pyyaml.py
    - 📄 test_requirements_validation.py
    - 📄 test_requirements.py
    - 📄 test_workflow_changes_validation.py
    - 📄 test_workflow_config_changes.py
    - 📄 test_workflow_documentation.py
    - 📄 test_workflow_requirements_integration.py
    - 📄 test_workflow_security_advanced.py
    - 📄 test_workflow_yaml_validation.py
    - 📄 test_yaml_config_validation.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_database_memory.py
    - 📄 test_database.py
    - 📄 test_db_models.py
    - 📄 test_dev_scripts.py
    - 📄 test_documentation_validation.py
    - 📄 test_financial_models.py
    - 📄 test_formulaic_analysis.py
    - 📄 test_formulaic_visuals.py
    - 📄 test_graph_2d_visuals.py
    - 📄 test_graph_visuals.py
    - 📄 test_metric_visuals.py
    - 📄 test_microagent_validation.py
    - 📄 test_real_data_fetcher.py
    - 📄 test_repository_comprehensive.py
    - 📄 test_repository.py
    - 📄 test_root_conftest_comprehensive.py
    - 📄 test_root_conftest.py
    - 📄 test_sample_data.py
    - 📄 test_schema_report.py
    - 📄 test_summary_documentation.py
    - 📄 test_workflow_validator.py
  - 📄 **init**.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 add_test_files.sh
- 📄 analyze_pr_mergeability.sh
- 📄 app.py
- 📄 asset_graph.db
- 📄 cleanup-branches.sh
- 📄 close_unmergeable_prs_script.sh
- 📄 close_unmergeable_prs.sh
- 📄 CNAME
- 📄 compass.yml
- 📄 conftest.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 mcp_server.py
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 s
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_scripts.sh
- 📄 test_supabase.py
- 📄 validate_new_tests.sh

## PY Dependencies

### \test_supabase.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- supabase
- Client,

### \test_postgres.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- psycopg2
- connect
- env

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

### \tests\_\_init\_\_.py

Dependencies:

- os
- pathlib
- Path
- it.

## TS Dependencies

### \frontend\_\_tests\_\_\test-utils.ts

No dependencies found

### \frontend\_\_tests\_\_\test-utils.test.ts

Dependencies:

- ../app/types/api

### \frontend\_\_tests\_\_\lib\api.test.ts

Dependencies:

- axios
- ../../app/types/api

### \frontend\_\_tests\_\_\lib\api-upgrade-integration.test.ts

Dependencies:

- axios
- ../test-utils

### \frontend\_\_tests\_\_\lib\api-axios-compatibility.test.ts

Dependencies:

- ../../app/types/api
- ../test-utils

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

## TSX Dependencies

### \frontend\_\_tests\_\_\integration\component-integration.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\_\_tests\_\_\components\AssetList.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/AssetList
- ../../app/lib/api
- ../test-utils

### \frontend\_\_tests\_\_\app\page.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\app\components\AssetList.tsx

Dependencies:

- react
- next/navigation
- ../types/api

### \frontend\_\_tests\_\_\components\NetworkVisualization.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api
- ../test-utils

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 database.py
  - 📄 main.py
- 📂 branch_reviews/
- 📂 docs/
- 📂 frontend/
  - 📂 **tests**/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 config/
      - 📄 package-integration.test.ts
      - 📄 package-lock-validation.test.ts
      - 📄 package-validation.test.ts
    - 📂 integration/
      - 📄 component-integration.test.tsx
    - 📂 lib/
      - 📄 api-axios-compatibility.test.ts
      - 📄 api-upgrade-integration.test.ts
      - 📄 api.test.ts
    - 📄 test-utils.test.ts
    - 📄 test-utils.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 assetHelpers.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 **init**.py
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
  - 📄 workflow_validator.py
- 📂 tests/
  - 📂 integration/
    - 📄 **init**.py
    - 📄 conftest.py
    - 📄 test_api_integration.py
    - 📄 test_bearer_workflow.py
    - 📄 test_branch_integration.py
    - 📄 test_debricked_workflow.py
    - 📄 test_documentation_files_validation.py
    - 📄 test_documentation_validation.py
    - 📄 test_github_workflows_helpers.py
    - 📄 test_github_workflows.py
    - 📄 test_github_workflows.py.backup
    - 📄 test_modified_config_files_validation.py
    - 📄 test_pr_agent_config_validation.py
    - 📄 test_pr_agent_workflow_specific.py
    - 📄 test_repository.py
    - 📄 test_requirements_dev.py
    - 📄 test_requirements_pyyaml.py
    - 📄 test_requirements_validation.py
    - 📄 test_requirements.py
    - 📄 test_workflow_changes_validation.py
    - 📄 test_workflow_config_changes.py
    - 📄 test_workflow_documentation.py
    - 📄 test_workflow_requirements_integration.py
    - 📄 test_workflow_security_advanced.py
    - 📄 test_workflow_yaml_validation.py
    - 📄 test_yaml_config_validation.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_database_memory.py
    - 📄 test_database.py
    - 📄 test_db_models.py
    - 📄 test_dev_scripts.py
    - 📄 test_documentation_validation.py
    - 📄 test_financial_models.py
    - 📄 test_formulaic_analysis.py
    - 📄 test_formulaic_visuals.py
    - 📄 test_graph_2d_visuals.py
    - 📄 test_graph_visuals.py
    - 📄 test_metric_visuals.py
    - 📄 test_microagent_validation.py
    - 📄 test_real_data_fetcher.py
    - 📄 test_repository_comprehensive.py
    - 📄 test_repository.py
    - 📄 test_root_conftest_comprehensive.py
    - 📄 test_root_conftest.py
    - 📄 test_sample_data.py
    - 📄 test_schema_report.py
    - 📄 test_summary_documentation.py
    - 📄 test_workflow_validator.py
  - 📄 **init**.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 add_test_files.sh
- 📄 analyze_pr_mergeability.sh
- 📄 app.py
- 📄 asset_graph.db
- 📄 cleanup-branches.sh
- 📄 close_unmergeable_prs_script.sh
- 📄 close_unmergeable_prs.sh
- 📄 CNAME
- 📄 compass.yml
- 📄 conftest.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 mcp_server.py
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 s
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_scripts.sh
- 📄 test_supabase.py
- 📄 validate_new_tests.sh

## PY Dependencies

### \test_supabase.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- supabase
- Client,

### \test_postgres.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- psycopg2
- connect
- env

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

### \tests\_\_init\_\_.py

Dependencies:

- os
- pathlib
- Path
- it.

## JS Dependencies

### \frontend\jest.config.js

Dependencies:

- next/jest

### \frontend\tailwind.config.js

No dependencies found

### \frontend\postcss.config.js

No dependencies found

### \frontend\next.config.js

No dependencies found

### \frontend\jest.setup.js

Dependencies:

- @testing-library/jest-dom

## TSX Dependencies

### \frontend\app\page.tsx

Dependencies:

- react
- ./lib/api
- ./components/NetworkVisualization
- ./components/MetricsDashboard
- ./components/AssetList
- ./types/api

### \frontend\_\_tests\_\_\integration\component-integration.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\_\_tests\_\_\components\MetricsDashboard.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api
- ../test-utils

### \frontend\_\_tests\_\_\components\AssetList.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/AssetList
- ../../app/lib/api
- ../test-utils

### \frontend\app\layout.tsx

Dependencies:

- ./globals.css
- next
- @vercel/speed-insights/next

## TS Dependencies

### \frontend\_\_tests\_\_\test-utils.ts

No dependencies found

### \frontend\_\_tests\_\_\test-utils.test.ts

Dependencies:

- ../app/types/api

### \frontend\_\_tests\_\_\lib\api.test.ts

Dependencies:

- axios
- ../../app/types/api

### \frontend\_\_tests\_\_\lib\api-upgrade-integration.test.ts

Dependencies:

- axios
- ../test-utils

### \frontend\_\_tests\_\_\lib\api-axios-compatibility.test.ts

Dependencies:

- ../../app/types/api
- ../test-utils

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 database.py
  - 📄 main.py
- 📂 branch_reviews/
- 📂 docs/
- 📂 frontend/
  - 📂 **tests**/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 config/
      - 📄 package-integration.test.ts
      - 📄 package-lock-validation.test.ts
      - 📄 package-validation.test.ts
    - 📂 integration/
      - 📄 component-integration.test.tsx
    - 📂 lib/
      - 📄 api-axios-compatibility.test.ts
      - 📄 api-upgrade-integration.test.ts
      - 📄 api.test.ts
    - 📄 test-utils.test.ts
    - 📄 test-utils.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 assetHelpers.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 **init**.py
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
  - 📄 workflow_validator.py
- 📂 tests/
  - 📂 integration/
    - 📄 **init**.py
    - 📄 conftest.py
    - 📄 test_api_integration.py
    - 📄 test_bearer_workflow.py
    - 📄 test_branch_integration.py
    - 📄 test_debricked_workflow.py
    - 📄 test_documentation_files_validation.py
    - 📄 test_documentation_validation.py
    - 📄 test_github_workflows_helpers.py
    - 📄 test_github_workflows.py
    - 📄 test_github_workflows.py.backup
    - 📄 test_modified_config_files_validation.py
    - 📄 test_pr_agent_config_validation.py
    - 📄 test_pr_agent_workflow_specific.py
    - 📄 test_repository.py
    - 📄 test_requirements_dev.py
    - 📄 test_requirements_pyyaml.py
    - 📄 test_requirements_validation.py
    - 📄 test_requirements.py
    - 📄 test_workflow_changes_validation.py
    - 📄 test_workflow_config_changes.py
    - 📄 test_workflow_documentation.py
    - 📄 test_workflow_requirements_integration.py
    - 📄 test_workflow_security_advanced.py
    - 📄 test_workflow_yaml_validation.py
    - 📄 test_yaml_config_validation.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_database_memory.py
    - 📄 test_database.py
    - 📄 test_db_models.py
    - 📄 test_dev_scripts.py
    - 📄 test_documentation_validation.py
    - 📄 test_financial_models.py
    - 📄 test_formulaic_analysis.py
    - 📄 test_formulaic_visuals.py
    - 📄 test_graph_2d_visuals.py
    - 📄 test_graph_visuals.py
    - 📄 test_metric_visuals.py
    - 📄 test_microagent_validation.py
    - 📄 test_real_data_fetcher.py
    - 📄 test_repository_comprehensive.py
    - 📄 test_repository.py
    - 📄 test_root_conftest_comprehensive.py
    - 📄 test_root_conftest.py
    - 📄 test_sample_data.py
    - 📄 test_schema_report.py
    - 📄 test_summary_documentation.py
    - 📄 test_workflow_validator.py
  - 📄 **init**.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 add_test_files.sh
- 📄 analyze_pr_mergeability.sh
- 📄 app.py
- 📄 asset_graph.db
- 📄 cleanup-branches.sh
- 📄 close_unmergeable_prs_script.sh
- 📄 close_unmergeable_prs.sh
- 📄 CNAME
- 📄 compass.yml
- 📄 conftest.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 mcp_server.py
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 s
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_scripts.sh
- 📄 test_supabase.py
- 📄 validate_new_tests.sh

## PY Dependencies

### \test_supabase.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- supabase
- Client,

### \test_postgres.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- psycopg2
- connect
- env

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

### \tests\_\_init\_\_.py

Dependencies:

- os
- pathlib
- Path
- it.

## JS Dependencies

### \frontend\next.config.js

No dependencies found

### \frontend\jest.setup.js

Dependencies:

- @testing-library/jest-dom

### \frontend\jest.config.js

Dependencies:

- next/jest

### \frontend\tailwind.config.js

No dependencies found

### \frontend\postcss.config.js

No dependencies found

## TSX Dependencies

### \frontend\app\layout.tsx

Dependencies:

- ./globals.css
- next
- @vercel/speed-insights/next

### \frontend\_\_tests\_\_\integration\component-integration.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\app\components\NetworkVisualization.tsx

Dependencies:

- react
- next/dynamic
- ../types/api
- plotly.js

### \frontend\app\components\MetricsDashboard.tsx

Dependencies:

- react
- ../types/api

### \frontend\app\components\AssetList.tsx

Dependencies:

- react
- next/navigation
- ../types/api

## TS Dependencies

### \frontend\_\_tests\_\_\test-utils.ts

No dependencies found

### \frontend\_\_tests\_\_\test-utils.test.ts

Dependencies:

- ../app/types/api

### \frontend\_\_tests\_\_\lib\api.test.ts

Dependencies:

- axios
- ../../app/types/api

### \frontend\_\_tests\_\_\lib\api-upgrade-integration.test.ts

Dependencies:

- axios
- ../test-utils

### \frontend\_\_tests\_\_\lib\api-axios-compatibility.test.ts

Dependencies:

- ../../app/types/api
- ../test-utils

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 database.py
  - 📄 main.py
- 📂 branch_reviews/
- 📂 docs/
- 📂 frontend/
  - 📂 **tests**/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 config/
      - 📄 package-integration.test.ts
      - 📄 package-lock-validation.test.ts
      - 📄 package-validation.test.ts
    - 📂 integration/
      - 📄 component-integration.test.tsx
    - 📂 lib/
      - 📄 api-axios-compatibility.test.ts
      - 📄 api-upgrade-integration.test.ts
      - 📄 api.test.ts
    - 📄 test-utils.test.ts
    - 📄 test-utils.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 assetHelpers.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 **init**.py
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
  - 📄 workflow_validator.py
- 📂 tests/
  - 📂 integration/
    - 📄 **init**.py
    - 📄 conftest.py
    - 📄 test_api_integration.py
    - 📄 test_bearer_workflow.py
    - 📄 test_branch_integration.py
    - 📄 test_debricked_workflow.py
    - 📄 test_documentation_files_validation.py
    - 📄 test_documentation_validation.py
    - 📄 test_github_workflows_helpers.py
    - 📄 test_github_workflows.py
    - 📄 test_github_workflows.py.backup
    - 📄 test_modified_config_files_validation.py
    - 📄 test_pr_agent_config_validation.py
    - 📄 test_pr_agent_workflow_specific.py
    - 📄 test_repository.py
    - 📄 test_requirements_dev.py
    - 📄 test_requirements_pyyaml.py
    - 📄 test_requirements_validation.py
    - 📄 test_requirements.py
    - 📄 test_workflow_changes_validation.py
    - 📄 test_workflow_config_changes.py
    - 📄 test_workflow_documentation.py
    - 📄 test_workflow_requirements_integration.py
    - 📄 test_workflow_security_advanced.py
    - 📄 test_workflow_yaml_validation.py
    - 📄 test_yaml_config_validation.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_database_memory.py
    - 📄 test_database.py
    - 📄 test_db_models.py
    - 📄 test_dev_scripts.py
    - 📄 test_documentation_validation.py
    - 📄 test_financial_models.py
    - 📄 test_formulaic_analysis.py
    - 📄 test_formulaic_visuals.py
    - 📄 test_graph_2d_visuals.py
    - 📄 test_graph_visuals.py
    - 📄 test_metric_visuals.py
    - 📄 test_microagent_validation.py
    - 📄 test_real_data_fetcher.py
    - 📄 test_repository_comprehensive.py
    - 📄 test_repository.py
    - 📄 test_root_conftest_comprehensive.py
    - 📄 test_root_conftest.py
    - 📄 test_sample_data.py
    - 📄 test_schema_report.py
    - 📄 test_summary_documentation.py
    - 📄 test_workflow_validator.py
  - 📄 **init**.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 add_test_files.sh
- 📄 analyze_pr_mergeability.sh
- 📄 app.py
- 📄 asset_graph.db
- 📄 cleanup-branches.sh
- 📄 close_unmergeable_prs_script.sh
- 📄 close_unmergeable_prs.sh
- 📄 CNAME
- 📄 compass.yml
- 📄 conftest.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 mcp_server.py
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 s
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_scripts.sh
- 📄 test_supabase.py
- 📄 validate_new_tests.sh

## PY Dependencies

### \mcp_server.py

Dependencies:

- argparse
- copy
- json
- threading
- src.logic.asset_graph
- AssetRelationshipGraph
- src.models.financial_models
- AssetClass,
- mcp.server.fastmcp
- FastMCP
- (lazy)
- e

### \main.py

Dependencies:

- os
- socket
- psycopg2
- dotenv
- load_dotenv
- supabase
- Client,
- .env
- DATABASE_URL

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

### \test_supabase.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- supabase
- Client,

## JS Dependencies

### \frontend\next.config.js

No dependencies found

### \frontend\postcss.config.js

No dependencies found

### \frontend\jest.setup.js

Dependencies:

- @testing-library/jest-dom

### \frontend\jest.config.js

Dependencies:

- next/jest

### \frontend\tailwind.config.js

No dependencies found

## TS Dependencies

### \frontend\_\_tests\_\_\test-utils.ts

No dependencies found

### \frontend\_\_tests\_\_\test-utils.test.ts

Dependencies:

- ../app/types/api

### \frontend\_\_tests\_\_\lib\api.test.ts

Dependencies:

- axios
- ../../app/types/api

### \frontend\app\types\api.ts

No dependencies found

### \frontend\_\_tests\_\_\lib\api-upgrade-integration.test.ts

Dependencies:

- axios
- ../test-utils

## TSX Dependencies

### \frontend\app\page.tsx

Dependencies:

- react
- ./lib/api
- ./components/NetworkVisualization
- ./components/MetricsDashboard
- ./components/AssetList
- ./types/api

### \frontend\_\_tests\_\_\integration\component-integration.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\app\layout.tsx

Dependencies:

- ./globals.css
- next
- @vercel/speed-insights/next

### \frontend\_\_tests\_\_\components\NetworkVisualization.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api
- ../test-utils

### \frontend\_\_tests\_\_\components\MetricsDashboard.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api
- ../test-utils

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 database.py
  - 📄 main.py
- 📂 branch_reviews/
- 📂 docs/
- 📂 frontend/
  - 📂 **tests**/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 config/
      - 📄 package-integration.test.ts
      - 📄 package-lock-validation.test.ts
      - 📄 package-validation.test.ts
    - 📂 integration/
      - 📄 component-integration.test.tsx
    - 📂 lib/
      - 📄 api-axios-compatibility.test.ts
      - 📄 api-upgrade-integration.test.ts
      - 📄 api.test.ts
    - 📄 test-utils.test.ts
    - 📄 test-utils.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 assetHelpers.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 **init**.py
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
  - 📄 workflow_validator.py
- 📂 tests/
  - 📂 integration/
    - 📄 **init**.py
    - 📄 conftest.py
    - 📄 test_api_integration.py
    - 📄 test_bearer_workflow.py
    - 📄 test_branch_integration.py
    - 📄 test_debricked_workflow.py
    - 📄 test_documentation_files_validation.py
    - 📄 test_documentation_validation.py
    - 📄 test_github_workflows_helpers.py
    - 📄 test_github_workflows.py
    - 📄 test_github_workflows.py.backup
    - 📄 test_modified_config_files_validation.py
    - 📄 test_pr_agent_config_validation.py
    - 📄 test_pr_agent_workflow_specific.py
    - 📄 test_repository.py
    - 📄 test_requirements_dev.py
    - 📄 test_requirements_pyyaml.py
    - 📄 test_requirements_validation.py
    - 📄 test_requirements.py
    - 📄 test_workflow_changes_validation.py
    - 📄 test_workflow_config_changes.py
    - 📄 test_workflow_documentation.py
    - 📄 test_workflow_requirements_integration.py
    - 📄 test_workflow_security_advanced.py
    - 📄 test_workflow_yaml_validation.py
    - 📄 test_yaml_config_validation.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_database_memory.py
    - 📄 test_database.py
    - 📄 test_db_models.py
    - 📄 test_dev_scripts.py
    - 📄 test_documentation_validation.py
    - 📄 test_financial_models.py
    - 📄 test_formulaic_analysis.py
    - 📄 test_formulaic_visuals.py
    - 📄 test_graph_2d_visuals.py
    - 📄 test_graph_visuals.py
    - 📄 test_metric_visuals.py
    - 📄 test_microagent_validation.py
    - 📄 test_real_data_fetcher.py
    - 📄 test_repository_comprehensive.py
    - 📄 test_repository.py
    - 📄 test_root_conftest_comprehensive.py
    - 📄 test_root_conftest.py
    - 📄 test_sample_data.py
    - 📄 test_schema_report.py
    - 📄 test_summary_documentation.py
    - 📄 test_workflow_validator.py
  - 📄 **init**.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 add_test_files.sh
- 📄 analyze_pr_mergeability.sh
- 📄 app.py
- 📄 asset_graph.db
- 📄 cleanup-branches.sh
- 📄 close_unmergeable_prs_script.sh
- 📄 close_unmergeable_prs.sh
- 📄 CNAME
- 📄 compass.yml
- 📄 conftest.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 mcp_server.py
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 s
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_scripts.sh
- 📄 test_supabase.py
- 📄 validate_new_tests.sh

## PY Dependencies

### \test_supabase.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- supabase
- Client,

### \test_postgres.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- psycopg2
- connect
- env

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

### \tests\_\_init\_\_.py

Dependencies:

- os
- pathlib
- Path
- it.

## JS Dependencies

### \frontend\jest.config.js

Dependencies:

- next/jest

### \frontend\postcss.config.js

No dependencies found

### \frontend\tailwind.config.js

No dependencies found

### \frontend\next.config.js

No dependencies found

### \frontend\jest.setup.js

Dependencies:

- @testing-library/jest-dom

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
- @vercel/speed-insights/next

### \frontend\app\components\NetworkVisualization.tsx

Dependencies:

- react
- next/dynamic
- ../types/api
- plotly.js

### \frontend\app\components\MetricsDashboard.tsx

Dependencies:

- react
- ../types/api

### \frontend\app\components\AssetList.tsx

Dependencies:

- react
- next/navigation
- ../types/api

## TS Dependencies

### \frontend\app\types\api.ts

No dependencies found

### \frontend\app\lib\api.ts

Dependencies:

- axios

### \frontend\app\lib\assetHelpers.ts

Dependencies:

- ./api
- ../types/api

### \frontend\app\lib\index.ts

No dependencies found

### \frontend\_\_tests\_\_\test-utils.ts

No dependencies found

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 database.py
  - 📄 main.py
- 📂 branch_reviews/
- 📂 docs/
- 📂 frontend/
  - 📂 **tests**/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 config/
      - 📄 package-integration.test.ts
      - 📄 package-lock-validation.test.ts
      - 📄 package-validation.test.ts
    - 📂 integration/
      - 📄 component-integration.test.tsx
    - 📂 lib/
      - 📄 api-axios-compatibility.test.ts
      - 📄 api-upgrade-integration.test.ts
      - 📄 api.test.ts
    - 📄 test-utils.test.ts
    - 📄 test-utils.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 assetHelpers.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 **init**.py
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
  - 📄 workflow_validator.py
- 📂 tests/
  - 📂 integration/
    - 📄 **init**.py
    - 📄 conftest.py
    - 📄 test_api_integration.py
    - 📄 test_bearer_workflow.py
    - 📄 test_branch_integration.py
    - 📄 test_debricked_workflow.py
    - 📄 test_documentation_files_validation.py
    - 📄 test_documentation_validation.py
    - 📄 test_github_workflows_helpers.py
    - 📄 test_github_workflows.py
    - 📄 test_github_workflows.py.backup
    - 📄 test_modified_config_files_validation.py
    - 📄 test_pr_agent_config_validation.py
    - 📄 test_pr_agent_workflow_specific.py
    - 📄 test_repository.py
    - 📄 test_requirements_dev.py
    - 📄 test_requirements_pyyaml.py
    - 📄 test_requirements_validation.py
    - 📄 test_requirements.py
    - 📄 test_workflow_changes_validation.py
    - 📄 test_workflow_config_changes.py
    - 📄 test_workflow_documentation.py
    - 📄 test_workflow_requirements_integration.py
    - 📄 test_workflow_security_advanced.py
    - 📄 test_workflow_yaml_validation.py
    - 📄 test_yaml_config_validation.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_database_memory.py
    - 📄 test_database.py
    - 📄 test_db_models.py
    - 📄 test_dev_scripts.py
    - 📄 test_documentation_validation.py
    - 📄 test_financial_models.py
    - 📄 test_formulaic_analysis.py
    - 📄 test_formulaic_visuals.py
    - 📄 test_graph_2d_visuals.py
    - 📄 test_graph_visuals.py
    - 📄 test_metric_visuals.py
    - 📄 test_microagent_validation.py
    - 📄 test_real_data_fetcher.py
    - 📄 test_repository_comprehensive.py
    - 📄 test_repository.py
    - 📄 test_root_conftest_comprehensive.py
    - 📄 test_root_conftest.py
    - 📄 test_sample_data.py
    - 📄 test_schema_report.py
    - 📄 test_summary_documentation.py
    - 📄 test_workflow_validator.py
  - 📄 **init**.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 add_test_files.sh
- 📄 analyze_pr_mergeability.sh
- 📄 app.py
- 📄 asset_graph.db
- 📄 cleanup-branches.sh
- 📄 close_unmergeable_prs_script.sh
- 📄 close_unmergeable_prs.sh
- 📄 CNAME
- 📄 compass.yml
- 📄 conftest.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 mcp_server.py
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 s
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_scripts.sh
- 📄 test_supabase.py
- 📄 validate_new_tests.sh

## PY Dependencies

### \test_supabase.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- supabase
- Client,

### \test_postgres.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- psycopg2
- connect
- env

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

### \tests\_\_init\_\_.py

Dependencies:

- os
- pathlib
- Path
- it.

## JS Dependencies

### \frontend\next.config.js

No dependencies found

### \frontend\jest.setup.js

Dependencies:

- @testing-library/jest-dom

### \frontend\postcss.config.js

No dependencies found

### \frontend\tailwind.config.js

No dependencies found

### \frontend\jest.config.js

Dependencies:

- next/jest

## TS Dependencies

### \frontend\_\_tests\_\_\test-utils.test.ts

Dependencies:

- ../app/types/api

### \frontend\_\_tests\_\_\test-utils.ts

No dependencies found

### \frontend\_\_tests\_\_\lib\api.test.ts

Dependencies:

- axios
- ../../app/types/api

### \frontend\_\_tests\_\_\lib\api-upgrade-integration.test.ts

Dependencies:

- axios
- ../test-utils

### \frontend\_\_tests\_\_\lib\api-axios-compatibility.test.ts

Dependencies:

- ../../app/types/api
- ../test-utils

## TSX Dependencies

### \frontend\_\_tests\_\_\integration\component-integration.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\_\_tests\_\_\components\NetworkVisualization.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api
- ../test-utils

### \frontend\_\_tests\_\_\components\MetricsDashboard.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api
- ../test-utils

### \frontend\_\_tests\_\_\components\AssetList.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/AssetList
- ../../app/lib/api
- ../test-utils

### \frontend\_\_tests\_\_\app\page.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 database.py
  - 📄 main.py
- 📂 branch_reviews/
- 📂 docs/
- 📂 frontend/
  - 📂 **tests**/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 config/
      - 📄 package-integration.test.ts
      - 📄 package-lock-validation.test.ts
      - 📄 package-validation.test.ts
    - 📂 integration/
      - 📄 component-integration.test.tsx
    - 📂 lib/
      - 📄 api-axios-compatibility.test.ts
      - 📄 api-upgrade-integration.test.ts
      - 📄 api.test.ts
    - 📄 test-utils.test.ts
    - 📄 test-utils.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 assetHelpers.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 **init**.py
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
  - 📄 workflow_validator.py
- 📂 tests/
  - 📂 integration/
    - 📄 **init**.py
    - 📄 conftest.py
    - 📄 test_api_integration.py
    - 📄 test_bearer_workflow.py
    - 📄 test_branch_integration.py
    - 📄 test_debricked_workflow.py
    - 📄 test_documentation_files_validation.py
    - 📄 test_documentation_validation.py
    - 📄 test_github_workflows_helpers.py
    - 📄 test_github_workflows.py
    - 📄 test_github_workflows.py.backup
    - 📄 test_modified_config_files_validation.py
    - 📄 test_pr_agent_config_validation.py
    - 📄 test_pr_agent_workflow_specific.py
    - 📄 test_repository.py
    - 📄 test_requirements_dev.py
    - 📄 test_requirements_pyyaml.py
    - 📄 test_requirements_validation.py
    - 📄 test_requirements.py
    - 📄 test_workflow_changes_validation.py
    - 📄 test_workflow_config_changes.py
    - 📄 test_workflow_documentation.py
    - 📄 test_workflow_requirements_integration.py
    - 📄 test_workflow_security_advanced.py
    - 📄 test_workflow_yaml_validation.py
    - 📄 test_yaml_config_validation.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_database_memory.py
    - 📄 test_database.py
    - 📄 test_db_models.py
    - 📄 test_dev_scripts.py
    - 📄 test_documentation_validation.py
    - 📄 test_financial_models.py
    - 📄 test_formulaic_analysis.py
    - 📄 test_formulaic_visuals.py
    - 📄 test_graph_2d_visuals.py
    - 📄 test_graph_visuals.py
    - 📄 test_metric_visuals.py
    - 📄 test_microagent_validation.py
    - 📄 test_real_data_fetcher.py
    - 📄 test_repository_comprehensive.py
    - 📄 test_repository.py
    - 📄 test_root_conftest_comprehensive.py
    - 📄 test_root_conftest.py
    - 📄 test_sample_data.py
    - 📄 test_schema_report.py
    - 📄 test_summary_documentation.py
    - 📄 test_workflow_validator.py
  - 📄 **init**.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 add_test_files.sh
- 📄 analyze_pr_mergeability.sh
- 📄 app.py
- 📄 asset_graph.db
- 📄 cleanup-branches.sh
- 📄 close_unmergeable_prs_script.sh
- 📄 close_unmergeable_prs.sh
- 📄 CNAME
- 📄 compass.yml
- 📄 conftest.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 mcp_server.py
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 s
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_scripts.sh
- 📄 test_supabase.py
- 📄 validate_new_tests.sh

## PY Dependencies

### \test_supabase.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- supabase
- Client,

### \test_postgres.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- psycopg2
- connect
- env

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

### \tests\_\_init\_\_.py

Dependencies:

- os
- pathlib
- Path
- it.

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

### \frontend\_\_tests\_\_\test-utils.ts

No dependencies found

### \frontend\_\_tests\_\_\test-utils.test.ts

Dependencies:

- ../app/types/api

### \frontend\_\_tests\_\_\lib\api.test.ts

Dependencies:

- axios
- ../../app/types/api

### \frontend\_\_tests\_\_\lib\api-upgrade-integration.test.ts

Dependencies:

- axios
- ../test-utils

### \frontend\_\_tests\_\_\lib\api-axios-compatibility.test.ts

Dependencies:

- ../../app/types/api
- ../test-utils

## TSX Dependencies

### \frontend\_\_tests\_\_\integration\component-integration.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

### \frontend\_\_tests\_\_\components\NetworkVisualization.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
- ../../app/types/api
- ../test-utils

### \frontend\_\_tests\_\_\components\MetricsDashboard.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api
- ../test-utils

### \frontend\_\_tests\_\_\components\AssetList.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/AssetList
- ../../app/lib/api
- ../test-utils

### \frontend\_\_tests\_\_\app\page.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 database.py
  - 📄 main.py
- 📂 branch_reviews/
- 📂 docs/
- 📂 frontend/
  - 📂 **tests**/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 config/
      - 📄 package-integration.test.ts
      - 📄 package-lock-validation.test.ts
      - 📄 package-validation.test.ts
    - 📂 integration/
      - 📄 component-integration.test.tsx
    - 📂 lib/
      - 📄 api-axios-compatibility.test.ts
      - 📄 api-upgrade-integration.test.ts
      - 📄 api.test.ts
    - 📄 test-utils.test.ts
    - 📄 test-utils.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 assetHelpers.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 **init**.py
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
  - 📄 workflow_validator.py
- 📂 tests/
  - 📂 integration/
    - 📄 **init**.py
    - 📄 conftest.py
    - 📄 test_api_integration.py
    - 📄 test_bearer_workflow.py
    - 📄 test_branch_integration.py
    - 📄 test_debricked_workflow.py
    - 📄 test_documentation_files_validation.py
    - 📄 test_documentation_validation.py
    - 📄 test_github_workflows_helpers.py
    - 📄 test_github_workflows.py
    - 📄 test_github_workflows.py.backup
    - 📄 test_modified_config_files_validation.py
    - 📄 test_pr_agent_config_validation.py
    - 📄 test_pr_agent_workflow_specific.py
    - 📄 test_repository.py
    - 📄 test_requirements_dev.py
    - 📄 test_requirements_pyyaml.py
    - 📄 test_requirements_validation.py
    - 📄 test_requirements.py
    - 📄 test_workflow_changes_validation.py
    - 📄 test_workflow_config_changes.py
    - 📄 test_workflow_documentation.py
    - 📄 test_workflow_requirements_integration.py
    - 📄 test_workflow_security_advanced.py
    - 📄 test_workflow_yaml_validation.py
    - 📄 test_yaml_config_validation.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_database_memory.py
    - 📄 test_database.py
    - 📄 test_db_models.py
    - 📄 test_dev_scripts.py
    - 📄 test_documentation_validation.py
    - 📄 test_financial_models.py
    - 📄 test_formulaic_analysis.py
    - 📄 test_formulaic_visuals.py
    - 📄 test_graph_2d_visuals.py
    - 📄 test_graph_visuals.py
    - 📄 test_metric_visuals.py
    - 📄 test_microagent_validation.py
    - 📄 test_real_data_fetcher.py
    - 📄 test_repository_comprehensive.py
    - 📄 test_repository.py
    - 📄 test_root_conftest_comprehensive.py
    - 📄 test_root_conftest.py
    - 📄 test_sample_data.py
    - 📄 test_schema_report.py
    - 📄 test_summary_documentation.py
    - 📄 test_workflow_validator.py
  - 📄 **init**.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 add_test_files.sh
- 📄 analyze_pr_mergeability.sh
- 📄 app.py
- 📄 asset_graph.db
- 📄 cleanup-branches.sh
- 📄 close_unmergeable_prs_script.sh
- 📄 close_unmergeable_prs.sh
- 📄 CNAME
- 📄 compass.yml
- 📄 conftest.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 mcp_server.py
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 s
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_scripts.sh
- 📄 test_supabase.py
- 📄 validate_new_tests.sh

## PY Dependencies

### \test_supabase.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- supabase
- Client,

### \test_postgres.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- psycopg2
- connect
- env

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

### \tests\_\_init\_\_.py

Dependencies:

- os
- pathlib
- Path
- it.

## JS Dependencies

### \frontend\next.config.js

No dependencies found

### \frontend\jest.setup.js

Dependencies:

- @testing-library/jest-dom

### \frontend\jest.config.js

Dependencies:

- next/jest

### \frontend\tailwind.config.js

No dependencies found

### \frontend\postcss.config.js

No dependencies found

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
- @vercel/speed-insights/next

### \frontend\app\components\NetworkVisualization.tsx

Dependencies:

- react
- next/dynamic
- ../types/api
- plotly.js

### \frontend\app\components\MetricsDashboard.tsx

Dependencies:

- react
- ../types/api

### \frontend\app\components\AssetList.tsx

Dependencies:

- react
- next/navigation
- ../types/api

## TS Dependencies

### \frontend\app\lib\assetHelpers.ts

Dependencies:

- ./api
- ../types/api

### \frontend\_\_tests\_\_\test-utils.ts

No dependencies found

### \frontend\app\lib\index.ts

No dependencies found

### \frontend\app\lib\api.ts

Dependencies:

- axios

### \frontend\_\_tests\_\_\test-utils.test.ts

Dependencies:

- ../app/types/api

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 database.py
  - 📄 main.py
- 📂 branch_reviews/
- 📂 docs/
- 📂 frontend/
  - 📂 **tests**/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 config/
      - 📄 package-integration.test.ts
      - 📄 package-lock-validation.test.ts
      - 📄 package-validation.test.ts
    - 📂 integration/
      - 📄 component-integration.test.tsx
    - 📂 lib/
      - 📄 api-axios-compatibility.test.ts
      - 📄 api-upgrade-integration.test.ts
      - 📄 api.test.ts
    - 📄 test-utils.test.ts
    - 📄 test-utils.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 assetHelpers.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 **init**.py
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
  - 📄 workflow_validator.py
- 📂 tests/
  - 📂 integration/
    - 📄 **init**.py
    - 📄 conftest.py
    - 📄 test_api_integration.py
    - 📄 test_bearer_workflow.py
    - 📄 test_branch_integration.py
    - 📄 test_debricked_workflow.py
    - 📄 test_documentation_files_validation.py
    - 📄 test_documentation_validation.py
    - 📄 test_github_workflows_helpers.py
    - 📄 test_github_workflows.py
    - 📄 test_github_workflows.py.backup
    - 📄 test_modified_config_files_validation.py
    - 📄 test_pr_agent_config_validation.py
    - 📄 test_pr_agent_workflow_specific.py
    - 📄 test_repository.py
    - 📄 test_requirements_dev.py
    - 📄 test_requirements_pyyaml.py
    - 📄 test_requirements_validation.py
    - 📄 test_requirements.py
    - 📄 test_workflow_changes_validation.py
    - 📄 test_workflow_config_changes.py
    - 📄 test_workflow_documentation.py
    - 📄 test_workflow_requirements_integration.py
    - 📄 test_workflow_security_advanced.py
    - 📄 test_workflow_yaml_validation.py
    - 📄 test_yaml_config_validation.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_database_memory.py
    - 📄 test_database.py
    - 📄 test_db_models.py
    - 📄 test_dev_scripts.py
    - 📄 test_documentation_validation.py
    - 📄 test_financial_models.py
    - 📄 test_formulaic_analysis.py
    - 📄 test_formulaic_visuals.py
    - 📄 test_graph_2d_visuals.py
    - 📄 test_graph_visuals.py
    - 📄 test_metric_visuals.py
    - 📄 test_microagent_validation.py
    - 📄 test_real_data_fetcher.py
    - 📄 test_repository_comprehensive.py
    - 📄 test_repository.py
    - 📄 test_root_conftest_comprehensive.py
    - 📄 test_root_conftest.py
    - 📄 test_sample_data.py
    - 📄 test_schema_report.py
    - 📄 test_summary_documentation.py
    - 📄 test_workflow_validator.py
  - 📄 **init**.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 add_test_files.sh
- 📄 analyze_pr_mergeability.sh
- 📄 app.py
- 📄 asset_graph.db
- 📄 cleanup-branches.sh
- 📄 close_unmergeable_prs_script.sh
- 📄 close_unmergeable_prs.sh
- 📄 CNAME
- 📄 compass.yml
- 📄 conftest.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 mcp_server.py
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 s
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_scripts.sh
- 📄 test_supabase.py
- 📄 validate_new_tests.sh

## PY Dependencies

### \test_supabase.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- supabase
- Client,

### \test_postgres.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- psycopg2
- connect
- env

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

### \tests\_\_init\_\_.py

Dependencies:

- os
- pathlib
- Path
- it.

## JS Dependencies

### \frontend\next.config.js

No dependencies found

### \frontend\jest.setup.js

Dependencies:

- @testing-library/jest-dom

### \frontend\jest.config.js

Dependencies:

- next/jest

### \frontend\tailwind.config.js

No dependencies found

### \frontend\postcss.config.js

No dependencies found

## TS Dependencies

### \frontend\app\types\api.ts

No dependencies found

### \frontend\app\lib\index.ts

No dependencies found

### \frontend\app\lib\assetHelpers.ts

Dependencies:

- ./api
- ../types/api

### \frontend\app\lib\api.ts

Dependencies:

- axios

### \frontend\_\_tests\_\_\test-utils.ts

No dependencies found

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
- @vercel/speed-insights/next

### \frontend\app\components\AssetList.tsx

Dependencies:

- react
- next/navigation
- ../types/api

### \frontend\app\components\NetworkVisualization.tsx

Dependencies:

- react
- next/dynamic
- ../types/api
- plotly.js

### \frontend\app\components\MetricsDashboard.tsx

Dependencies:

- react
- ../types/api

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 database.py
  - 📄 main.py
- 📂 branch_reviews/
- 📂 docs/
- 📂 frontend/
  - 📂 **tests**/
    - 📂 app/
      - 📄 page.test.tsx
    - 📂 components/
      - 📄 AssetList.test.tsx
      - 📄 MetricsDashboard.test.tsx
      - 📄 NetworkVisualization.test.tsx
    - 📂 config/
      - 📄 package-integration.test.ts
      - 📄 package-lock-validation.test.ts
      - 📄 package-validation.test.ts
    - 📂 integration/
      - 📄 component-integration.test.tsx
    - 📂 lib/
      - 📄 api-axios-compatibility.test.ts
      - 📄 api-upgrade-integration.test.ts
      - 📄 api.test.ts
    - 📄 test-utils.test.ts
    - 📄 test-utils.ts
  - 📂 app/
    - 📂 components/
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📄 api.ts
      - 📄 assetHelpers.ts
      - 📄 index.ts
    - 📂 types/
      - 📄 api.ts
    - 📄 globals.css
    - 📄 layout.tsx
    - 📄 page.tsx
  - 📄 jest.config.js
  - 📄 jest.setup.js
  - 📄 next.config.js
  - 📄 postcss.config.js
  - 📄 tailwind.config.js
- 📂 migrations/
  - 📄 001_initial.sql
- 📂 src/
  - 📂 analysis/
    - 📄 **init**.py
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
  - 📄 workflow_validator.py
- 📂 tests/
  - 📂 integration/
    - 📄 **init**.py
    - 📄 conftest.py
    - 📄 test_api_integration.py
    - 📄 test_bearer_workflow.py
    - 📄 test_branch_integration.py
    - 📄 test_debricked_workflow.py
    - 📄 test_documentation_files_validation.py
    - 📄 test_documentation_validation.py
    - 📄 test_github_workflows_helpers.py
    - 📄 test_github_workflows.py
    - 📄 test_github_workflows.py.backup
    - 📄 test_modified_config_files_validation.py
    - 📄 test_pr_agent_config_validation.py
    - 📄 test_pr_agent_workflow_specific.py
    - 📄 test_repository.py
    - 📄 test_requirements_dev.py
    - 📄 test_requirements_pyyaml.py
    - 📄 test_requirements_validation.py
    - 📄 test_requirements.py
    - 📄 test_workflow_changes_validation.py
    - 📄 test_workflow_config_changes.py
    - 📄 test_workflow_documentation.py
    - 📄 test_workflow_requirements_integration.py
    - 📄 test_workflow_security_advanced.py
    - 📄 test_workflow_yaml_validation.py
    - 📄 test_yaml_config_validation.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_database_memory.py
    - 📄 test_database.py
    - 📄 test_db_models.py
    - 📄 test_dev_scripts.py
    - 📄 test_documentation_validation.py
    - 📄 test_financial_models.py
    - 📄 test_formulaic_analysis.py
    - 📄 test_formulaic_visuals.py
    - 📄 test_graph_2d_visuals.py
    - 📄 test_graph_visuals.py
    - 📄 test_metric_visuals.py
    - 📄 test_microagent_validation.py
    - 📄 test_real_data_fetcher.py
    - 📄 test_repository_comprehensive.py
    - 📄 test_repository.py
    - 📄 test_root_conftest_comprehensive.py
    - 📄 test_root_conftest.py
    - 📄 test_sample_data.py
    - 📄 test_schema_report.py
    - 📄 test_summary_documentation.py
    - 📄 test_workflow_validator.py
  - 📄 **init**.py
  - 📄 conftest.py
- 📄 =2.8.0
- 📄 add_test_files.sh
- 📄 analyze_pr_mergeability.sh
- 📄 app.py
- 📄 asset_graph.db
- 📄 cleanup-branches.sh
- 📄 close_unmergeable_prs_script.sh
- 📄 close_unmergeable_prs.sh
- 📄 CNAME
- 📄 compass.yml
- 📄 conftest.py
- 📄 docker-compose.yml
- 📄 Dockerfile
- 📄 latest_ci_logs.zip
- 📄 LICENSE
- 📄 main.py
- 📄 Makefile
- 📄 mcp_server.py
- 📄 prod-ca-2021.crt
- 📄 pyproject.toml
- 📄 python_ci_logs.zip
- 📄 python38_logs.txt
- 📄 requirements-dev.txt
- 📄 requirements.txt
- 📄 run-dev.bat
- 📄 run-dev.sh
- 📄 s
- 📄 test_api.py
- 📄 test_db_module.py
- 📄 test_postgres.py
- 📄 test_scripts.sh
- 📄 test_supabase.py
- 📄 validate_new_tests.sh

## PY Dependencies

### \app.py

Dependencies:

- json
- logging
- dataclasses
- asdict
- typing
- Dict,
- gradio
- plotly.graph_objects
- src.analysis.formulaic_analysis
- FormulaicdAnalyzer
- src.data.real_data_fetcher
- create_real_database
- src.logic.asset_graph
- AssetRelationshipGraph
- src.models.financial_models
- Asset
- src.reports.schema_report
- generate_schema_report
- src.visualizations.formulaic_visuals
- FormulaicVisualizer
- src.visualizations.graph_2d_visuals
- visualize_2d_graph
- src.visualizations.graph_visuals
- (
- Yahoo
- starting.
- the

### \main.py

Dependencies:

- os
- socket
- psycopg2
- dotenv
- load_dotenv
- supabase
- Client,
- .env
- DATABASE_URL

### \test_supabase.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- supabase
- Client,

### \test_postgres.py

Dependencies:

- **future**
- annotations
- os
- typing
- Final,
- pytest
- psycopg2
- connect
- env

### \test_db_module.py

Dependencies:

- logging
- src.data.database
- get_db

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

### \frontend\_\_tests\_\_\test-utils.ts

No dependencies found

### \frontend\_\_tests\_\_\test-utils.test.ts

Dependencies:

- ../app/types/api

### \frontend\_\_tests\_\_\lib\api.test.ts

Dependencies:

- axios
- ../../app/types/api

### \frontend\_\_tests\_\_\lib\api-upgrade-integration.test.ts

Dependencies:

- axios
- ../test-utils

### \frontend\_\_tests\_\_\lib\api-axios-compatibility.test.ts

Dependencies:

- ../../app/types/api
- ../test-utils

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
- @vercel/speed-insights/next

### \frontend\app\components\NetworkVisualization.tsx

Dependencies:

- react
- next/dynamic
- ../types/api
- plotly.js

### \frontend\app\components\MetricsDashboard.tsx

Dependencies:

- react
- ../types/api

### \frontend\_\_tests\_\_\integration\component-integration.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/page
- ../../app/lib/api

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 **tests**/
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
    - 📄 **init**.py
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
    - 📄 **init**.py
    - 📄 test_api_integration.py
    - 📄 test_repository.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 **init**.py
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

- psycopg2>=2.9.0,<3.0.0 # PostgreSQL adapter with version constraint
- psycopg2-binary>=2.9.0 # For distributed deployments

# Environment management

- python-dotenv>=1.0.0,<2.0.0 # Unified environment variable management
  # Usage: from dotenv import load_dotenv
  # load_dotenv() # Load environment variables from .env file

# Development/Testing dependencies

- pytest>=7.0.0 # Test framework
- factory-boy>=3.2.0 # Test data generation
- pytest-asyncio>=0.21.0 # Async test support

# Error handling and resilience

- tenacity>=8.0.0 # Retry logic for database operations
- backoff>=2.2.0 # Exponential backoff for failures

# Logging and monitoring

- structlog>=22.0.0 # Structured logging
- sentry-sdk>=1.20.0 # Error tracking (optional)

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

### \api\_\_init\_\_.py

No dependencies found

## TS Dependencies

### \frontend\_\_tests\_\_\lib\api.test.ts

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

### \frontend\_\_tests\_\_\components\NetworkVisualization.test.tsx

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
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 **tests**/
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
      - 📂 **tests**/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 **tests**/
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
    - 📄 **init**.py
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
    - 📄 **init**.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 **init**.py
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

### \frontend\_\_tests\_\_\lib\api.test.ts

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

### \frontend\app\lib\_\_tests\_\_\api.test.ts

Dependencies:

- axios
- ../api

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
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 **tests**/
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
      - 📂 **tests**/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 **tests**/
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
    - 📄 **init**.py
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
    - 📄 **init**.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 **init**.py
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

### \frontend\app\types\api.ts

No dependencies found

### \frontend\_\_tests\_\_\lib\api.test.ts

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

### \frontend\app\lib\_\_tests\_\_\api.test.ts

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
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 **tests**/
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
      - 📂 **tests**/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 **tests**/
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
    - 📄 **init**.py
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
    - 📄 **init**.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 **init**.py
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
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 **tests**/
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
      - 📂 **tests**/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 **tests**/
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
    - 📄 **init**.py
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
    - 📄 **init**.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 **init**.py
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

### \api\_\_init\_\_.py

No dependencies found

## TSX Dependencies

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

### \frontend\_\_tests\_\_\lib\api.test.ts

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

### \frontend\app\lib\_\_tests\_\_\api.test.ts

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
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 **tests**/
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
      - 📂 **tests**/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 **tests**/
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
    - 📄 **init**.py
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
    - 📄 **init**.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 **init**.py
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

### \frontend\app\lib\api.ts

Dependencies:

- axios
- ../types/api

### \frontend\app\lib\_\_tests\_\_\api.test.ts

Dependencies:

- axios
- ../api

### \frontend\app\lib\index.ts

No dependencies found

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

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 **tests**/
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
      - 📂 **tests**/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 **tests**/
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
    - 📄 **init**.py
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
    - 📄 **init**.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 **init**.py
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

### \frontend\app\lib\index.ts

No dependencies found

### \frontend\app\lib\api.ts

Dependencies:

- axios
- ../types/api

### \frontend\app\lib\_\_tests\_\_\api.test.ts

Dependencies:

- axios
- ../api

## TSX Dependencies

### \frontend\_\_tests\_\_\components\MetricsDashboard.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/MetricsDashboard
- ../../app/types/api

### \frontend\_\_tests\_\_\components\NetworkVisualization.test.tsx

Dependencies:

- react
- @testing-library/react
- @testing-library/jest-dom
- ../../app/components/NetworkVisualization
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

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 **tests**/
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
      - 📂 **tests**/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 **tests**/
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
    - 📄 **init**.py
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
    - 📄 **init**.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 **init**.py
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

### \api\_\_init\_\_.py

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

## TS Dependencies

### \frontend\app\lib\index.ts

No dependencies found

### \frontend\app\lib\api.ts

Dependencies:

- axios
- ../types/api

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

## Project Directory Structure

- 📂 api/
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 **tests**/
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
      - 📂 **tests**/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 **tests**/
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
    - 📄 **init**.py
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
    - 📄 **init**.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 **init**.py
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

### \api\_\_init\_\_.py

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

### \frontend\_\_tests\_\_\lib\api.test.ts

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

### \frontend\app\lib\_\_tests\_\_\api.test.ts

Dependencies:

- axios
- ../api

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
  - 📄 **init**.py
  - 📄 auth.py
  - 📄 main.py
- 📂 frontend/
  - 📂 **tests**/
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
      - 📂 **tests**/
        ...
      - 📄 AssetList.tsx
      - 📄 MetricsDashboard.tsx
      - 📄 NetworkVisualization.tsx
    - 📂 lib/
      - 📂 **tests**/
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
    - 📄 **init**.py
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
    - 📄 **init**.py
    - 📄 test_api_integration.py
  - 📂 unit/
    - 📄 **init**.py
    - 📄 test_api_main.py
    - 📄 test_api.py
    - 📄 test_asset_graph.py
    - 📄 test_config_validation.py
    - 📄 test_dev_scripts.py
    - 📄 test_financial_models.py
  - 📄 **init**.py
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
