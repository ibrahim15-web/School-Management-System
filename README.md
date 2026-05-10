# School Management System (Django)

A production-structured School Management System built with Django.
This system manages user identity, academic structure, enrollment workflows, attendance tracking, grading, timetabling, announcements, and in-app notifications — all within a clean, scalable multi-app architecture.

---

## 📌Overview

The School Management System is designed with a layered backend architecture and server-rendered templates. It is built for real-world use by school administrators, teachers, students, and parents.

The system currently supports:

- Custom role-based authentication with an admin approval workflow
- Academic structure management across departments, classes, subjects, and terms
- Student enrollment per academic year with capacity enforcement
- Teacher-to-class-subject assignment management
- Daily student attendance marking and editing by teachers
- Daily teacher attendance marking by administrators
- Grade entry per subject, exam type, and term with automatic letter grade calculation
- Weekly timetable management per class
- Parent-student account linking
- School-wide and role-targeted announcements
- In-app notification system for attendance, grades, and announcements
- A structured admin dashboard with live statistics and Chart.js attendance charts

---

## 🛠️Features

### 🔐Identity and Access Layer

- Custom User Model built on `AbstractUser`
- UUID as primary key across all models
- Role flags: `is_student`, `is_teacher`, `is_parent`, `is_admin`
- Unique phone number and national ID fields
- Profile image and national ID image uploads
- Account status workflow: `pending`, `approved`, `rejected`
- Rejection reason tracking
- `is_member_of_this_school` approval flag to separate business approval from Django's `is_active`
- Secure login, logout, forgot password, OTP verification, and password reset flows
- In-app waiting approval page for newly registered users

---

### ▶Admin Approval Workflow

A custom field `is_member_of_this_school` controls whether a registered user can access the system. Django's default `is_active` alone cannot serve this purpose because Django sets it to `True` after registration by default.

- `False` means the user has registered but is not yet approved
- `True` means the user has been approved by an administrator

Administrators can approve or reject pending registrations individually or in bulk directly from the admin dashboard. Approvals include role assignment. Rejections require a mandatory written reason. All actions trigger email notifications to the user.

```python
pending_count = CustomUser.objects.filter(is_member_of_this_school=False).count()
```

---

### 🏫Academic Structure

- Academic Year model with a `is_current` flag (only one active year at a time)
- Term model with date range validation within the academic year
- Department model for grouping subjects and classes
- Subject model with unique codes and optional department assignment
- Class model per academic year with capacity enforcement and subject assignment
- Teaching Assignment model linking one teacher to one subject in one class for one year
- Duplicate assignment prevention via database constraints

---

### 🎓Enrollment Layer

- Enrollment model connecting students to classes per academic year
- Business rule enforcement at the model level:
  - Student must be approved and a member of the school
  - One enrollment per student per academic year
  - Class capacity cannot be exceeded
  - Class must belong to the correct academic year
- Enrollment status tracking: `active`, `withdrawn`, `graduated`
- Enrollment date recorded automatically

---

### ✔Attendance System

Student attendance is marked by teachers per class per day. Teacher attendance is marked by administrators. Both support editing of previously saved records.

- `Attendance` model in the `teachers` app for student attendance
- `TeacherAttendance` model for daily staff presence
- Both models use `update_or_create` to support editing without duplicate entries
- Unique constraints prevent double entries per student/teacher per date
- Analytics layer (`teachers/analytics.py`) provides:
  - Last 7 days attendance grouped by date for Chart.js
  - Today's present/absent counts and percentage
  - Separate analytics for student and teacher attendance
- Admin dashboard displays both student and teacher attendance charts and live summaries

---

### 💯Grading System

- `Grade` model in the `academics` app
- Grades are scoped to student, subject, class, academic year, exam type, and optional term
- Exam types: Quiz, Assignment, Midterm, Final Exam
- Automatic `percentage` and `letter_grade` properties:
  - 90 and above: A
  - 80 and above: B
  - 70 and above: C
  - 60 and above: D
  - Below 60: F
- Teachers enter grades per assignment per class with a configurable max score
- Students and parents see all recorded grades on their dashboards
- Live letter grade preview shown to teachers as they type scores

---

### 📰Timetable System

- `TimetableSlot` model linked to class, subject, optional teacher, academic year, day, and time
- Days supported: Monday through Saturday
- Unique constraint prevents double-booking a class at the same time slot
- Administrators build timetables via the admin panel
- Teachers view their personal weekly schedule
- Students view their class timetable on their dashboard

---

### 💬Announcements System

- `Announcement` model with audience targeting: Everyone, Students, Teachers, Parents, Staff
- Pinned announcements appear at the top for all targeted users
- Administrators can create, delete, pin, and unpin announcements
- Announcements are displayed on the home page and relevant dashboards based on the logged-in user's role
- In-app notifications are sent automatically to all targeted users when a new announcement is posted

---

### 🔔Notification System

- `Notification` model with types: Attendance, Grade, Announcement, General
- Notifications are created automatically when:
  - A teacher marks a student's attendance
  - A teacher enters a grade for a student
  - An administrator posts an announcement
  - Parents of enrolled students receive copies of their child's attendance and grade notifications
- Unread notification count displayed in the navigation bar for all authenticated users
- Users can mark all notifications as read from the notification list page
- A `Notification.send()` class method centralizes all notification creation

