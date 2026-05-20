# pyrefly: ignore [missing-import]
from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('doctor', 'Doctor'),
        ('patient', 'Patient'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    email = models.EmailField(unique=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

class DoctorProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='doctor_profile')
    specialization = models.CharField(max_length=100, blank=True)
    biography = models.TextField(blank=True)

    def __str__(self):
        return f"Dr. {self.user.username} - {self.specialization or 'General'}"

class PatientProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='patient_profile')
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return f"Patient: {self.user.username}"

class AvailabilitySlot(models.Model):
    doctor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'doctor'}, related_name='slots')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_booked = models.BooleanField(default=False)

    class Meta:
        ordering = ['start_time']
        # Prevent overlapping identical slots for the same doctor
        unique_together = ('doctor', 'start_time', 'end_time')

    def __str__(self):
        return f"Dr. {self.doctor.username}: {self.start_time.strftime('%Y-%m-%d %H:%M')} - {self.end_time.strftime('%H:%M')}"

class Booking(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'patient'}, related_name='bookings')
    slot = models.OneToOneField(AvailabilitySlot, on_delete=models.CASCADE, related_name='booking')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Track calendar sync IDs
    google_event_id_doctor = models.CharField(max_length=255, blank=True, null=True)
    google_event_id_patient = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Booking: {self.patient.username} with Dr. {self.slot.doctor.username} on {self.slot.start_time.strftime('%Y-%m-%d')}"

class GoogleCredential(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='google_credentials')
    token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    token_uri = models.CharField(max_length=255)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    scopes = models.TextField()

    def __str__(self):
        return f"Google Credentials for {self.user.username}"
