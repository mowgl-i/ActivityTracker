"""
Unit tests for ActivityTracker data models.

Tests the Pydantic models including validation, serialization, and
business logic methods. These tests ensure data integrity and proper
validation of user input.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.activitytracker.models.activity import Activity, ActivityType
from src.activitytracker.models.sms import SMSMessage


class TestActivity:
    """Test cases for the Activity model."""

    def test_activity_creation_with_required_fields(self):
        """Test creating an activity with only required fields."""
        activity = Activity(
            activity_type=ActivityType.WORK,
            description="Team meeting",
            phone_number="+1234567890",
        )

        assert activity.activity_type == ActivityType.WORK
        assert activity.description == "Team meeting"
        assert activity.phone_number == "+1234567890"
        assert activity.timestamp is not None
        assert activity.id.startswith("act_")
        assert activity.duration_minutes is None
        assert activity.location is None
        assert activity.metadata == {}

    def test_activity_creation_with_all_fields(self):
        """Test creating an activity with all fields populated."""
        timestamp = datetime(2024, 1, 15, 14, 30, 0)
        metadata = {"source": "test"}

        activity = Activity(
            activity_type=ActivityType.EXERCISE,
            description="Morning jog",
            duration_minutes=30,
            location="Central Park",
            phone_number="+1234567890",
            timestamp=timestamp,
            metadata=metadata,
        )

        assert activity.activity_type == ActivityType.EXERCISE
        assert activity.description == "Morning jog"
        assert activity.duration_minutes == 30
        assert activity.location == "Central Park"
        assert activity.phone_number == "+1234567890"
        assert activity.timestamp == timestamp
        assert activity.metadata == metadata

    def test_activity_id_generation(self):
        """Test that activity IDs are generated correctly."""
        activity1 = Activity(
            activity_type=ActivityType.WORK,
            description="Meeting 1",
            phone_number="+1234567890",
        )

        activity2 = Activity(
            activity_type=ActivityType.WORK,
            description="Meeting 2",
            phone_number="+1234567890",
        )

        # IDs should be unique
        assert activity1.id != activity2.id

        # IDs should follow expected format
        assert activity1.id.startswith("act_")
        assert activity2.id.startswith("act_")

        # Custom ID should be preserved
        custom_activity = Activity(
            id="custom_id_123",
            activity_type=ActivityType.WORK,
            description="Custom ID test",
            phone_number="+1234567890",
        )
        assert custom_activity.id == "custom_id_123"

    def test_phone_number_validation(self):
        """Test phone number validation and normalization."""
        # Valid phone numbers
        valid_phones = [
            "+1234567890",
            "1234567890",
            "+44 20 7123 4567",
            "(123) 456-7890",
        ]

        for phone in valid_phones:
            activity = Activity(
                activity_type=ActivityType.WORK, description="Test", phone_number=phone
            )
            # Should not raise an exception
            assert (
                len(
                    activity.phone_number.replace("+", "")
                    .replace(" ", "")
                    .replace("-", "")
                    .replace("(", "")
                    .replace(")", "")
                )
                >= 10
            )

    def test_phone_number_validation_invalid(self):
        """Test phone number validation with invalid numbers."""
        invalid_phones = [
            "123",  # Too short
            "",  # Empty
            "abc",  # Non-numeric
        ]

        for phone in invalid_phones:
            with pytest.raises(ValidationError):
                Activity(
                    activity_type=ActivityType.WORK,
                    description="Test",
                    phone_number=phone,
                )

    def test_duration_validation(self):
        """Test duration field validation."""
        # Valid durations
        activity = Activity(
            activity_type=ActivityType.WORK,
            description="Test",
            phone_number="+1234567890",
            duration_minutes=60,
        )
        assert activity.duration_minutes == 60

        # Invalid durations should raise validation errors
        with pytest.raises(ValidationError):
            Activity(
                activity_type=ActivityType.WORK,
                description="Test",
                phone_number="+1234567890",
                duration_minutes=0,  # Must be >= 1
            )

        with pytest.raises(ValidationError):
            Activity(
                activity_type=ActivityType.WORK,
                description="Test",
                phone_number="+1234567890",
                duration_minutes=1500,  # Must be <= 1440 (24 hours)
            )

    def test_description_validation(self):
        """Test description field validation."""
        # Valid description
        activity = Activity(
            activity_type=ActivityType.WORK,
            description="Team meeting with product team",
            phone_number="+1234567890",
        )
        assert activity.description == "Team meeting with product team"

        # Empty description should raise validation error
        with pytest.raises(ValidationError):
            Activity(
                activity_type=ActivityType.WORK,
                description="",
                phone_number="+1234567890",
            )

        # Too long description should raise validation error
        with pytest.raises(ValidationError):
            Activity(
                activity_type=ActivityType.WORK,
                description="x" * 501,  # Max length is 500
                phone_number="+1234567890",
            )

    def test_to_dynamodb_item(self):
        """Test conversion to DynamoDB item format."""
        timestamp = datetime(2024, 1, 15, 14, 30, 0)

        activity = Activity(
            activity_type=ActivityType.WORK,
            description="Team meeting",
            duration_minutes=60,
            location="Office",
            phone_number="+1234567890",
            timestamp=timestamp,
            metadata={"test": "value"},
        )

        item = activity.to_dynamodb_item()

        assert item["id"] == activity.id
        assert item["activity_type"] == "work"
        assert item["description"] == "Team meeting"
        assert item["duration_minutes"] == 60
        assert item["location"] == "Office"
        assert item["phone_number"] == "+1234567890"
        assert item["timestamp"] == timestamp.isoformat()
        assert item["metadata"] == {"test": "value"}

    def test_from_dynamodb_item(self):
        """Test creation from DynamoDB item format."""
        timestamp_str = "2024-01-15T14:30:00"

        item = {
            "id": "act_test_123",
            "activity_type": "work",
            "description": "Team meeting",
            "duration_minutes": 60,
            "location": "Office",
            "phone_number": "+1234567890",
            "timestamp": timestamp_str,
            "metadata": {"test": "value"},
        }

        activity = Activity.from_dynamodb_item(item)

        assert activity.id == "act_test_123"
        assert activity.activity_type == ActivityType.WORK
        assert activity.description == "Team meeting"
        assert activity.duration_minutes == 60
        assert activity.location == "Office"
        assert activity.phone_number == "+1234567890"
        assert activity.timestamp == datetime.fromisoformat(timestamp_str)
        assert activity.metadata == {"test": "value"}


class TestSMSMessage:
    """Test cases for the SMSMessage model."""

    def test_sms_message_creation(self):
        """Test creating an SMS message with required fields."""
        timestamp = datetime(2024, 1, 15, 14, 30, 0)

        sms = SMSMessage(
            message_id="msg-123",
            phone_number="+1234567890",
            message_body="WORK team meeting for 60 minutes",
            timestamp=timestamp,
        )

        assert sms.message_id == "msg-123"
        assert sms.phone_number == "+1234567890"
        assert sms.message_body == "WORK team meeting for 60 minutes"
        assert sms.timestamp == timestamp
        assert sms.keyword is None
        assert sms.metadata == {}

    def test_sms_message_with_keyword_and_metadata(self):
        """Test creating an SMS message with keyword and metadata."""
        metadata = {"carrier": "Test Carrier"}

        sms = SMSMessage(
            message_id="msg-123",
            phone_number="+1234567890",
            message_body="WORK team meeting for 60 minutes",
            keyword="WORK",
            metadata=metadata,
        )

        assert sms.keyword == "WORK"
        assert sms.metadata == metadata

    def test_phone_number_validation(self):
        """Test phone number validation in SMS messages."""
        # Valid phone number
        sms = SMSMessage(
            message_id="msg-123", phone_number="1234567890", message_body="Test message"
        )
        assert sms.phone_number.startswith("+1")  # Should be normalized

        # Invalid phone number
        with pytest.raises(ValidationError):
            SMSMessage(
                message_id="msg-123",
                phone_number="123",  # Too short
                message_body="Test message",
            )

    def test_message_body_validation(self):
        """Test message body validation and cleaning."""
        # Normal message
        sms = SMSMessage(
            message_id="msg-123",
            phone_number="+1234567890",
            message_body="  WORK   team   meeting  ",
        )
        assert sms.message_body == "WORK team meeting"  # Cleaned whitespace

        # Empty message should fail
        with pytest.raises(ValidationError):
            SMSMessage(
                message_id="msg-123", phone_number="+1234567890", message_body=""
            )

        # Too long message should fail
        with pytest.raises(ValidationError):
            SMSMessage(
                message_id="msg-123",
                phone_number="+1234567890",
                message_body="x" * 1601,  # Max length is 1600
            )

    def test_clean_message_body_property(self):
        """Test the clean_message_body property."""
        # Without keyword
        sms = SMSMessage(
            message_id="msg-123",
            phone_number="+1234567890",
            message_body="team meeting for 60 minutes",
        )
        assert sms.clean_message_body == "team meeting for 60 minutes"

        # With keyword
        sms_with_keyword = SMSMessage(
            message_id="msg-123",
            phone_number="+1234567890",
            message_body="WORK team meeting for 60 minutes",
            keyword="WORK",
        )
        assert sms_with_keyword.clean_message_body == "team meeting for 60 minutes"

    def test_is_activity_message_property(self):
        """Test the is_activity_message property."""
        # Message with activity keywords
        activity_messages = [
            "WORK team meeting",
            "exercise in the gym",
            "lunch with friends",
            "studying for exam",
            "meeting with client",
        ]

        for message in activity_messages:
            sms = SMSMessage(
                message_id="msg-123", phone_number="+1234567890", message_body=message
            )
            assert (
                sms.is_activity_message
            ), f"'{message}' should be recognized as activity"

        # Message without activity keywords
        non_activity_messages = ["hello world", "how are you", "random text message"]

        for message in non_activity_messages:
            sms = SMSMessage(
                message_id="msg-123", phone_number="+1234567890", message_body=message
            )
            assert (
                not sms.is_activity_message
            ), f"'{message}' should not be recognized as activity"

    def test_from_pinpoint_event(self):
        """Test creating SMS message from Pinpoint event."""
        event = {
            "Records": [
                {
                    "pinpoint": {
                        "sms": {
                            "messageId": "msg-12345",
                            "originationNumber": "+1234567890",
                            "messageBody": "WORK team meeting for 60 minutes",
                            "timestamp": "2024-01-15T14:30:00Z",
                            "keyword": "WORK",
                            "messageType": "TRANSACTIONAL",
                            "destinationNumber": "+15551234567",
                            "isoCountryCode": "US",
                            "carrierName": "Test Carrier",
                        }
                    }
                }
            ]
        }

        sms = SMSMessage.from_pinpoint_event(event)

        assert sms.message_id == "msg-12345"
        assert sms.phone_number == "+1234567890"
        assert sms.message_body == "WORK team meeting for 60 minutes"
        assert sms.keyword == "WORK"
        assert sms.metadata["messageType"] == "TRANSACTIONAL"
        assert sms.metadata["destinationNumber"] == "+15551234567"
        assert sms.metadata["country"] == "US"
        assert sms.metadata["carrier"] == "Test Carrier"

    def test_from_pinpoint_event_invalid(self):
        """Test handling invalid Pinpoint events."""
        invalid_events = [
            {},  # Empty event
            {"Records": []},  # No records
            {"Records": [{}]},  # No pinpoint data
            {"Records": [{"pinpoint": {}}]},  # No sms data
            {"Records": [{"pinpoint": {"sms": {}}}]},  # Missing required fields
        ]

        for event in invalid_events:
            with pytest.raises(ValueError):
                SMSMessage.from_pinpoint_event(event)


class TestActivityType:
    """Test cases for the ActivityType enum."""

    def test_activity_type_values(self):
        """Test that all activity types have expected values."""
        expected_types = {
            ActivityType.WORK: "work",
            ActivityType.EXERCISE: "exercise",
            ActivityType.MEAL: "meal",
            ActivityType.STUDY: "study",
            ActivityType.SOCIAL: "social",
            ActivityType.TRAVEL: "travel",
            ActivityType.OTHER: "other",
        }

        for enum_value, string_value in expected_types.items():
            assert enum_value.value == string_value

    def test_activity_type_from_string(self):
        """Test creating ActivityType from string values."""
        assert ActivityType("work") == ActivityType.WORK
        assert ActivityType("exercise") == ActivityType.EXERCISE
        assert ActivityType("meal") == ActivityType.MEAL
        assert ActivityType("study") == ActivityType.STUDY
        assert ActivityType("social") == ActivityType.SOCIAL
        assert ActivityType("travel") == ActivityType.TRAVEL
        assert ActivityType("other") == ActivityType.OTHER

        # Invalid string should raise ValueError
        with pytest.raises(ValueError):
            ActivityType("invalid_type")
