import os
import smtplib
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Gmail config
GMAIL_USER = "jesmine0820@gmail.com"
GMAIL_PASSWORD = "vhkf batb xhyk ftzl"
BARCODE_DIR = "database/barcode_generated"
CSV_PATH = "dataset/dataset.csv"

def send_email_with_barcode(to_email, subject, body, attachment_path):
    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = to_email
        msg["Subject"] = subject

        # Email body
        msg.attach(MIMEText(body, "plain"))

        # Attach barcode if exists
        if os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition",
                                f"attachment; filename={os.path.basename(attachment_path)}")
                msg.attach(part)
        else:
            print(f"[WARN] Barcode not found: {attachment_path}")
            return False

        # Connect to Gmail SMTP
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)

        server.sendmail(GMAIL_USER, to_email, msg.as_string())
        server.quit()

        print(f"[INFO] Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email to {to_email}: {e}")
        return False


def send_graduation_tickets(csv_path=CSV_PATH, barcode_dir=BARCODE_DIR):
    df = pd.read_csv(csv_path)

    for _, student in df.iterrows():
        # Skip if no email column or empty
        if "email" not in student or pd.isna(student["email"]):
            continue

        student_id = str(student["StudentID"])
        name = student["Name"].replace(" ", "_")
        email = student["email"]

        barcode_file = os.path.join(barcode_dir, f"{student_id}_{name}.png")

        subject = "🎓 Graduation Ceremony Ticket"
        body = f"""
            Dear {student['Name']},

            Congratulations on your upcoming graduation! 🎉

            Attached is your official graduation ceremony ticket. 
            Please present the barcode at the entrance.

            Best regards,
            Graduation Committee
        """

        send_email_with_barcode(email, subject, body, barcode_file)