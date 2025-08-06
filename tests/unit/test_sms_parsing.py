"""
Unit tests for SMS parsing service.

Tests the SMS parsing logic including activity type detection,
duration extraction, location parsing, and confidence scoring.
"""

import pytest
from datetime import datetime

from src.activitytracker.models.activity import ActivityType
from src.activitytracker.models.sms import SMSMessage
from src.activitytracker.services.sms_parsing_service import SMSParsingService


class TestSMSParsingService:
    """Test cases for the SMSParsingService."""
    
    @pytest.fixture
    def parser(self):
        """Fixture to provide a SMSParsingService instance."""
        return SMSParsingService()
    
    def test_parse_work_activity(self, parser):
        """Test parsing a work activity SMS."""
        sms = SMSMessage(
            message_id="msg-001",
            phone_number="+1234567890",
            message_body="WORK team meeting for 60 minutes in conference room A",
            keyword="WORK"
        )
        
        activity = parser.parse_sms_to_activity(sms)
        
        assert activity is not None
        assert activity.activity_type == ActivityType.WORK
        assert activity.duration_minutes == 60
        assert activity.location == "conference room A"
        assert "team meeting" in activity.description
        assert activity.phone_number == "+1234567890"
        assert activity.metadata["sms_message_id"] == "msg-001"
        assert activity.metadata["keyword"] == "WORK"
    
    def test_parse_exercise_activity(self, parser):
        """Test parsing an exercise activity SMS."""
        sms = SMSMessage(
            message_id="msg-002",
            phone_number="+1234567890",
            message_body="went for a 30 minute run in the park this morning"
        )
        
        activity = parser.parse_sms_to_activity(sms)
        
        assert activity is not None
        assert activity.activity_type == ActivityType.EXERCISE
        assert activity.duration_minutes == 30
        assert activity.location == "the park"
        assert "went for" in activity.description or "run" in activity.description
    
    def test_parse_meal_activity(self, parser):
        """Test parsing a meal activity SMS."""
        sms = SMSMessage(
            message_id="msg-003",
            phone_number="+1234567890",
            message_body="lunch with colleagues for 45 minutes at downtown restaurant"
        )
        
        activity = parser.parse_sms_to_activity(sms)
        
        assert activity is not None
        assert activity.activity_type == ActivityType.MEAL
        assert activity.duration_minutes == 45
        assert activity.location == "downtown restaurant"
        assert "colleagues" in activity.description
    
    def test_extract_activity_type_work(self, parser):
        """Test work activity type detection."""
        work_messages = [
            "WORK team meeting",
            "office work session", 
            "project development time",
            "coding session",
            "conference call"
        ]
        
        for message in work_messages:
            activity_type = parser._extract_activity_type(message)
            assert activity_type == ActivityType.WORK, f"'{message}' should be classified as WORK"
    
    def test_extract_activity_type_exercise(self, parser):
        """Test exercise activity type detection."""
        exercise_messages = [
            "morning workout at gym",
            "running in the park",
            "yoga session",
            "cycling to work",
            "swimming at pool"
        ]
        
        for message in exercise_messages:
            activity_type = parser._extract_activity_type(message)
            assert activity_type == ActivityType.EXERCISE, f"'{message}' should be classified as EXERCISE"
    
    def test_extract_activity_type_meal(self, parser):
        """Test meal activity type detection."""
        meal_messages = [
            "breakfast with family",
            "lunch meeting",
            "dinner at restaurant", 
            "cooking at home",
            "eating snack"
        ]
        
        for message in meal_messages:
            activity_type = parser._extract_activity_type(message)
            assert activity_type == ActivityType.MEAL, f"'{message}' should be classified as MEAL"
    
    def test_extract_activity_type_with_keyword(self, parser):
        """Test activity type detection with explicit keyword."""
        # Keyword should override content-based detection
        activity_type = parser._extract_activity_type("meeting with team", keyword="EXERCISE")
        assert activity_type == ActivityType.EXERCISE
        
        # Content-based should work when keyword is not recognized
        activity_type = parser._extract_activity_type("workout at gym", keyword="UNKNOWN")
        assert activity_type == ActivityType.EXERCISE
    
    def test_extract_activity_type_fallback(self, parser):
        """Test fallback to OTHER for unrecognized activities."""
        unclear_messages = [
            "random text message",
            "hello world",
            "some random activity"
        ]
        
        for message in unclear_messages:
            activity_type = parser._extract_activity_type(message)
            assert activity_type == ActivityType.OTHER, f"'{message}' should fallback to OTHER"
    
    def test_extract_duration_hours_minutes(self, parser):
        """Test extracting duration in hours and minutes format."""
        test_cases = [
            ("meeting for 2 hours and 30 minutes", 150),
            ("worked for 1 hour and 15 minutes", 75),
            ("session lasted 3 hours and 45 minutes", 225)
        ]
        
        for message, expected_minutes in test_cases:
            duration = parser._extract_duration(message)
            assert duration == expected_minutes, f"'{message}' should extract {expected_minutes} minutes"
    
    def test_extract_duration_minutes_only(self, parser):
        """Test extracting duration in minutes only format."""
        test_cases = [
            ("meeting for 45 minutes", 45),
            ("worked for 90 mins", 90),
            ("session lasted 120 minutes", 120),
            ("quick 15 minute call", 15)
        ]
        
        for message, expected_minutes in test_cases:
            duration = parser._extract_duration(message)
            assert duration == expected_minutes, f"'{message}' should extract {expected_minutes} minutes"
    
    def test_extract_duration_hours_only(self, parser):
        """Test extracting duration in hours only format."""
        test_cases = [
            ("meeting for 2 hours", 120),
            ("worked for 1 hour", 60),
            ("session lasted 3 hrs", 180)
        ]
        
        for message, expected_minutes in test_cases:
            duration = parser._extract_duration(message)
            assert duration == expected_minutes, f"'{message}' should extract {expected_minutes} minutes"
    
    def test_extract_duration_generic_for_pattern(self, parser):
        """Test extracting duration with generic 'for X' pattern."""
        test_cases = [
            ("meeting for 45", 45),  # Assume minutes for values > 10
            ("session for 2", 120),  # Assume hours for values <= 10
            ("worked for 90", 90)    # Assume minutes for values > 10
        ]
        
        for message, expected_minutes in test_cases:
            duration = parser._extract_duration(message)
            assert duration == expected_minutes, f"'{message}' should extract {expected_minutes} minutes"
    
    def test_extract_duration_no_match(self, parser):
        """Test duration extraction with no time information."""
        no_time_messages = [
            "team meeting",
            "worked on project", 
            "had lunch",
            "random message"
        ]
        
        for message in no_time_messages:
            duration = parser._extract_duration(message)
            assert duration is None, f"'{message}' should not extract any duration"
    
    def test_extract_location_at_pattern(self, parser):
        """Test location extraction with 'at' pattern."""
        test_cases = [
            ("meeting at conference room B", "conference room B"),
            ("workout at the gym", "the gym"),
            ("lunch at downtown restaurant", "downtown restaurant")
        ]
        
        for message, expected_location in test_cases:
            location = parser._extract_location(message)
            assert location == expected_location, f"'{message}' should extract location '{expected_location}'"
    
    def test_extract_location_in_pattern(self, parser):
        """Test location extraction with 'in' pattern."""
        test_cases = [
            ("meeting in conference room A", "conference room A"),
            ("running in central park", "central park"),
            ("studying in the library", "the library")
        ]
        
        for message, expected_location in test_cases:
            location = parser._extract_location(message)
            assert location == expected_location, f"'{message}' should extract location '{expected_location}'"
    
    def test_extract_location_no_match(self, parser):
        """Test location extraction with no location information."""
        no_location_messages = [
            "team meeting",
            "worked for 2 hours",
            "had breakfast",
            "exercise session"
        ]
        
        for message in no_location_messages:
            location = parser._extract_location(message)
            assert location is None, f"'{message}' should not extract any location"
    
    def test_create_description_cleanup(self, parser):
        """Test description creation and cleanup."""
        test_cases = [
            # Remove duration and location patterns
            ("WORK meeting for 60 minutes at office", "meeting", ActivityType.WORK, 60, "office"),
            # Remove activity type keywords
            ("exercise session for 30 minutes", "session", ActivityType.EXERCISE, 30, None),
            # Handle empty description
            ("WORK for 30 minutes", "Work activity", ActivityType.WORK, 30, None)
        ]
        
        for message, expected_desc, activity_type, duration, location in test_cases:
            description = parser._create_description(message, activity_type, duration, location)
            assert expected_desc.lower() in description.lower(), \
                f"'{message}' should create description containing '{expected_desc}'"
    
    def test_calculate_confidence(self, parser):
        """Test confidence score calculation."""
        # High confidence: clear keywords, duration, location
        high_conf_message = "WORK team meeting for 60 minutes in conference room"
        confidence = parser._calculate_confidence(high_conf_message, ActivityType.WORK)
        assert confidence > 0.7, "Clear activity should have high confidence"
        
        # Low confidence: vague message
        low_conf_message = "stuff"
        confidence = parser._calculate_confidence(low_conf_message, ActivityType.OTHER)
        assert confidence < 0.5, "Vague activity should have low confidence"
        
        # Medium confidence: some clear elements
        med_conf_message = "meeting for 30 minutes"
        confidence = parser._calculate_confidence(med_conf_message, ActivityType.WORK)
        assert 0.4 < confidence < 0.8, "Partially clear activity should have medium confidence"
    
    def test_get_parsing_suggestions(self, parser):
        """Test parsing suggestions generation."""
        # Message without activity keyword
        suggestions = parser.get_parsing_suggestions("had a session for 30 minutes")
        assert any("activity keyword" in s for s in suggestions)
        
        # Message without duration
        suggestions = parser.get_parsing_suggestions("WORK team meeting")
        assert any("duration" in s for s in suggestions)
        
        # Message without location
        suggestions = parser.get_parsing_suggestions("WORK meeting for 60 minutes")
        assert any("location" in s for s in suggestions)
        
        # Short message
        suggestions = parser.get_parsing_suggestions("WORK")
        assert any("details" in s for s in suggestions)
        
        # Complete message should have no suggestions
        suggestions = parser.get_parsing_suggestions("WORK team meeting for 60 minutes at conference room")
        assert len(suggestions) == 0, "Complete message should not need suggestions"
    
    def test_parse_sms_invalid_input(self, parser):
        """Test parsing with invalid SMS input."""
        # Empty message body
        empty_sms = SMSMessage(
            message_id="msg-empty",
            phone_number="+1234567890",
            message_body=""
        )
        activity = parser.parse_sms_to_activity(empty_sms)
        assert activity is None
        
        # Message that doesn't look like activity
        non_activity_sms = SMSMessage(
            message_id="msg-random",
            phone_number="+1234567890",
            message_body="hello how are you"
        )
        # This should still parse but might not be recognized as activity
        activity = parser.parse_sms_to_activity(non_activity_sms)
        # Could be None or OTHER type depending on implementation
    
    def test_parse_sms_complex_scenarios(self, parser):
        """Test parsing complex real-world scenarios."""
        complex_scenarios = [
            {
                "message": "Had a great workout at the gym this morning for about 90 minutes, did cardio and weights",
                "expected_type": ActivityType.EXERCISE,
                "expected_duration": 90,
                "expected_location": "the gym"
            },
            {
                "message": "MEAL dinner with family at home lasted 1 hour and 15 minutes",
                "expected_type": ActivityType.MEAL,
                "expected_duration": 75,
                "expected_location": "home"
            },
            {
                "message": "studying for certification exam for 2 hours in library",
                "expected_type": ActivityType.STUDY,
                "expected_duration": 120,
                "expected_location": "library"
            }
        ]
        
        for scenario in complex_scenarios:
            sms = SMSMessage(
                message_id="msg-complex",
                phone_number="+1234567890",
                message_body=scenario["message"]
            )
            
            activity = parser.parse_sms_to_activity(sms)
            
            assert activity is not None, f"Failed to parse: {scenario['message']}"
            assert activity.activity_type == scenario["expected_type"]
            
            if scenario.get("expected_duration"):
                assert activity.duration_minutes == scenario["expected_duration"]
            
            if scenario.get("expected_location"):
                assert activity.location == scenario["expected_location"]