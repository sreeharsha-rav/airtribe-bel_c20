# Todos Proj

A simple todo list application built with Django. It allows users to create, read, update, and delete todo items. The project demonstrates basic CRUD operations and RESTful API design principles.

## Concepts Demonstrated

- Modular app structure in Django
- Data modelling with Django ORM
- Migrations workflow
- URL routing and view handling
- Templates and template inheritance
- Admin interface for managing todo items

## Project Structure

```
todos_proj/
├── manage.py
├── db.sqlite3
├── templates/
│   └── base.html                   # Base template with navigation
├── todos_proj/                     # Project configuration
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
└── todos/                          # Main application
    ├── models.py
    ├── views.py
    ├── urls.py
    ├── admin.py
    ├── migrations/
    ├── management/
    │   └── commands/
    │       └── seed.py             # Seed command
    └── templates/todos/
        ├── todo_list.html
        └── todo_detail.html
```

## Data Model

### Todo

| Field         | Type          | Description                        |
|---------------|---------------|------------------------------------|
| `id`          | AutoField     | Primary key                        |
| `title`       | CharField     | Required, max 255 characters       |
| `description` | TextField     | Optional, long text                |
| `completed`   | BooleanField  | Defaults to `False`                |
| `created_at`  | DateTimeField | Set automatically on creation      |
| `updated_at`  | DateTimeField | Updated automatically on each save |

## API Endpoints

JSON-based endpoints for programmatic access. All responses use `Content-Type: application/json`. CSRF is exempt on these views.

### `GET /api/todos/`

Returns all todo items.

**Response `200 OK`**
```json
[
  {
    "id": 1,
    "title": "Buy groceries",
    "description": "Milk, eggs, bread",
    "completed": false,
    "created_at": "2024-01-01T10:00:00Z",
    "updated_at": "2024-01-01T10:00:00Z"
  }
]
```

---

### `POST /api/todos/`

Create a new todo item.

**Request body**
```json
{
  "title": "Buy groceries",
  "description": "Milk, eggs, bread"
}
```

| Field         | Required | Description            |
|---------------|----------|------------------------|
| `title`       | Yes      | Title of the todo item |
| `description` | No       | Additional detail      |

**Response `201 Created`** — the created todo object.

**Response `400 Bad Request`** — if `title` is missing.
```json
{"error": "Title is required"}
```

---

### `GET /api/todos/<id>/`

Retrieve a single todo item by ID.

**Response `200 OK`** — the todo object.

**Response `404 Not Found`**
```json
{"error": "Todo not found"}
```

---

### `PUT /api/todos/<id>/`

Update an existing todo item. All fields are optional; only provided fields are updated.

**Request body**
```json
{
  "title": "Buy groceries",
  "description": "Updated list",
  "completed": true
}
```

**Response `200 OK`** — the updated todo object.

**Response `404 Not Found`**
```json
{"error": "Todo not found"}
```

---

### `DELETE /api/todos/<id>/`

Delete a todo item by ID.

**Response `200 OK`**
```json
{"message": "Todo deleted successfully"}
```

**Response `404 Not Found`**
```json
{"error": "Todo not found"}
```

---

## HTML Endpoints

Browser-facing views that render Django templates.

### `GET /todos/`

Displays all todo items as a clickable list. Each item shows its title and a `(done)` badge if completed. Shows a fallback message when no todos exist.

- Template: `todos/todo_list.html`
- Context: `todos` — QuerySet of all Todo objects

---

### `GET /todos/<id>/`

Displays the full detail of a single todo item, including title, description, status, and timestamps. Includes a back link to the list.

- Template: `todos/todo_detail.html`
- Context: `todo` — the Todo object (or an `error` key on 404)

---

## Admin Interface

### `GET /admin/`

Django's built-in admin interface. The `Todo` model is registered, providing full CRUD access with authentication.

---

## Setup & Running

```bash
# Install Django
pip install django

# Apply migrations
python manage.py migrate

# Seed sample data and create a superuser
python manage.py seed

# Start development server
python manage.py runserver
```

The app will be available at `http://127.0.0.1:8000/`.

---

## Seed Command

`todos/management/commands/seed.py` is a Django management command that:

- Creates 5 sample `Todo` records (skips any that already exist, matched by title)
- Creates a superuser for the admin interface

```bash
# Seed todos + create superuser
python manage.py seed

# Wipe all existing todos first, then seed fresh
python manage.py seed --clear
```

**Default superuser credentials** (development only):

| Field    | Value               |
|----------|---------------------|
| Username | `admin`             |
| Password | `admin123`          |
| Email    | `admin@example.com` |

The command is idempotent — running it multiple times will not create duplicates.

---

## Admin Walkthrough

### 1. Run migrations and seed data

```bash
python manage.py migrate
python manage.py seed
```

You should see output like:
```
Seeded 5 todo(s) (0 already existed).
Superuser created — username: admin, password: admin123
```

### 2. Start the server

```bash
python manage.py runserver
```

### 3. Log in to the admin

Open `http://127.0.0.1:8000/admin/` in your browser.

Enter the credentials from the seed command (`admin` / `admin123`) and click **Log in**.

### 4. Explore the admin interface

You will see the admin home page with two sections:

- **Authentication and Authorization** — manage users and groups (built into Django)
- **Todos** — manage your `Todo` records

Click **Todos** to see the list of all seeded todos.

### 5. Create a new todo

Click **Add Todo** (top right). Fill in:

- **Title** — required
- **Description** — optional
- **Completed** — checkbox

Click **Save**. The new record appears in the list immediately.

### 6. Edit a todo

Click any todo title in the list. Change any field and click **Save**.

### 7. Mark todos as completed in bulk

On the todo list page, check the boxes next to one or more todos. In the **Action** dropdown select **Delete selected todos** (or any other registered action) and click **Go**.

### 8. Delete a todo

Open a todo's edit page and click **Delete** at the bottom left. Confirm the deletion.

### 9. Verify changes via the HTML view

Open `http://127.0.0.1:8000/todos/` to see the same data rendered in the app's own template — confirming that admin changes are immediately reflected in the app.