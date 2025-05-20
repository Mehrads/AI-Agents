from typing import Optional, Literal
from pydantic import BaseModel, Field
from openai import OpenAI
import os
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from dateutil import parser


load_dotenv()
# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Calendar Configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = '/Users/mehrad/Programming/agents/corded-cable-431717-g0-0ad41cef68fe.json'
CALENDAR_ID = 'msoltani2001@gmail.com'

# LLM model configuration
client = OpenAI(base_url="https://openrouter.ai/api/v1",
                api_key=os.environ.get("OPENAI_API_KEY"),)
model = "gpt-4o"

# --------------------------------------------------------------
# Step 1: Define the data models for routing and responses
# --------------------------------------------------------------


class CalendarRequestType(BaseModel):
    """Router LLM call: Determine the type of calendar request"""

    request_type: Literal["new_event", "modify_event", "other"] = Field(
        description="Type of calendar request being made"
    )
    confidence_score: float = Field(description="Confidence score between 0 and 1")
    description: str = Field(description="Cleaned description of the request")


class NewEventDetails(BaseModel):
    """Details for creating a new event"""

    name: str = Field(description="Name of the event")
    date: str = Field(description="Date and time of the event (ISO 8601)")
    duration_minutes: int = Field(description="Duration in minutes")
    start_time: str = Field(description="The start time of the event")
    participants: list[str] = Field(description="List of participants")


class Change(BaseModel):
    """Details for changing an existing event"""

    field: str = Field(description="Field to change")
    new_value: str = Field(description="New value for the field")


class ModifyEventDetails(BaseModel):
    """Details for modifying an existing event"""

    event_identifier: str = Field(
        description="Description to identify the existing event"
    )
    changes: list[Change] = Field(description="List of changes to make")
    date: str = Field(description="The new Date and time of the event (ISO 8601)")
    duration_minutes: int = Field(description="Duration in minutes")
    start_time: str = Field(description="The new start time of the event")
    participants_to_add: list[str] = Field(description="New participants to add")
    participants_to_remove: list[str] = Field(description="Participants to remove")


class CalendarResponse(BaseModel):
    """Final response format"""

    success: bool = Field(description="Whether the operation was successful")
    message: str = Field(description="User-friendly response message")
    calendar_link: Optional[str] = Field(description="Calendar link if applicable")


# --------------------------------------------------------------
# Step 2: Define the routing and processing functions
# --------------------------------------------------------------


def route_calendar_request(user_input: str) -> CalendarRequestType:
    """Router LLM call to determine the type of calendar request"""
    logger.info("Routing calendar request")

    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Determine if this is a request to create a new calendar event or modify an existing one.",
            },
            {"role": "user", "content": user_input},
        ],
        response_format=CalendarRequestType,
    )
    result = completion.choices[0].message.parsed
    logger.info(
        f"Request routed as: {result.request_type} with confidence: {result.confidence_score}"
    )
    return result


event_id = None
def create_event(start_time, end_time, description):
    """Create an event in Google Calendar"""
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=credentials)
    event = {
        'summary': description,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'America/Toronto',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'America/Toronto',
        },
    }
    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    global event_id
    event_id = created_event["id"]
    logger.info(f"Created event: {created_event.get('htmlLink')}")
    return created_event

def modify_event(event_id: str, summary: str = None, start_time: datetime = None, end_time: datetime = None, time_zone: str = 'America/Toronto'):
    """Modifies an existing event in Google Calendar based on start_time and end_time.

    Args:
        event_id: The ID of the event to modify.
        summary: The new summary (title) of the event (optional).
        start_time: The new start time of the event (optional).
        time_zone: The time zone for the event (default: America/Toronto).

    Returns:
        The updated event object, or None if the update failed.
    """

    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=credentials)

    event_updates = {
        'summary': summary,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'America/Toronto',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'America/Toronto',
        },
    }

    try:
        updated_event = service.events().update(calendarId=CALENDAR_ID, eventId=event_id, body=event_updates).execute()  # Use 'patch'
        logger.info(f"Modified event: {updated_event.get('htmlLink')}")
        return updated_event
    except Exception as e:
        logger.error(f"Failed to modify event: {e}")
        return None

# def modify_event(description: str, start_time: datetime = None, end_time: datetime = None, time_zone: str = 'America/Toronto'):
#     """Modifies an existing event in Google Calendar by searching for an event at the given start time and the event ID.
#
#     Args:
#         description: Description of changes
#         start_time: The start time of the event to modify.
#         end_time: The new end time of the event (optional).
#         time_zone: The time zone for the event (default: America/Toronto).
#
#     Returns:
#         The updated event object, or None if the update failed.
#     """
#     credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
#     service = build('calendar', 'v3', credentials=credentials)
#
#     # Search for events at the given start time
#     start_time_str = start_time.isoformat() + 'Z'  # Format for Google Calendar API
#     end_time_search = start_time + timedelta(minutes=1)  # Search within a 1-minute window
#     end_time_str = end_time_search.isoformat() + 'Z'
#
#     events_result = service.events().list(
#         calendarId=CALENDAR_ID,
#         timeMin=start_time_str,
#         timeMax=end_time_str,
#         singleEvents=True,
#         orderBy='startTime'
#     ).execute()
#     events = events_result.get('items', [])
#
#     if not events:
#         logger.warning(f"No event found at start time: {start_time_str}")
#         return None
#
#     event_id = events[0]['id']  # Get the ID of the first event found
#
#     event_updates = {}  # Dictionary to hold the updates
#
#     if description:
#         event_updates['summary'] = description
#
#     if end_time:
#         event_updates['end'] = {
#             'dateTime': end_time.isoformat(),
#             'timeZone': time_zone,
#         }
#
#     try:
#         updated_event = service.events().patch(calendarId=CALENDAR_ID, eventId=event_id, body=event_updates).execute()  # Use 'patch'
#         logger.info(f"Modified event: {updated_event.get('htmlLink')}")
#         return updated_event
#     except Exception as e:
#         logger.error(f"Failed to modify event: {e}")
#         return None




