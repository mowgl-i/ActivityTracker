"""
ActivityTracker: Serverless activity tracking using AWS Pinpoint and Lambda.

This package provides serverless activity tracking functionality that receives
SMS messages via AWS Pinpoint, processes them through Lambda functions, and
stores the data in DynamoDB for dashboard visualization.

Modules:
    lambdas: AWS Lambda function handlers for SMS processing and API endpoints
    services: Business logic and AWS service integrations
    models: Data models and validation using Pydantic
    utils: Utility functions and helpers

Author: Generated with Claude Code
Version: 0.1.0
"""

__version__ = "0.1.0"
__author__ = "Generated with Claude Code"

from .models import Activity, ActivityType, SMSMessage
from .services import ActivityService, DynamoDBService, PinpointService

__all__ = [
    "Activity",
    "ActivityType",
    "SMSMessage",
    "ActivityService",
    "PinpointService",
    "DynamoDBService",
]
