"""
SMS parsing service for the ActivityTracker application.

This service handles the parsing of incoming SMS messages to extract activity
information. It uses natural language processing techniques to identify activity
types, durations, locations, and descriptions from unstructured SMS text.

Classes:
    SMSParsingService: Service for parsing SMS messages into Activity objects
"""

import re
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta

from ..models.activity import Activity, ActivityType
from ..models.sms import SMSMessage


class SMSParsingService:
    """
    Service for parsing SMS messages into structured activity data.

    This service analyzes incoming SMS messages and extracts activity information
    using pattern matching, keyword recognition, and natural language processing
    techniques. It handles various SMS formats and provides robust parsing.

    Attributes:
        activity_keywords: Dictionary mapping keywords to activity types
        duration_patterns: Regular expressions for extracting duration
        location_patterns: Regular expressions for extracting location

    Example:
        >>> parser = SMSParsingService()
        >>> sms = SMSMessage(message_body="WORK team meeting for 60 minutes in conference room")
        >>> activity = parser.parse_sms_to_activity(sms)
        >>> print(activity.activity_type)
        ActivityType.WORK
    """

    def __init__(self):
        """
        Initialize the SMS parsing service with keyword mappings and patterns.

        Sets up the keyword mappings for activity type detection and compiles
        regular expression patterns for extracting duration and location information.
        """
        # Keyword mappings for activity type detection
        self.activity_keywords: Dict[str, ActivityType] = {
            # Work-related keywords
            "work": ActivityType.WORK,
            "meeting": ActivityType.WORK,
            "conference": ActivityType.WORK,
            "office": ActivityType.WORK,
            "project": ActivityType.WORK,
            "coding": ActivityType.WORK,
            "development": ActivityType.WORK,
            "task": ActivityType.WORK,
            # Exercise keywords
            "exercise": ActivityType.EXERCISE,
            "workout": ActivityType.EXERCISE,
            "gym": ActivityType.EXERCISE,
            "run": ActivityType.EXERCISE,
            "running": ActivityType.EXERCISE,
            "walk": ActivityType.EXERCISE,
            "walking": ActivityType.EXERCISE,
            "bike": ActivityType.EXERCISE,
            "cycling": ActivityType.EXERCISE,
            "swim": ActivityType.EXERCISE,
            "swimming": ActivityType.EXERCISE,
            "yoga": ActivityType.EXERCISE,
            "fitness": ActivityType.EXERCISE,
            # Meal keywords
            "meal": ActivityType.MEAL,
            "breakfast": ActivityType.MEAL,
            "lunch": ActivityType.MEAL,
            "dinner": ActivityType.MEAL,
            "eat": ActivityType.MEAL,
            "eating": ActivityType.MEAL,
            "food": ActivityType.MEAL,
            "restaurant": ActivityType.MEAL,
            "cooking": ActivityType.MEAL,
            "snack": ActivityType.MEAL,
            # Study keywords
            "study": ActivityType.STUDY,
            "studying": ActivityType.STUDY,
            "reading": ActivityType.STUDY,
            "research": ActivityType.STUDY,
            "learning": ActivityType.STUDY,
            "course": ActivityType.STUDY,
            "lecture": ActivityType.STUDY,
            "homework": ActivityType.STUDY,
            "assignment": ActivityType.STUDY,
            # Social keywords
            "social": ActivityType.SOCIAL,
            "friends": ActivityType.SOCIAL,
            "family": ActivityType.SOCIAL,
            "party": ActivityType.SOCIAL,
            "hangout": ActivityType.SOCIAL,
            "coffee": ActivityType.SOCIAL,
            "drinks": ActivityType.SOCIAL,
            "date": ActivityType.SOCIAL,
            "gathering": ActivityType.SOCIAL,
            # Travel keywords
            "travel": ActivityType.TRAVEL,
            "drive": ActivityType.TRAVEL,
            "driving": ActivityType.TRAVEL,
            "commute": ActivityType.TRAVEL,
            "flight": ActivityType.TRAVEL,
            "train": ActivityType.TRAVEL,
            "bus": ActivityType.TRAVEL,
            "trip": ActivityType.TRAVEL,
            "journey": ActivityType.TRAVEL,
        }

        # Compile duration extraction patterns
        self.duration_patterns = [
            re.compile(
                r"(\d+)\s*(?:hours?|hrs?|h)\s*(?:and\s*)?(?:(\d+)\s*(?:minutes?|mins?|m))?",
                re.IGNORECASE,
            ),
            re.compile(r"(\d+)\s*(?:minutes?|mins?|m)", re.IGNORECASE),
            re.compile(r"(\d+)\s*(?:seconds?|secs?|s)", re.IGNORECASE),
            re.compile(r"for\s+(\d+)", re.IGNORECASE),  # Generic "for X" pattern
        ]

        # Compile location extraction patterns
        self.location_patterns = [
            re.compile(r"(?:at|in|@)\s+([^,\n]+?)(?:\s+for|\s+\d|\s*$)", re.IGNORECASE),
            re.compile(r"location[:\s]+([^,\n]+?)(?:\s+for|\s+\d|\s*$)", re.IGNORECASE),
            re.compile(r"venue[:\s]+([^,\n]+?)(?:\s+for|\s+\d|\s*$)", re.IGNORECASE),
        ]

    def parse_sms_to_activity(self, sms_message: SMSMessage) -> Optional[Activity]:
        """
        Parse an SMS message into an Activity object.

        Analyzes the SMS message content to extract activity information including
        type, description, duration, and location. Returns None if the message
        cannot be parsed as an activity.

        Args:
            sms_message: SMSMessage instance to parse

        Returns:
            Activity object if parsing successful, None otherwise

        Example:
            >>> sms = SMSMessage(message_body="WORK team meeting for 60 minutes")
            >>> activity = parser.parse_sms_to_activity(sms)
            >>> activity.activity_type == ActivityType.WORK
            True
            >>> activity.duration_minutes
            60
        """
        try:
            # Extract the clean message body
            message_body = sms_message.clean_message_body

            if not message_body.strip():
                return None

            # Determine activity type
            activity_type = self._extract_activity_type(
                message_body, sms_message.keyword
            )

            # Extract duration
            duration_minutes = self._extract_duration(message_body)

            # Extract location
            location = self._extract_location(message_body)

            # Create description (cleaned message without extracted info)
            description = self._create_description(
                message_body, activity_type, duration_minutes, location
            )

            # Validate that we have enough information for a valid activity
            if not description or len(description.strip()) < 2:
                return None

            # Create and return the activity
            return Activity(
                activity_type=activity_type,
                description=description,
                duration_minutes=duration_minutes,
                location=location,
                phone_number=sms_message.phone_number,
                timestamp=sms_message.timestamp,
                metadata={
                    "sms_message_id": sms_message.message_id,
                    "original_message": sms_message.message_body,
                    "keyword": sms_message.keyword,
                    "parsing_confidence": self._calculate_confidence(
                        message_body, activity_type
                    ),
                },
            )

        except Exception as e:
            # Log the error but don't raise - return None to indicate parsing failure
            print(f"Error parsing SMS message {sms_message.message_id}: {e}")
            return None

    def _extract_activity_type(
        self, message_body: str, keyword: Optional[str] = None
    ) -> ActivityType:
        """
        Extract the activity type from the message body and keyword.

        Uses keyword matching to identify the most likely activity type based
        on the message content. Prioritizes explicit keywords over inferred types.

        Args:
            message_body: Clean message body text
            keyword: Optional explicit keyword from SMS

        Returns:
            Detected ActivityType (defaults to OTHER if no match)
        """
        message_lower = message_body.lower()

        # First, check if we have an explicit keyword that maps to an activity type
        if keyword:
            keyword_lower = keyword.lower()
            if keyword_lower in self.activity_keywords:
                return self.activity_keywords[keyword_lower]

        # Score each activity type based on keyword matches
        type_scores: Dict[ActivityType, int] = {
            activity_type: 0 for activity_type in ActivityType
        }

        for word, activity_type in self.activity_keywords.items():
            if word in message_lower:
                # Give higher scores for exact word matches
                if f" {word} " in f" {message_lower} ":
                    type_scores[activity_type] += 3
                else:
                    type_scores[activity_type] += 1

        # Return the activity type with the highest score
        if max(type_scores.values()) > 0:
            return max(type_scores, key=type_scores.get)

        return ActivityType.OTHER

    def _extract_duration(self, message_body: str) -> Optional[int]:
        """
        Extract duration in minutes from the message body.

        Searches for duration patterns in the message text and converts
        various time formats to minutes.

        Args:
            message_body: Message text to search

        Returns:
            Duration in minutes, or None if not found

        Example:
            >>> parser._extract_duration("meeting for 2 hours and 30 minutes")
            150
        """
        for pattern in self.duration_patterns:
            match = pattern.search(message_body)
            if match:
                groups = match.groups()

                if len(groups) >= 2 and groups[1]:  # Hours and minutes
                    hours = int(groups[0])
                    minutes = int(groups[1])
                    return hours * 60 + minutes
                elif groups[0]:  # Single time value
                    value = int(groups[0])

                    # Determine if it's likely hours or minutes based on context
                    if "hour" in match.group().lower() or "hr" in match.group().lower():
                        return value * 60
                    elif (
                        "minute" in match.group().lower()
                        or "min" in match.group().lower()
                    ):
                        return value
                    elif (
                        "second" in match.group().lower()
                        or "sec" in match.group().lower()
                    ):
                        return max(
                            1, value // 60
                        )  # Convert seconds to minutes, minimum 1
                    else:
                        # Heuristic: values > 10 are likely minutes, <= 10 might be hours
                        return value if value > 10 else value * 60

        return None

    def _extract_location(self, message_body: str) -> Optional[str]:
        """
        Extract location information from the message body.

        Searches for location patterns and keywords to identify where
        the activity took place.

        Args:
            message_body: Message text to search

        Returns:
            Location string, or None if not found

        Example:
            >>> parser._extract_location("meeting at conference room B")
            "conference room B"
        """
        for pattern in self.location_patterns:
            match = pattern.search(message_body)
            if match:
                location = match.group(1).strip()
                # Clean up the location string
                location = re.sub(r"\s+", " ", location)  # Normalize whitespace
                if len(location) > 2:  # Minimum length check
                    return location

        return None

    def _create_description(
        self,
        message_body: str,
        activity_type: ActivityType,
        duration_minutes: Optional[int],
        location: Optional[str],
    ) -> str:
        """
        Create a clean description by removing extracted information.

        Produces a human-readable description by cleaning the original message
        and removing duration and location information that was extracted.

        Args:
            message_body: Original message body
            activity_type: Detected activity type
            duration_minutes: Extracted duration
            location: Extracted location

        Returns:
            Cleaned description string
        """
        description = message_body

        # Remove duration patterns
        for pattern in self.duration_patterns:
            description = pattern.sub("", description)

        # Remove location patterns
        for pattern in self.location_patterns:
            description = pattern.sub("", description)

        # Remove activity type keywords that were likely used for classification
        description_lower = description.lower()
        for keyword, keyword_type in self.activity_keywords.items():
            if keyword_type == activity_type and keyword in description_lower:
                # Only remove if it's at the beginning or a standalone word
                description = re.sub(
                    rf"\b{re.escape(keyword)}\b", "", description, flags=re.IGNORECASE
                )

        # Clean up the description
        description = re.sub(r"\s+", " ", description).strip()  # Normalize whitespace
        description = re.sub(
            r"^[,\-\s]+|[,\-\s]+$", "", description
        )  # Remove leading/trailing punctuation

        # If description is too short or empty, create a default one
        if not description or len(description) < 3:
            description = f"{activity_type.value.title()} activity"

        return description

    def _calculate_confidence(
        self, message_body: str, activity_type: ActivityType
    ) -> float:
        """
        Calculate parsing confidence score between 0.0 and 1.0.

        Evaluates how confident the parser is in the extracted information
        based on keyword matches and message structure.

        Args:
            message_body: Original message body
            activity_type: Detected activity type

        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.5  # Base confidence

        message_lower = message_body.lower()

        # Increase confidence for direct keyword matches
        matching_keywords = [
            keyword
            for keyword, keyword_type in self.activity_keywords.items()
            if keyword_type == activity_type and keyword in message_lower
        ]

        confidence += min(0.3, len(matching_keywords) * 0.1)

        # Increase confidence for structured patterns (duration, location)
        if any(pattern.search(message_body) for pattern in self.duration_patterns):
            confidence += 0.1

        if any(pattern.search(message_body) for pattern in self.location_patterns):
            confidence += 0.1

        # Decrease confidence for very short messages
        if len(message_body.split()) < 3:
            confidence -= 0.2

        return max(0.0, min(1.0, confidence))

    def get_parsing_suggestions(self, message_body: str) -> List[str]:
        """
        Get suggestions for improving SMS message formatting.

        Analyzes a message and provides suggestions to the user on how to
        format future messages for better parsing accuracy.

        Args:
            message_body: Message to analyze

        Returns:
            List of formatting suggestions
        """
        suggestions = []

        # Check for activity type keywords
        has_activity_keyword = any(
            keyword in message_body.lower() for keyword in self.activity_keywords.keys()
        )

        if not has_activity_keyword:
            suggestions.append(
                "Include an activity keyword like 'work', 'exercise', 'meal', etc."
            )

        # Check for duration
        has_duration = any(
            pattern.search(message_body) for pattern in self.duration_patterns
        )

        if not has_duration:
            suggestions.append("Include duration like 'for 30 minutes' or '2 hours'")

        # Check for location
        has_location = any(
            pattern.search(message_body) for pattern in self.location_patterns
        )

        if not has_location:
            suggestions.append("Include location like 'at office' or 'in gym'")

        # Check message length
        if len(message_body.split()) < 3:
            suggestions.append("Provide more details about the activity")

        return suggestions
