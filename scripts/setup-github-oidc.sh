#!/bin/bash

# Setup script for GitHub OIDC authentication with AWS
# This script creates the necessary IAM role and policies for GitHub Actions deployment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}
╔══════════════════════════════════════════════════════════════════════════════╗
║                     ActivityTracker GitHub OIDC Setup                       ║
║              Setting up AWS IAM for GitHub Actions deployment               ║
╚══════════════════════════════════════════════════════════════════════════════╝
${NC}"
}

# Function to check if required tools are installed
check_prerequisites() {
    print_status "Checking prerequisites..."

    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi

    if ! command -v jq &> /dev/null; then
        print_error "jq is not installed. Please install it first."
        exit 1
    fi

    # Check AWS CLI authentication
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS CLI is not configured or authenticated."
        print_error "Please run 'aws configure' first."
        exit 1
    fi

    print_status "Prerequisites check passed!"
}

# Function to get user inputs
get_user_inputs() {
    print_status "Gathering configuration information..."

    # Get AWS account ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    print_status "AWS Account ID: $AWS_ACCOUNT_ID"

    # Get current AWS region
    AWS_REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")

    # Get GitHub repository information
    echo ""
    read -p "Enter your GitHub username: " GITHUB_USERNAME
    read -p "Enter repository name (default: ActivityTracker): " GITHUB_REPO
    GITHUB_REPO=${GITHUB_REPO:-ActivityTracker}
    read -p "Enter AWS region for deployment (default: $AWS_REGION): " INPUT_REGION
    AWS_REGION=${INPUT_REGION:-$AWS_REGION}

    # Confirm inputs
    echo ""
    print_status "Configuration Summary:"
    echo "  AWS Account ID: $AWS_ACCOUNT_ID"
    echo "  AWS Region: $AWS_REGION"
    echo "  GitHub Repository: $GITHUB_USERNAME/$GITHUB_REPO"
    echo ""
    read -p "Is this correct? (y/n): " CONFIRM

    if [[ $CONFIRM != "y" && $CONFIRM != "Y" ]]; then
        print_error "Setup cancelled by user."
        exit 1
    fi
}

# Function to check if OIDC provider exists
check_oidc_provider() {
    print_status "Checking for GitHub OIDC provider..."

    OIDC_PROVIDER_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"

    if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_PROVIDER_ARN" &> /dev/null; then
        print_status "GitHub OIDC provider already exists."
    else
        print_status "Creating GitHub OIDC provider..."
        aws iam create-open-id-connect-provider \
            --url https://token.actions.githubusercontent.com \
            --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
            --thumbprint-list 1c58a3a8518e8759bf075b76b750d4f2df264fcd \
            --client-id-list sts.amazonaws.com \
            --tags Key=Project,Value=ActivityTracker Key=Purpose,Value=GitHubActions

        print_status "GitHub OIDC provider created successfully!"
    fi
}

# Function to create trust policy
create_trust_policy() {
    print_status "Creating IAM role trust policy..."

    cat > /tmp/github-trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws:iam::$AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
            },
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                },
                "StringLike": {
                    "token.actions.githubusercontent.com:sub": "repo:$GITHUB_USERNAME/$GITHUB_REPO:*"
                }
            }
        }
    ]
}
EOF

    print_status "Trust policy created."
}

