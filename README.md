# airtribe-bel_c20

Repository for Airtribe assignments, batch C20 for Backend-Python.

## Projects

- [devtrack](./devtrack): A backend API for tracking engineering issues. Engineers report bugs, assign priorities, and track status similar to a stripped-down GitHub Issues.

## Prerequisites

- Python 3.12+

## Setup

1. Clone the repository:
```bash
git clone https://github.com/harshavvs/airtribe-bel_c20.git
```

2. Create virtual environment:
```bash
python -m venv .venv
```

3. Activate virtual environment:
```bash
# for windows
.venv\Scripts\activate

# for mac and linux
source .venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Go to specified project directory and run the server:
```bash
cd devtrack
python manage.py runserver
```

6. Check the server at `http://localhost:8000/`

## API Endpoints

### Reporters
- **GET `/api/reporters/`**: 
  - Retrieves a list of all reporters.
  - Query Parameter: `id` (Optional) - Returns a single reporter if an ID is provided.
- **POST `/api/reporters/`**:
  - Creates a new reporter.
  - Body: `{"name": "Full Name", "email": "email@example.com"}`.

### Issues
- **GET `/api/issues/`**:
  - Retrieves a list of all issues.
  - Query Parameter: `id` (Optional) - Returns a single issue if an ID is provided.
  - Query Parameter: `status` (Optional) - Filters issues by status (`open`, `in_progress`, `resolved`, `closed`).
- **POST `/api/issues/`**:
  - Creates a new issue.
  - Body: `{"title": "Issue Summary", "description": "Details", "status": "open", "priority": "high", "reporter": "Reporter Name/ID"}`.
  - Based on the `priority` provided (`critical`, `low`, or other), it instantiates the corresponding class (`CriticalIssue`, `LowPriorityIssue`, or `Issue`).

## Design Decision

### Plain Python OOP with JSON Storage
Instead of using the Django ORM and a traditional database (like SQLite or PostgreSQL), I decided to implement the domain logic using **Plain Python OOP classes** and **JSON file storage**. 

**Why?**
This decision was made to fulfill the requirement of keeping the project beginner-friendly and avoiding the overhead of database migrations. It demonstrates core OOP principles (inheritance, encapsulation, and polymorphism) and basic file I/O operations while still providing a functional and persistent API using the Django REST Framework. This approach makes the code easier to reason about for someone learning basic Python and API development without getting bogged down in database-specific configurations.
