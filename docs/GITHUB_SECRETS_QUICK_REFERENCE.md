# 🔐 GitHub Secrets Quick Reference

## Required Secrets for ActivityTracker Deployment

### Essential Secrets

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `AWS_ROLE_ARN` | IAM role for GitHub Actions OIDC | Run `./scripts/setup-github-oidc.sh` |
| `AWS_REGION` | AWS deployment region | Choose your preferred region (e.g., `us-east-1`) |

### Optional Secrets

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `CODECOV_TOKEN` | Code coverage reporting | Sign up at [codecov.io](https://codecov.io) |
| `SLACK_WEBHOOK_URL` | Deployment notifications | Create webhook in Slack settings |

## 🚀 Quick Setup

### Option 1: Automated Setup (Recommended)

```bash
# Run the automated setup script
./scripts/setup-github-oidc.sh
```

This script will:
- ✅ Create AWS OIDC provider (if needed)
- ✅ Create IAM role with proper permissions
- ✅ Output the exact secret values to copy

### Option 2: Manual Setup

1. **Create IAM Role with OIDC trust policy**
2. **Attach deployment permissions**
3. **Copy Role ARN**
4. **Add secrets to GitHub**

## 📋 Adding Secrets to GitHub

1. Go to **GitHub Repository** → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Add each secret with exact name and value

### Secret Values Format

```bash
# AWS_ROLE_ARN (from setup script output)
arn:aws:iam::123456789012:role/ActivityTracker-GitHubActions

# AWS_REGION (your choice)
us-east-1
```

## ✅ Verification

### Test Deployment
1. Create a feature branch: `git checkout -b test-deployment`
2. Push to GitHub: `git push origin test-deployment`
3. Open Pull Request
4. Check **Actions** tab for workflow success

### Expected Workflow Steps
- ✅ Tests run and pass
- ✅ Application builds successfully
- ✅ Deployment to AWS completes
- ✅ Health checks pass
- ✅ Dashboard URL is accessible

## 🚨 Common Issues

| Issue | Solution |
|-------|----------|
| `Error: Could not assume role` | Check role ARN and trust policy |
| `Error: Access denied` | Verify IAM permissions are attached |
| `Workflow doesn't trigger` | Check secrets are in correct repository |
| `Deployment fails` | Check AWS region and resource limits |

## 🔗 Helpful Links

- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [AWS OIDC with GitHub Actions](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Setup Script Details](./GITHUB_SECRETS_SETUP.md)

---

**💡 Pro Tip**: Save the setup script output - it contains your exact secret values!
