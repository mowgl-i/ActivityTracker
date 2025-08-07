# GitHub Secrets Setup Files Overview

This document provides an overview of all the files created to support GitHub OIDC authentication setup for ActivityTracker deployment.

## 📁 File Structure

```
ActivityTracker/
├── docs/
│   ├── GITHUB_SECRETS_SETUP.md           # Complete setup guide
│   ├── GITHUB_SECRETS_QUICK_REFERENCE.md # Quick reference card
│   ├── FILES_OVERVIEW.md                 # This file
│   └── policies/
│       ├── README.md                      # Policy files documentation
│       ├── github-trust-policy.json      # IAM role trust policy
│       └── github-permissions-policy.json # IAM permissions policy
└── scripts/
    ├── setup-github-oidc.sh              # Automated setup script
    └── manual-iam-setup.sh               # Manual setup commands
```

## 📋 File Descriptions

### Documentation Files

| File | Purpose | Usage |
|------|---------|-------|
| `GITHUB_SECRETS_SETUP.md` | Complete setup guide with detailed instructions | Primary reference for setup |
| `GITHUB_SECRETS_QUICK_REFERENCE.md` | Quick reference for secrets and common issues | Quick troubleshooting |
| `policies/README.md` | Documentation for policy files | Understanding IAM policies |

### Policy Files

| File | Purpose | Security Notes |
|------|---------|----------------|
| `github-trust-policy.json` | Defines which repositories can assume the role | Repository-specific access |
| `github-permissions-policy.json` | Defines what AWS actions are allowed | Least-privilege permissions |

### Scripts

| File | Purpose | When to Use |
|------|---------|-------------|
| `setup-github-oidc.sh` | Automated setup with interactive prompts | **Recommended** - handles everything |
| `manual-iam-setup.sh` | Shows manual commands for step-by-step setup | Learning or troubleshooting |

## 🚀 Quick Setup Options

### Option 1: Automated (Recommended)
```bash
# Run the interactive setup script
./scripts/setup-github-oidc.sh
```
- ✅ Handles all AWS commands automatically
- ✅ Interactive prompts for configuration
- ✅ Outputs exact GitHub secret values
- ✅ Includes error checking and validation

### Option 2: Manual Step-by-Step
```bash
# See all commands without running them
./scripts/manual-iam-setup.sh

# Then run commands manually using the policy files
```
- ✅ Learn each step of the process
- ✅ Customize for specific requirements
- ✅ Good for troubleshooting issues

### Option 3: Direct File Usage
```bash
# Update policy files manually
sed -i "s/ACCOUNT_ID/123456789012/g" docs/policies/github-trust-policy.json
sed -i "s/YOUR_GITHUB_USERNAME/myusername/g" docs/policies/github-trust-policy.json

# Use AWS CLI with policy files
aws iam create-role --assume-role-policy-document file://docs/policies/github-trust-policy.json
```

## 🔐 Required GitHub Secrets

After running any setup option, you'll need these secrets in your GitHub repository:

| Secret Name | Example Value | Source |
|-------------|---------------|--------|
| `AWS_ROLE_ARN` | `arn:aws:iam::123456789012:role/ActivityTracker-GitHubActions` | Setup script output |
| `AWS_REGION` | `us-east-1` | Your chosen AWS region |

## 🛡️ Security Features

All setup methods implement these security best practices:

- **🔒 OIDC Authentication**: No long-lived AWS access keys
- **🎯 Least Privilege**: Minimal required permissions only
- **📍 Resource Scoping**: Limited to ActivityTracker-* resources
- **🏢 Repository Specific**: Only your repo can assume the role
- **📊 Audit Ready**: All actions logged in AWS CloudTrail

## 📞 Getting Help

If you encounter issues:

1. **Check the [Quick Reference](GITHUB_SECRETS_QUICK_REFERENCE.md)** for common problems
2. **Review the [Setup Guide](GITHUB_SECRETS_SETUP.md)** for detailed instructions
3. **Use the [Manual Commands](../scripts/manual-iam-setup.sh)** for step-by-step debugging
4. **Check AWS CloudTrail logs** for permission issues

## ✅ Verification Checklist

After setup, verify everything works:

- [ ] AWS OIDC provider exists
- [ ] IAM role created with correct trust policy
- [ ] Permissions policy attached to role
- [ ] GitHub secrets added with correct values
- [ ] Test deployment via Pull Request succeeds
- [ ] AWS resources created in correct region
- [ ] Dashboard accessible at CloudFront URL

---

**💡 Pro Tip**: Bookmark the [Quick Reference](GITHUB_SECRETS_QUICK_REFERENCE.md) for easy access to secret values and troubleshooting!
