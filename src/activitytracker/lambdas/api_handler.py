"""
API Gateway Lambda handler for the ActivityTracker application.

This Lambda function provides REST API endpoints for the ActivityTracker
dashboard and external integrations. It handles HTTP requests for activity
management, statistics, and health checks with proper CORS support.

Functions:
    lambda_handler: Main entry point for API Gateway events
    _handle_get_activities: Handle GET /activities endpoint
    _handle_get_activity: Handle GET /activities/{id} endpoint  
    _handle_create_activity: Handle POST /activities endpoint
    _handle_get_stats: Handle GET /stats endpoint
    _handle_health_check: Handle GET /health endpoint
    _create_response: Create standardized HTTP responses
    _handle_cors_preflight: Handle OPTIONS requests for CORS
"""

import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from urllib.parse import unquote_plus

from ..services.activity_service import ActivityService
from ..models.activity import Activity, ActivityType
from ..models.sms import SMSMessage


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for API Gateway events.
    
    Routes incoming HTTP requests to the appropriate handler functions
    based on the HTTP method and resource path. Provides comprehensive
    error handling and CORS support for web dashboard integration.
    
    Args:
        event: API Gateway event containing HTTP request data
        context: AWS Lambda runtime context
        
    Returns:
        HTTP response dictionary with statusCode, headers, and body
        
    Event Structure:
        {
            "httpMethod": "GET|POST|OPTIONS",
            "resource": "/activities|/activities/{id}|/stats|/health",
            "pathParameters": {"id": "activity_id"},
            "queryStringParameters": {"limit": "10", "days": "30"},
            "headers": {"Content-Type": "application/json"},
            "body": "{\"key\": \"value\"}"
        }
        
    Response Structure:
        {
            "statusCode": 200|400|404|500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization"
            },
            "body": "{\"data\": {...}}"
        }
    """
    try:
        # Log incoming request (without sensitive data)
        _log_api_request(event)
        
        # Extract request information
        http_method = event.get('httpMethod', '').upper()
        resource = event.get('resource', '')
        path_params = event.get('pathParameters') or {}
        query_params = event.get('queryStringParameters') or {}
        
        # Handle CORS preflight requests
        if http_method == 'OPTIONS':
            return _handle_cors_preflight()
        
        # Initialize activity service
        try:
            activity_service = ActivityService()
        except Exception as e:
            return _create_error_response(500, "Service initialization failed", str(e))
        
        # Route to appropriate handler based on resource and method
        if resource == '/health' and http_method == 'GET':
            return _handle_health_check(activity_service)
            
        elif resource == '/activities' and http_method == 'GET':
            return _handle_get_activities(activity_service, query_params)
            
        elif resource == '/activities/{id}' and http_method == 'GET':
            activity_id = path_params.get('id')
            return _handle_get_activity(activity_service, activity_id)
            
        elif resource == '/activities' and http_method == 'POST':
            body = event.get('body', '{}')
            return _handle_create_activity(activity_service, body)
            
        elif resource == '/stats' and http_method == 'GET':
            return _handle_get_stats(activity_service, query_params)
            
        else:
            return _create_error_response(
                404, 
                "Not Found", 
                f"Resource {resource} with method {http_method} not found"
            )
    
    except Exception as e:
        _log_api_error("UNEXPECTED_ERROR", str(e), event)
        return _create_error_response(500, "Internal Server Error", "Unexpected error occurred")


def _handle_health_check(activity_service: ActivityService) -> Dict[str, Any]:
    """
    Handle GET /health endpoint for service health monitoring.
    
    Performs comprehensive health checks on all service dependencies
    and returns detailed status information for monitoring systems.
    
    Args:
        activity_service: Activity service instance
        
    Returns:
        HTTP response with health check results
        
    Response Body:
        {
            "status": "healthy|degraded|unhealthy",
            "timestamp": "2024-01-15T14:30:00Z",
            "services": {
                "database": {"status": "healthy", ...},
                "parser": {"status": "healthy", ...}
            },
            "environment": "dev|staging|prod"
        }
    """
    try:
        health_result = activity_service.health_check()
        
        response_data = {
            **health_result,
            "environment": os.getenv('ENVIRONMENT', 'unknown'),
            "version": "1.0.0"
        }
        
        # Determine HTTP status code based on health status
        if health_result['status'] == 'healthy':
            status_code = 200
        elif health_result['status'] == 'degraded':
            status_code = 200  # Still operational but with issues
        else:
            status_code = 503  # Service unavailable
        
        return _create_response(status_code, response_data)
        
    except Exception as e:
        _log_api_error("HEALTH_CHECK_ERROR", str(e))
        return _create_error_response(503, "Health Check Failed", str(e))


def _handle_get_activities(activity_service: ActivityService, query_params: Dict[str, str]) -> Dict[str, Any]:
    """
    Handle GET /activities endpoint for retrieving activity lists.
    
    Supports filtering by phone number, date range, and pagination
    for efficient activity retrieval and dashboard display.
    
    Args:
        activity_service: Activity service instance
        query_params: Query string parameters from request
        
    Returns:
        HTTP response with activities list
        
    Query Parameters:
        - phone: Filter by phone number
        - limit: Maximum number of activities (default: 50)
        - days: Number of days back to search (optional)
        - type: Filter by activity type (optional)
        
    Response Body:
        {
            "activities": [
                {
                    "id": "act_2024_01_15_14_30_00_abc123",
                    "activity_type": "work",
                    "description": "Team meeting",
                    "duration_minutes": 60,
                    "location": "Conference Room A",
                    "phone_number": "+1234567890",
                    "timestamp": "2024-01-15T14:30:00Z"
                }
            ],
            "total_count": 42,
            "filters": {
                "phone": "+1234567890",
                "days": 30,
                "limit": 50
            }
        }
    """
    try:
        # Parse query parameters with defaults
        phone_number = query_params.get('phone')
        limit = min(int(query_params.get('limit', '50')), 100)  # Cap at 100
        days = int(query_params.get('days')) if query_params.get('days') else None
        activity_type_filter = query_params.get('type')
        
        # Validate phone number if provided
        if phone_number:
            phone_number = unquote_plus(phone_number)  # URL decode
        
        # Get activities based on filters
        if phone_number:
            activities = activity_service.get_activities_for_user(
                phone_number=phone_number,
                limit=limit,
                days=days
            )
        else:
            # Get recent activities across all users
            activities = activity_service.db_service.get_recent_activities(limit)
        
        # Filter by activity type if specified
        if activity_type_filter:
            try:
                filter_type = ActivityType(activity_type_filter.lower())
                activities = [a for a in activities if a.activity_type == filter_type]
            except ValueError:
                return _create_error_response(
                    400, 
                    "Invalid Activity Type", 
                    f"Activity type '{activity_type_filter}' is not valid"
                )
        
        # Convert activities to JSON-serializable format
        activities_data = []
        for activity in activities:
            activity_dict = activity.dict()
            activity_dict['timestamp'] = activity.timestamp.isoformat()
            activity_dict['activity_type'] = activity.activity_type.value
            activities_data.append(activity_dict)
        
        response_data = {
            "activities": activities_data,
            "total_count": len(activities_data),
            "filters": {
                "phone": phone_number,
                "limit": limit,
                "days": days,
                "type": activity_type_filter
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return _create_response(200, response_data)
        
    except ValueError as e:
        return _create_error_response(400, "Invalid Parameters", str(e))
    except Exception as e:
        _log_api_error("GET_ACTIVITIES_ERROR", str(e), {"query_params": query_params})
        return _create_error_response(500, "Failed to retrieve activities", str(e))


def _handle_get_activity(activity_service: ActivityService, activity_id: Optional[str]) -> Dict[str, Any]:
    """
    Handle GET /activities/{id} endpoint for retrieving a specific activity.
    
    Fetches a single activity by its unique ID and returns detailed information
    including metadata and processing information.
    
    Args:
        activity_service: Activity service instance
        activity_id: Unique activity identifier from path parameters
        
    Returns:
        HTTP response with activity details or 404 if not found
    """
    try:
        if not activity_id:
            return _create_error_response(400, "Missing Activity ID", "Activity ID is required")
        
        # URL decode the activity ID
        activity_id = unquote_plus(activity_id)
        
        # Retrieve activity from service
        activity = activity_service.db_service.get_activity(activity_id)
        
        if not activity:
            return _create_error_response(404, "Activity Not Found", f"Activity with ID '{activity_id}' not found")
        
        # Convert to JSON-serializable format
        activity_dict = activity.dict()
        activity_dict['timestamp'] = activity.timestamp.isoformat()
        activity_dict['activity_type'] = activity.activity_type.value
        
        response_data = {
            "activity": activity_dict,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return _create_response(200, response_data)
        
    except Exception as e:
        _log_api_error("GET_ACTIVITY_ERROR", str(e), {"activity_id": activity_id})
        return _create_error_response(500, "Failed to retrieve activity", str(e))


def _handle_create_activity(activity_service: ActivityService, body: str) -> Dict[str, Any]:
    """
    Handle POST /activities endpoint for manually creating activities.
    
    Allows manual creation of activities through the API, useful for
    dashboard interfaces and external integrations.
    
    Args:
        activity_service: Activity service instance
        body: JSON request body string
        
    Returns:
        HTTP response with created activity or validation errors
        
    Request Body:
        {
            "activity_type": "work",
            "description": "Team meeting",
            "duration_minutes": 60,
            "location": "Conference Room A",
            "phone_number": "+1234567890"
        }
    """
    try:
        # Parse request body
        if not body or body.strip() == '':
            return _create_error_response(400, "Missing Request Body", "Request body is required")
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            return _create_error_response(400, "Invalid JSON", f"Request body is not valid JSON: {str(e)}")
        
        # Validate required fields
        required_fields = ['activity_type', 'description', 'phone_number']
        for field in required_fields:
            if field not in data or not data[field]:
                return _create_error_response(400, "Missing Required Field", f"Field '{field}' is required")
        
        # Validate activity type
        try:
            activity_type = ActivityType(data['activity_type'].lower())
        except ValueError:
            valid_types = [t.value for t in ActivityType]
            return _create_error_response(
                400, 
                "Invalid Activity Type", 
                f"Activity type must be one of: {', '.join(valid_types)}"
            )
        
        # Create activity object
        try:
            activity = Activity(
                activity_type=activity_type,
                description=data['description'],
                duration_minutes=data.get('duration_minutes'),
                location=data.get('location'),
                phone_number=data['phone_number'],
                timestamp=datetime.utcnow(),
                metadata={
                    'source': 'api',
                    'created_via': 'manual_entry',
                    'api_version': '1.0.0'
                }
            )
        except Exception as e:
            return _create_error_response(400, "Invalid Activity Data", str(e))
        
        # Save activity
        if activity_service.db_service.save_activity(activity):
            # Convert to JSON-serializable format
            activity_dict = activity.dict()
            activity_dict['timestamp'] = activity.timestamp.isoformat()
            activity_dict['activity_type'] = activity.activity_type.value
            
            response_data = {
                "activity": activity_dict,
                "message": "Activity created successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return _create_response(201, response_data)
        else:
            return _create_error_response(500, "Failed to Save Activity", "Could not save activity to database")
    
    except Exception as e:
        _log_api_error("CREATE_ACTIVITY_ERROR", str(e), {"body": body[:200] if body else None})
        return _create_error_response(500, "Failed to create activity", str(e))


def _handle_get_stats(activity_service: ActivityService, query_params: Dict[str, str]) -> Dict[str, Any]:
    """
    Handle GET /stats endpoint for activity statistics and analytics.
    
    Provides comprehensive statistics and insights for dashboard
    visualizations and reporting.
    
    Args:
        activity_service: Activity service instance
        query_params: Query string parameters from request
        
    Returns:
        HTTP response with activity statistics and insights
        
    Query Parameters:
        - phone: Filter statistics by phone number (optional)
        - days: Number of days for statistics (default: 30)
        
    Response Body:
        {
            "statistics": {
                "total_activities": 42,
                "by_type": {"work": 15, "exercise": 10, ...},
                "total_duration_minutes": 2400,
                "average_duration_minutes": 57.14,
                "unique_locations": ["Office", "Gym", ...],
                "most_active_day": "2024-01-15"
            },
            "insights": [
                "You're very active! Recording 3+ activities per day on average.",
                "Your most tracked activity type is work (15 activities, 35.7%)"
            ],
            "date_range": {
                "start": "2023-12-16T00:00:00Z",
                "end": "2024-01-15T23:59:59Z",
                "days": 30
            }
        }
    """
    try:
        # Parse query parameters
        phone_number = query_params.get('phone')
        days = int(query_params.get('days', '30'))
        
        # Validate parameters
        if days < 1 or days > 365:
            return _create_error_response(400, "Invalid Days Parameter", "Days must be between 1 and 365")
        
        if phone_number:
            phone_number = unquote_plus(phone_number)
        
        # Get statistics from service
        if phone_number:
            stats = activity_service.get_user_statistics(phone_number, days)
        else:
            stats = activity_service.db_service.get_activity_statistics(days=days)
        
        # Check if statistics generation failed
        if 'error' in stats:
            return _create_error_response(500, "Failed to generate statistics", stats['error'])
        
        response_data = {
            "statistics": stats,
            "filters": {
                "phone": phone_number,
                "days": days
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return _create_response(200, response_data)
        
    except ValueError as e:
        return _create_error_response(400, "Invalid Parameters", str(e))
    except Exception as e:
        _log_api_error("GET_STATS_ERROR", str(e), {"query_params": query_params})
        return _create_error_response(500, "Failed to retrieve statistics", str(e))


def _handle_cors_preflight() -> Dict[str, Any]:
    """
    Handle OPTIONS requests for CORS preflight checks.
    
    Returns appropriate CORS headers to allow browser requests
    from the dashboard frontend.
    
    Returns:
        HTTP response with CORS headers
    """
    return {
        "statusCode": 200,
        "headers": _get_cors_headers(),
        "body": ""
    }


def _create_response(status_code: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a standardized HTTP response with proper headers.
    
    Generates consistent API responses with CORS headers and
    proper JSON formatting.
    
    Args:
        status_code: HTTP status code
        data: Response data to serialize as JSON
        
    Returns:
        HTTP response dictionary
    """
    return {
        "statusCode": status_code,
        "headers": {
            **_get_cors_headers(),
            "Content-Type": "application/json"
        },
        "body": json.dumps(data, indent=2, default=str)
    }


