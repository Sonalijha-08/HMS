# pyrefly: ignore [missing-import]
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('doctor/dashboard/', views.doctor_dashboard_view, name='doctor_dashboard'),
    path('patient/dashboard/', views.patient_dashboard_view, name='patient_dashboard'),
    path('book/<int:slot_id>/', views.book_appointment_view, name='book_appointment'),
    path('oauth/init/', views.google_auth_init_view, name='google_auth_init'),
    path('oauth/callback/', views.google_auth_callback_view, name='google_auth_callback'),
]
