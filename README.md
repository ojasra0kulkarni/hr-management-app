# HRNexus — HR Management System

## Quick Start
```bash
pip install flask reportlab pillow
python app.py
# Open http://localhost:5000
# Login: admin / admin123
```

## Features
- **Indian Payroll Engine**: PF (12% basic, capped ₹15,000), ESI (0.75% / 3.25% if gross ≤ ₹21,000), Professional Tax (Maharashtra slabs), TDS (New Tax Regime FY2024-25 with ₹75,000 std deduction, rebate u/s 87A up to ₹7L)
- **Form 16**: Part A (TDS certificate, quarterly breakdown) + Part B (salary computation, Chapter VI-A deductions)
- **Field Validation**: Email format, phone (10-15 digits), PAN (ABCDE1234F), Aadhar (12 digits), IFSC (ABCD0123456), GSTIN, Pincode
- **Image Uploads**: Logo, stamp, HR signature — shows file size before upload, max 2MB enforced
- **Employee Documents**: Upload Aadhar, PAN, degree, experience letters etc. — PDF/JPG/PNG/DOC, max 5MB per file
- **Photo Upload**: Employee photo in profile and payslip
- **Documents**: Offer, Appointment, Relieving, Experience, Increment, Warning, Termination letters

## Default Login
- Username: `admin`  Password: `admin123`
