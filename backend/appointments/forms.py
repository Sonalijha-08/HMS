# pyrefly: ignore [missing-import]
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from .models import CustomUser, DoctorProfile, PatientProfile, AvailabilitySlot
from datetime import datetime, date

class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Enter your password',
        'class': 'form-input'
    }))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Confirm your password',
        'class': 'form-input'
    }))
    role = forms.ChoiceField(choices=CustomUser.ROLE_CHOICES, widget=forms.RadioSelect(attrs={
        'class': 'role-radio'
    }))
    specialization = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'e.g. Cardiology, Pediatrics',
        'class': 'form-input'
    }))
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={
        'type': 'date',
        'class': 'form-input'
    }))

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Enter username', 'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Enter email address', 'class': 'form-input'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'First Name', 'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last Name', 'class': 'form-input'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        role = cleaned_data.get("role")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")

        if role == 'doctor' and not cleaned_data.get('specialization'):
            self.add_error('specialization', "Specialization is required for doctors.")
        
        if role == 'patient' and not cleaned_data.get('date_of_birth'):
            self.add_error('date_of_birth', "Date of birth is required for patients.")

        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            role = self.cleaned_data.get('role')
            if role == 'doctor':
                DoctorProfile.objects.create(
                    user=user,
                    specialization=self.cleaned_data.get('specialization')
                )
            elif role == 'patient':
                PatientProfile.objects.create(
                    user=user,
                    date_of_birth=self.cleaned_data.get('date_of_birth')
                )
        return user

class AvailabilityForm(forms.Form):
    slot_date = forms.DateField(widget=forms.DateInput(attrs={
        'type': 'date',
        'class': 'form-input'
    }))
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={
        'type': 'time',
        'class': 'form-input'
    }))
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={
        'type': 'time',
        'class': 'form-input'
    }))

    def clean(self):
        cleaned_data = super().clean()
        slot_date = cleaned_data.get('slot_date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if slot_date and start_time and end_time:
            # Combine date and time
            start_dt = datetime.combine(slot_date, start_time)
            end_dt = datetime.combine(slot_date, end_time)

            if start_dt < datetime.now():
                self.add_error('slot_date', "Availability slot cannot be set in the past.")

            if end_dt <= start_dt:
                self.add_error('end_time', "End time must be after the start time.")

            cleaned_data['start_datetime'] = start_dt
            cleaned_data['end_datetime'] = end_dt

        return cleaned_data
