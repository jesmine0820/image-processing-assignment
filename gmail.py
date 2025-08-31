import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Gmail configuration
GMAIL_USER = "jesmine0820@gmail.com"
GMAIL_PASSWORD = "vhkf batb xhyk ftzl"

def send_email(to_email, subject, body):
    try:
        # create email
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        # connect to Gmail SMTP
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)

        server.sendmail(GMAIL_USER, to_email, msg.as_string())
        server.quit()

        print(f"[INFO] Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False
