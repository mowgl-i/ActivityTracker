"""
AWS Pinpoint service for the ActivityTracker application.

This service handles interactions with AWS Pinpoint for SMS operations,
including sending response messages and managing SMS channel configuration.
While the primary use case is receiving SMS messages, this service provides
utility functions for Pinpoint management.

Classes:
    PinpointService: Service for AWS Pinpoint SMS operations
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class PinpointService:
    """
    Service for managing AWS Pinpoint SMS operations.
    
    This service provides functionality for interacting with AWS Pinpoint,
    primarily for SMS channel management and sending response messages.
    It handles authentication, error handling, and provides utility methods
    for Pinpoint operations.
    
    Attributes:
        application_id: Pinpoint application ID
        pinpoint_client: Boto3 Pinpoint client
        region: AWS region for Pinpoint operations
        
    Example:
        >>> pinpoint_service = PinpointService()
        >>> result = pinpoint_service.send_sms_response(
        ...     "+1234567890", 
        ...     "Activity tracked successfully!"
        ... )
    """
    
    def __init__(self, application_id: Optional[str] = None):
        """
        Initialize the Pinpoint service.
        
        Sets up the Pinpoint client and configuration using environment
        variables or provided parameters.
        
        Args:
            application_id: Optional Pinpoint application ID override
            
        Raises:
            ValueError: If application ID is not provided and not in environment
            NoCredentialsError: If AWS credentials are not configured
        """
        self.application_id = application_id or os.getenv('PINPOINT_APPLICATION_ID')
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        
        if not self.application_id:
            raise ValueError(
                "Pinpoint application ID must be provided either as parameter "
                "or PINPOINT_APPLICATION_ID environment variable"
            )
        
        try:
            # Initialize Pinpoint client
            self.pinpoint_client = boto3.client('pinpoint', region_name=self.region)
            
            # Verify application exists
            self._verify_application()
            
        except NoCredentialsError:
            raise NoCredentialsError(
                "AWS credentials not found. Please configure AWS credentials."
            )
    
    def send_sms_response(self, phone_number: str, message: str, 
                         message_type: str = "TRANSACTIONAL") -> Dict[str, Any]:
        """
        Send an SMS response message via Pinpoint.
        
        Sends an SMS message to the specified phone number using the configured
        Pinpoint application. Useful for sending confirmations or error messages
        back to users after processing their activity submissions.
        
        Args:
            phone_number: Destination phone number in E.164 format
            message: Message content to send
            message_type: Message type (TRANSACTIONAL or PROMOTIONAL)
            
        Returns:
            Dictionary containing send results:
            - success: Boolean indicating if send was successful
            - message_id: Pinpoint message ID if successful
            - error: Error message if send failed
            
        Example:
            >>> result = pinpoint_service.send_sms_response(
            ...     "+1234567890",
            ...     "Activity 'Team meeting' tracked successfully! 📊"
            ... )
            >>> if result['success']:
            ...     print(f"Sent message: {result['message_id']}")
        """
        try:
            # Validate phone number format
            if not phone_number.startswith('+'):
                if phone_number.startswith('1') and len(phone_number) == 11:
                    phone_number = f"+{phone_number}"
                elif len(phone_number) == 10:
                    phone_number = f"+1{phone_number}"
                else:
                    return {
                        'success': False,
                        'error': f"Invalid phone number format: {phone_number}"
                    }
            
            # Validate message content
            if not message or len(message.strip()) == 0:
                return {
                    'success': False,
                    'error': "Message content cannot be empty"
                }
            
            if len(message) > 1600:  # SMS length limit
                return {
                    'success': False,
                    'error': "Message content exceeds SMS length limit (1600 characters)"
                }
            
            # Send SMS via Pinpoint
            response = self.pinpoint_client.send_messages(
                ApplicationId=self.application_id,
                MessageRequest={
                    'Addresses': {
                        phone_number: {
                            'ChannelType': 'SMS'
                        }
                    },
                    'MessageConfiguration': {
                        'SMSMessage': {
                            'Body': message,
                            'MessageType': message_type,
                            'OriginationNumber': self._get_origination_number()
                        }
                    }
                }
            )
            
            # Parse response
            message_response = response['MessageResponse']
            phone_result = message_response['Result'].get(phone_number, {})
            
            if phone_result.get('StatusCode') == 200:
                return {
                    'success': True,
                    'message_id': phone_result.get('MessageId'),
                    'status_message': phone_result.get('StatusMessage', 'Message sent successfully')
                }
            else:
                return {
                    'success': False,
                    'error': phone_result.get('StatusMessage', 'Unknown error'),
                    'status_code': phone_result.get('StatusCode')
                }
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            return {
                'success': False,
                'error': f"Pinpoint error ({error_code}): {error_message}"
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Unexpected error sending SMS: {str(e)}"
            }
    
    def send_activity_confirmation(self, phone_number: str, activity_id: str, 
                                 activity_type: str, description: str) -> Dict[str, Any]:
        """
        Send a confirmation message for a successfully tracked activity.
        
        Sends a formatted confirmation message to the user after their activity
        has been successfully parsed and stored.
        
        Args:
            phone_number: User's phone number
            activity_id: Unique activity identifier
            activity_type: Type of activity (work, exercise, etc.)
            description: Brief activity description
            
        Returns:
            Dictionary with send results
        """
        # Create confirmation message
        emoji_map = {
            'work': '💼',
            'exercise': '🏃',
            'meal': '🍽️',
            'study': '📚',
            'social': '👥',
            'travel': '✈️',
            'other': '📝'
        }
        
        emoji = emoji_map.get(activity_type.lower(), '📝')
        
        message = (
            f"{emoji} Activity tracked successfully!\n\n"
            f"Type: {activity_type.title()}\n"
            f"Description: {description}\n"
            f"ID: {activity_id[:16]}...\n\n"
            f"View your activities at your dashboard! 📊"
        )
        
        return self.send_sms_response(phone_number, message)
    
    def send_parsing_error(self, phone_number: str, original_message: str, 
                          suggestions: List[str]) -> Dict[str, Any]:
        """
        Send an error message when SMS parsing fails.
        
        Sends a helpful error message with suggestions for improving
        the SMS message format when activity parsing fails.
        
        Args:
            phone_number: User's phone number
            original_message: Original SMS message that failed to parse
            suggestions: List of formatting suggestions
            
        Returns:
            Dictionary with send results
        """
        message = (
            f"❌ Could not parse your activity message:\n"
            f'"{original_message[:50]}{"..." if len(original_message) > 50 else ""}"\n\n'
            f"💡 Tips for better tracking:\n"
        )
        
        # Add up to 3 suggestions to keep message short
        for i, suggestion in enumerate(suggestions[:3], 1):
            message += f"{i}. {suggestion}\n"
        
        message += (
            f"\n📱 Example: 'WORK team meeting for 60 minutes in conference room'\n\n"
            f"Try again with more details!"
        )
        
        return self.send_sms_response(phone_number, message)
    
    def get_sms_channel_info(self) -> Dict[str, Any]:
        """
        Get SMS channel configuration information.
        
        Retrieves information about the SMS channel configuration
        for the Pinpoint application, including phone numbers and settings.
        
        Returns:
            Dictionary containing SMS channel information
        """
        try:
            response = self.pinpoint_client.get_sms_channel(
                ApplicationId=self.application_id
            )
            
            sms_channel = response['SMSChannelResponse']
            
            return {
                'success': True,
                'enabled': sms_channel.get('Enabled', False),
                'sender_id': sms_channel.get('SenderId'),
                'short_code': sms_channel.get('ShortCode'),
                'application_id': sms_channel.get('ApplicationId'),
                'creation_date': sms_channel.get('CreationDate'),
                'last_modified_date': sms_channel.get('LastModifiedDate'),
                'platform': sms_channel.get('Platform', 'SMS'),
                'promotional_messages_per_second': sms_channel.get('PromotionalMessagesPerSecond'),
                'transactional_messages_per_second': sms_channel.get('TransactionalMessagesPerSecond')
            }
            
        except ClientError as e:
            return {
                'success': False,
                'error': f"Error retrieving SMS channel info: {e.response['Error']['Message']}"
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Pinpoint service.
        
        Tests connectivity and basic functionality of the Pinpoint service
        to ensure it's operational for SMS operations.
        
        Returns:
            Dictionary with health check results
        """
        try:
            # Check if application exists and is accessible
            app_response = self.pinpoint_client.get_app(
                ApplicationId=self.application_id
            )
            
            # Check SMS channel status
            sms_info = self.get_sms_channel_info()
            
            return {
                'status': 'healthy',
                'application_id': self.application_id,
                'application_name': app_response['ApplicationResponse'].get('Name'),
                'region': self.region,
                'sms_channel_enabled': sms_info.get('enabled', False),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except ClientError as e:
            return {
                'status': 'unhealthy',
                'error': f"Pinpoint error: {e.response['Error']['Message']}",
                'application_id': self.application_id,
                'region': self.region,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'status': 'unhealthy', 
                'error': f"Unexpected error: {str(e)}",
                'application_id': self.application_id,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def _verify_application(self) -> None:
        """
        Verify that the Pinpoint application exists and is accessible.
        
        Raises:
            ValueError: If application is not found or not accessible
        """
        try:
            self.pinpoint_client.get_app(ApplicationId=self.application_id)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NotFoundException':
                raise ValueError(f"Pinpoint application '{self.application_id}' not found")
            raise ValueError(f"Cannot access Pinpoint application: {e.response['Error']['Message']}")
    
    def _get_origination_number(self) -> Optional[str]:
        """
        Get the origination phone number for SMS sending.
        
        Attempts to retrieve a configured phone number or short code
        for sending SMS messages. Returns None if not configured.
        
        Returns:
            Origination phone number or None if not available
        """
        try:
            sms_info = self.get_sms_channel_info()
            
            if sms_info.get('success'):
                # Return short code if available, otherwise sender ID
                return sms_info.get('short_code') or sms_info.get('sender_id')
            
            return None
            
        except Exception:
            # If we can't get channel info, return None and let Pinpoint handle it
            return None