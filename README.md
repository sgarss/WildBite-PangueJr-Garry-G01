# WildBite

WildBite is a food pre-ordering system for the CIT-U canteen. Students can create an account and order ahead, while canteen staff manage orders from their own dashboard. It is built with Django and uses Supabase PostgreSQL as the database.

## Project Structure

```
WildBite-PangueJr-Garry-G01/
├── accounts/          # User accounts: registration, login, roles, profiles
├── static/            # CSS and JavaScript files
├── templates/         # HTML pages (Django templates)
├── wildbite/          # Project settings and main URL routes
├── .env.example       # Template for the environment variables
├── manage.py          # Django command-line tool
└── requirements.txt   # Python packages needed by the project
```

## Prerequisites

- **Python 3.10 or newer** ([download](https://www.python.org/downloads/))
- **Git** ([download](https://git-scm.com/downloads))
- **Supabase PostgreSQL credentials** (database host, user, password and port)

To check if Python and Git are installed:

```
python --version
git --version
```

## Local Setup

### 1. Clone the repository

```
git clone https://github.com/sgarss/WildBite-PangueJr-Garry-G01.git
cd WildBite-PangueJr-Garry-G01
```

### 2. Create and activate a virtual environment

**Windows (PowerShell)**

```
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux**

```
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` at the start of your terminal line.

> On Windows, if PowerShell says running scripts is disabled, run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again.

### 3. Install the dependencies

```
pip install -r requirements.txt
```

### 4. Set up the environment variables

Copy `.env.example` to a new file named `.env`:

**Windows**

```
copy .env.example .env
```

**macOS / Linux**

```
cp .env.example .env
```

Open `.env` and fill in each value:

| Key | What to put |
|---|---|
| `SECRET_KEY` | A long random string (see below) |
| `DEBUG` | `True` for local development |
| `DB_NAME` | Database name, usually `postgres` |
| `DB_USER` | Supabase database user |
| `DB_PASSWORD` | Supabase database password |
| `DB_HOST` | Supabase host (click **Connect** in Supabase and use the Session pooler details) |
| `DB_PORT` | Database port, usually `5432` |

To generate a `SECRET_KEY`:

```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Never commit the `.env` file. It is already listed in `.gitignore`.

### 5. Run the database migrations

```
python manage.py migrate
```

This creates or updates the tables in Supabase.

### 6. Start the server

```
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser. Press `Ctrl+C` in the terminal to stop the server.

### Optional: create an admin account

```
python manage.py createsuperuser
```

Log in at http://127.0.0.1:8000/admin/ to manage users and create canteen staff accounts.
