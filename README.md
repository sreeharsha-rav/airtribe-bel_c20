# airtribe-bel_c20

Repository for Airtribe assignments, batch C20 for Backend-Python.

## Learning Projects

1. [sorting](sort_1.py): A simple Python script that implements various sorting algorithms (like bubble sort, insertion sort) to sort a list of numbers. It demonstrates basic algorithmic thinking and Python programming skills.

2. [todos_proj](./todos_proj/): A simple todo list application built with Django. It allows users to create, read, update, and delete todo items. The project demonstrates basic CRUD operations and RESTful API design principles.

3. [jobsapi](./jobsapi/): A backend API for browsing and applying for jobs. Demonstrates middleware, Django REST Framework (DRF) and serializers usage.

## Projects

- [devtrack](./devtrack): A backend API for tracking engineering issues. Engineers report bugs, assign priorities, and track status similar to a stripped-down GitHub Issues.

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

5. Go to specified project directory and run the server:
```bash
cd devtrack
python manage.py runserver
```

6. Check the server at `http://localhost:8000/`
