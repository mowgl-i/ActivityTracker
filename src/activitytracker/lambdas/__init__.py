"""
AWS Lambda functions for the ActivityTracker application.

This package contains all Lambda function handlers for the ActivityTracker
system, including SMS processing, API endpoints, and background tasks.

Modules:
    sms_processor: Handles incoming SMS messages from AWS Pinpoint
    api_handler: Provides REST API endpoints for dashboard and external access
"""

# Lambda function entry points are imported directly from their modules
# This allows for clean imports in the AWS SAM template