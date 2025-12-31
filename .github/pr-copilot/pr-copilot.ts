{
  "name": "pr-copilot",
  "version": "1.0.0",
  "description": "Automated PR maintenance and completion agent for DashFin/financial-asset-relationship-db.",
  "main": "pr-copilot.js",
  "scripts": {
    "start": "probot run ./pr-copilot.ts"
  },
  "dependencies": {
    "probot": "^14.0.0",
    "@octokit/rest": "^20.0.0",
    "js-yaml": "^4.1.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "typescript": "^5.0.0"
  }
}
