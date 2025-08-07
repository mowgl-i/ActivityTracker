# GitHub Secrets Setup Guide

This guide explains how to set up the required GitHub secrets for the ActivityTracker deployment pipeline using modern OIDC authentication.

## 🔐 Required Secrets

### Essential Secrets (Required)

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `AWS_ROLE_ARN` | IAM role ARN for GitHub Actions | `arn:aws:iam::123456789012:role/ActivityTracker-GitHubActions` |
| `AWS_REGION` | AWS region for deployment | `us-east-1` |

### Optional Secrets (Recommended)

| Secret Name | Description | Purpose |
|-------------|-------------|---------|
| `CODECOV_TOKEN` | Code coverage reporting token | Upload test coverage to Codecov |
| `SLACK_WEBHOOK_URL` | Slack webhook for notifications | Deployment status notifications |

## 🏗️ Step-by-Step Setup

### Step 1: Create AWS IAM Role for GitHub OIDC

First, create an IAM role that GitHub Actions can assume using OIDC authentication.

#### 1.1 Create the Trust Policy

The trust policy file is provided at `docs/policies/github-trust-policy.json`. Update the placeholders:

```bash
# Get your AWS account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Update the policy file with your information
sed -i "s/ACCOUNT_ID/$AWS_ACCOUNT_ID/g" docs/policies/github-trust-policy.json
sed -i "s/YOUR_GITHUB_USERNAME/your-username/g" docs/policies/github-trust-policy.json
```

**Or use the automated setup script:**
```bash
./scripts/setup-github-oidc.sh  # Recommended - handles everything automatically
```

#### 1.2 Create the OIDC Identity Provider (if not exists)

Check if the GitHub OIDC provider exists:

```bash
aws iam get-open-id-connect-provider \
    --open-id-connect-provider-arn arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
```

If it doesn't exist, create it:

```bash
aws iam create-open-id-connect-provider \
    --url https://token.actions.githubusercontent.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
    --thumbprint-list 1c58a3a8518e8759bf075b76b750d4f2df264fcd \
    --client-id-list sts.amazonaws.com
```

#### 1.3 Create the IAM Role

```bash
aws iam create-role \
    --role-name ActivityTracker-GitHubActions \
    --assume-role-policy-document file://docs/policies/github-trust-policy.json \
    --description "Role for GitHub Actions to deploy ActivityTracker"
```

#### 1.4 Create and Attach Permission Policy

The permissions policy is provided at `docs/policies/github-permissions-policy.json`. This policy grants the minimum required permissions for deploying ActivityTracker, scoped to specific resource patterns for security.

**Key permissions included:**
- CloudFormation (stack management)
- Lambda (function deployment)
- DynamoDB (table management)
- API Gateway (API management)
- S3 & CloudFront (static hosting)
- Pinpoint (SMS handling)
- IAM (role management for ActivityTracker resources)
- CloudWatch Logs (log management)

Create and attach the policy:

```bash
aws iam create-policy \
    --policy-name ActivityTracker-GitHubActions-Policy \
    --policy-document file://docs/policies/github-permissions-policy.json \
    --description "Permissions for GitHub Actions to deploy ActivityTracker"

aws iam attach-role-policy \
    --role-name ActivityTracker-GitHubActions \
    --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/ActivityTracker-GitHubActions-Policy
```

### Step 2: Get Role ARN

Get the role ARN that you'll need for the GitHub secret:

```bash
aws iam get-role \
    --role-name ActivityTracker-GitHubActions \
    --query 'Role.Arn' \
    --output text
```

Save this ARN - you'll need it for the GitHub secret.

### Step 3: Add Secrets to GitHub Repository

1. **Go to your GitHub repository**
2. **Click on "Settings" tab**
3. **Click on "Secrets and variables" > "Actions"**
4. **Click "New repository secret"**

Add these secrets:

#### Required Secrets:

**AWS_ROLE_ARN**
- Name: `AWS_ROLE_ARN`
- Value: The role ARN from Step 2 (e.g., `arn:aws:iam::123456789012:role/ActivityTracker-GitHubActions`)

**AWS_REGION**
- Name: `AWS_REGION`
- Value: Your preferred AWS region (e.g., `us-east-1`)

#### Optional Secrets:

