"""
SMS message data model for the ActivityTracker application.

This module defines the SMSMessage model used to represent and validate
incoming SMS data from AWS Pinpoint. It handles the parsing of Pinpoint
event payloads and extraction of relevant message information.

Classes:
    SMSMessage: Pydantic model for incoming SMS message data
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class SMSMessage(BaseModel):
    """
    Pydantic model representing an incoming SMS message from AWS Pinpoint.

    This model handles validation and parsing of SMS message data received
    through AWS Pinpoint events. It extracts the essential information needed
    to process activity tracking requests.

    Attributes:
        message_id: Unique identifier for the SMS message
        phone_number: Sender's phone number
        message_body: The actual text content of the SMS
        timestamp: When the message was received
        keyword: Optional keyword that triggered the message (if any)
        metadata: Additional message metadata from Pinpoint

    Example:
        >>> sms = SMSMessage(
        ...     message_id="msg-123",
        ...     phone_number="+1234567890",
        ...     message_body="WORK meeting with team for 60 minutes",
        ...     timestamp=datetime.utcnow()
        ... )
        >>> print(sms.clean_message_body)
        "meeting with team for 60 minutes"
    """

    message_id: str = Field(..., description="Unique message identifier")
    phone_number: str = Field(..., description="Sender phone number")
    message_body: str = Field(
        ..., min_length=1, max_length=1600, description="SMS message content"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Message timestamp"
    )
    keyword: Optional[str] = Field(None, description="Triggering keyword")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional message data"
    )

    @validator("phone_number")
    def validate_phone_number(cls, v: str) -> str:
        """
        Validate and normalize phone number format.

        Ensures phone number is in a consistent format for processing.
        Handles various input formats and normalizes to E.164 format.

        Args:
            v: Phone number string

        Returns:
            Normalized phone number

        Raises:
            ValueError: If phone number format is invalid
        """
        # Remove all non-digit characters except +
        cleaned = "".join(c for c in v if c.isdigit() or c == "+")

        # Must be at least 10 digits
        digits_only = "".join(c for c in cleaned if c.isdigit())
        if len(digits_only) < 10:
            raise ValueError("Phone number must contain at least 10 digits")

        # Add + if not present and ensure proper format
        if not cleaned.startswith("+"):
            if len(digits_only) == 10:
                cleaned = f"+1{digits_only}"  # Assume US number
            else:
                cleaned = f"+{digits_only}"

        return cleaned

    @validator("message_body")
    def validate_message_body(cls, v: str) -> str:
        """
        Validate and clean message body content.

        Removes excessive whitespace and ensures the message content
        is suitable for activity parsing.

        Args:
            v: Raw message body

        Returns:
            Cleaned message body
        """
        # Remove extra whitespace and normalize
        cleaned = " ".join(v.strip().split())

        if not cleaned:
            raise ValueError("Message body cannot be empty")

        return cleaned

    @property
    def clean_message_body(self) -> str:
        """
        Get the message body with keyword removed if present.

        This property returns the message content with any leading
        keyword removed, making it easier to parse activity details.

        Returns:
            Message body without leading keyword

        Example:
            >>> sms = SMSMessage(message_body="WORK meeting with team")
            >>> sms.clean_message_body
            "meeting with team"
        """
        if not self.keyword:
            return self.message_body

        # Remove keyword from the beginning of the message
        body = self.message_body.strip()
        if body.upper().startswith(self.keyword.upper()):
            body = body[len(self.keyword) :].strip()

        return body

    @property
    def is_activity_message(self) -> bool:
        """
        Check if this SMS appears to be an activity tracking message.

        Determines if the message content looks like it contains activity
        information that should be processed by the system.

        Returns:
            True if message appears to contain activity data
        """
        # List of common activity keywords
        activity_keywords = [
            "work",
            "exercise",
            "meal",
            "study",
            "social",
            "travel",
            "workout",
            "meeting",
            "lunch",
            "dinner",
            "breakfast",
            "gym",
            "run",
            "walk",
            "drive",
            "commute",
        ]

        message_lower = self.message_body.lower()
        return any(keyword in message_lower for keyword in activity_keywords)

    class Config:
        """Pydantic model configuration."""

        json_encoders = {datetime: lambda dt: dt.isoformat()}

    @classmethod
    def from_pinpoint_event(cls, event: Dict[str, Any]) -> "SMSMessage":
        """
        Create an SMSMessage instance from a Pinpoint event payload.

        Parses the AWS Pinpoint event structure to extract SMS message
        information and create a validated SMSMessage instance.

        Args:
            event: AWS Pinpoint event dictionary

        Returns:
            SMSMessage instance

        Raises:
            ValueError: If event format is invalid or required fields missing

        Example:
            >>> event = {
            ...     'Records': [{
            ...         'pinpoint': {
            ...             'sms': {
            ...                 'messageId': 'msg-123',
            ...                 'originationNumber': '+1234567890',
            ...                 'messageBody': 'WORK meeting with team',
            ...                 'timestamp': '2024-01-15T14:30:00Z'
            ...             }
            ...         }
            ...     }]
            ... }
            >>> sms = SMSMessage.from_pinpoint_event(event)
        """
        try:
            # Navigate the Pinpoint event structure
            record = event["Records"][0]
            sms_data = record["pinpoint"]["sms"]

            # Extract required fields
            message_id = sms_data["messageId"]
            phone_number = sms_data["originationNumber"]
            message_body = sms_data["messageBody"]

            # Parse timestamp if present
            timestamp = datetime.utcnow()
            if "timestamp" in sms_data:
                timestamp = datetime.fromisoformat(
                    sms_data["timestamp"].replace("Z", "+00:00")
                )

            # Extract keyword if present
            keyword = sms_data.get("keyword")

            # Collect additional metadata
            metadata = {
                "messageType": sms_data.get("messageType"),
                "destinationNumber": sms_data.get("destinationNumber"),
                "country": sms_data.get("isoCountryCode"),
                "carrier": sms_data.get("carrierName"),
            }

            return cls(
                message_id=message_id,
                phone_number=phone_number,
                message_body=message_body,
                timestamp=timestamp,
                keyword=keyword,
                metadata={k: v for k, v in metadata.items() if v is not None},
            )

        except (KeyError, IndexError, ValueError) as e:
            raise ValueError(f"Invalid Pinpoint event format: {e}") from e
