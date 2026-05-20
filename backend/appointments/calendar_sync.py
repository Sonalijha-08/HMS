import os
import datetime
# pyrefly: ignore [missing-import]
from django.conf import settings
from .models import GoogleCredential, Booking
# pyrefly: ignore [missing-import]
from google.oauth2.credentials import Credentials
# pyrefly: ignore [missing-import]
from google_auth_oauthlib.flow import Flow
# pyrefly: ignore [missing-import]
from googleapiclient.discovery import build
# pyrefly: ignore [missing-import]
from django.utils.timezone import is_naive, make_aware

# Scopes required for Calendar API
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def get_oauth_flow(state=None):
    """
    Returns a Google OAuth Flow object.
    """
    client_config = {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", "mock_client_id"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "mock_client_secret"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/oauth/callback/")]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        state=state
    )
    flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/oauth/callback/")
    return flow

def get_google_auth_url(user, state):
    """
    Generates the authorization URL.
    In Mock Mode, directly points to local callback URI.
    """
    is_mock = os.getenv("MOCK_GOOGLE_CALENDAR", "True") == "True"
    if is_mock:
        callback_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/oauth/callback/")
        return f"{callback_uri}?code=mock_auth_code_for_{user.username}&state={state}"
    
    flow = get_oauth_flow(state=state)
    authorization_url, _ = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        include_granted_scopes='true'
    )
    return authorization_url

def exchange_code_for_credentials(user, code, state):
    """
    Exchanges authorization code for credentials and stores them.
    """
    is_mock = os.getenv("MOCK_GOOGLE_CALENDAR", "True") == "True"
    
    if is_mock:
        GoogleCredential.objects.update_or_create(
            user=user,
            defaults={
                'token': "mock_access_token",
                'refresh_token': "mock_refresh_token",
                'token_uri': "https://oauth2.googleapis.com/token",
                'client_id': "mock_client_id",
                'client_secret': "mock_client_secret",
                'scopes': ",".join(SCOPES)
            }
        )
        return True

    try:
        flow = get_oauth_flow(state=state)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        GoogleCredential.objects.update_or_create(
            user=user,
            defaults={
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': ",".join(credentials.scopes)
            }
        )
        return True
    except Exception as e:
        print(f"Error in Google OAuth code exchange: {e}")
        return False

def get_google_credentials_for_user(user):
    """
    Utility to load credentials model into a google-auth Credentials object.
    """
    try:
        cred_model = GoogleCredential.objects.get(user=user)
        return Credentials(
            token=cred_model.token,
            refresh_token=cred_model.refresh_token,
            token_uri=cred_model.token_uri,
            client_id=cred_model.client_id,
            client_secret=cred_model.client_secret,
            scopes=cred_model.scopes.split(',')
        )
    except GoogleCredential.DoesNotExist:
        return None

def create_calendar_event(user_creds, summary, description, start_time, end_time):
    """
    Creates an event on the user's primary calendar using credentials.
    In Mock Mode, returns a simulated event ID.
    """
    is_mock = os.getenv("MOCK_GOOGLE_CALENDAR", "True") == "True"
    if is_mock:
        simulated_id = f"mock_event_id_{datetime.datetime.now().timestamp()}"
        print(f"\n[GOOGLE CALENDAR MOCK] Event created successfully on account.")
        print(f"  Summary: {summary}")
        print(f"  Timeslot: {start_time} to {end_time}")
        print(f"  Event ID: {simulated_id}\n")
        return simulated_id

    try:
        service = build('calendar', 'v3', credentials=user_creds)
        
        # Ensure times are ISO 8601 formatted
        start_str = start_time.isoformat()
        end_str = end_time.isoformat()
        
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_str,
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_str,
                'timeZone': 'UTC',
            },
        }
        
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return created_event.get('id')
    except Exception as e:
        print(f"Error creating Google Calendar event for user: {e}")
        return None

def sync_appointment_event(booking):
    """
    Synchronizes booking to both Patient and Doctor's calendars if they are authenticated.
    """
    slot = booking.slot
    doctor = slot.doctor
    patient = booking.patient
    
    start_time = slot.start_time
    end_time = slot.end_time
    
    # Sync Doctor's Calendar
    doc_creds = get_google_credentials_for_user(doctor)
    if doc_creds:
        doc_summary = f"Appointment with {patient.first_name or patient.username}"
        doc_desc = f"HMS Appointment. Patient contact: {patient.email}"
        event_id = create_calendar_event(doc_creds, doc_summary, doc_desc, start_time, end_time)
        if event_id:
            booking.google_event_id_doctor = event_id
            
    # Sync Patient's Calendar
    pat_creds = get_google_credentials_for_user(patient)
    if pat_creds:
        pat_summary = f"Appointment with Dr. {doctor.first_name or doctor.username}"
        pat_desc = f"HMS Appointment. Specialization: {getattr(doctor.doctor_profile, 'specialization', 'General')}"
        event_id = create_calendar_event(pat_creds, pat_summary, pat_desc, start_time, end_time)
        if event_id:
            booking.google_event_id_patient = event_id
            
    booking.save()
