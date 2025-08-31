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

def send_qrcode(student_id, csv_path="dataset/dataset.csv", qr_dir="database/QR_codes"):
    try:
        df = pd.read_csv(csv_path)
        student_data = df[df["StudentID"] == student_id]
        
        if student_data.empty:
            print(f"[ERROR] Student with ID {student_id} not found in dataset")
            return False

        student = student_data.iloc[0]
        name = student["Name"]
        email = student.get("email", "")
        
        if not email:
            print(f"[ERROR] No email address found for student {student_id}")
            return False
    
        qr_filename1 = f"{student_id}.png"
        qr_filename2 = f"{student_id}_{name.replace(' ', '_')}.png"
        
        qr_path = None
        
        if os.path.exists(os.path.join(qr_dir, qr_filename1)):
            qr_path = os.path.join(qr_dir, qr_filename1)
        elif os.path.exists(os.path.join(qr_dir, qr_filename2)):
            qr_path = os.path.join(qr_dir, qr_filename2)
        else:
            print(f"[ERROR] QR code not found for student {student_id}")
            return False
        
        subject = "🎓 Your Graduation QR Code"
        body = f"""
            Dear {name},

            Congratulations on your upcoming graduation! 🎉

            Attached is your personalized QR code for the graduation ceremony. 
            Please present this QR code at the entrance for verification.

            Important Details:
            - Student ID: {student_id}
            - Name: {name}
            - Faculty: {student.get('Faculty', 'N/A')}
            - Course: {student.get('Course', 'N/A')}

            Please keep this QR code safe and bring it with you to the ceremony.

            Best regards,
            Graduation Committee
        """

        success = send_email_with_barcode(email, subject, body, qr_path)
        
        if success:
            print(f"[INFO] QR code email sent successfully to {name} ({email})")
        else:
            print(f"[ERROR] Failed to send QR code email to {name} ({email})")
        
        return success
        
    except Exception as e:
        print(f"[ERROR] Failed to send QR code for student {student_id}: {e}")
        return False