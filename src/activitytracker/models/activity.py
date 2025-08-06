"""
Activity data model for the ActivityTracker application.

This module defines the core Activity model and related enums used to represent
and validate activity data throughout the system. Activities are created from
parsed SMS messages and stored in DynamoDB.

Classes:
    ActivityType: Enum defining the types of activities that can be tracked
    Activity: Pydantic model for activity data with validation
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, validator


class ActivityType(str, Enum):
    """
    Enumeration of supported activity types.

    This enum defines the different categories of activities that can be
    tracked through SMS messages. Each type corresponds to a specific
    parsing pattern and validation rules.
    """

    WORK = "work"
    EXERCISE = "exercise"
    MEAL = "meal"
    STUDY = "study"
    SOCIAL = "social"
    TRAVEL = "travel"
    OTHER = "other"


class Activity(BaseModel):
    """
    Pydantic model representing a tracked activity.

    This model handles validation and serialization of activity data received
    from SMS messages. It includes automatic timestamp generation and validation
    of required fields.

    Attributes:
        id: Unique identifier for the activity (auto-generated)
        activity_type: Category of the activity (ActivityType enum)
        description: Human-readable description of the activity
        duration_minutes: Optional duration in minutes
        location: Optional location where activity occurred
        phone_number: Phone number that sent the SMS
        timestamp: When the activity was recorded (auto-generated)
        metadata: Additional key-value data from SMS parsing

    Example:
        >>> activity = Activity(
        ...     activity_type=ActivityType.WORK,
        ...     description="Team meeting with product team",
        ...     duration_minutes=60,
        ...     phone_number="+1234567890"
        ... )
        >>> print(activity.id)
        act_2024_01_15_14_30_00_abc123
    """

    id: str = Field(default="", description="Unique activity identifier")
    activity_type: ActivityType = Field(..., description="Type of activity")
    description: str = Field(
        ..., min_length=1, max_length=500, description="Activity description"
    )
    duration_minutes: Optional[int] = Field(
        None, ge=1, le=1440, description="Duration in minutes"
    )
    location: Optional[str] = Field(
        None, max_length=200, description="Activity location"
    )
    phone_number: str = Field(..., description="Source phone number")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Activity timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional activity data"
    )

    @validator("id", pre=True, always=True)
    def generate_id(cls, v: str, values: Dict[str, Any]) -> str:
        """
        Generate a unique ID for the activity if not provided.

        Creates an ID in the format: act_YYYY_MM_DD_HH_MM_SS_hash
        where hash is derived from the timestamp and phone number.

        Args:
            v: Current ID value (may be empty)
            values: All field values for validation context

        Returns:
            Generated or existing activity ID
        """
        if v:
            return v

        now = datetime.utcnow()
        timestamp_str = now.strftime("%Y_%m_%d_%H_%M_%S")

        # Simple hash based on timestamp and phone for uniqueness
        phone = values.get("phone_number", "")
        hash_input = f"{timestamp_str}_{phone}"
        simple_hash = str(hash(hash_input))[-6:]

        return f"act_{timestamp_str}_{simple_hash}"

    @validator("phone_number")
    def validate_phone_number(cls, v: str) -> str:
        """
        Validate phone number format.

        Ensures phone number is in a valid format for SMS processing.
        Accepts formats like +1234567890 or 1234567890.

        Args:
            v: Phone number string

        Returns:
            Validated phone number

        Raises:
            ValueError: If phone number format is invalid
        """
        # Remove all non-digit characters except +
        cleaned = "".join(c for c in v if c.isdigit() or c == "+")

        # Must be at least 10 digits
        digits_only = "".join(c for c in cleaned if c.isdigit())
        if len(digits_only) < 10:
            raise ValueError("Phone number must contain at least 10 digits")

        return cleaned

    class Config:
        """Pydantic model configuration."""

        json_encoders = {datetime: lambda dt: dt.isoformat()}
        use_enum_values = True

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """
        Convert the activity to a DynamoDB item format.

        Transforms the Pydantic model into a dictionary suitable for
        DynamoDB storage, including proper type conversions.

        Returns:
            Dictionary representation for DynamoDB
        """
        item = self.dict()
        item["timestamp"] = self.timestamp.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "Activity":
        """
        Create an Activity instance from a DynamoDB item.

        Converts a DynamoDB item back into an Activity model with
        proper type conversions and validation.

        Args:
            item: DynamoDB item dictionary

        Returns:
            Activity instance
        """
        if "timestamp" in item and isinstance(item["timestamp"], str):
            item["timestamp"] = datetime.fromisoformat(item["timestamp"])

        return cls(**item)
