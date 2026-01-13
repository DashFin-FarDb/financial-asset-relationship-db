# Deployment Guide - Vercel Next.js Integration

This guide explains how to deploy the Financial Asset Relationship Database with a Next.js frontend on Vercel.

## Architecture Overview

The application now consists of two main components:

1. **Backend API** (`/api`): FastAPI server that provides REST endpoints for the asset relationship graph
2. **Frontend** (`/frontend`): Next.js application with React components for visualization

## Local Development

### Prerequisites

- Python 3.8+
- Node.js 18+ and npm
- Virtual environment (recommended for Python)

### Backend Setup

1. **Create and activate Python virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the FastAPI backend:**

   ```bash
   python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   ```

   The API will be available at `http://localhost:8000`
   - API documentation: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/api/health`

### Frontend Setup

1. **Navigate to the frontend directory:**

   ```bash
   cd frontend
   ```

2. **Install Node.js dependencies:**

   ```bash
   npm install
   ```

3. **(Optional) Create environment file:**

   Copy the environment template:

   ```bash
   cp ../.env.example .env.local

   ```

4. **Run the Next.js development server:**

   ```bash
   npm run dev
   ```

   The frontend will be available at `http://localhost:3000`

### Development Workflow

With both servers running:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

The frontend automatically connects to the backend API on port 8000.

## Vercel Deployment

### Option 1: Deploy via Vercel CLI

1. **Install Vercel CLI:**

   ```bash
   npm install -g vercel
   ```

2. **Login to Vercel:**

   ```bash
   vercel login
   ```

3. **Deploy from the project root:**

   ```bash
   vercel
   ```

4. **Follow the prompts to configure your project**

### Option 2: Deploy via GitHub Integration

1. **Push your code to GitHub:**

   ```bash
   git add .
   git commit -m "Add Vercel Next.js integration"
   git push origin main
   ```

2. **Connect to Vercel:**
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your GitHub repository
   - Vercel will automatically detect the Next.js app

3. **Configure environment variables in Vercel dashboard:**
   - `NEXT_PUBLIC_API_URL`: Set to your deployed API URL (e.g., `https://your-project.vercel.app`)

### Project Structure for Vercel

```
.
├── api/                    # FastAPI backend
│   ├── __init__.py
│   └── main.py            # API entry point
├── frontend/              # Next.js frontend
│   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── types/
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.js
├── src/                   # Python source code
├── requirements.txt       # Python dependencies
├── vercel.json           # Vercel configuration
└── DEPLOYMENT.md         # This file
```

## API Endpoints

The FastAPI backend exposes the following endpoints:

### Core Endpoints

- `GET /` - API information
- `GET /api/health` - Health check

### Assets

- `GET /api/assets` - Get all assets (with optional filters)
  - Query params: `asset_class`, `sector`
- `GET /api/assets/{asset_id}` - Get asset details
- `GET /api/assets/{asset_id}/relationships` - Get asset relationships

### Relationships

- `GET /api/relationships` - Get all relationships

### Metrics

- `GET /api/metrics` - Get network metrics

### Visualization

- `GET /api/visualization` - Get 3D visualization data

### Metadata

- `GET /api/asset-classes` - Get available asset classes
- `GET /api/sectors` - Get available sectors

## Frontend Features

The Next.js frontend includes:

1. **3D Visualization Tab**: Interactive 3D network graph using Plotly
2. **Metrics & Analytics Tab**: Dashboard with key network statistics
3. **Asset Explorer Tab**: Filterable table of all assets

## Environment Variables

### Frontend (.env.local)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

For production on Vercel, set this in the Vercel dashboard:

```bash
NEXT_PUBLIC_API_URL=https://your-api-domain.vercel.app
```

## Troubleshooting

### CORS Issues

If you encounter CORS errors, ensure the FastAPI backend has the correct origins configured in `api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    ...
)
```

### API Connection Errors

1. Check that the backend is running: `curl http://localhost:8000/api/health`
2. Verify the `NEXT_PUBLIC_API_URL` environment variable
3. Check browser console for detailed error messages

### Build Errors

For frontend build issues:

```bash
cd frontend
rm -rf .next node_modules
npm install
npm run build
```

For backend issues:

```bash
pip install --upgrade -r requirements.txt
```

## Monitoring and Logs

### Local Development

- Backend logs: Visible in the terminal where `uvicorn` is running
- Frontend logs: Visible in the browser console and terminal

### Vercel Production

- View logs in the Vercel dashboard under your project
- Real-time logs: `vercel logs`
- Function logs: Available in the "Functions" tab

## Performance Considerations

1. **Cold Starts**: First API request may be slower due to serverless cold starts
2. **Data Caching**: The API initializes the graph on first request and keeps it in memory
3. **Lambda Size**: Vercel Python functions have a 50MB limit (configured in vercel.json)

## Scaling

For production deployments with higher traffic:

1. Consider using Vercel's Edge Functions for the API
2. Implement caching for frequently accessed data
3. Use a persistent database instead of in-memory data
4. Add Redis for session/state management

## Security

1. Add authentication/authorization if needed
2. Rate limiting for API endpoints
3. Validate all input data
4. Use HTTPS in production
5. Set up CORS properly for your domain

## Additional Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Vercel Documentation](https://vercel.com/docs)
- [Plotly React Documentation](https://plotly.com/javascript/react/)