**CODECOV_TOKEN** (for code coverage)
- Name: `CODECOV_TOKEN`
- Value: Get from [codecov.io](https://codecov.io) after connecting your repo
- Purpose: Upload test coverage reports

**SLACK_WEBHOOK_URL** (for notifications)
- Name: `SLACK_WEBHOOK_URL`
- Value: Slack incoming webhook URL
- Purpose: Send deployment notifications to Slack

## 🧪 Testing the Setup

### Test with a Simple Deployment

1. **Create a test branch:**
   ```bash
   git checkout -b test-deployment
   git push origin test-deployment
   ```

2. **Open a Pull Request** - This will trigger the development deployment

3. **Check GitHub Actions** - Go to "Actions" tab to see if the workflow runs successfully

4. **Verify AWS Resources** - Check AWS Console to see if resources are created

### Test Commands

You can also test the role assumption locally:

```bash
# Test role assumption (requires AWS CLI configured)
aws sts assume-role-with-web-identity \
    --role-arn arn:aws:iam::YOUR_ACCOUNT_ID:role/ActivityTracker-GitHubActions \
    --role-session-name test-session \
    --web-identity-token $(curl -s -H "Authorization: bearer $GITHUB_TOKEN" \
        https://api.github.com/repos/YOUR_USERNAME/ActivityTracker/actions/secrets)
```

## 🔒 Security Best Practices

### 1. Principle of Least Privilege
- The IAM role only has permissions needed for deployment
- Resources are scoped to ActivityTracker-specific naming patterns

### 2. Repository-Specific Access
- OIDC trust policy restricts access to your specific repository
- Wildcards allow for branch-based deployments but maintain repo security

### 3. Environment-Specific Roles (Advanced)
For production environments, consider separate roles:

```bash
# Production role (more restrictive)
aws iam create-role \
    --role-name ActivityTracker-GitHubActions-Prod \
    --assume-role-policy-document file://github-trust-policy-prod.json

# Staging role
aws iam create-role \
    --role-name ActivityTracker-GitHubActions-Staging \
    --assume-role-policy-document file://github-trust-policy-staging.json
```

### 4. Monitoring and Auditing
- Enable AWS CloudTrail to monitor role usage
- Set up CloudWatch alarms for unusual activity
- Regular review of role permissions and usage

## 🚨 Troubleshooting

### Common Issues

#### "Role cannot be assumed" Error
- Check that the OIDC provider exists
- Verify the trust policy repository path matches exactly
- Ensure GitHub repository is public or OIDC is properly configured for private repos

#### "Access Denied" Errors
- Check that all required permissions are attached to the role
- Verify resource naming patterns match your actual resources
- Check CloudTrail logs for specific permission denials

#### Workflow Not Triggering
- Ensure secrets are added to the correct repository
- Check that the workflow file is in `.github/workflows/` directory
- Verify branch protection rules aren't preventing the workflow

### Debug Commands

```bash
# Check if OIDC provider exists
aws iam list-open-id-connect-providers

# Verify role trust policy
aws iam get-role --role-name ActivityTracker-GitHubActions

# Check attached policies
aws iam list-attached-role-policies --role-name ActivityTracker-GitHubActions

# Test CloudFormation permissions
aws cloudformation validate-template --template-body file://infrastructure/template.yaml
```

## 📋 Checklist

Use this checklist to ensure everything is set up correctly:

- [ ] AWS account has necessary service quotas
- [ ] OIDC identity provider created for GitHub
- [ ] IAM role created with proper trust policy
- [ ] Permission policy created and attached
- [ ] Role ARN copied to GitHub secrets
- [ ] AWS region added to GitHub secrets
- [ ] Optional secrets added (Codecov, Slack)
- [ ] Test deployment completed successfully
- [ ] AWS resources created in correct region
- [ ] CloudWatch logs showing successful deployment
- [ ] Dashboard accessible at CloudFront URL

## 🎯 Next Steps

After completing this setup:

1. **Configure AWS Pinpoint** - Set up SMS channel and phone number
2. **Test SMS Processing** - Send test messages to verify end-to-end flow
3. **Set up Monitoring** - Configure CloudWatch alarms and dashboards
4. **Configure Notifications** - Set up Slack or email alerts for deployment status

---

**💡 Pro Tip**: Store the setup commands in a script for easy reproduction across environments or team members.
