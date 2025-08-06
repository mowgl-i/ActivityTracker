"""
DynamoDB service for the ActivityTracker application.

This service handles all interactions with DynamoDB for storing and retrieving
activity data. It provides high-level methods for CRUD operations with proper
error handling and data validation.

Classes:
    DynamoDBService: Service for DynamoDB operations and data persistence
"""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key, Attr
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from ..models.activity import Activity


class DynamoDBService:
    """
    Service for managing ActivityTracker data in DynamoDB.

    This service provides a high-level interface for storing and retrieving
    activities from DynamoDB. It handles connection management, error handling,
    and data serialization/deserialization.

    Attributes:
        table_name: Name of the DynamoDB table
        dynamodb: Boto3 DynamoDB resource
        table: DynamoDB table resource

    Example:
        >>> db_service = DynamoDBService()
        >>> activity = Activity(...)
        >>> db_service.save_activity(activity)
        >>> retrieved = db_service.get_activity(activity.id)
    """

    def __init__(self, table_name: Optional[str] = None):
        """
        Initialize the DynamoDB service.

        Sets up the connection to DynamoDB and configures the table resource.
        Uses environment variables for configuration when available.

        Args:
            table_name: Optional table name override, uses env var if not provided

        Raises:
            ValueError: If table name is not provided and not in environment
            NoCredentialsError: If AWS credentials are not configured
        """
        self.table_name = table_name or os.getenv("ACTIVITIES_TABLE")

        if not self.table_name:
            raise ValueError(
                "Table name must be provided either as parameter or ACTIVITIES_TABLE environment variable"
            )

        try:
            # Initialize DynamoDB resource
            self.dynamodb = boto3.resource("dynamodb")
            self.table = self.dynamodb.Table(self.table_name)

            # Verify table exists by getting its description
            self.table.load()

        except NoCredentialsError:
            raise NoCredentialsError(
                "AWS credentials not found. Please configure AWS credentials."
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                raise ValueError(f"DynamoDB table '{self.table_name}' not found")
            raise

    def save_activity(self, activity: Activity) -> bool:
        """
        Save an activity to DynamoDB.

        Stores an Activity object in the DynamoDB table with proper error
        handling and data validation. Converts the activity to the appropriate
        DynamoDB format.

        Args:
            activity: Activity object to save

        Returns:
            True if save successful, False otherwise

        Example:
            >>> activity = Activity(
            ...     activity_type=ActivityType.WORK,
            ...     description="Team meeting",
            ...     phone_number="+1234567890"
            ... )
            >>> success = db_service.save_activity(activity)
        """
        try:
            # Convert activity to DynamoDB item format
            item = activity.to_dynamodb_item()

            # Add GSI attributes for efficient querying
            item["phone_number"] = activity.phone_number
            item["timestamp"] = activity.timestamp.isoformat()

            # Save to DynamoDB
            response = self.table.put_item(Item=item)

            # Check if the operation was successful
            return response["ResponseMetadata"]["HTTPStatusCode"] == 200

        except ClientError as e:
            print(f"Error saving activity {activity.id}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error saving activity {activity.id}: {e}")
            return False

    def get_activity(self, activity_id: str) -> Optional[Activity]:
        """
        Retrieve an activity by ID from DynamoDB.

        Fetches a single activity from the database using its unique ID and
        converts it back to an Activity object.

        Args:
            activity_id: Unique activity identifier

        Returns:
            Activity object if found, None otherwise

        Example:
            >>> activity = db_service.get_activity("act_2024_01_15_14_30_00_abc123")
            >>> print(activity.description if activity else "Not found")
        """
        try:
            response = self.table.get_item(Key={"id": activity_id})

            if "Item" in response:
                return Activity.from_dynamodb_item(response["Item"])

            return None

        except ClientError as e:
            print(f"Error retrieving activity {activity_id}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error retrieving activity {activity_id}: {e}")
            return None

    def get_activities_by_phone(
        self,
        phone_number: str,
        limit: int = 50,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Activity]:
        """
        Retrieve activities for a specific phone number.

        Uses the GSI to efficiently query activities by phone number with
        optional date filtering. Returns results in reverse chronological order.

        Args:
            phone_number: Phone number to query
            limit: Maximum number of activities to return
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of Activity objects

        Example:
            >>> activities = db_service.get_activities_by_phone(
            ...     "+1234567890",
            ...     limit=10,
            ...     start_date=datetime(2024, 1, 1)
            ... )
        """
        try:
            # Build the query expression
            key_condition = Key("phone_number").eq(phone_number)

            # Add date range if specified
            if start_date or end_date:
                if start_date and end_date:
                    key_condition = key_condition & Key("timestamp").between(
                        start_date.isoformat(), end_date.isoformat()
                    )
                elif start_date:
                    key_condition = key_condition & Key("timestamp").gte(
                        start_date.isoformat()
                    )
                elif end_date:
                    key_condition = key_condition & Key("timestamp").lte(
                        end_date.isoformat()
                    )

            # Query the GSI
            response = self.table.query(
                IndexName="PhoneNumberTimestampIndex",
                KeyConditionExpression=key_condition,
                ScanIndexForward=False,  # Reverse order (newest first)
                Limit=limit,
            )

            # Convert items to Activity objects
            activities = []
            for item in response.get("Items", []):
                try:
                    activity = Activity.from_dynamodb_item(item)
                    activities.append(activity)
                except Exception as e:
                    print(f"Error converting item to Activity: {e}")
                    continue

            return activities

        except ClientError as e:
            print(f"Error querying activities for phone {phone_number}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error querying activities: {e}")
            return []

    def get_recent_activities(self, limit: int = 20) -> List[Activity]:
        """
        Get the most recent activities across all users.

        Performs a scan operation to retrieve recent activities. This is less
        efficient than phone-specific queries but useful for dashboard views.

        Args:
            limit: Maximum number of activities to return

        Returns:
            List of Activity objects sorted by timestamp (newest first)
        """
        try:
            # Use scan with projection to get recent items
            response = self.table.scan(
                ProjectionExpression="id, activity_type, description, phone_number, #ts, duration_minutes, #loc",
                ExpressionAttributeNames={"#ts": "timestamp", "#loc": "location"},
                Limit=limit * 3,  # Get more items to sort and filter
            )

            # Convert to Activity objects and sort
            activities = []
            for item in response.get("Items", []):
                try:
                    activity = Activity.from_dynamodb_item(item)
                    activities.append(activity)
                except Exception as e:
                    print(f"Error converting item to Activity: {e}")
                    continue

            # Sort by timestamp (newest first) and limit
            activities.sort(key=lambda a: a.timestamp, reverse=True)
            return activities[:limit]

        except ClientError as e:
            print(f"Error scanning recent activities: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error getting recent activities: {e}")
            return []

    def get_activity_statistics(
        self, phone_number: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """
        Get activity statistics for a phone number or all users.

        Calculates various statistics including activity counts by type,
        total duration, and activity patterns over the specified time period.

        Args:
            phone_number: Optional phone number filter
            days: Number of days to include in statistics

        Returns:
            Dictionary containing activity statistics

        Example:
            >>> stats = db_service.get_activity_statistics("+1234567890", days=7)
            >>> print(f"Total activities: {stats['total_activities']}")
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            if phone_number:
                # Get activities for specific phone number
                activities = self.get_activities_by_phone(
                    phone_number,
                    limit=1000,  # Large limit to get all activities in range
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                # Scan all activities within date range
                response = self.table.scan(
                    FilterExpression=Attr("timestamp").between(
                        start_date.isoformat(), end_date.isoformat()
                    ),
                    Limit=1000,
                )

                activities = []
                for item in response.get("Items", []):
                    try:
                        activity = Activity.from_dynamodb_item(item)
                        activities.append(activity)
                    except Exception as e:
                        print(f"Error converting item to Activity: {e}")
                        continue

            # Calculate statistics
            stats = {
                "total_activities": len(activities),
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "days": days,
                },
                "by_type": {},
                "total_duration_minutes": 0,
                "average_duration_minutes": 0,
                "activities_with_duration": 0,
                "activities_with_location": 0,
                "unique_locations": set(),
                "most_active_day": None,
                "daily_counts": {},
            }

            if not activities:
                return stats

            # Process each activity
            for activity in activities:
                # Count by type
                activity_type = activity.activity_type.value
                stats["by_type"][activity_type] = (
                    stats["by_type"].get(activity_type, 0) + 1
                )

                # Duration statistics
                if activity.duration_minutes:
                    stats["total_duration_minutes"] += activity.duration_minutes
                    stats["activities_with_duration"] += 1

                # Location statistics
                if activity.location:
                    stats["activities_with_location"] += 1
                    stats["unique_locations"].add(activity.location)

                # Daily activity counts
                day_key = activity.timestamp.strftime("%Y-%m-%d")
                stats["daily_counts"][day_key] = (
                    stats["daily_counts"].get(day_key, 0) + 1
                )

            # Calculate averages
            if stats["activities_with_duration"] > 0:
                stats["average_duration_minutes"] = (
                    stats["total_duration_minutes"] / stats["activities_with_duration"]
                )

            # Find most active day
            if stats["daily_counts"]:
                stats["most_active_day"] = max(
                    stats["daily_counts"], key=stats["daily_counts"].get
                )

            # Convert set to list for JSON serialization
            stats["unique_locations"] = list(stats["unique_locations"])

            return stats

        except Exception as e:
            print(f"Error calculating activity statistics: {e}")
            return {"total_activities": 0, "error": str(e)}

    def delete_activity(self, activity_id: str) -> bool:
        """
        Delete an activity from DynamoDB.

        Removes an activity from the database using its unique ID.

        Args:
            activity_id: ID of activity to delete

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            response = self.table.delete_item(
                Key={"id": activity_id}, ReturnValues="ALL_OLD"
            )

            # Check if item existed and was deleted
            return "Attributes" in response

        except ClientError as e:
            print(f"Error deleting activity {activity_id}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error deleting activity {activity_id}: {e}")
            return False

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the DynamoDB service.

        Tests the connection and basic functionality of the DynamoDB service
        to ensure it's operational.

        Returns:
            Dictionary with health check results
        """
        try:
            # Try to describe the table
            table_description = self.table.meta.client.describe_table(
                TableName=self.table_name
            )

            return {
                "status": "healthy",
                "table_name": self.table_name,
                "table_status": table_description["Table"]["TableStatus"],
                "item_count": table_description["Table"].get("ItemCount", "unknown"),
                "region": self.dynamodb.meta.client.meta.region_name,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "table_name": self.table_name,
            }
