# MainCode_firebase.py
import datetime
import sys
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
import socket
import random
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter


# =========================
# CONFIG - service account
# =========================
SERVICE_ACCOUNT_FILE = "voltify-bb595-firebase-adminsdk-fbsvc-6c67872eea.json"


# ================================================================
# 🔧 Phone normalization
# ================================================================
def normalize_phone(s: str) -> str:
    """
    Normalize input to E.164.
    - Strips non-digits, removes leading zeros.
    - Defaults to +91 for 10-digit inputs (India).
    - Keeps +<digits> if already in that format.
    """
    if not s:
        return ""
    s = s.strip()
    if s.startswith("+") and len(s) > 1 and s[1:].isdigit():
        return s
    digits = re.sub(r"\D", "", s)
    while len(digits) > 0 and digits[0] == "0":
        digits = digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    return f"+{digits}" if digits else ""


# ================================================================
# ✉ NOTIFICATION FUNCTION (generic message_body)
# ================================================================
def notify_user(user_identifier, message_body, contact=None, mode="email"):
    """
    Sends alert or OTP via email or SMS or console.
    Note: Update sender credentials and Twilio credentials to real ones for production.
    """
    try:
        if mode == "email":
            sender_email = "yourvoltifyalerts@gmail.com"  # <-- change this
            sender_pass = "your-app-password"           # <-- change this
            receiver_email = contact

            if not receiver_email:
                print("❌ Error: No receiver email provided")
                return

            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Voltify Notification"
            msg["From"] = sender_email
            msg["To"] = receiver_email
            msg.attach(MIMEText(message_body, "plain"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, sender_pass)
                server.sendmail(sender_email, receiver_email, msg.as_string())
            print(f"📧 Email sent to {receiver_email}")

        elif mode == "sms":
            account_sid = "YOUR_TWILIO_ACCOUNT_SID"   # <-- change this
            auth_token = "YOUR_TWILIO_AUTH_TOKEN"     # <-- change this
            twilio_number = "YOUR_TWILIO_NUMBER"      # <-- change this 

            if not contact:
                print("❌ Error: No phone number provided for SMS")
                return

            phone_number = normalize_phone(contact)
            if not phone_number.startswith("+") or not phone_number[1:].isdigit():
                print(f"❌ Invalid phone after normalization: {phone_number}")
                return

            try:
                print(f"📤 Sending SMS to {phone_number}... (using Twilio)")
                client = Client(account_sid, auth_token)
                message = client.messages.create(
                    body=message_body,
                    from_=twilio_number,
                    to=phone_number
                )
                print(f"✅ SMS sent successfully! (SID: {message.sid})")
            except Exception as e:
                error_msg = str(e)
                print(f"❌ SMS Failed: {error_msg}")
                if "not verified" in error_msg.lower() or "unverified" in error_msg.lower():
                    print(" → Phone number not verified in Twilio trial account")
                    print(" → Verify numbers in Twilio console")
        else:
            # console
            print("\n⚠ MESSAGE ⚠")
            print(message_body)

    except Exception as e:
        print(f"Error sending alert: {e}")


# ================================================================
# 🔒 SECURITY & DATA HELPERS
# ================================================================
def get_current_ip():
    """
    Get the current IP address of the system (local).
    Returns 'Unknown-IP' if not available.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return "Unknown-IP"


def generate_otp():
    """Generate 6-digit OTP"""
    return str(random.randint(100000, 999999))


    


# ================================================================
# Firestore helpers (wrap common operations)
# ================================================================
def get_provider_rate(db, provider):
    doc_ref = db.collection("provider_rates").document(provider)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        try:
            return float(data.get("cost_per_unit", 0))
        except Exception:
            return None
    return None


def provider_exists(db, provider):
    return db.collection("provider_rates").document(provider).get().exists


def list_providers(db):
    docs = db.collection("electricity_provider_details").get()
    providers = []
    for d in docs:
        data = d.to_dict()
        providers.append((d.id, data.get("electricity_provider", "")))
    return providers


# ================================================================
# --- SUPER ADMIN FUNCTIONS (converted to Firestore)
# ================================================================
def add_customer_unscoped(db):
    print("\n--- (Super Admin) Add New Customer ---")
    try:
        acc_no = input("Enter Account Number: ").strip()
        if not acc_no:
            print("Error: Account number cannot be empty.")
            return

        existing_customer = db.collection("electricity_customers").where(filter=FieldFilter("account_number", "==", acc_no)).limit(1).get()
        if existing_customer:
            print(f"Error: Customer with account number '{acc_no}' already exists.")
            return

        name = input("Enter Name: ")
        address = input("Enter Address: ")
        district = input("Enter District: ")
        provider = input("Enter Electricity Provider: ")
        mobile = input("Enter Mobile Number: ")

        if not db.collection("electricity_provider_details").document(provider).get().exists:
            print(f"--- WARNING --- Provider '{provider}' not found in electricity_provider_details ---")

        customer_data = {
            "account_number": acc_no,
            "name": name,
            "address": address,
            "district": district,
            "electricity_provider": provider,
            "mobile_number": mobile,
            "age": None
        }

        db.collection("electricity_customers").add(customer_data)
        print(f"Customer '{name}' added successfully.")
    except Exception as e:
        print(f"Error adding customer: {e}")


def generate_bill_unscoped(db):
    print("\n--- Generate Bill (Super Admin) ---")
    key = input("Enter Account No or Mobile No: ")
    try:
        cust = None
        query = db.collection("electricity_customers").where(filter=FieldFilter("account_number", "==", key)).limit(1).get()
        if query:
            cust = query[0].to_dict()
        else:
            query_mob1 = db.collection("electricity_customers").where(filter=FieldFilter("mobile_number", "==", key)).limit(1).get()
            if query_mob1:
                cust = query_mob1[0].to_dict()
            else:
                query_mob2 = db.collection("electricity_customers").where(filter=FieldFilter("mobile_no", "==", key)).limit(1).get()
                if query_mob2:
                    cust = query_mob2[0].to_dict()

        if not cust:
            print("Customer not found.")
            return

        acc_no = cust.get("account_number", "")
        if not acc_no:
            print("Error: Customer account number is missing in database.")
            return

        name = cust.get("name", "")
        provider = cust.get("electricity_provider", "")
        try:
            units = float(input("Enter Units Consumed (kWh): "))
        except Exception:
            print("Invalid units value.")
            return

        rate = get_provider_rate(db, provider)
        if rate is None:
            print(f"--- ERROR --- No rate found for provider '{provider}'. Please add one in the Super Admin menu.")
            return

        total = round(units * rate, 2)
        today = datetime.datetime.utcnow()

        # Determine next bill_number for this account (incremental per account)
        try:
            existing = db.collection("electricity_bills").where(filter=FieldFilter("account_number", "==", str(acc_no))).get()
            max_no = 0
            for snap in existing:
                data = snap.to_dict()
                if data is None:
                    continue
                bn = data.get("bill_number")
                if isinstance(bn, int) and bn > max_no:
                    max_no = bn
            next_bill_number = max_no + 1
        except Exception:
            next_bill_number = 1

        bill_data = {
            "account_number": acc_no,
            "no_of_units": units,
            "cost_per_unit": rate,
            "total_bill": total,
            "arrear": 0.0,
            "bill_date": today,
            "due_date": today + datetime.timedelta(days=15),
            "status": "due",
            "bill_number": next_bill_number
        }

        doc_ref = db.collection("electricity_bills").add(bill_data)
        print(f"Bill generated successfully. Bill Number: {next_bill_number}")
    except Exception as e:
        print(f"Error generating bill: {e}")


def manage_provider_rates(db):
    print("\n--- Manage Provider Rates ---")
    docs = db.collection("provider_rates").get()
    for d in docs:
        data = d.to_dict()
        print(f" {d.id}: ₹{data.get('cost_per_unit')}")
    ch = input("\n1.Add 2.Update 3.Back: ")
    if ch == "1":
        p = input("Provider (document id/name): ")
        try:
            r = float(input("Rate: "))
        except Exception:
            print("Invalid rate.")
            return
        db.collection("provider_rates").document(p).set({"electricity_provider": p, "cost_per_unit": r})
        print("Rate added.")
    elif ch == "2":
        p = input("Provider (document id/name): ")
        try:
            r = float(input("New Rate: "))
        except Exception:
            print("Invalid rate.")
            return
        doc_ref = db.collection("provider_rates").document(p)
        if doc_ref.get().exists:
            doc_ref.update({"cost_per_unit": r})
            print("Rate updated.")
        else:
            print("Provider not found.")
    else:
        return


def create_provider_admin(db):
    print("\n--- Create Provider Admin ---")
    try:
        provider = input("Enter Provider Name (this will be the document id): ").strip()
        if not provider:
            print("Provider name cannot be empty.")
            return
        admin = input("Enter Admin Name: ").strip()
        password = provider + "@123"
        doc_ref = db.collection("electricity_provider_details").document(provider)
        if doc_ref.get().exists:
            print("Admin already exists.")
            return

        doc_ref.set({
            "electricity_provider": provider,
            "admin_name": admin,
            "password": password,
            "time": None
        })
        print(f"Admin created for {provider}. Password: {password}")
    except Exception as e:
        print(f"Error: {e}")


# ================================================================
# --- PROVIDER ADMIN LOGIN (with OTP) ---
# ================================================================
def provider_login(db):
    print("\n--- Provider Admin Login ---")
    try:
        provider = input("Provider Name (document id): ").strip()
        admin = input("Admin Name: ").strip()
        password = input("Password: ").strip()

        # Look up provider doc by document id (as per your structure)
        doc_ref = db.collection("electricity_provider_details").document(provider)
        doc = doc_ref.get()
        if not doc.exists:
            print("Invalid provider or admin name.")
            return None

        data = doc.to_dict()
        stored_pass = data.get("password")
        stored_admin = data.get("admin_name")

        if admin != stored_admin:
            print("Invalid provider or admin name.")
            return None

        if password == stored_pass:
            print(f"✅ Login successful. Welcome {admin}.")
            doc_ref.update({"time": datetime.datetime.utcnow()})
            return provider
        else:
            print("⚠ Invalid password.")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None


# ================================================================
# --- PROVIDER PORTAL FUNCTIONS ---
# ================================================================
def add_customer_scoped(db, provider):
    print(f"\n--- Add Customer for {provider} ---")
    try:
        acc = input("Account No: ").strip()
        if not acc:
            print("Error: Account number cannot be empty.")
            return

        existing_customer = db.collection("electricity_customers").where(filter=FieldFilter("account_number", "==", acc)).limit(1).get()
        if existing_customer:
            print(f"Error: Customer with account number '{acc}' already exists.")
            return

        name = input("Name: ")
        addr = input("Address: ")
        dist = input("District: ")
        mob = input("Mobile: ")

        customer_data = {
            "account_number": acc,
            "name": name,
            "address": addr,
            "district": dist,
            "electricity_provider": provider,
            "mobile_number": mob,
            "age": None
        }

        db.collection("electricity_customers").add(customer_data)
        print("Customer added.")
    except Exception as e:
        print(f"Error: {e}")


def generate_bill_scoped(db, provider):
    print(f"\n--- Generate Bill for {provider} ---")
    try:
        key = input("Enter Account or Mobile: ").strip()
        cust_doc = None

        query = (db.collection("electricity_customers")
                   .where(filter=FieldFilter("account_number", "==", key))
                   .where(filter=FieldFilter("electricity_provider", "==", provider))
                   .limit(1).get())
        if query:
            cust_doc = query[0].to_dict()
        else:
            query_mob1 = (db.collection("electricity_customers")
                          .where(filter=FieldFilter("mobile_number", "==", key))
                          .where(filter=FieldFilter("electricity_provider", "==", provider))
                          .limit(1).get())
            if query_mob1:
                cust_doc = query_mob1[0].to_dict()
            else:
                query_mob2 = (db.collection("electricity_customers")
                              .where(filter=FieldFilter("mobile_no", "==", key))
                              .where(filter=FieldFilter("electricity_provider", "==", provider))
                              .limit(1).get())
                if query_mob2:
                    cust_doc = query_mob2[0].to_dict()

        if not cust_doc:
            print("Customer not found for this provider.")
            return

        acc = cust_doc.get("account_number", "")
        if not acc:
            print("Error: Customer account number is missing in database.")
            return

        rate = get_provider_rate(db, provider)
        if rate is None:
            print(f"--- ERROR --- No rate found for provider '{provider}'. Please add one.")
            return

        try:
            units = float(input("Units: "))
        except Exception:
            print("Invalid units value.")
            return

        total = round(units * rate, 2)
        today = datetime.datetime.utcnow()

        # Determine next bill_number for this account (incremental per account)
        try:
            existing = db.collection("electricity_bills").where(filter=FieldFilter("account_number", "==", str(acc))).get()
            max_no = 0
            for snap in existing:
                data = snap.to_dict()
                if data is None:
                    continue
                bn = data.get("bill_number")
                if isinstance(bn, int) and bn > max_no:
                    max_no = bn
            next_bill_number = max_no + 1
        except Exception:
            next_bill_number = 1

        bill_data = {
            "account_number": acc,
            "no_of_units": units,
            "cost_per_unit": rate,
            "total_bill": total,
            "arrear": 0.0,
            "bill_date": today,
            "due_date": today + datetime.timedelta(days=15),
            "status": "due",
            "bill_number": next_bill_number
        }

        ref = db.collection("electricity_bills").add(bill_data)
        print(f"Bill generated. Bill Number: {next_bill_number}")
    except Exception as e:
        print(f"Fatal Error: {e}")


# ================================================================
# --- CUSTOMER LOGIN (OTP before portal) ---
# ================================================================
def customer_login(db):
    print("\n--- Customer Login ---")
    try:
        acc_input = input("Account Number: ").strip()
        mob_input = input("Mobile (Password): ").strip()

        docs = db.collection("electricity_customers").where(filter=FieldFilter("account_number", "==", acc_input)).limit(1).get()

        if not docs:
            print("Login failed.")
            return None

        customer_doc = docs[0]
        row = customer_doc.to_dict()

        stored_mobile = row.get("mobile_number") or row.get("mobile_no")

        if not stored_mobile or normalize_phone(stored_mobile) != normalize_phone(mob_input):
            print("Login failed.")
            return None

        otp = generate_otp()
        notify_user(row.get('name', 'user'), f"Your Voltify OTP is: {otp}", contact=stored_mobile, mode="sms")
        entered = input("Enter OTP: ").strip()

        if entered == otp:
            print(f"✅ Welcome {row.get('name', 'user')}!")
            return row.get("account_number")
        else:
            print("❌ Incorrect OTP.")
            return None
    except Exception as e:
        print(f"An error occurred during login: {e}")
        return None


# ================================================================
# --- BILL VIEW & PAYMENT (Firestore) ---
# ================================================================
def view_my_bills(db, acc):
    try:
        bills = (
            db.collection("electricity_bills")
            .where(filter=FieldFilter("account_number", "==", str(acc)))
            .order_by("bill_date", direction=firestore.Query.DESCENDING)
            .get()
        )
    except Exception as e:
        print("Note: Bills fetched without date ordering (index may be required).")
        bills = db.collection("electricity_bills").where(filter=FieldFilter("account_number", "==", str(acc))).get()
        bills_list = sorted(list(bills), key=lambda x: x.to_dict().get("bill_date", datetime.datetime.min), reverse=True)
        bills = bills_list

    if not bills:
        print("\n--- You have no bills on record. ---")
        return

    print("\n--- Your Bills ---")
    for b in bills:
        if hasattr(b, "to_dict"):
            d = b.to_dict()
            bill_id = b.id
        else:
            d = b
            bill_id = d.get("id", "unknown")
        date = d.get("bill_date")
        date_str = date.strftime("%Y-%m-%d") if isinstance(date, datetime.datetime) else str(date)
        bn = d.get("bill_number")
        if isinstance(bn, int):
            label = f"Bill {bn}"
        else:
            label = f"Bill {bill_id}"
        print(f"{label} | Date: {date_str} | Units: {d.get('no_of_units')} | Amount: ₹{d.get('total_bill')} | Status: {d.get('status')}")


def pay_bill(db, acc):
    print("\n--- Pay a Bill ---")
    bills = (
        db.collection("electricity_bills")
        .where(filter=FieldFilter("account_number", "==", str(acc)))
        .where(filter=FieldFilter("status", "==", "due"))
        .get()
    )
    if not bills:
        print("No due bills.")
        return

    print("Available bills to pay:")
    bill_map = {}
    for b in bills:
        d = b.to_dict()
        bn = d.get("bill_number")
        amount = d.get('total_bill')
        if isinstance(bn, int):
            bill_map[bn] = b.id
            print(f"Bill {bn} - Amount: ₹{amount}")
        else:
            print(f"Bill {b.id} - Amount: ₹{amount}")

    sel = input("Enter Bill Number to pay: ").strip()
    if not sel.isdigit():
        print("Invalid bill number.")
        return
    sel_num = int(sel)

    # Find matching due bill by bill_number
    target = (
        db.collection("electricity_bills")
        .where(filter=FieldFilter("account_number", "==", str(acc)))
        .where(filter=FieldFilter("status", "==", "due"))
        .where(filter=FieldFilter("bill_number", "==", sel_num))
        .limit(1)
        .get()
    )
    if not target:
        print("Bill number not found among due bills.")
        return
    bill_snap = target[0]
    bill_ref = db.collection("electricity_bills").document(bill_snap.id)
    bill_doc = bill_snap
    bill_data = bill_doc.to_dict()

    if bill_data.get("status") != "due":
        print("This bill is not due or already paid.")
        return

    total = float(bill_data.get("total_bill", 0.0))
    amount_usd = round(total / 80.0, 2)

    print("\n========================================================")
    print("PAYMENT REQUIRED")
    bn = bill_data.get("bill_number")
    if isinstance(bn, int):
        print(f"Bill Number: {bn}")
    else:
        print(f"Bill ID: {bill_ref.id}")
    print(f"Amount: ₹{total} (approx ${amount_usd} USD)")
    print("\nPlease open the following URL in your browser to complete the payment:")
    print(f"\nhttp://localhost:3000/pay.html?bill_id={bill_ref.id}&amount={amount_usd}&acc_no={acc}")
    print("\nAfter paying, mark the bill as paid by confirming here.")
    confirm = input("Mark as paid now? (y/n): ").lower()
    if confirm == "y":
        bill_ref.update({"status": "paid", "paid_on": datetime.datetime.utcnow()})
        print("Payment recorded. Bill marked as paid.")
    else:
        print("Payment not recorded here. Complete payment on the payment page.")
    print("========================================================\n")


# ================================================================
# --- BILL DUE REMINDER NOTIFICATION FEATURE ---
# ================================================================
def send_due_bill_notifications(db):
    """
    Checks all bills and sends reminders via SMS and email for upcoming or overdue bills.
    """
    today = datetime.datetime.utcnow()
    bills_ref = db.collection("electricity_bills").where(filter=FieldFilter("status", "==", "due")).get()

    print("\n--- Checking for due bill reminders ---")
    found_due_bills = False
    for b in bills_ref:
        found_due_bills = True
        data = b.to_dict()
        due_date = data.get("due_date")
        if not due_date:
            continue

        if hasattr(due_date, "to_datetime"):
            due_date = due_date.to_datetime()

        acc_no = data.get("account_number")
        total = data.get("total_bill", 0.0)
        days_left = (due_date - today).days

        message = ""
        if 0 <= days_left <= 2:
            message = f"💡 Reminder: Your electricity bill of ₹{total} is due on {due_date.strftime('%Y-%m-%d')}."
        elif days_left < 0:
            message = f"⚠️ Your electricity bill of ₹{total} was due on {due_date.strftime('%Y-%m-%d')}. Please pay immediately."
        else:
            continue

        cust_docs = db.collection("electricity_customers").where(filter=FieldFilter("account_number", "==", str(acc_no))).limit(1).get()
        if not cust_docs:
            print(f"  - Warning: Could not find customer for account {acc_no}.")
            continue

        cust = cust_docs[0].to_dict()
        name = cust.get("name", "Customer")
        mobile = cust.get("mobile_number") or cust.get("mobile_no")
        email = cust.get("email", None)

        if mobile:
            notify_user(name, message, contact=mobile, mode="sms")
        if email:
            notify_user(name, message, contact=email, mode="email")

        print(f"  📤 Reminder sent to {name} for account {acc_no}")

    if not found_due_bills:
        print("--- No due bills found needing a reminder at this time. ---")


# ================================================================
# --- PORTALS (OTP-gated; no duplicate main options)
# ================================================================
def run_customer_portal(db):
    acc = customer_login(db)
    if not acc:
        return
    while True:
        print("\n--- Customer Portal ---")
        print("1.View Bills 2.Pay Bill 3.Logout")
        ch = input("Choice: ")
        if ch == "1":
            view_my_bills(db, acc)
        elif ch == "2":
            pay_bill(db, acc)
        elif ch == "3":
            break
        else:
            print("Invalid choice.")


def run_provider_portal(db):
    prov = provider_login(db)
    if not prov:
        return
    while True:
        print(f"\n--- Provider Portal [{prov}] ---")
        print("1.Add Customer 2.Generate Bill 3.List My Customers 4.Logout")
        ch = input("Choice: ")
        if ch == "1":
            add_customer_scoped(db, prov)
        elif ch == "2":
            generate_bill_scoped(db, prov)
        elif ch == "3":
            print(f"\nCustomers for provider: {prov}")
            docs = db.collection("electricity_customers").where(filter=FieldFilter("electricity_provider", "==", prov)).limit(50).get()
            for d in docs:
                c = d.to_dict()
                print(f" - {c.get('account_number')} | {c.get('name')} | {c.get('mobile_number')}")
        elif ch == "4":
            break
        else:
            print("Invalid choice.")


def run_super_admin_portal(db):
    while True:
        print("\n--- Super Admin Portal ---")
        print("1.Add Customer 2.Generate Bill 3.Manage Rates 4.Create Admin 5.List Providers 6.Logout")
        ch = input("Choice: ")
        if ch == "1":
            add_customer_unscoped(db)
        elif ch == "2":
            generate_bill_unscoped(db)
        elif ch == "3":
            manage_provider_rates(db)
        elif ch == "4":
            create_provider_admin(db)
        elif ch == "5":
            print("\nProviders (document_id -> electricity_provider):")
            provs = list_providers(db)
            for pid, pname in provs:
                print(f" - {pid} -> {pname}")
        elif ch == "6":
            break
        else:
            print("Invalid choice.")


# ================================================================
# --- MAIN (initialize Firebase and seed data) ---
# ================================================================
def main():
    try:
        print("Initializing Firebase Firestore...")
        cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)

        db = firestore.client()
        print("Connected to Firestore.")

    except FileNotFoundError:
        print(f"❌ FATAL ERROR: Service account key not found at '{SERVICE_ACCOUNT_FILE}'")
        sys.exit(1)
    except Exception as e:
        print(f"Fatal Error during initialization: {e}")
        sys.exit(1)

    while True:
        print("\n===== VOLTIFY MAIN PORTAL =====")
        print("1.Customer Login\n2.Provider Admin Login\n3.Super Admin Login\n4.Send Bill Reminders\n5.Exit")
        ch = input("Choice: ")
        if ch == "1":
            run_customer_portal(db)
        elif ch == "2":
            run_provider_portal(db)
        elif ch == "3":
            run_super_admin_portal(db)
        elif ch == "4":
            send_due_bill_notifications(db)
        elif ch == "5":
            print("Exiting.")
            sys.exit(0)
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
