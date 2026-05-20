import os
import requests
import uuid
# pyrefly: ignore [missing-import]
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from .models import CustomUser, DoctorProfile, PatientProfile, AvailabilitySlot, Booking, GoogleCredential
from .forms import SignUpForm, AvailabilityForm
from .calendar_sync import get_google_auth_url, exchange_code_for_credentials, sync_appointment_event

def send_notification_email(trigger_type, recipient_email, data):
    """
    Triggers the separate Serverless email notification microservice via HTTP POST.
    """
    url = os.getenv('EMAIL_SERVICE_URL', 'http://127.0.0.1:3000/dev/email/send')
    payload = {
        "trigger_type": trigger_type,
        "recipient_email": recipient_email,
        "data": data,
        "smtp_host": os.getenv('SMTP_HOST', '127.0.0.1'),
        "smtp_port": int(os.getenv('SMTP_PORT', '1025')),
        "smtp_user": os.getenv('SMTP_USER', ''),
        "smtp_password": os.getenv('SMTP_PASSWORD', '')
    }
    try:
        response = requests.post(url, json=payload, timeout=4)
        if response.status_code == 200:
            print(f"[HMS EMAIL SERVICE] Notification triggered successfully: {response.json()}")
            return True
        else:
            print(f"[HMS EMAIL SERVICE ERROR] HTTP status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[HMS EMAIL SERVICE EXCEPTION] Connection failed (microservice might be offline): {e}")
    return False

# Custom authorization decorators
def doctor_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.role != 'doctor':
            messages.error(request, "Access Denied: Only doctors can view this page.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

def patient_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.role != 'patient':
            messages.error(request, "Access Denied: Only patients can view this page.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

# Home / Index
def index_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'index.html')

# Signup
def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Account created successfully for {user.username}! You can now log in.")
            
            # Trigger SIGNUP_WELCOME email notification
            email_data = {
                "username": user.username,
                "role": user.role
            }
            send_notification_email('SIGNUP_WELCOME', user.email, email_data)
            
            return redirect('login')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})

# Login
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, 'login.html')

# Logout
def logout_view(request):
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect('login')

# Dashboard Dispatcher
@login_required
def dashboard_view(request):
    if request.user.role == 'doctor':
        return redirect('doctor_dashboard')
    elif request.user.role == 'patient':
        return redirect('patient_dashboard')
    else:
        messages.error(request, "Unrecognized user role.")
        logout(request)
        return redirect('login')

# Doctor Dashboard
@login_required
@doctor_required
def doctor_dashboard_view(request):
    doctor = request.user
    slots = AvailabilitySlot.objects.filter(doctor=doctor).order_by('start_time')
    
    # Form for adding slots
    if request.method == 'POST':
        form = AvailabilityForm(request.POST)
        if form.is_valid():
            start_dt = form.cleaned_data['start_datetime']
            end_dt = form.cleaned_data['end_datetime']
            
            # Check overlap
            overlapping = AvailabilitySlot.objects.filter(
                doctor=doctor,
                start_time__lt=end_dt,
                end_time__gt=start_dt
            ).exists()
            
            if overlapping:
                messages.error(request, "This slot overlaps with an already existing availability slot.")
            else:
                try:
                    AvailabilitySlot.objects.create(
                        doctor=doctor,
                        start_time=start_dt,
                        end_time=end_dt
                    )
                    messages.success(request, "Availability slot added successfully!")
                    return redirect('doctor_dashboard')
                except Exception as e:
                    messages.error(request, f"Failed to save slot: {e}")
    else:
        form = AvailabilityForm()
        
    # Check Google Calendar connection
    has_calendar = GoogleCredential.objects.filter(user=doctor).exists()
    
    context = {
        'slots': slots,
        'form': form,
        'has_calendar': has_calendar
    }
    return render(request, 'doctor_dashboard.html', context)

