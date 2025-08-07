"""
SMS Processor Lambda function for the ActivityTracker application.

This Lambda function is triggered by AWS Pinpoint when SMS messages are received.
It processes incoming SMS messages, extracts activity information, and stores
the data in DynamoDB. The function also handles error cases and provides
feedback through SMS responses when configured.

Functions:
    lambda_handler: Main entry point for the Lambda function
    _handle_processing_error: Handles processing errors and logging
    _log_processing_metrics: Logs metrics for monitoring
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from ..models.sms import SMSMessage
from ..services.activity_service import ActivityService


def lambda_handler(
    event: Dict[str, Any], context: Any  # noqa: ARG001
) -> Dict[str, Any]:
    """
    Main Lambda handler for processing SMS messages from AWS Pinpoint.

    This function is triggered when AWS Pinpoint receives an inbound SMS message.
    It extracts the SMS data from the Pinpoint event, processes it to create
    an activity record, and stores the result in DynamoDB.

    Args:
        event: AWS Lambda event containing Pinpoint SMS data
        context: AWS Lambda runtime context (unused but required)

    Returns:
        Dictionary containing processing results and status information

    Event Structure:
        The event contains Pinpoint SMS event data in the following format:
        {
            "Records": [{
                "pinpoint": {
                    "sms": {
                        "messageId": "string",
                        "originationNumber": "+1234567890",
                        "destinationNumber": "+0987654321",
                        "messageBody": "WORK team meeting for 60 minutes",
                        "timestamp": "2024-01-15T14:30:00Z",
                        "keyword": "WORK",
                        "messageType": "TRANSACTIONAL"
                    }
                }
            }]
        }

    Returns:
        {
            "statusCode": 200|400|500,
            "success": true|false,
            "message": "Processing result message",
            "activityId": "activity_id_if_created",
            "processingTime": "processing_time_in_ms",
            "metadata": {
                "messageId": "original_message_id",
                "phoneNumber": "sender_phone_number",
                "confidence": 0.85
            }
        }

    Example:
        >>> event = {"Records": [{"pinpoint": {"sms": {...}}}]}
        >>> result = lambda_handler(event, None)
        >>> print(result["success"])
        True
    """
    # Initialize response structure
    response = {
        "statusCode": 500,
        "success": False,
        "message": "Internal processing error",
        "activityId": None,
        "processingTime": None,
        "metadata": {},
    }

    start_time = datetime.utcnow()

    try:
        # Log incoming event for debugging (mask sensitive data)
        print(f"DEBUG: Raw event received: {json.dumps(event, default=str)[:1000]}")
        _log_event_received(event)

        # Handle both SNS and direct Pinpoint events
        print("DEBUG: Extracting Pinpoint event from SNS wrapper...")
        pinpoint_event = _extract_pinpoint_event(event)
        print(
            f"DEBUG: Extracted Pinpoint event: {json.dumps(pinpoint_event, default=str)[:1000]}"
        )

        # Validate event structure
        print("DEBUG: Validating event structure...")
        if not _validate_event_structure(pinpoint_event):
            print("ERROR: Event structure validation failed")
            return _create_error_response(
                400, "Invalid event structure - expected Pinpoint SMS event", start_time
            )
        print("DEBUG: Event structure validation passed")

        # Extract SMS message from Pinpoint event
        try:
            print("DEBUG: Extracting SMS message from Pinpoint event...")
            sms_message = SMSMessage.from_pinpoint_event(pinpoint_event)
            print(
                f"DEBUG: SMS message extracted successfully: {sms_message.message_body[:100]}"
            )
            response["metadata"].update(
                {
                    "messageId": sms_message.message_id,
                    "phoneNumber": sms_message.phone_number,
                    "messageLength": len(sms_message.message_body),
                }
            )

        except ValueError as e:
            print(f"ERROR: Failed to extract SMS data: {e}")
            _log_processing_error("SMS_EXTRACTION_ERROR", str(e), event)
            return _create_error_response(
                400, f"Failed to extract SMS data: {str(e)}", start_time
            )

        # Initialize activity service
        try:
            print("DEBUG: Initializing ActivityService...")
            activity_service = ActivityService()
            print("DEBUG: ActivityService initialized successfully")
        except Exception as e:
            print(f"ERROR: Service initialization failed: {e}")
            _log_processing_error("SERVICE_INITIALIZATION_ERROR", str(e), event)
            return _create_error_response(
                500, "Service initialization failed", start_time
            )

        # Process the SMS message
        print("DEBUG: Processing SMS message...")
        try:
            processing_result = activity_service.process_sms_message(sms_message)
            print(
                f"DEBUG: Processing result: {processing_result.get('success', False)}"
            )
        except Exception as e:
            print(f"ERROR: SMS processing failed: {e}")
            _log_processing_error("SMS_PROCESSING_ERROR", str(e), event)
            return _create_error_response(
                500, f"SMS processing failed: {str(e)}", start_time
            )

        # Handle processing results
        if processing_result["success"]:
            activity = processing_result["activity"]

            response.update(
                {
                    "statusCode": 200,
                    "success": True,
                    "message": "Activity created successfully",
                    "activityId": activity.id,
                    "metadata": {
                        **response["metadata"],
                        "activityType": (
                            activity.activity_type.value
                            if hasattr(activity.activity_type, "value")
                            else activity.activity_type
                        ),
                        "confidence": processing_result.get("confidence", 0.0),
                        "duration": activity.duration_minutes,
                        "location": activity.location,
                    },
                }
            )

            # Log successful processing metrics
            _log_processing_metrics("SUCCESS", activity, sms_message, start_time)

        else:
            # Processing failed but SMS was valid
            error_message = processing_result.get("error", "Unknown processing error")
            suggestions = processing_result.get("suggestions", [])

            response.update(
                {
                    "statusCode": 422,  # Unprocessable Entity
                    "success": False,
                    "message": f"Could not process activity: {error_message}",
                    "suggestions": suggestions,
                    "metadata": {
                        **response["metadata"],
                        "parseError": error_message,
                        "confidence": processing_result.get("confidence", 0.0),
                    },
                }
            )

            # Log processing failure
            _log_processing_metrics(
                "PROCESSING_FAILED", None, sms_message, start_time, error_message
            )

    except Exception as e:
        # Unexpected error during processing
        print(f"CRITICAL ERROR: Unexpected error during processing: {e}")
        print(f"CRITICAL ERROR: Exception type: {type(e).__name__}")
        import traceback

        print(f"CRITICAL ERROR: Full traceback: {traceback.format_exc()}")
        _log_processing_error("UNEXPECTED_ERROR", str(e), event, exc_info=True)
        response = _create_error_response(
            500, "Unexpected processing error occurred", start_time
        )

    finally:
        # Calculate and add processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        response["processingTime"] = round(processing_time, 2)

        # Log final response (without sensitive data)
        print(
            f"SMS Processing completed: {response['statusCode']} - {response['message']}"
        )

    return response


def _validate_event_structure(event: Dict[str, Any]) -> bool:
    """
    Validate that the event has the expected Pinpoint SMS structure.

    Checks for the presence of required fields in the Pinpoint event
    to ensure it can be processed correctly.

    Args:
        event: Lambda event to validate

    Returns:
        True if event structure is valid, False otherwise
    """
    try:
        print(f"DEBUG: _validate_event_structure - Event keys: {list(event.keys())}")

        # Check for direct SMS data (from SNS message body)
        if "originationNumber" in event and "messageBody" in event:
            print("DEBUG: Found direct SMS data format")
            required_fields = ["originationNumber", "messageBody"]
            is_valid = all(field in event for field in required_fields)
            print(f"DEBUG: Direct SMS validation result: {is_valid}")
            return is_valid

        # Check for basic Pinpoint SMS event structure (legacy format)
        records = event.get("Records", [])
        if records and len(records) > 0:
            print("DEBUG: Found Records format, checking for pinpoint structure")
            first_record = records[0]
            pinpoint_data = first_record.get("pinpoint", {})
            sms_data = pinpoint_data.get("sms", {})

            # Check for required SMS fields
            required_fields = ["messageId", "originationNumber", "messageBody"]
            is_valid = all(field in sms_data for field in required_fields)
            print(f"DEBUG: Legacy Pinpoint validation result: {is_valid}")
            return is_valid

        print("DEBUG: No valid structure found")
        return False

    except (KeyError, TypeError, AttributeError) as e:
        print(f"DEBUG: Exception in validation: {e}")
        return False


def _create_error_response(
    status_code: int, message: str, start_time: datetime
) -> Dict[str, Any]:
    """
    Create a standardized error response.

    Generates a consistent error response structure for various error conditions
    encountered during SMS processing.

    Args:
        status_code: HTTP status code for the error
        message: Human-readable error message
        start_time: Processing start time for duration calculation

    Returns:
        Standardized error response dictionary
    """
    processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

    return {
        "statusCode": status_code,
        "success": False,
        "message": message,
        "activityId": None,
        "processingTime": round(processing_time, 2),
        "metadata": {"error": True, "timestamp": datetime.utcnow().isoformat()},
    }


def _log_event_received(event: Dict[str, Any]) -> None:
    """
    Log the receipt of an SMS processing event.

    Logs event information for debugging while masking sensitive data
    like phone numbers and message content.

    Args:
        event: Lambda event to log
    """
    try:
        # Extract basic event info without sensitive data
        records_count = len(event.get("Records", []))

        log_data = {
            "event": "SMS_EVENT_RECEIVED",
            "recordsCount": records_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add basic SMS info if available
        if records_count > 0:
            first_record = event["Records"][0]
            sms_data = first_record.get("pinpoint", {}).get("sms", {})

            if "messageId" in sms_data:
                log_data["messageId"] = sms_data["messageId"]

            if "originationNumber" in sms_data:
                # Mask phone number for privacy
                phone = sms_data["originationNumber"]
                masked_phone = (
                    f"{phone[:2]}***{phone[-2:]}" if len(phone) > 4 else "***"
                )
                log_data["originationNumber"] = masked_phone

            if "messageBody" in sms_data:
                log_data["messageLength"] = len(sms_data["messageBody"])

        print(json.dumps(log_data))

    except Exception as e:
        print(f"Error logging event received: {e}")


def _extract_pinpoint_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract Pinpoint event from either direct Pinpoint event or SNS wrapper.

    Handles both:
    1. Direct Pinpoint events (original format)
    2. SNS events containing Pinpoint data in message body

    Args:
        event: Lambda event (either Pinpoint or SNS format)

    Returns:
        Pinpoint event in the expected format
    """
    try:
        print(f"DEBUG: _extract_pinpoint_event - Event keys: {list(event.keys())}")

        # Check if this is an SNS event
        if "Records" in event and len(event["Records"]) > 0:
            first_record = event["Records"][0]
            print(f"DEBUG: First record keys: {list(first_record.keys())}")

            # SNS event structure
            if "Sns" in first_record and "Message" in first_record["Sns"]:
                print("DEBUG: Detected SNS event structure")
                import json

                sns_message_body = first_record["Sns"]["Message"]
                print(
                    f"DEBUG: SNS message body (first 500 chars): {sns_message_body[:500]}"
                )

                # Parse the SNS message body which contains the Pinpoint event
                sns_message = json.loads(sns_message_body)
                print(f"DEBUG: Parsed SNS message keys: {list(sns_message.keys())}")
                return sns_message

            # Direct Pinpoint event structure
            elif "pinpoint" in first_record:
                print("DEBUG: Detected direct Pinpoint event structure")
                return event
            else:
                print(
                    f"DEBUG: Unknown record structure, keys: {list(first_record.keys())}"
                )

        # Return as-is if unrecognized format (will fail validation)
        print("DEBUG: Returning event as-is (unrecognized format)")
        return event

    except Exception as e:
        print(f"ERROR: Exception in _extract_pinpoint_event: {e}")
        import traceback

        print(f"ERROR: Traceback: {traceback.format_exc()}")
        return event