def _create_error_response(status_code: int, error: str, details: str = "") -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Generates consistent error responses with proper structure
    and debugging information.
    
    Args:
        status_code: HTTP status code
        error: High-level error message
        details: Detailed error information
        
    Returns:
        HTTP error response dictionary
    """
    error_data = {
        "error": error,
        "details": details,
        "timestamp": datetime.utcnow().isoformat(),
        "status_code": status_code
    }
    
    return _create_response(status_code, error_data)


def _get_cors_headers() -> Dict[str, str]:
    """
    Get CORS headers for API responses.
    
    Returns appropriate CORS headers based on environment
    configuration for security and functionality.
    
    Returns:
        Dictionary of CORS headers
    """
    # Get allowed origin from environment
    cors_origin = os.getenv('CORS_ORIGIN', '*')
    
    return {
        "Access-Control-Allow-Origin": cors_origin,
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Max-Age": "86400"  # 24 hours
    }


def _log_api_request(event: Dict[str, Any]) -> None:
    """
    Log API request information for monitoring.
    
    Creates structured logs for API requests while protecting
    sensitive information.
    
    Args:
        event: API Gateway event
    """
    try:
        log_data = {
            "event": "API_REQUEST",
            "httpMethod": event.get('httpMethod'),
            "resource": event.get('resource'),
            "timestamp": datetime.utcnow().isoformat(),
            "requestId": event.get('requestContext', {}).get('requestId'),
            "sourceIp": event.get('requestContext', {}).get('identity', {}).get('sourceIp')
        }
        
        # Add query parameters (without sensitive data)
        query_params = event.get('queryStringParameters') or {}
        safe_params = {k: v for k, v in query_params.items() if k not in ['phone']}
        if safe_params:
            log_data["queryParams"] = safe_params
        
        print(json.dumps(log_data))
        
    except Exception as e:
        print(f"Error logging API request: {e}")


def _log_api_error(error_type: str, error_message: str, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log API errors with context for debugging.
    
    Creates structured error logs for monitoring and debugging
    API issues.
    
    Args:
        error_type: Type of error that occurred
        error_message: Detailed error message
        context: Additional context information
    """
    try:
        log_data = {
            "event": "API_ERROR",
            "errorType": error_type,
            "errorMessage": error_message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if context:
            # Add context but protect sensitive data
            safe_context = {k: v for k, v in context.items() if k not in ['phone_number', 'body']}
            log_data["context"] = safe_context
        
        print(json.dumps(log_data))
        
    except Exception as e:
        print(f"Error logging API error: {e}")


# Environment configuration
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')
CORS_ORIGIN = os.getenv('CORS_ORIGIN', '*')

# Initialize service on cold start
try:
    print(f"API Handler Lambda initialized - Environment: {ENVIRONMENT}")
except Exception as e:
    print(f"Warning: Initialization warning: {e}")