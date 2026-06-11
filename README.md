# ⚡ Voltify — Automated Utility Billing & Ledger System

Voltify is a Python-based utility billing engine that handles automated monthly ledger updates, digital wallet deductions, and late-payment penalty calculations. It uses a **Google Cloud Firestore** NoSQL database for secure data persistence and integrates the **Twilio API** for programmatic out-of-band One-Time Password (OTP) user authentication.

## 🚀 Core Features
* **Role-Based Access Control:** Distinct, secure portal loops for Super Admins, Provider Admins, and Customers.
* **Automated Ledger Logic:** Deterministic balance deductions, grace period simulations (5-day limits), and automatic arrear/penalty updates.
* **Cloud Database:** Real-time data syncing and schema-less document storage using Google Cloud Firestore.
* **OTP Security:** SMS-based two-factor authentication via Twilio.
* **Automated Notifications:** Email and SMS alert dispatchers for upcoming and overdue bills.

## 🛠️ Tech Stack
* **Language:** Python 3.13
* **Database:** Google Cloud Firestore (`firebase-admin`)
* **External APIs:** Twilio (SMS/OTP), `smtplib` (Email)
* **Environment Management:** `python-dotenv`

## ⚙️ Local Setup & Installation

**1. Clone the repository**
```bash
git clone (https://github.com/Hardik-Dot-Jain/Voltify.git)
cd Voltify
