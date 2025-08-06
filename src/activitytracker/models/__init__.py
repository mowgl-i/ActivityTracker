"""
Data models for the ActivityTracker application.

This module contains Pydantic models for data validation and serialization
used throughout the application for handling activities, SMS messages, and
other data structures.

Classes:
    Activity: Model representing a tracked activity
    ActivityType: Enum for different types of activities
    SMSMessage: Model for incoming SMS message data
"""

from .activity import Activity, ActivityType
from .sms import SMSMessage

__all__ = ["Activity", "ActivityType", "SMSMessage"]