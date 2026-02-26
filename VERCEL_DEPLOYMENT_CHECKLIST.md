# Vercel Deployment Checklist

Use this checklist to ensure a smooth deployment to Vercel.

## Pre-Deployment Checklist

### 1. Code Preparation

- [ ] All code is committed to your Git repository
- [ ] `.gitignore` excludes build artifacts and dependencies
- [ ] No sensitive data or secrets in code
- [ ] Environment variables are documented in `.env.example`

### 2. Local Testing

- [ ] Backend API runs successfully: `python -m uvicorn api.main:app --port 8000`
- [ ] Frontend builds without errors: `cd frontend && npm run build`
- [ ] All API endpoints return valid responses
- [ ] 3D visualization renders correctly
- [ ] No console errors in browser

### 3. Configuration Files

- [ ] `vercel.json` exists in project root
- [ ] `frontend/package.json` is properly configured
- [ ] `frontend/next.config.js` has correct settings
- [ ] `requirements.txt` includes all Python dependencies

### 4. Dependencies Check

Python dependencies (requirements.txt):

- [ ] fastapi>=0.104.0
- [ ] uvicorn[standard]>=0.24.0
- [ ] pydantic>=2.4.0
- [ ] gradio>=4.0.0
- [ ] plotly>=5.0.0
- [ ] numpy>=1.21.0
- [ ] yfinance>=0.2.0
- [ ] pandas>=1.5.0

Frontend dependencies (frontend/package.json):

- [ ] react and react-dom
- [ ] next
- [ ] typescript
- [ ] tailwindcss
- [ ] plotly.js and react-plotly.js
- [ ] axios

## Deployment Steps

### Option 1: Deploy via GitHub Integration (Recommended)

#### Step 1: Push to GitHub

```bash
# Ensure all changes are committed
git status

# Push to your repository
git push origin main  # or your branch name
```

#### Step 2: Connect to Vercel

