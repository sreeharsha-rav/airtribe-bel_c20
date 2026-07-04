# PulseNotify - Flight Price Monitor & Alert System

PulseNotify is an flight price monitoring service that allows users to set price alerts for specific routes. Users can specify a target price, and the system will continuously monitor flight prices in the background. When the price drops below the specified target, PulseNotify will send a notification to the user.

**System Overview:**
- Does not make user wait for the price check to complete. Instead, it runs in the background and notifies the user when the price drops below the target.
- Checks price automatically at regular intervals and decides whether to send a notification based on the user's specified target price.
- Calls it's own price feed to get the latest flight prices and compares them with the user's target price.

---

## Data Models

---

## API Endpoints

---

## Usage

### Prerequisites

- Docker installed on your system

### Setup

1. Create and activate virtual environment:
```bash
python -m venv .venv

# for windows
.venv\Scripts\activate

# for mac and linux
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run migrations:
```bash
python manage.py make_migrations
python manage.py migrate
```

4. Start the server:
```bash
python manage.py runserver
```

5. Check the server at `http://localhost:8000/api/docs/`

6. Use postman or any other API testing tool to test the endpoints.
