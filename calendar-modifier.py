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
import re
import chromadb
from database_retrieval import add_to_db, update_to_db
from gmail_reader import readEmails
import tracemalloc

tracemalloc.start()

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

client_db = chromadb.PersistentClient(path="eventdb")
database_path = "eventdb/df_db.csv"

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


def calendar_create_event(start_time, end_time, description):
    """Create an event in Google Calendar"""
    # Setting up the connection to the calendar
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=credentials)

    # Get the event details in the JSON format to use it as the body of the event
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

    # Create the event in the calendar
    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    logger.info(f"Created event: {created_event.get('htmlLink')}")

    return created_event

def calendar_modify_event(summary: str = None, start_time: datetime = None, end_time: datetime = None, time_zone: str = 'America/Toronto'):
    "Modify event in the Google calendar"
    # Setting up the connection to the calendar
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=credentials)

    # Get the updated event information in the JSON format to use as the body of the event
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
        # Extracting the event_id from Database
        collection = client_db.get_or_create_collection(name="eventdb")
        similar_record = collection.query(
            query_texts=summary,
            n_results=1
        )
        match = re.search(r"Calendar_ID=([a-zA-Z0-9]+)", similar_record["documents"][0][0])
        if match:
            event_id = match.group(1)
            logger.info(f"Found the event id={event_id} from the database")
        else:
            logger.info("No Calendar_ID found.")

        # Updating the event using event id in the Google calendar
        updated_event = service.events().update(calendarId=CALENDAR_ID, eventId=event_id, body=event_updates).execute()
        logger.info(f"Modified event: {updated_event.get('htmlLink')}")

        return updated_event

    except Exception as e:
        logger.error(f"Failed to modify event: {e}")
        return None


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

        # Step 3: Create the event in Google Calendar
        calendar_created_event = calendar_create_event(start_time, end_time, details.name)
        event_id = calendar_created_event["id"]

        # Step 4: Prepare success response
        message = f"Created new event with the name '{details.name}' with Calendar_ID={event_id} starting at {start_time.strftime('%Y-%m-%d %H:%M')} with participant(s) {', '.join(details.participants)}"
        calendar_link = calendar_created_event.get('htmlLink', None)

        add_to_db(message, database_path)
        logger.info("The event is added to the database!")

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

    # Step 1: Extract modification details using OpenAI
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

    # Step 2: Parse the date and time
    combined_datetime_str = f"{details.date} {details.start_time}" if details.date else details.start_time
    start_time = parser.parse(combined_datetime_str)
    end_time = start_time + timedelta(minutes=details.duration_minutes)

    # Step 3: Modify the event in Google Calendar
    modified_event = calendar_modify_event(summary=details.event_identifier, start_time=start_time, end_time=end_time)
    event_id = modified_event["id"]

    # Step 4: Prepare success response
    message = f"Modified existing event with the name '{details.event_identifier}' with the new Calendar_ID={event_id} starting at {start_time}"
    logger.info(f"Modified event: {details.model_dump_json(indent=2)}")

    # Step 5: Update the event's record in the database
    update_to_db(description=description, path=database_path, message=message)
    logger.info("Updated in the database and the dataframe")

    # Generate success response
    return CalendarResponse(
        success=True,
        message=message,
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
new_event_input = readEmails()
result = process_calendar_request(new_event_input)
if result:
    print(f"Response: {result.message}")

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("[ Top 10 Memory Allocations ]")
for stat in top_stats[:50]:
    print(stat)
# --------------------------------------------------------------
# Step 4: Test with modify event
# --------------------------------------------------------------
#
# modify_event_input = (
#     "Can you move the team meeting with Alice and Bob to next Wednesday at 3pm instead?"
# )
# modify_event_input = readEmails()
# result = process_calendar_request(modify_event_input)
# if result:
#
#     print(f"Response: {result.message}")

# --------------------------------------------------------------
# Step 5: Test with invalid request
# --------------------------------------------------------------

# invalid_input = "What's the weather like today?"
# result = process_calendar_request(invalid_input)
# if not result:
#     print("Request not recognized as a calendar operation")