---

### 🖥️Admin Dashboard

- Staff and superuser restricted access
- Live clock display
- Today's student and teacher attendance summary cards with percentage and progress bars
- Last 7 days attendance charts for both students and teachers using Chart.js
- Pending registration table with search, sort, and time filter
- Bulk approve and bulk reject with mandatory rejection reason via modal
- Role assignment enforced before approval
- All actions are processed via a single JSON API endpoint with full transaction safety
- Quick action links to all management sections

---

### 📺Role-Based Dashboards

Each user role has a dedicated dashboard:

- Administrator: Full system overview, pending registrations, attendance charts, quick action links
- Teacher: Teaching assignments, student counts, attendance marking, grade entry, weekly schedule
- Student: Enrolled class, subjects, teachers, attendance history, grades, weekly timetable, announcements
- Parent: All linked children with enrollment status, attendance summary, grades, and today's presence status

---

### 📐User Management (Admin Panel)

The `admin_panel` app provides a full management interface for administrators:

- Student management: list, assign class, change class, remove from class
- Teacher management: list, assign subject-class combinations, remove assignments
- Class management: create, view detail, update capacity, delete, manage subjects
- Subject management: create, edit, delete
- Department management: create, edit, delete
- Academic year management: create, edit, set as current, delete
- Term management: create, edit, delete with date range validation
- User management: search, filter by role and status, view detail, edit, toggle active, change role, delete
- Parent management: list, link students to parent accounts, remove links
- Timetable management: create slots, filter by class, delete slots

---

## 🔧Tech Stack

- Python 3
- Django 5.2.5
- HTML, CSS, JavaScript (server-rendered templates, no frontend framework)
- Tailwind CSS (Play CDN)
- Alpine.js 3.x (reactive UI components)
- Chart.js (attendance charts)
- Font Awesome 6.4 (icons)
- SQLite (default) / PostgreSQL (optional)
- Django messages framework
- Custom User Model with UUID primary keys
- Multi-app architecture

---

## 🖇Project Structure and App Logic

### 📧1. Accounts

Responsibility: Core identity and authentication system.

Key logic:
- CustomUser using `AbstractUser` with UUID primary key
- Role-based access flags and approval workflow
- Secure login, logout, password reset, and profile update flows
- National ID and profile image handling

This app forms the identity backbone of the entire system.

---

### 📏2. Core

Responsibility: Global routing, shared views, announcements, and notifications.

Key logic:
- Home page with live statistics for all user roles
- Admin dashboard with attendance analytics and pending registration management
- Single JSON API endpoint for approving and rejecting registrations
- Announcement model, views, and audience targeting
- Notification model with a centralized `send()` factory method
- Context processor that injects unread notification count into all templates

---

### 🏫3. Academics

Responsibility: School institutional structure and academic records.

Key logic:
- AcademicYear, Term, Department, Subject, Class models
- TeachingAssignment model with full validation
- Grade model with automatic percentage and letter grade calculation
- TimetableSlot model for weekly class scheduling

---

### 🎓4. Students

Responsibility: Student academic lifecycle and parent linking.

Key logic:
- Enrollment model with business rule validation at the model level
- ParentStudent model linking parent accounts to student accounts
- Student dashboard view with attendance, grades, timetable, and announcements
- Parent dashboard view showing all linked children

---

### 5. Teachers

Responsibility: Attendance tracking, grade entry, schedule, and analytics.

Key logic:
- Attendance model for student attendance records
- TeacherAttendance model for staff attendance records
- Analytics module providing data for admin dashboard charts
- Teacher dashboard, attendance marking, grade entry, and schedule views

---

### 📠6. Admin Panel

Responsibility: Administrator management of all school entities.

Key logic:
- Full CRUD views for students, teachers, classes, subjects, departments, academic years, terms, users, parents, and timetable slots
- Role change and account activation/deactivation
- User search and filtering with pagination

---

## 📁Folder Directory

```text
school_management/
│
├── accounts/          # CustomUser, Authentication, Approval Workflow
├── core/              # Home, Admin Dashboard, Announcements, Notifications
├── academics/         # AcademicYear, Term, Department, Subject, Class, TeachingAssignment, Grade, TimetableSlot
├── students/          # Enrollment, Parent-Student Link, Student & Parent Dashboards
├── teachers/          # Student & Teacher Attendance, Grade Entry, Schedule, Analytics
├── admin_panel/       # Full Admin Management Views (Students, Teachers, Classes, Users, Timetable, etc.)
├── static/            # Tailwind CSS, JavaScript, Assets
├── templates/         # HTML Templates (base.html, dashboards, partials)
└── manage.py          # Django Project Manager
```

---

## ⚙️Installation and Setup

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

### 5. Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create superuser

```bash
python manage.py createsuperuser
```

### 7. Run the server

```bash
python manage.py runserver
```

---

## 🔧 **Tech Stack**

* **Python 3**
* **Django**
* HTML, CSS, JS
* SQLite (default) / PostgreSQL (optional)
* Django messages framework
* Custom User Model + permissions

---

## 📐 **Future Enhancements**

* Student ID cards
* Classes & subjects
* Attendance system
* Fee management
* API endpoints
* Push notifications

---
