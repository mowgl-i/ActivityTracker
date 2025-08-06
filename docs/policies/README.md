# IAM Policy Files

This directory contains the IAM policy files needed to set up GitHub OIDC authentication for the ActivityTracker deployment pipeline.

## Files

### `github-trust-policy.json`
**Purpose**: Defines which GitHub repositories can assume the IAM role

**Before using**: Replace the following placeholders:
- `ACCOUNT_ID` → Your AWS account ID (e.g., `123456789012`)
- `YOUR_GITHUB_USERNAME` → Your GitHub username (e.g., `johndoe`)

**Usage**:
```bash
# Update placeholders
sed -i "s/ACCOUNT_ID/$(aws sts get-caller-identity --query Account --output text)/g" github-trust-policy.json
sed -i "s/YOUR_GITHUB_USERNAME/your-username/g" github-trust-policy.json

# Create IAM role
aws iam create-role \
    --role-name ActivityTracker-GitHubActions \
    --assume-role-policy-document file://github-trust-policy.json
```

### `github-permissions-policy.json`
**Purpose**: Defines what AWS actions the GitHub Actions workflow can perform

**Permissions included**:
- ✅ CloudFormation (create/update/delete stacks)
- ✅ Lambda (create/update functions)
- ✅ DynamoDB (create/manage tables)
- ✅ API Gateway (create/manage APIs)
- ✅ S3 (create buckets, upload files)
- ✅ CloudFront (create/manage distributions)
- ✅ Pinpoint (create/manage SMS apps)
- ✅ IAM (manage ActivityTracker resources)
- ✅ CloudWatch Logs (create/manage log groups)

**Security**: All permissions are scoped to ActivityTracker-specific resources using naming patterns.

**Usage**:
```bash
# Create policy
aws iam create-policy \
    --policy-name ActivityTracker-GitHubActions-Policy \
    --policy-document file://github-permissions-policy.json

# Attach to role
aws iam attach-role-policy \
    --role-name ActivityTracker-GitHubActions \
    --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/ActivityTracker-GitHubActions-Policy
```

## Quick Setup

### Option 1: Automated (Recommended)
```bash
./scripts/setup-github-oidc.sh
```

### Option 2: Manual
```bash
./scripts/manual-iam-setup.sh  # Shows all commands
```

### Option 3: Step-by-step
1. Update placeholders in `github-trust-policy.json`
2. Create OIDC provider (if needed)
3. Create IAM role with trust policy
4. Create and attach permissions policy
5. Copy role ARN to GitHub secrets

## Security Notes

- **Least Privilege**: Policies only grant minimum required permissions
- **Resource Scoping**: Actions are limited to ActivityTracker-* resources
- **Repository Specific**: Trust policy only allows your specific GitHub repo
- **No Long-lived Keys**: Uses temporary OIDC tokens instead of access keys

## Troubleshooting

**"Role cannot be assumed" error**:
- Verify OIDC provider exists
- Check trust policy repository path matches exactly
- Ensure GitHub repository path is correct

**"Access denied" errors**:
- Check all required permissions are attached
- Verify resource naming patterns match
- Review CloudTrail logs for specific denials