def handle_new_event(description: str) -> CalendarResponse:
    """Process a new event request and create it in Google Calendar"""
    logger.info("Processing new event request")
    today = datetime.now()
    date_context = f"Today is {today.strftime('%A, %B %d, %Y')}."

    try:
        # Step 1: Extract event details using OpenAI
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"Extract details for creating a new calendar event. {date_context}",
                },
                {"role": "user", "content": description},
            ],
            response_format=NewEventDetails,
        )
        details = completion.choices[0].message.parsed
        logger.info(f"New event extracted: {details.model_dump_json(indent=2)}")

        # Step 2: Parse the date and time
        combined_datetime_str = f"{details.date} {details.start_time}" if details.date else details.start_time
        start_time = parser.parse(combined_datetime_str)
        end_time = start_time + timedelta(minutes=details.duration_minutes)
        global event_id
        # Step 3: Create the event in Google Calendar
        created_event = create_event(start_time, end_time, details.name)

        # Step 4: Prepare success response
        message = f"Created new event '{details.name}' with ID {event_id} starting at {start_time.strftime('%Y-%m-%d %H:%M')} with {', '.join(details.participants)}"
        calendar_link = created_event.get('htmlLink', None)

        return CalendarResponse(
            success=True,
            message=message,
            calendar_link=calendar_link,
        )

    except Exception as e:
        logger.error(f"Failed to process new event: {e}")
        return CalendarResponse(
            success=False,
            message=f"Failed to create event: {str(e)}",
            calendar_link=None,
        )


def handle_modify_event(description: str) -> CalendarResponse:
    """Process an event modification request"""
    logger.info("Processing event modification request")

    today = datetime.now()
    date_context = f"Today is {today.strftime('%A, %B %d, %Y')}."

    # Get modification details
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {
                "role": "system",
                "content": f"""Extract details for modifying an existing calendar event. Today's date is {date_context}.
                                Note that terms like "next" indicate the modification should be scheduled after the event's original date.""",
            },
            {"role": "user", "content": description},
        ],
        response_format=ModifyEventDetails,
    )
    details = completion.choices[0].message.parsed
    combined_datetime_str = f"{details.date} {details.start_time}" if details.date else details.start_time
    start_time = parser.parse(combined_datetime_str)
    end_time = start_time + timedelta(minutes=details.duration_minutes)
    modify_event(event_id="p9hb6pri1f0vh8gs93517qrsfs", summary=details.event_identifier, start_time=start_time, end_time=end_time)

    logger.info(f"Modified event: {details.model_dump_json(indent=2)}")

    # Generate response
    return CalendarResponse(
        success=True,
        message=f"Modified event '{details.event_identifier}' with the requested changes",
        calendar_link=f"calendar://modify?event={details.event_identifier}",
    )

def process_calendar_request(user_input: str) -> Optional[CalendarResponse]:
    """Main function implementing the routing workflow"""
    logger.info("Processing calendar request")

    # Route the request
    route_result = route_calendar_request(user_input)

    # Check confidence threshold
    if route_result.confidence_score < 0.7:
        logger.warning(f"Low confidence score: {route_result.confidence_score}")
        return None

    # Route to appropriate handler
    if route_result.request_type == "new_event":
        return handle_new_event(route_result.description)
    elif route_result.request_type == "modify_event":
        return handle_modify_event(route_result.description)
    else:
        logger.warning("Request type not supported")
        return None


# --------------------------------------------------------------
# Step 3: Using tools to interact with Google Calendar
# --------------------------------------------------------------


# new_event_input = "Let's schedule a team meeting next Tuesday at 2pm with Alice and Bob"
# result = process_calendar_request(new_event_input)
# if result:
#     print(f"Response: {result.message}")

# --------------------------------------------------------------
# Step 4: Test with modify event
# --------------------------------------------------------------
#
modify_event_input = (
    "Can you move the team meeting with Alice and Bob to next Wednesday at 3pm instead?"
)
result = process_calendar_request(modify_event_input)
if result:
    print(f"Response: {result.message}")

# --------------------------------------------------------------
# Step 5: Test with invalid request
# --------------------------------------------------------------

# invalid_input = "What's the weather like today?"
# result = process_calendar_request(invalid_input)
# if not result:
#     print("Request not recognized as a calendar operation")