# Patient Dashboard
@login_required
@patient_required
def patient_dashboard_view(request):
    patient = request.user
    
    # Get all doctors
    doctors = CustomUser.objects.filter(role='doctor')
    
    selected_doctor_id = request.GET.get('doctor_id')
    selected_doctor = None
    available_slots = []
    
    if selected_doctor_id:
        selected_doctor = get_object_or_404(CustomUser, id=selected_doctor_id, role='doctor')
        # Only show future slots that are not booked
        available_slots = AvailabilitySlot.objects.filter(
            doctor=selected_doctor,
            start_time__gt=timezone.now(),
            is_booked=False
        ).order_by('start_time')
        
    bookings = Booking.objects.filter(patient=patient).order_by('slot__start_time')
    has_calendar = GoogleCredential.objects.filter(user=patient).exists()
    
    context = {
        'doctors': doctors,
        'selected_doctor': selected_doctor,
        'available_slots': available_slots,
        'bookings': bookings,
        'has_calendar': has_calendar
    }
    return render(request, 'patient_dashboard.html', context)

# Booking Flow with Race Condition handling
@login_required
@patient_required
def book_appointment_view(request, slot_id):
    patient = request.user
    
    # 1. Lock the selected availability slot inside a transaction to prevent dual-bookings
    # select_for_update blocks concurrent transactions attempting to read/write this row
    try:
        with transaction.atomic():
            # Query the slot while locking it
            slot = AvailabilitySlot.objects.select_for_update().get(id=slot_id)
            
            # Verify if it's already booked
            if slot.is_booked:
                messages.error(request, "This time slot has already been booked by another patient.")
                return redirect('patient_dashboard')
                
            # Verify slot time is in the future
            if slot.start_time <= timezone.now():
                messages.error(request, "This slot is in the past and cannot be booked.")
                return redirect('patient_dashboard')
                
            # Perform atomic reservation
            slot.is_booked = True
            slot.save()
            
            # Create booking
            booking = Booking.objects.create(
                patient=patient,
                slot=slot
            )
            messages.success(request, f"Appointment successfully booked with Dr. {slot.doctor.username}!")
            
    except AvailabilitySlot.DoesNotExist:
        messages.error(request, "The requested availability slot does not exist.")
        return redirect('patient_dashboard')
    except Exception as e:
        messages.error(request, f"A system error occurred during booking: {e}")
        return redirect('patient_dashboard')

    # 2. Trigger Out-of-Transaction integrations (Google Calendar & Serverless Emails)
    # This prevents calendar API timeouts from blocking the database connection lock
    try:
        sync_appointment_event(booking)
    except Exception as e:
        print(f"[GOOGLE CALENDAR ERROR] Failed to sync booking: {e}")
        
    try:
        slot_time_str = f"{booking.slot.start_time.strftime('%Y-%m-%d %H:%M')} to {booking.slot.end_time.strftime('%H:%M')} UTC"
        
        # Send confirmation email to patient
        patient_email_data = {
            "patient_name": patient.username,
            "doctor_name": slot.doctor.username,
            "slot_time": slot_time_str
        }
        send_notification_email('BOOKING_CONFIRMATION', patient.email, patient_email_data)
        
        # Send notification email to doctor
        doctor_email_data = {
            "patient_name": patient.username,
            "doctor_name": slot.doctor.username,
            "slot_time": slot_time_str
        }
        send_notification_email('BOOKING_CONFIRMATION', slot.doctor.email, doctor_email_data)
        
    except Exception as e:
        print(f"[EMAIL NOTIFICATION ERROR] Failed to send emails: {e}")
        
    return redirect('patient_dashboard')

# Google Calendar OAuth flow initiation
@login_required
def google_auth_init_view(request):
    # Create random state to verify redirect integrity
    state = str(uuid.uuid4())
    request.session['google_oauth_state'] = state
    
    authorization_url = get_google_auth_url(request.user, state)
    return redirect(authorization_url)

# Google Calendar OAuth flow callback
@login_required
def google_auth_callback_view(request):
    code = request.GET.get('code')
    state = request.GET.get('state')
    
    saved_state = request.session.get('google_oauth_state')
    if not state or state != saved_state:
        messages.error(request, "Google OAuth security verification failed: State mismatch.")
        return redirect('dashboard')
        
    if 'google_oauth_state' in request.session:
        del request.session['google_oauth_state']
        
    if not code:
        messages.error(request, "Google OAuth failed: No authorization code received.")
        return redirect('dashboard')
        
    success = exchange_code_for_credentials(request.user, code, state)
    if success:
        messages.success(request, "Successfully linked your Google Calendar! Appointments will now sync automatically.")
    else:
        messages.error(request, "Failed to authenticate with Google Calendar.")
        
    return redirect('dashboard')
