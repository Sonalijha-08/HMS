import os
# pyrefly: ignore [missing-import]
import django
import sys
from datetime import datetime, timedelta

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms_backend.settings')
try:
    django.setup()
except Exception as e:
    print(f"Error initializing Django: {e}")
    sys.exit(1)

# pyrefly: ignore [missing-import]
from django.contrib.auth import get_user_model
# pyrefly: ignore [missing-import]
from django.utils import timezone
from appointments.models import CustomUser, AvailabilitySlot, Booking, GoogleCredential
from appointments.views import send_notification_email
from appointments.calendar_sync import sync_appointment_event

User = get_user_model()

def run_verification():
    print("\n" + "="*80)
    print("               HOSPITAL MANAGEMENT SYSTEM - INTEGRATION VERIFIER")
    print("="*80)
    
    # 1. Clean up old verification test data
    print("[*] Cleaning up old test data...")
    User.objects.filter(username__in=['verify_doc', 'verify_pat']).delete()
    print("    -> Clean complete.")
    
    # 2. Create Doctor User & Profile
    print("[*] Creating Doctor User 'verify_doc' with password hashing...")
    doc = User.objects.create_user(
        username='verify_doc',
        email='dr_verify@example.com',
        password='verifyPassword123!',
        role='doctor',
        first_name='John',
        last_name='Doe'
    )
    from appointments.models import DoctorProfile
    DoctorProfile.objects.create(user=doc, specialization='Cardiology', biography='Expert cardiologist.')
    print("    -> Doctor user and Neurology profile saved.")
    
    # Trigger Serverless welcome email for Doctor
    print("[*] Triggering Welcome Email for Doctor via Serverless Offline HTTP endpoint...")
    doc_welcome_data = {
        "username": doc.username,
        "role": doc.role
    }
    send_notification_email('SIGNUP_WELCOME', doc.email, doc_welcome_data)
    
    # 3. Create Patient User & Profile
    print("[*] Creating Patient User 'verify_pat'...")
    pat = User.objects.create_user(
        username='verify_pat',
        email='patient_verify@example.com',
        password='verifyPassword123!',
        role='patient',
        first_name='Alice',
        last_name='Smith'
    )
    from appointments.models import PatientProfile
    PatientProfile.objects.create(user=pat, date_of_birth='1992-05-18')
    print("    -> Patient user and date-of-birth profile saved.")
    
    # Trigger Serverless welcome email for Patient
    print("[*] Triggering Welcome Email for Patient via Serverless Offline HTTP endpoint...")
    pat_welcome_data = {
        "username": pat.username,
        "role": pat.role
    }
    send_notification_email('SIGNUP_WELCOME', pat.email, pat_welcome_data)
    
    # Link Google accounts (creates GoogleCredential entries to activate sync flow)
    GoogleCredential.objects.create(
        user=doc,
        token='mock_doc_token',
        refresh_token='mock_doc_refresh',
        token_uri='https://oauth2.googleapis.com/token',
        client_id='mock_client_id',
        client_secret='mock_client_secret',
        scopes='https://www.googleapis.com/auth/calendar.events'
    )
    GoogleCredential.objects.create(
        user=pat,
        token='mock_pat_token',
        refresh_token='mock_pat_refresh',
        token_uri='https://oauth2.googleapis.com/token',
        client_id='mock_client_id',
        client_secret='mock_client_secret',
        scopes='https://www.googleapis.com/auth/calendar.events'
    )
    print("[*] Google Calendar Linked for both Doctor and Patient accounts.")
    
    # 4. Create Availability Slot (Future Slot)
    start_time = timezone.now() + timedelta(days=2)
    end_time = start_time + timedelta(minutes=30)
    print(f"[*] Publishing Doctor Availability: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%H:%M')} UTC...")
    slot = AvailabilitySlot.objects.create(
        doctor=doc,
        start_time=start_time,
        end_time=end_time
    )
    print(f"    -> Slot published successfully (ID: {slot.id})")
    
    # 5. Exclusive Booking Flow with transaction locking
    print("[*] Reserving slot (Simulating row locking transaction)...")
    # pyrefly: ignore [missing-import]
    from django.db import transaction
    try:
        with transaction.atomic():
            # Query slot using select_for_update to block race conditions
            locked_slot = AvailabilitySlot.objects.select_for_update().get(id=slot.id)
            if locked_slot.is_booked:
                print("    [!] ERROR: Slot is already booked.")
                return
            locked_slot.is_booked = True
            locked_slot.save()
            
            booking = Booking.objects.create(patient=pat, slot=locked_slot)
            print(f"    -> Slot locked & Booking created ID: {booking.id}")
    except Exception as e:
        print(f"    [!] Transaction Failed: {e}")
        return
        
    # 6. Trigger Integrations
    print("[*] Triggering Google Calendar event creations for both users...")
    sync_appointment_event(booking)
    
    print("[*] Triggering Booking Confirmation emails via Serverless Offline...")
    slot_time_str = f"{booking.slot.start_time.strftime('%Y-%m-%d %H:%M')} to {booking.slot.end_time.strftime('%H:%M')} UTC"
    booking_email_data = {
        "patient_name": pat.username,
        "doctor_name": doc.username,
        "slot_time": slot_time_str
    }
    
    # Trigger email to patient
    send_notification_email('BOOKING_CONFIRMATION', pat.email, booking_email_data)
    # Trigger email to doctor
    send_notification_email('BOOKING_CONFIRMATION', doc.email, booking_email_data)
    
    print("="*80)
    print("                 HMS INTEGRATION VERIFICATION COMPLETE!")
    print("="*80 + "\n")

if __name__ == '__main__':
    run_verification()
