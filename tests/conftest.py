"""
Pytest configuration and shared fixtures for ActivityTracker tests.

This module contains pytest configuration, shared fixtures, and test utilities
that are used across multiple test modules. It sets up mock AWS services,
test data, and common test patterns.

Fixtures:
    mock_dynamodb: Mocked DynamoDB service for testing
    mock_pinpoint_event: Sample Pinpoint SMS event data
    sample_activities: Collection of test activity objects
    activity_service: Configured ActivityService instance for testing
"""

import os
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch

import boto3
from moto import mock_dynamodb

from src.activitytracker.models.activity import Activity, ActivityType
from src.activitytracker.models.sms import SMSMessage
from src.activitytracker.services.activity_service import ActivityService
from src.activitytracker.services.dynamodb_service import DynamoDBService
from src.activitytracker.services.sms_parsing_service import SMSParsingService


# Test configuration constants
TEST_TABLE_NAME = "test-activities-table"
TEST_PHONE_NUMBER = "+1234567890"
TEST_ENVIRONMENT = "test"


@pytest.fixture(scope="session")
def aws_credentials():
    """
    Fixture to set up AWS credentials for testing.
    
    Sets environment variables for AWS credentials that are used by moto
    for mocking AWS services. These are fake credentials for testing only.
    """
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture
def mock_dynamodb_table(aws_credentials):
    """
    Fixture that creates a mocked DynamoDB table for testing.
    
    Uses moto to create an in-memory DynamoDB table that matches
    the structure defined in the SAM template. This allows testing
    database operations without requiring actual AWS resources.
    
    Returns:
        boto3.resource.Table: Mocked DynamoDB table resource
    """
    with mock_dynamodb():
        # Create DynamoDB resource
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create table matching SAM template structure
        table = dynamodb.create_table(
            TableName=TEST_TABLE_NAME,
            KeySchema=[
                {
                    'AttributeName': 'id',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'phone_number',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'timestamp',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'PhoneNumberTimestampIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'phone_number',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Wait for table to be created
        table.wait_until_exists()
        yield table


@pytest.fixture
def dynamodb_service(mock_dynamodb_table):
    """
    Fixture that provides a DynamoDBService instance for testing.
    
    Creates a configured DynamoDBService instance that uses the mocked
    DynamoDB table for testing database operations.
    
    Returns:
        DynamoDBService: Configured service instance
    """
    return DynamoDBService(table_name=TEST_TABLE_NAME)


@pytest.fixture
def sms_parsing_service():
    """
    Fixture that provides an SMSParsingService instance for testing.
    
    Returns:
        SMSParsingService: Service instance for testing SMS parsing
    """
    return SMSParsingService()


@pytest.fixture
def activity_service(dynamodb_service, sms_parsing_service):
    """
    Fixture that provides a complete ActivityService instance for testing.
    
    Creates a fully configured ActivityService with mocked dependencies
    for comprehensive testing of business logic.
    
    Returns:
        ActivityService: Configured service instance
    """
    return ActivityService(
        db_service=dynamodb_service,
        parser_service=sms_parsing_service
    )


@pytest.fixture
def sample_sms_message() -> SMSMessage:
    """
    Fixture that provides a sample SMS message for testing.
    
    Returns:
        SMSMessage: Sample SMS message with typical activity content
    """
    return SMSMessage(
        message_id="test-message-001",
        phone_number=TEST_PHONE_NUMBER,
        message_body="WORK team meeting for 60 minutes in conference room",
        timestamp=datetime.utcnow(),
        keyword="WORK",
        metadata={"test": True}
    )


@pytest.fixture
def sample_activities() -> List[Activity]:
    """
    Fixture that provides a collection of sample activities for testing.
    
    Creates a diverse set of test activities with different types,
    durations, and timestamps for comprehensive testing scenarios.
    
    Returns:
        List[Activity]: Collection of sample activity objects
    """
    base_time = datetime.utcnow() - timedelta(hours=24)
    
    activities = [
        Activity(
            activity_type=ActivityType.WORK,
            description="Team meeting with product team",
            duration_minutes=60,
            location="Conference Room A",
            phone_number=TEST_PHONE_NUMBER,
            timestamp=base_time
        ),
        Activity(
            activity_type=ActivityType.EXERCISE,
            description="Morning jog in the park",
            duration_minutes=30,
            location="Central Park",
            phone_number=TEST_PHONE_NUMBER,
            timestamp=base_time + timedelta(hours=8)
        ),
        Activity(
            activity_type=ActivityType.MEAL,
            description="Lunch with colleagues",
            duration_minutes=45,
            location="Downtown Restaurant",
            phone_number=TEST_PHONE_NUMBER,
            timestamp=base_time + timedelta(hours=12)
        ),
        Activity(
            activity_type=ActivityType.STUDY,
            description="Reading technical documentation",
            duration_minutes=90,
            phone_number=TEST_PHONE_NUMBER,
            timestamp=base_time + timedelta(hours=20)
        ),
        Activity(
            activity_type=ActivityType.OTHER,
            description="Quick phone call",
            duration_minutes=15,
            phone_number="+1987654321",  # Different phone number
            timestamp=base_time + timedelta(hours=22)
        )
    ]
    
    return activities


@pytest.fixture
def mock_pinpoint_event() -> Dict[str, Any]:
    """
    Fixture that provides a mock AWS Pinpoint SMS event for testing.
    
    Creates a realistic Pinpoint event structure that matches what
    would be received by the SMS processor Lambda function.
    
    Returns:
        Dict[str, Any]: Mock Pinpoint SMS event
    """
    return {
        "Records": [
            {
                "pinpoint": {
                    "sms": {
                        "messageId": "test-msg-12345",
                        "originationNumber": TEST_PHONE_NUMBER,
                        "destinationNumber": "+15551234567",
                        "messageBody": "WORK team meeting for 60 minutes",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "keyword": "WORK",
                        "messageType": "TRANSACTIONAL",
                        "isoCountryCode": "US",
                        "carrierName": "Test Carrier"
                    }
                },
                "eventSource": "aws:pinpoint",
                "eventVersion": "1.0"
            }
        ]
    }


@pytest.fixture
def mock_api_gateway_event() -> Dict[str, Any]:
    """
    Fixture that provides a mock API Gateway event for testing.
    
    Creates a realistic API Gateway event structure for testing
    the API handler Lambda function.
    
    Returns:
        Dict[str, Any]: Mock API Gateway event
    """
    return {
        "httpMethod": "GET",
        "resource": "/activities",
        "pathParameters": None,
        "queryStringParameters": {
            "limit": "10",
            "days": "30"
        },
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "test-client/1.0"
        },
        "body": None,
        "requestContext": {
            "requestId": "test-request-123",
            "identity": {
                "sourceIp": "127.0.0.1"
            }
        }
    }


@pytest.fixture
def populated_database(dynamodb_service, sample_activities):
    """
    Fixture that populates the test database with sample activities.
    
    Pre-populates the database with test data for scenarios that
    require existing data to be present.
    
    Args:
        dynamodb_service: DynamoDB service instance
        sample_activities: Collection of sample activities
    
    Returns:
        DynamoDBService: Database service with populated data
    """
    for activity in sample_activities:
        dynamodb_service.save_activity(activity)
    
    return dynamodb_service


# Pytest configuration
def pytest_configure(config):
    """
    Pytest configuration function.
    
    Sets up test environment configuration and custom markers
    for organizing test execution.
    """
    # Add custom markers
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "aws: mark test as requiring AWS services")


# Test utilities
def assert_activity_equals(actual: Activity, expected: Activity, ignore_id: bool = True):
    """
    Utility function to assert two activities are equal.
    
    Compares two Activity objects while optionally ignoring auto-generated
    fields like ID and timestamp for testing purposes.
    
    Args:
        actual: Actual activity object
        expected: Expected activity object
        ignore_id: Whether to ignore ID differences
    """
    assert actual.activity_type == expected.activity_type
    assert actual.description == expected.description
    assert actual.duration_minutes == expected.duration_minutes
    assert actual.location == expected.location
    assert actual.phone_number == expected.phone_number
    
    if not ignore_id:
        assert actual.id == expected.id


def create_test_activity(**kwargs) -> Activity:
    """
    Utility function to create test activities with default values.
    
    Creates Activity objects with sensible defaults for testing,
    allowing specific fields to be overridden as needed.
    
    Args:
        **kwargs: Activity field overrides
        
    Returns:
        Activity: Test activity object
    """
    defaults = {
        'activity_type': ActivityType.WORK,
        'description': 'Test activity',
        'duration_minutes': 30,
        'location': 'Test Location',
        'phone_number': TEST_PHONE_NUMBER,
        'timestamp': datetime.utcnow()
    }
    
    defaults.update(kwargs)
    return Activity(**defaults)