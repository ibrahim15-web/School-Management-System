# School Management System (Django)
 
A school management platform built with Django, covering authentication, role-based dashboards, attendance, grades, timetabling, and notifications — designed for real use by administrators, teachers, students, and parents.
 
Backed by **111 passing tests** across the core apps.
 
---
 
## What it does
 
- **Role-based accounts** with an admin approval workflow (students, teachers, parents, and admins all register and wait for approval before gaining access)
- **Attendance tracking** for both students and teachers, with daily marking, editing, and 7-day trend charts on the admin dashboard
- **Grading** per subject, exam type, and term, with automatic letter-grade calculation
- **Timetabling** per class, with teacher and student views
- **Parent accounts** linked to one or more children, with attendance and grade visibility
- **Announcements and in-app notifications** targeted by role
- **PDF report cards** generated per student
- **A full admin panel** for managing students, teachers, classes, subjects, departments, academic years, terms, and users
---
 
## Tech stack
 
- Python 3 / Django 5.2.5
- Server-rendered Django templates (no frontend framework)
- Tailwind and CSS + Alpine.js
- Chart.js for attendance charts
- SQLite (default), easily swapped for PostgreSQL
- ReportLab for PDF generation
---
 
## Installation and Setup
 
### 1. Clone the repository
 
```bash
git clone https://github.com/your-username/school-management.git
cd school-management
```
 
### 2. Create a virtual environment
 
```bash
python -m venv env
```
 
### 3. Activate environment
 
Windows:
 
```bash
env\Scripts\activate
```
 
macOS/Linux:
 
```bash
source env/bin/activate
```
 
### 4. Install dependencies
 
```bash
pip install -r requirements.txt
```
 
### 5. Set up environment variables
 
Copy `.env.example` to `.env` and fill in your own values:
 
```bash
cp .env.example .env
```
 
### 6. Run migrations
 
```bash
python manage.py makemigrations
python manage.py migrate
```
 
### 7. Create superuser
 
```bash
python manage.py createsuperuser
```
 
### 8. Run the server
 
```bash
python manage.py runserver
```
 
---
 
## Project Structure
 
```text
school_management/
│
├── accounts/          # CustomUser, authentication, approval workflow
├── core/               # Home page, admin dashboard, announcements, notifications
├── academics/          # Academic years, terms, departments, subjects, classes, grades, timetable
├── students/           # Enrollment, parent-student linking, student & parent dashboards
├── teachers/           # Attendance, grade entry, schedule, analytics
├── admin_panel/        # Full admin management views
├── static/             # Css, JavaScript, assets
├── templates/          # HTML templates
└── manage.py
```
 
---
 
## Planned Next Phases If Needed In The Future
 
- Finance module for fee tracking and payment records
- Advanced reporting and data export for attendance and grades
- Exam scheduling and exam room assignment
- Email-based notification delivery alongside in-app notifications
---
 
## Notes on Production Readiness
 
This project is currently configured for local development. Before deploying, the following need attention (see Django's `python manage.py check --deploy` for the full list):
 
- Set `ALLOWED_HOSTS` to your actual domain(s)
- Generate a strong `SECRET_KEY` (not the auto-generated dev key)
- Enable `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and `SECURE_HSTS_SECONDS` once HTTPS is in place
- Swap SQLite for PostgreSQL in any environment with ephemeral or non-persistent storage
 