# airtribe-bel_c20

Repository for Airtribe assignments, batch C20 for Backend-Python.

## Learning Projects

1. [sorting](sort_1.py): A simple Python script that implements various sorting algorithms (like bubble sort, insertion sort) to sort a list of numbers. It demonstrates basic algorithmic thinking and Python programming skills.

2. [todos_proj](./todos_proj/): A simple todo list application built with Django. It allows users to create, read, update, and delete todo items. The project demonstrates basic CRUD operations and RESTful API design principles.

3. [jobsapi](./jobsapi/): A backend API for browsing and applying for jobs. Demonstrates middleware, Django REST Framework (DRF), serializers, filtering, and API documentation using drf-spectacular. It includes models for companies, jobs, and applications, along with views and serializers to handle API requests.

4. [clear_ledger](./clear_ledger/): A simple ledger application built with Django. It allows users to link bank accounts, categorize and track transactions, get monthly budgets per category, get spending reports and manage their finances. The project demonstrates schema design, model relationships, queries, query sets, transactions and query optimization.

5. [event_hub](./event_hub/): A backend REST API for a simplified event ticketing platform — browse events, reserve seats, and cancel reservations. The project demonstrates ORM usage, queries, serializers, viewsets and middleware in Django REST Framework (DRF).

## Projects

- [devtrack](./devtrack): A backend API for tracking engineering issues. Engineers report bugs, assign priorities, and track status similar to a stripped-down GitHub Issues.

- [team_board](./TeamBoard): A backend API for providing curated questions and answers on common technical topics such as APIs, databases, cloud infrastructure, backend frameworks, and more.

- [pulse_notify](./pulse_notify): A backend API for flight price tracking and notification service. Users can set up alerts for specific flights, receive notifications when prices drop, and manage their flight preferences.

- [collab_docs](./collab_docs/): A backend REST API for a simplified collaborative document platform — create workspaces, invite collaborators, write and version documents, leave comments, and control access with role-based permissions.

## Prerequisites

- Python 3.12+
- `uv` (optional) for dependency management and running the server


## Setup

1. Clone the repository:
```bash
git clone https://github.com/harshavvs/airtribe-bel_c20.git
```

2. Create virtual environment:
```bash
python -m venv .venv

# using uv
uv sync
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

## using uv
uv sync
```

5. Create Django project and app (if not already created):
```bash
django-admin startproject devtrack
cd devtrack

python manage.py startapp issues
```

6. Apply migrations:
```bash
python manage.py migrate
```

7. Go to specified project directory and run the server:
```bash
python manage.py runserver
```

8. Check the server at `http://localhost:8000/`
