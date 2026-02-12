

# **School Management System (Django)**

A production-structured School Management System built with Django.
This system manages user identity, academic structure, enrollment workflows, and administrative control in a clean, scalable architecture.

---

## 📌 **Overview**

The Ibrahim School Management System is designed with a layered backend architecture.

The system currently supports:

* Custom role-based authentication
* Admin approval workflow
* Academic structure foundation
* Student enrollment per academic year
* Structured admin dashboard with statistics

This project follows a scalable database design approach to support future modules such as teaching assignments, attendance, exams, grading, and finance.

---

## 🛠️ **Features (Current State)**

### 🔐 Identity & Access Layer

* Custom User Model (`CustomUser`)
* UUID as primary key
* Role flags:

  * `is_student`
  * `is_teacher`
  * `is_parent`
* Unique phone number
* National ID support
* Profile image upload
* Status workflow:

  * `pending`
  * `approved`
  * `rejected`
* Rejection reason tracking
* `is_member_of_this_school` approval flag

---

### 🏫 Academic Structure (Foundation Layer)

* Academic Year model
* Department model
* Class model
* Subject model
* Clean relational hierarchy

---

### 🎓 Enrollment Layer

* Enrollment model linking:

  * Student
  * Class
  * Academic Year
* Enrollment status tracking
* Enrollment date
* Metadata:

  * `created_at`
  * `updated_at`
* Structured Django Admin configuration:

  * Filters
  * Search
  * Read-only metadata
  * Organized fieldsets

This ensures students are officially assigned to classes per academic year.

---

### 🖥️ Admin Dashboard

* Staff & superuser restricted access
* Pending registration counter
* User approval / rejection management
* Clean structured dashboard logic
* Secure bulk approval & rejection flow

---

## 🔐 **User Approval Logic (Important)**

We added a custom field inside the `CustomUser` model:

```python
is_member_of_this_school = models.BooleanField(default=False)
```

### Why?

Django automatically sets `is_active = True` after registration.
This means we cannot use `is_active` to detect users waiting for approval.

So we created **is_member_of_this_school** to track admin approval.

* `False` → User registered but **not approved yet**
* `True` → User approved by admin

Additionally:

* `status` field tracks:

  * pending
  * approved
  * rejected
* `rejection_reason` stores explanation when rejected

Example used in `admin_dashboard`:

```python
pending_count = CustomUser.objects.filter(is_member_of_this_school=False).count()
```

This count is displayed on the dashboard so admins can see how many users still need approval.

---

## 📂 Project Structure & App Logic

### 🔐 1. Accounts

**Responsibility:** Core identity and authentication system.

**Key Logic:**

* CustomUser using `AbstractUser`
* UUID-based primary key
* Role-based access flags
* Approval workflow management
* Secure login/logout flow
* Rejection reason tracking

This app forms the identity backbone of the entire system.

---

### 📐 2. Core

**Responsibility:** Global routing, shared logic, and dashboard redirection.

**Key Logic:**

* Role-based dashboard routing
* Global navigation handling
* Shared templates & layout logic
* System-wide utilities

---

### 🏫 3. Academics

**Responsibility:** School institutional structure.

**Key Logic:**

* AcademicYear
* Department
* Class
* Subject
* Structured relational mapping
* Foundation for future teaching assignment layer

This app defines the educational backbone of the system.

---

### 🎓 4. Students

**Responsibility:** Student academic lifecycle management.

**Key Logic:**

* Enrollment model
* Student ↔ Class ↔ AcademicYear linking
* Enrollment status tracking
* Clean admin management
* Academic assignment tracking

This ensures proper yearly class assignment per student.

---

###  5. Teachers 

**Responsibility:** Teacher profile and future academic allocation.

**Current State:**

* Teacher role supported in CustomUser
* Ready for Teaching Assignment layer (Phase 3)

Planned:

* Teacher → Subject → Class assignment system

---

## 📁 Folder Directory

```text
school_management/
│
├── accounts/          # CustomUser, Authentication, Approval Workflow
├── core/              # Global Views, Dashboard Routing, Shared Logic
├── academics/         # AcademicYear, Department, Class, Subject
├── students/          # Enrollment Model, Student Academic Linking
├── teachers/          # Teacher Role Structure (Assignment Layer Coming Next)
├── static/            # Tailwind CSS, JavaScript, Assets
├── templates/         # Shared HTML (base.html, dashboards, partials)
└── manage.py          # Django Project Manager
```

---

## ⚙️ **Installation & Setup**

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
* HTML, CSS, JS (Server-rendered templates)
* Tailwind CSS
* SQLite (default) / PostgreSQL (optional)
* Django messages framework
* Custom User Model + role-based permissions
* Structured multi-app architecture

---

## 📐 **Planned Next Phases**

###  Phase 3 — Teaching Assignment Layer 

* Teacher → Subject → Class → AcademicYear linking
* Core academic engine foundation

### 🗓️ Phase 4 — Timetable System

* Period scheduling
* Room allocation
* Weekly structure

### 📊 Phase 5 — Attendance System

* Per-class attendance
* Subject-based tracking
* Daily records

###  Phase 6 — Exams & Grading 

* Exam creation per subject
* Marks management
* Academic performance reports

###  Parent Linking System 

* Parent ↔ Student relationship mapping
* Parent dashboard access

### 💰 Finance Module (Future)

* Fee tracking
* Payment records
* Financial reporting

---