# Function to create permissions policy
create_permissions_policy() {
    print_status "Creating IAM permissions policy..."

    cat > /tmp/github-permissions-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "cloudformation:CreateStack",
                "cloudformation:UpdateStack",
                "cloudformation:DeleteStack",
                "cloudformation:DescribeStacks",
                "cloudformation:DescribeStackResources",
                "cloudformation:DescribeStackEvents",
                "cloudformation:GetTemplate",
                "cloudformation:ValidateTemplate",
                "cloudformation:ListStacks"
            ],
            "Resource": [
                "arn:aws:cloudformation:*:*:stack/ActivityTracker-*/*",
                "arn:aws:cloudformation:*:*:stack/aws-sam-cli-managed-default*/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "lambda:CreateFunction",
                "lambda:UpdateFunctionCode",
                "lambda:UpdateFunctionConfiguration",
                "lambda:DeleteFunction",
                "lambda:GetFunction",
                "lambda:ListFunctions",
                "lambda:TagResource",
                "lambda:UntagResource",
                "lambda:AddPermission",
                "lambda:RemovePermission",
                "lambda:GetPolicy",
                "lambda:PutFunctionEventInvokeConfig",
                "lambda:DeleteFunctionEventInvokeConfig"
            ],
            "Resource": [
                "arn:aws:lambda:*:*:function:ActivityTracker-*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:CreateTable",
                "dynamodb:UpdateTable",
                "dynamodb:DeleteTable",
                "dynamodb:DescribeTable",
                "dynamodb:ListTables",
                "dynamodb:TagResource",
                "dynamodb:UntagResource"
            ],
            "Resource": [
                "arn:aws:dynamodb:*:*:table/ActivityTracker-*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "apigateway:GET",
                "apigateway:POST",
                "apigateway:PUT",
                "apigateway:DELETE",
                "apigateway:PATCH"
            ],
            "Resource": [
                "arn:aws:apigateway:*::/restapis*",
                "arn:aws:apigateway:*::/apis*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:CreateBucket",
                "s3:DeleteBucket",
                "s3:GetBucketLocation",
                "s3:GetBucketPolicy",
                "s3:PutBucketPolicy",
                "s3:DeleteBucketPolicy",
                "s3:GetBucketVersioning",
                "s3:PutBucketVersioning",
                "s3:GetBucketEncryption",
                "s3:PutBucketEncryption",
                "s3:GetBucketPublicAccessBlock",
                "s3:PutBucketPublicAccessBlock",
                "s3:GetBucketWebsite",
                "s3:PutBucketWebsite",
                "s3:DeleteBucketWebsite",
                "s3:ListBucket",
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:GetObjectVersion",
                "s3:DeleteObjectVersion"
            ],
            "Resource": [
                "arn:aws:s3:::activitytracker-*",
                "arn:aws:s3:::activitytracker-*/*",
                "arn:aws:s3:::aws-sam-cli-managed-default-*",
                "arn:aws:s3:::aws-sam-cli-managed-default-*/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "cloudfront:CreateDistribution",
                "cloudfront:UpdateDistribution",
                "cloudfront:DeleteDistribution",
                "cloudfront:GetDistribution",
                "cloudfront:GetDistributionConfig",
                "cloudfront:ListDistributions",
                "cloudfront:CreateOriginAccessIdentity",
                "cloudfront:DeleteOriginAccessIdentity",
                "cloudfront:GetOriginAccessIdentity",
                "cloudfront:CreateInvalidation",
                "cloudfront:GetInvalidation",
                "cloudfront:ListInvalidations"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "pinpoint:CreateApp",
                "pinpoint:DeleteApp",
                "pinpoint:GetApp",
                "pinpoint:UpdateApplicationSettings",
                "pinpoint:GetSMSChannel",
                "pinpoint:UpdateSMSChannel"
            ],
            "Resource": [
                "arn:aws:pinpoint:*:*:apps/ActivityTracker*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "iam:CreateRole",
                "iam:DeleteRole",
                "iam:GetRole",
                "iam:PassRole",
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:GetRolePolicy",
                "iam:ListRolePolicies",
                "iam:TagRole",
                "iam:UntagRole"
            ],
            "Resource": [
                "arn:aws:iam::*:role/ActivityTracker-*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:DeleteLogGroup",
                "logs:DescribeLogGroups",
                "logs:PutRetentionPolicy",
                "logs:TagLogGroup",
                "logs:UntagLogGroup"
            ],
            "Resource": [
                "arn:aws:logs:*:*:log-group:/aws/lambda/ActivityTracker-*"
            ]
        }
    ]
}
EOF

    print_status "Permissions policy created."
}

# Function to create IAM role
create_iam_role() {
    ROLE_NAME="ActivityTracker-GitHubActions"

    print_status "Creating IAM role: $ROLE_NAME"

    # Check if role already exists
    if aws iam get-role --role-name "$ROLE_NAME" &> /dev/null; then
        print_warning "Role $ROLE_NAME already exists."
        read -p "Do you want to update it? (y/n): " UPDATE_ROLE

        if [[ $UPDATE_ROLE == "y" || $UPDATE_ROLE == "Y" ]]; then
            print_status "Updating role trust policy..."
            aws iam update-assume-role-policy \
                --role-name "$ROLE_NAME" \
                --policy-document file:///tmp/github-trust-policy.json
        fi
    else
        aws iam create-role \
            --role-name "$ROLE_NAME" \
            --assume-role-policy-document file:///tmp/github-trust-policy.json \
            --description "Role for GitHub Actions to deploy ActivityTracker" \
            --tags Key=Project,Value=ActivityTracker Key=Purpose,Value=GitHubActions

        print_status "IAM role created successfully!"
    fi

    # Create and attach permissions policy
    POLICY_NAME="ActivityTracker-GitHubActions-Policy"
    POLICY_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:policy/$POLICY_NAME"

    print_status "Creating and attaching permissions policy..."

    # Check if policy exists
    if aws iam get-policy --policy-arn "$POLICY_ARN" &> /dev/null; then
        print_status "Policy already exists, creating new version..."
        aws iam create-policy-version \
            --policy-arn "$POLICY_ARN" \
            --policy-document file:///tmp/github-permissions-policy.json \
            --set-as-default
    else
        aws iam create-policy \
            --policy-name "$POLICY_NAME" \
            --policy-document file:///tmp/github-permissions-policy.json \
            --description "Permissions for GitHub Actions to deploy ActivityTracker"
    fi

    # Attach policy to role
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "$POLICY_ARN"

    print_status "Permissions policy attached successfully!"

    # Get and display role ARN
    ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)

    echo ""
    print_status "🎉 IAM Role setup completed successfully!"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}GitHub Secrets to Add:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${BLUE}AWS_ROLE_ARN:${NC}"
    echo "$ROLE_ARN"
    echo ""
    echo -e "${BLUE}AWS_REGION:${NC}"
    echo "$AWS_REGION"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    print_status "Next steps:"
    echo "1. Go to https://github.com/$GITHUB_USERNAME/$GITHUB_REPO/settings/secrets/actions"
    echo "2. Add the secrets shown above"
    echo "3. Create a test commit to trigger the deployment pipeline"
    echo ""
}

# Function to cleanup temporary files
cleanup() {
    rm -f /tmp/github-trust-policy.json /tmp/github-permissions-policy.json
}

# Main execution
main() {
    print_header

    # Set up cleanup trap
    trap cleanup EXIT

    check_prerequisites
    get_user_inputs
    check_oidc_provider
    create_trust_policy
    create_permissions_policy
    create_iam_role

    print_status "Setup completed successfully! 🚀"
}

# Run main function
main "$@"
