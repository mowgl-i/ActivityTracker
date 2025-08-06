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
from typing import Dict, Any, Optional
from datetime import datetime

from ..models.sms import SMSMessage
from ..services.activity_service import ActivityService


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
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
        "metadata": {}
    }
    
    start_time = datetime.utcnow()
    
    try:
        # Log incoming event for debugging (mask sensitive data)
        _log_event_received(event)
        
        # Validate event structure
        if not _validate_event_structure(event):
            return _create_error_response(
                400, 
                "Invalid event structure - expected Pinpoint SMS event",
                start_time
            )
        
        # Extract SMS message from Pinpoint event
        try:
            sms_message = SMSMessage.from_pinpoint_event(event)
            response["metadata"].update({
                "messageId": sms_message.message_id,
                "phoneNumber": sms_message.phone_number,
                "messageLength": len(sms_message.message_body)
            })
            
        except ValueError as e:
            _log_processing_error("SMS_EXTRACTION_ERROR", str(e), event)
            return _create_error_response(
                400,
                f"Failed to extract SMS data: {str(e)}",
                start_time
            )
        
        # Initialize activity service
        try:
            activity_service = ActivityService()
        except Exception as e:
            _log_processing_error("SERVICE_INITIALIZATION_ERROR", str(e), event)
            return _create_error_response(
                500,
                "Service initialization failed",
                start_time
            )
        
        # Process the SMS message
        processing_result = activity_service.process_sms_message(sms_message)
        
        # Handle processing results
        if processing_result["success"]:
            activity = processing_result["activity"]
            
            response.update({
                "statusCode": 200,
                "success": True,
                "message": "Activity created successfully",
                "activityId": activity.id,
                "metadata": {
                    **response["metadata"],
                    "activityType": activity.activity_type.value,
                    "confidence": processing_result.get("confidence", 0.0),
                    "duration": activity.duration_minutes,
                    "location": activity.location
                }
            })
            
            # Log successful processing metrics
            _log_processing_metrics("SUCCESS", activity, sms_message, start_time)
            
        else:
            # Processing failed but SMS was valid
            error_message = processing_result.get("error", "Unknown processing error")
            suggestions = processing_result.get("suggestions", [])
            
            response.update({
                "statusCode": 422,  # Unprocessable Entity
                "success": False,
                "message": f"Could not process activity: {error_message}",
                "suggestions": suggestions,
                "metadata": {
                    **response["metadata"],
                    "parseError": error_message,
                    "confidence": processing_result.get("confidence", 0.0)
                }
            })
            
            # Log processing failure
            _log_processing_metrics("PROCESSING_FAILED", None, sms_message, start_time, error_message)
    
    except Exception as e:
        # Unexpected error during processing
        _log_processing_error("UNEXPECTED_ERROR", str(e), event, exc_info=True)
        response = _create_error_response(
            500,
            "Unexpected processing error occurred",
            start_time
        )
    
    finally:
        # Calculate and add processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        response["processingTime"] = round(processing_time, 2)
        
        # Log final response (without sensitive data)
        print(f"SMS Processing completed: {response['statusCode']} - {response['message']}")
    
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
        # Check for basic Pinpoint SMS event structure
        records = event.get("Records", [])
        if not records or len(records) == 0:
            return False
        
        first_record = records[0]
        pinpoint_data = first_record.get("pinpoint", {})
        sms_data = pinpoint_data.get("sms", {})
        
        # Check for required SMS fields
        required_fields = ["messageId", "originationNumber", "messageBody"]
        for field in required_fields:
            if field not in sms_data:
                return False
        
        return True
        
    except (KeyError, TypeError, AttributeError):
        return False


def _create_error_response(status_code: int, message: str, start_time: datetime) -> Dict[str, Any]:
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
        "metadata": {
            "error": True,
            "timestamp": datetime.utcnow().isoformat()
        }
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
            "timestamp": datetime.utcnow().isoformat()
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
                masked_phone = f"{phone[:2]}***{phone[-2:]}" if len(phone) > 4 else "***"
                log_data["originationNumber"] = masked_phone
            
            if "messageBody" in sms_data:
                log_data["messageLength"] = len(sms_data["messageBody"])
        
        print(json.dumps(log_data))
        
    except Exception as e:
        print(f"Error logging event received: {e}")


def _log_processing_error(error_type: str, error_message: str, event: Dict[str, Any], 
                         exc_info: bool = False) -> None:
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
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add context from event if available
        try:
            records = event.get("Records", [])
            if records:
                sms_data = records[0].get("pinpoint", {}).get("sms", {})
                if "messageId" in sms_data:
                    log_data["messageId"] = sms_data["messageId"]
        except:
            pass
        
        print(json.dumps(log_data))
        
        # Print exception details if requested
        if exc_info:
            import traceback
            print(f"Exception details: {traceback.format_exc()}")
            
    except Exception as e:
        print(f"Error logging processing error: {e}")


def _log_processing_metrics(status: str, activity: Optional[Any], sms_message: SMSMessage, 
                           start_time: datetime, error_message: Optional[str] = None) -> None:
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
            "hasKeyword": sms_message.keyword is not None
        }
        
        # Add success-specific metrics
        if status == "SUCCESS" and activity:
            metrics.update({
                "activityType": activity.activity_type.value,
                "hasDuration": activity.duration_minutes is not None,
                "hasLocation": activity.location is not None,
                "confidence": activity.metadata.get("parsing_confidence", 0.0)
            })
        
        # Add error information if applicable
        if error_message:
            metrics["errorMessage"] = error_message
        
        print(json.dumps(metrics))
        
    except Exception as e:
        print(f"Error logging processing metrics: {e}")


# Environment variable configurations
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')
ACTIVITIES_TABLE = os.getenv('ACTIVITIES_TABLE')

# Initialize service health check on cold start
try:
    _health_check_service = ActivityService()
    print(f"SMS Processor Lambda initialized successfully - Environment: {ENVIRONMENT}")
except Exception as e:
    print(f"Warning: Service initialization failed during cold start: {e}")
    _health_check_service = None