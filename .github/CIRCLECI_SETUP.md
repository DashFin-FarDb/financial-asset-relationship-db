# CircleCI Setup Guide

## Current Issue: SSH Authentication Failure

The CircleCI builds are failing with the following error:

```
git@github.com: Permission denied (publickey).
fatal: Could not read from remote repository.
```

This error occurs during the checkout step and indicates that CircleCI doesn't have the proper SSH keys configured to access the repository.

## Solution

This is **not a code issue** - it's a CircleCI project configuration issue. To fix this:

### Option 1: Add User Key (Recommended)

1. Go to CircleCI project settings: https://app.circleci.com/settings/project/github/DashFin/financial-asset-relationship-db
2. Navigate to "SSH Keys" section
3. Click "Add User Key"
4. Authorize CircleCI to access your GitHub account
5. CircleCI will automatically add a user key with repository access

### Option 2: Add Deploy Key

1. Generate an SSH key pair:
   ```bash
   ssh-keygen -t ed25519 -C "circleci@financial-asset-relationship-db"
   ```
2. Add the public key to GitHub:
   - Go to repository Settings → Deploy keys
   - Click "Add deploy key"
   - Paste the public key
   - Check "Allow write access" if needed
3. Add the private key to CircleCI:
   - Go to CircleCI project settings → SSH Keys
   - Click "Add SSH Key"
   - Hostname: `github.com`
   - Paste the private key

### Option 3: Use Checkout Orb with HTTPS

Modify `.circleci/config.yml` to use HTTPS instead of SSH (requires GitHub token):

```yaml
- checkout:
    path: ~/project
```

And set `GITHUB_TOKEN` in CircleCI environment variables.

## Verification

After configuring SSH keys, re-run the failed CircleCI builds. The checkout step should succeed.

## Related Documentation

- [CircleCI GitHub Integration](https://circleci.com/docs/github-integration/)
- [CircleCI SSH Keys](https://circleci.com/docs/add-ssh-key/)
- [GitHub Deploy Keys](https://docs.github.com/en/developers/overview/managing-deploy-keys)

## PR Context

This issue was discovered while reviewing PR that adds CodeSherlock configuration. The PR changes themselves are valid - the CircleCI failure is due to missing SSH configuration, not the code changes.