- [ ] Go to [vercel.com](https://vercel.com)
- [ ] Sign up or log in
- [ ] Click "New Project"
- [ ] Import your GitHub repository
- [ ] Vercel will auto-detect Next.js

#### Step 3: Configure Project Settings

- [ ] **Framework Preset**: Next.js
- [ ] **Root Directory**: Leave as `.` (default)
- [ ] **Build Command**: Leave default
- [ ] **Output Directory**: Leave default

#### Step 4: Set Environment Variables

In the Vercel dashboard, add:

- [ ] `NEXT_PUBLIC_API_URL` = `https://your-project.vercel.app`
  - Note: Use your actual Vercel deployment URL
  - This will be available after first deployment

#### Step 5: Deploy

- [ ] Click "Deploy"
- [ ] Wait for build to complete (2-5 minutes)
- [ ] Check deployment logs for errors

#### Step 6: Update API URL

After first deployment:

- [ ] Copy your Vercel project URL (e.g., `https://your-project.vercel.app`)
- [ ] Update `NEXT_PUBLIC_API_URL` in environment variables
- [ ] Redeploy if necessary

### Option 2: Deploy via Vercel CLI

#### Step 1: Install Vercel CLI

```bash
npm install -g vercel
```

#### Step 2: Login

```bash
vercel login
```

#### Step 3: Deploy from Project Root

```bash
# From the project root directory
vercel

# Follow the prompts:
# - Set up and deploy? Yes
# - Which scope? Your account
# - Link to existing project? No (for first deployment)
# - Project name? Your choice
# - Directory? ./ (current directory)
```

#### Step 4: Set Environment Variables

```bash
# Set production environment variable
vercel env add NEXT_PUBLIC_API_URL production
# Enter: https://your-project.vercel.app
```

#### Step 5: Deploy to Production

```bash
vercel --prod
```

## Post-Deployment Checklist

### 1. Verify Deployment

- [ ] Open deployed URL in browser
- [ ] Check that frontend loads without errors
- [ ] Verify API health: `https://your-project.vercel.app/api/health`
- [ ] Test API docs: `https://your-project.vercel.app/docs`

### 2. Test Functionality

- [ ] 3D Visualization tab loads and displays graph
- [ ] Metrics tab shows correct statistics
- [ ] Asset Explorer tab displays and filters work
- [ ] No CORS errors in browser console
- [ ] All interactive features work

### 3. Performance Check

- [ ] Page load time is acceptable (< 3 seconds)
- [ ] API responses are fast (< 2 seconds)
- [ ] 3D visualization renders smoothly
- [ ] No memory leaks or errors

### 4. Mobile Testing

- [ ] Open site on mobile device
- [ ] Check responsive layout
- [ ] Test touch interactions
- [ ] Verify visualization works on mobile

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: Build Failed

**Error**: Build command failed
**Solution**:

- [ ] Check build logs in Vercel dashboard
- [ ] Verify all dependencies are in package.json
- [ ] Test build locally: `cd frontend && npm run build`
- [ ] Check for TypeScript errors
- [ ] Ensure Node.js version is compatible (18+)

#### Issue 2: API Not Found (404)

**Error**: `/api/` routes return 404
**Solution**:

- [ ] Verify `vercel.json` is in project root
- [ ] Check route configuration in vercel.json
- [ ] Ensure `api/main.py` exists
- [ ] Check Python version compatibility

#### Issue 3: CORS Errors

**Error**: CORS policy errors in browser
**Solution**:

- [ ] Check CORS configuration in `api/main.py`
- [ ] Add Vercel domain to allowed origins
- [ ] Verify `NEXT_PUBLIC_API_URL` is set correctly

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

#### Issue 4: Environment Variables Not Working

**Error**: API_URL is undefined
**Solution**:

- [ ] Verify variable name starts with `NEXT_PUBLIC_`
- [ ] Set in Vercel dashboard (Settings → Environment Variables)
- [ ] Redeploy after adding variables
- [ ] Check variable is accessed correctly in code

#### Issue 5: Python Dependencies Not Found

**Error**: Module not found errors
**Solution**:

- [ ] Verify `requirements.txt` includes all dependencies
- [ ] Check Python version in Vercel settings
- [ ] Use compatible package versions
- [ ] Check Vercel Python runtime logs

#### Issue 6: Lambda Size Exceeded

**Error**: Deployment exceeds size limit
**Solution**:

- [ ] Increase `maxLambdaSize` in vercel.json
- [ ] Remove unused dependencies
- [ ] Use lighter alternatives where possible
- [ ] Consider serverless-friendly packages

```json
{
  "builds": [
    {
      "src": "api/main.py",
      "use": "@vercel/python",
      "config": {
        "maxLambdaSize": "50mb"
      }
    }
  ]
}
```

## Continuous Deployment

### Automatic Deployments

Once connected to GitHub:

- [ ] Every push to main branch triggers deployment
- [ ] Pull requests create preview deployments
- [ ] Failed builds prevent deployment

### Branch Deployments

- [ ] **Production**: Deploy from `main` branch
- [ ] **Staging**: Deploy from `develop` branch (optional)
- [ ] **Preview**: Automatic for all PRs

## Monitoring

### Vercel Dashboard

- [ ] Check deployment status regularly
- [ ] Monitor function execution times
- [ ] Review error logs
- [ ] Check bandwidth usage

### Analytics

- [ ] Enable Vercel Analytics (optional)
- [ ] Monitor page views
- [ ] Track performance metrics
- [ ] Review user behavior

## Security

### Best Practices

- [ ] Never commit secrets to Git
- [ ] Use environment variables for sensitive data
- [ ] Enable HTTPS (automatic on Vercel)
- [ ] Set up proper CORS policies
- [ ] Regular dependency updates
- [ ] Monitor for security vulnerabilities

### Access Control

- [ ] Limit Vercel project access to team members
- [ ] Use separate production/staging environments
- [ ] Rotate secrets regularly
- [ ] Review access logs

## Backup Plan

### Rollback Procedure

If deployment fails or has issues:

- [ ] Go to Vercel dashboard
- [ ] Navigate to Deployments
- [ ] Find previous working deployment
- [ ] Click "Promote to Production"

### Local Fallback

- [ ] Keep Gradio UI as fallback: `python app.py`
- [ ] Document how to switch between UIs
- [ ] Maintain both deployment methods

## Resources

### Documentation Links

- [ ] [Vercel Documentation](https://vercel.com/docs)
- [ ] [Next.js Deployment](https://nextjs.org/docs/deployment)
- [ ] [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [ ] Project-specific: [DEPLOYMENT.md](DEPLOYMENT.md)

### Support Channels

- [ ] Vercel Support: support@vercel.com
- [ ] Vercel Community: Discord/Forum
- [ ] GitHub Issues: For project-specific issues

## Final Checks

Before going live:

- [ ] All tests pass
- [ ] Documentation is up to date
- [ ] Team members can access deployment
- [ ] Monitoring is set up
- [ ] Backup plan is documented
- [ ] Users are notified of new deployment

---

## Quick Reference Commands

```bash
# Test locally
./run-dev.sh  # or run-dev.bat on Windows

# Build frontend
cd frontend && npm run build

# Test API
python test_api.py

# Deploy to Vercel
vercel --prod

# View logs
vercel logs

# List deployments
vercel ls
```

---

**Deployment Complete?** 🎉

If all items are checked and deployment is successful, congratulations! Your Financial Asset Relationship Database is now live on Vercel.

For maintenance and updates, see [DEPLOYMENT.md](DEPLOYMENT.md).
