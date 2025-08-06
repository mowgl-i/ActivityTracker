#!/bin/bash

# Manual IAM setup script for GitHub OIDC authentication
# This script provides the AWS CLI commands for manual setup
# Use this if you prefer to run commands step-by-step

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}
╔══════════════════════════════════════════════════════════════════════════════╗
║                     Manual GitHub OIDC Setup Commands                       ║
║              Copy and run these commands in your terminal                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
${NC}"

echo -e "${GREEN}Step 1: Get your AWS Account ID${NC}"
echo "export AWS_ACCOUNT_ID=\$(aws sts get-caller-identity --query Account --output text)"
echo "echo \"Your AWS Account ID: \$AWS_ACCOUNT_ID\""
echo ""

echo -e "${GREEN}Step 2: Set your variables${NC}"
echo "export GITHUB_USERNAME=\"YOUR_GITHUB_USERNAME\"  # Replace with your GitHub username"
echo "export GITHUB_REPO=\"ActivityTracker\"           # Or your repository name"
echo "export AWS_REGION=\"us-east-1\"                  # Or your preferred region"
echo ""

echo -e "${GREEN}Step 3: Update policy files with your information${NC}"
echo "# Edit docs/policies/github-trust-policy.json:"
echo "sed -i \"s/ACCOUNT_ID/\$AWS_ACCOUNT_ID/g\" docs/policies/github-trust-policy.json"
echo "sed -i \"s/YOUR_GITHUB_USERNAME/\$GITHUB_USERNAME/g\" docs/policies/github-trust-policy.json"
echo ""

echo -e "${GREEN}Step 4: Create OIDC provider (if it doesn't exist)${NC}"
echo "# Check if OIDC provider exists:"
echo "aws iam get-open-id-connect-provider \\"
echo "    --open-id-connect-provider-arn arn:aws:iam::\$AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
echo ""
echo "# If it doesn't exist, create it:"
echo "aws iam create-open-id-connect-provider \\"
echo "    --url https://token.actions.githubusercontent.com \\"
echo "    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \\"
echo "    --thumbprint-list 1c58a3a8518e8759bf075b76b750d4f2df264fcd \\"
echo "    --client-id-list sts.amazonaws.com"
echo ""

echo -e "${GREEN}Step 5: Create IAM role${NC}"
echo "aws iam create-role \\"
echo "    --role-name ActivityTracker-GitHubActions \\"
echo "    --assume-role-policy-document file://docs/policies/github-trust-policy.json \\"
echo "    --description \"Role for GitHub Actions to deploy ActivityTracker\""
echo ""

echo -e "${GREEN}Step 6: Create and attach permission policy${NC}"
echo "aws iam create-policy \\"
echo "    --policy-name ActivityTracker-GitHubActions-Policy \\"
echo "    --policy-document file://docs/policies/github-permissions-policy.json \\"
echo "    --description \"Permissions for GitHub Actions to deploy ActivityTracker\""
echo ""
echo "aws iam attach-role-policy \\"
echo "    --role-name ActivityTracker-GitHubActions \\"
echo "    --policy-arn arn:aws:iam::\$AWS_ACCOUNT_ID:policy/ActivityTracker-GitHubActions-Policy"
echo ""

echo -e "${GREEN}Step 7: Get role ARN for GitHub secrets${NC}"
echo "export ROLE_ARN=\$(aws iam get-role --role-name ActivityTracker-GitHubActions --query 'Role.Arn' --output text)"
echo "echo \"Role ARN: \$ROLE_ARN\""
echo ""

echo -e "${GREEN}Step 8: Add secrets to GitHub${NC}"
echo "Go to: https://github.com/\$GITHUB_USERNAME/\$GITHUB_REPO/settings/secrets/actions"
echo ""
echo "Add these secrets:"
echo "• AWS_ROLE_ARN = \$ROLE_ARN"
echo "• AWS_REGION = \$AWS_REGION"
echo ""

echo -e "${YELLOW}💡 Pro Tip: Run './scripts/setup-github-oidc.sh' for automated setup instead!${NC}"