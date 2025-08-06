"""
Activity service for the ActivityTracker application.

This service contains the core business logic for managing activities. It
coordinates between SMS parsing, data validation, and storage operations
to provide a high-level interface for activity management.

Classes:
    ActivityService: Core business logic service for activity management
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ..models.activity import Activity, ActivityType
from ..models.sms import SMSMessage
from .dynamodb_service import DynamoDBService
from .sms_parsing_service import SMSParsingService


class ActivityService:
    """
    Core business logic service for activity management.

    This service orchestrates the processing of SMS messages into activities,
    handles validation and business rules, and manages the interaction between
    different service components.

    Attributes:
        db_service: DynamoDB service for data persistence
        parser_service: SMS parsing service for message analysis

    Example:
        >>> activity_service = ActivityService()
        >>> sms = SMSMessage(...)
        >>> result = activity_service.process_sms_message(sms)
        >>> if result['success']:
        ...     print(f"Created activity: {result['activity'].id}")
    """

    def __init__(
        self,
        db_service: Optional[DynamoDBService] = None,
        parser_service: Optional[SMSParsingService] = None,
    ):
        """
        Initialize the activity service.

        Sets up the service dependencies for database access and SMS parsing.
        Creates default service instances if not provided.

        Args:
            db_service: Optional DynamoDB service instance
            parser_service: Optional SMS parsing service instance
        """
        self.db_service = db_service or DynamoDBService()
        self.parser_service = parser_service or SMSParsingService()

    def process_sms_message(self, sms_message: SMSMessage) -> Dict[str, Any]:
        """
        Process an incoming SMS message into an activity.

        This is the main entry point for SMS message processing. It handles
        parsing, validation, storage, and error handling for incoming messages.

        Args:
            sms_message: SMS message to process

        Returns:
            Dictionary containing processing results:
            - success: boolean indicating if processing succeeded
            - activity: Activity object if created successfully
            - error: error message if processing failed
            - suggestions: list of formatting suggestions if parsing was partial

        Example:
            >>> sms = SMSMessage(message_body="WORK team meeting for 60 minutes")
            >>> result = activity_service.process_sms_message(sms)
            >>> if result['success']:
            ...     print(f"Activity created: {result['activity'].id}")
        """
        result = {
            "success": False,
            "activity": None,
            "error": None,
            "suggestions": [],
            "confidence": 0.0,
        }

        try:
            # Check if message looks like an activity
            if not sms_message.is_activity_message:
                result["error"] = (
                    "Message does not appear to contain activity information"
                )
                result["suggestions"] = self.parser_service.get_parsing_suggestions(
                    sms_message.message_body
                )
                return result

            # Parse SMS into activity
            activity = self.parser_service.parse_sms_to_activity(sms_message)

            if not activity:
                result["error"] = "Could not parse activity information from message"
                result["suggestions"] = self.parser_service.get_parsing_suggestions(
                    sms_message.message_body
                )
                return result

            # Validate the parsed activity
            validation_result = self._validate_activity(activity)
            if not validation_result["valid"]:
                result["error"] = validation_result["error"]
                result["suggestions"] = validation_result["suggestions"]
                return result

            # Apply business rules and enhancements
            activity = self._enhance_activity(activity)

            # Save to database
            if self.db_service.save_activity(activity):
                result["success"] = True
                result["activity"] = activity
                result["confidence"] = activity.metadata.get("parsing_confidence", 0.0)
            else:
                result["error"] = "Failed to save activity to database"

            return result

        except Exception as e:
            result["error"] = f"Unexpected error processing SMS: {str(e)}"
            return result

    def _validate_activity(self, activity: Activity) -> Dict[str, Any]:
        """
        Validate an activity object against business rules.

        Checks the activity data for completeness, consistency, and business
        rule compliance. Returns validation results with suggestions.

        Args:
            activity: Activity to validate

        Returns:
            Dictionary with validation results:
            - valid: boolean indicating if activity is valid
            - error: error message if validation failed
            - suggestions: list of suggestions for improvement
        """
        validation = {"valid": True, "error": None, "suggestions": []}

        # Check required fields
        if not activity.description or len(activity.description.strip()) < 3:
            validation["valid"] = False
            validation["error"] = "Activity description is too short or missing"
            validation["suggestions"].append("Provide more details about the activity")
            return validation

        # Validate duration if present
        if activity.duration_minutes is not None:
            if activity.duration_minutes <= 0:
                validation["valid"] = False
                validation["error"] = "Duration must be positive"
                return validation

            if activity.duration_minutes > 1440:  # More than 24 hours
                validation["suggestions"].append("Duration seems very long (>24 hours)")
            elif activity.duration_minutes < 1:
                validation["suggestions"].append(
                    "Duration seems very short (<1 minute)"
                )

        # Validate location if present
        if activity.location and len(activity.location) > 200:
            validation["valid"] = False
            validation["error"] = (
                "Location description is too long (max 200 characters)"
            )
            return validation

        # Check for reasonable timestamp (not too far in future/past)
        now = datetime.utcnow()
        time_diff = abs((activity.timestamp - now).total_seconds())

        if time_diff > 7 * 24 * 3600:  # More than 7 days difference
            validation["suggestions"].append(
                "Activity timestamp is more than 7 days from current time"
            )

        return validation

    def _enhance_activity(self, activity: Activity) -> Activity:
        """
        Apply business rules and enhancements to an activity.

        Adds additional metadata, applies business logic, and enhances
        the activity data based on patterns and rules.

        Args:
            activity: Activity to enhance

        Returns:
            Enhanced activity object
        """
        # Add processing metadata
        activity.metadata.update(
            {
                "processed_at": datetime.utcnow().isoformat(),
                "service_version": "1.0.0",
                "processing_rules_applied": [],
            }
        )

        # Apply duration inference if missing
        if activity.duration_minutes is None:
            inferred_duration = self._infer_duration(activity)
            if inferred_duration:
                activity.duration_minutes = inferred_duration
                activity.metadata["processing_rules_applied"].append(
                    "duration_inference"
                )

        # Apply location cleanup
        if activity.location:
            cleaned_location = self._clean_location(activity.location)
            if cleaned_location != activity.location:
                activity.location = cleaned_location
                activity.metadata["processing_rules_applied"].append("location_cleanup")

        # Apply description enhancement
        enhanced_description = self._enhance_description(activity)
        if enhanced_description != activity.description:
            activity.description = enhanced_description
            activity.metadata["processing_rules_applied"].append(
                "description_enhancement"
            )

        return activity

    def _infer_duration(self, activity: Activity) -> Optional[int]:
        """
        Infer reasonable duration based on activity type and description.

        Uses heuristics and patterns to estimate duration for activities
        that don't have explicit duration information.

        Args:
            activity: Activity to analyze

        Returns:
            Inferred duration in minutes, or None if cannot infer
        """
        # Default durations by activity type (in minutes)
        default_durations = {
            ActivityType.WORK: 60,  # 1 hour default for work activities
            ActivityType.EXERCISE: 45,  # 45 minutes for exercise
            ActivityType.MEAL: 30,  # 30 minutes for meals
            ActivityType.STUDY: 90,  # 1.5 hours for study sessions
            ActivityType.SOCIAL: 120,  # 2 hours for social activities
            ActivityType.TRAVEL: 30,  # 30 minutes for travel
            ActivityType.OTHER: 60,  # 1 hour default
        }

        # Check description for duration hints
        description_lower = activity.description.lower()

        # Quick activity hints
        if any(word in description_lower for word in ["quick", "brief", "short"]):
            return min(15, default_durations.get(activity.activity_type, 30))

        # Long activity hints
        if any(word in description_lower for word in ["long", "extended", "all day"]):
            return default_durations.get(activity.activity_type, 60) * 2

        # Meal-specific inference
        if activity.activity_type == ActivityType.MEAL:
            if "breakfast" in description_lower:
                return 20
            elif "lunch" in description_lower:
                return 45
            elif "dinner" in description_lower:
                return 60
            elif "snack" in description_lower:
                return 10

        # Exercise-specific inference
        if activity.activity_type == ActivityType.EXERCISE:
            if any(word in description_lower for word in ["walk", "walking"]):
                return 30
            elif any(word in description_lower for word in ["run", "running"]):
                return 45
            elif "gym" in description_lower:
                return 90

        # Return default for activity type
        return default_durations.get(activity.activity_type)

    def _clean_location(self, location: str) -> str:
        """
        Clean and standardize location strings.

        Applies formatting rules and standardization to location data
        for consistency and better data quality.

        Args:
            location: Raw location string

        Returns:
            Cleaned location string
        """
        # Basic cleanup
        cleaned = location.strip().title()

        # Common location standardizations
        replacements = {
            "Hq": "HQ",
            "Usa": "USA",
            "Nyc": "NYC",
            "La": "LA",
            "Sf": "SF",
        }

        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)

        return cleaned

    def _enhance_description(self, activity: Activity) -> str:
        """
        Enhance activity descriptions for consistency and readability.

        Applies formatting and enhancement rules to make descriptions
        more consistent and informative.

        Args:
            activity: Activity to enhance

        Returns:
            Enhanced description string
        """
        description = activity.description.strip()

        # Capitalize first letter
        if description and not description[0].isupper():
            description = description[0].upper() + description[1:]

        # Add activity type context if very generic
        generic_phrases = ["activity", "session", "time", "work", "stuff"]
        if any(phrase == description.lower() for phrase in generic_phrases):
            description = (
                f"{activity.activity_type.value.title()} {description.lower()}"
            )

        return description

    def get_activities_for_user(
        self, phone_number: str, limit: int = 50, days: Optional[int] = None
    ) -> List[Activity]:
        """
        Get activities for a specific user (phone number).

        Retrieves activities for a user with optional date filtering
        and proper error handling.

        Args:
            phone_number: User's phone number
            limit: Maximum number of activities to return
            days: Optional number of days back to search

        Returns:
            List of Activity objects
        """
        try:
            start_date = None
            if days is not None:
                start_date = datetime.utcnow() - timedelta(days=days)

            return self.db_service.get_activities_by_phone(
                phone_number=phone_number, limit=limit, start_date=start_date
            )

        except Exception as e:
            print(f"Error getting activities for user {phone_number}: {e}")
            return []

    def get_user_statistics(self, phone_number: str, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a user.

        Calculates detailed statistics and insights for a specific user's
        activity patterns over the specified time period.

        Args:
            phone_number: User's phone number
            days: Number of days to include in statistics

        Returns:
            Dictionary containing user statistics and insights
        """
        try:
            # Get basic statistics from database service
            stats = self.db_service.get_activity_statistics(phone_number, days)

            # Add service-level insights and analysis
            stats["insights"] = self._generate_insights(stats)

            return stats

        except Exception as e:
            print(f"Error getting statistics for user {phone_number}: {e}")
            return {"total_activities": 0, "error": str(e)}

    def _generate_insights(self, stats: Dict[str, Any]) -> List[str]:
        """
        Generate insights from activity statistics.

        Analyzes activity patterns to provide meaningful insights and
        recommendations to users.

        Args:
            stats: Activity statistics dictionary

        Returns:
            List of insight strings
        """
        insights = []

        total_activities = stats.get("total_activities", 0)

        if total_activities == 0:
            insights.append("No activities recorded in the selected period.")
            return insights

        # Activity frequency insights
        days = stats.get("date_range", {}).get("days", 30)
        avg_activities_per_day = total_activities / days

        if avg_activities_per_day >= 3:
            insights.append(
                "You're very active! Recording 3+ activities per day on average."
            )
        elif avg_activities_per_day >= 1:
            insights.append("You're consistently tracking activities daily.")
        else:
            insights.append("Consider tracking more activities to get better insights.")

        # Activity type insights
        by_type = stats.get("by_type", {})
        if by_type:
            most_common_type = max(by_type, key=by_type.get)
            most_common_count = by_type[most_common_type]
            most_common_pct = (most_common_count / total_activities) * 100

            insights.append(
                f"Your most tracked activity type is {most_common_type} "
                f"({most_common_count} activities, {most_common_pct:.1f}%)"
            )

            # Balance insights
            if most_common_pct > 70:
                insights.append(
                    "Consider diversifying your tracked activities for better balance."
                )

        # Duration insights
        avg_duration = stats.get("average_duration_minutes", 0)
        if avg_duration > 0:
            hours = avg_duration // 60
            minutes = avg_duration % 60

            if hours > 0:
                insights.append(f"Average activity duration: {hours}h {minutes}m")
            else:
                insights.append(f"Average activity duration: {minutes} minutes")

            if avg_duration > 120:
                insights.append("You tend to engage in longer activities.")
            elif avg_duration < 30:
                insights.append("You prefer shorter, focused activities.")

        # Location insights
        unique_locations = stats.get("unique_locations", [])
        if len(unique_locations) > 5:
            insights.append(
                f"You're quite mobile! Active in {len(unique_locations)} different locations."
            )
        elif len(unique_locations) == 1:
            insights.append("You tend to do activities in the same location.")

        return insights

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a comprehensive health check of the service.

        Tests all service dependencies and functionality to ensure
        the service is operating correctly.

        Returns:
            Dictionary with health check results
        """
        health_status = {
            "status": "healthy",
            "services": {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            # Check database service
            db_health = self.db_service.health_check()
            health_status["services"]["database"] = db_health

            if db_health["status"] != "healthy":
                health_status["status"] = "degraded"

            # Check parser service (basic functionality test)
            try:
                test_sms = SMSMessage(
                    message_id="health-check",
                    phone_number="+1234567890",
                    message_body="WORK test activity",
                )
                test_activity = self.parser_service.parse_sms_to_activity(test_sms)

                health_status["services"]["parser"] = {
                    "status": "healthy" if test_activity else "degraded",
                    "test_result": (
                        "parsed successfully" if test_activity else "failed to parse"
                    ),
                }

                if not test_activity:
                    health_status["status"] = "degraded"

            except Exception as e:
                health_status["services"]["parser"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health_status["status"] = "degraded"

        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)

        return health_status