def _log_processing_error(
    error_type: str, error_message: str, event: Dict[str, Any], exc_info: bool = False
) -> None:
    """
    Log processing errors with context information.

    Creates structured error logs for debugging and monitoring purposes
    while protecting sensitive information.

    Args:
        error_type: Type/category of the error
        error_message: Detailed error message
        event: Original Lambda event for context
        exc_info: Whether to include exception traceback
    """
    try:
        log_data = {
            "event": "SMS_PROCESSING_ERROR",
            "errorType": error_type,
            "errorMessage": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add context from event if available
        try:
            records = event.get("Records", [])
            if records:
                sms_data = records[0].get("pinpoint", {}).get("sms", {})
                if "messageId" in sms_data:
                    log_data["messageId"] = sms_data["messageId"]
        except Exception:  # noqa: S110  # nosec B110
            pass

        print(json.dumps(log_data))

        # Print exception details if requested
        if exc_info:
            import traceback

            print(f"Exception details: {traceback.format_exc()}")

    except Exception as e:
        print(f"Error logging processing error: {e}")


def _log_processing_metrics(
    status: str,
    activity: Optional[Any],
    sms_message: SMSMessage,
    start_time: datetime,
    error_message: Optional[str] = None,
) -> None:
    """
    Log processing metrics for monitoring and analytics.

    Creates structured logs with processing metrics that can be used
    for monitoring, alerting, and analytics dashboards.

    Args:
        status: Processing status (SUCCESS, PROCESSING_FAILED, etc.)
        activity: Created activity object (if successful)
        sms_message: Original SMS message
        start_time: Processing start time
        error_message: Error message if processing failed
    """
    try:
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        metrics = {
            "event": "SMS_PROCESSING_METRICS",
            "status": status,
            "processingTimeMs": round(processing_time, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "messageLength": len(sms_message.message_body),
            "hasKeyword": sms_message.keyword is not None,
        }

        # Add success-specific metrics
        if status == "SUCCESS" and activity:
            metrics.update(
                {
                    "activityType": (
                        activity.activity_type.value
                        if hasattr(activity.activity_type, "value")
                        else activity.activity_type
                    ),
                    "hasDuration": activity.duration_minutes is not None,
                    "hasLocation": activity.location is not None,
                    "confidence": activity.metadata.get("parsing_confidence", 0.0),
                }
            )

        # Add error information if applicable
        if error_message:
            metrics["errorMessage"] = error_message

        print(json.dumps(metrics))

    except Exception as e:
        print(f"Error logging processing metrics: {e}")


# Environment variable configurations
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
ACTIVITIES_TABLE = os.getenv("ACTIVITIES_TABLE")

# Initialize service health check on cold start
try:
    _health_check_service = ActivityService()
    print(f"SMS Processor Lambda initialized successfully - Environment: {ENVIRONMENT}")
except Exception as e:
    print(f"Warning: Service initialization failed during cold start: {e}")
    _health_check_service = None
