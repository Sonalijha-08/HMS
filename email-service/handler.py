import sys
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(event):
    # Parse event body
    body_str = event.get('body', '{}')
    if isinstance(body_str, str):
        try:
            body = json.loads(body_str)
        except Exception:
            body = {}
    else:
        body = body_str
        
    trigger_type = body.get('trigger_type')
    recipient_email = body.get('recipient_email')
    data = body.get('data', {})
    
    # SMTP configuration
    smtp_host = body.get('smtp_host', 'localhost')
    smtp_port = int(body.get('smtp_port', 1025))  # Default local mock SMTP port
    smtp_user = body.get('smtp_user', '')
    smtp_password = body.get('smtp_password', '')
    
    if not recipient_email:
        return {
            "statusCode": 400,
            "headers": { "Content-Type": "application/json" },
            "body": json.dumps({"error": "recipient_email is required"})
        }
        
    # Compose email based on trigger_type
    subject = ""
    message_content = ""
    
    if trigger_type == 'SIGNUP_WELCOME':
        subject = "Welcome to Hospital Management System!"
        username = data.get('username', 'User')
        role = data.get('role', 'patient')
        message_content = f"""Dear {username},

Welcome to the Hospital Management System! 

Your registration as a {role.upper()} was successful. You can now access your dashboard to manage appointments and calendar syncs.

Thank you for choosing our platform.

Best regards,
HMS Medical Team
"""
    elif trigger_type == 'BOOKING_CONFIRMATION':
        subject = "Appointment Booking Confirmation"
        patient_name = data.get('patient_name', 'Patient')
        doctor_name = data.get('doctor_name', 'Doctor')
        slot_time = data.get('slot_time', 'Scheduled Time')
        message_content = f"""Dear User,

This email confirms that your medical appointment has been successfully scheduled.

Appointment Details:
- Doctor: Dr. {doctor_name}
- Patient: {patient_name}
- Date & Time Slot: {slot_time}

Your Google Calendar has been synchronized with this appointment. If you need to make changes, please log in to your HMS dashboard.

Best regards,
HMS Medical Team
"""
    else:
        return {
            "statusCode": 400,
            "headers": { "Content-Type": "application/json" },
            "body": json.dumps({"error": f"Invalid trigger type: {trigger_type}"})
        }
        
    try:
        # Create message container
        msg = MIMEMultipart()
        msg['From'] = smtp_user if smtp_user else "hms@example.com"
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(message_content, 'plain'))
        
        # Connect and send via SMTP
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=5)
        if smtp_user and smtp_password:
            server.starttls()
            server.login(smtp_user, smtp_password)
        server.sendmail(msg['From'], recipient_email, msg.as_string())
        server.quit()
        
        return {
            "statusCode": 200,
            "headers": { "Content-Type": "application/json" },
            "body": json.dumps({
                "message": "Email sent successfully!",
                "trigger": trigger_type,
                "to": recipient_email,
                "details": f"Sent via SMTP server {smtp_host}:{smtp_port}"
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": { "Content-Type": "application/json" },
            "body": json.dumps({
                "error": "Failed to send email", 
                "details": str(e),
                "trigger": trigger_type,
                "recipient": recipient_email
            })
        }

if __name__ == '__main__':
    # Read event JSON from standard input
    try:
        input_data = sys.stdin.read()
        event = json.loads(input_data) if input_data else {}
        response = send_email(event)
        print(json.dumps(response))
    except Exception as ex:
        err_response = {
            "statusCode": 500,
            "headers": { "Content-Type": "application/json" },
            "body": json.dumps({"error": "Unhandled Python script exception", "details": str(ex)})
        }
        print(json.dumps(err_response))
