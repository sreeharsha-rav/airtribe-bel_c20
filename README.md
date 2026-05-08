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
