# WildBite

WildBite is a food pre-ordering system for the CIT-U canteen. Students can create an account and order ahead, while canteen staff manage orders from their own dashboard. It is built with Django and uses Supabase PostgreSQL as the database.

## Project Structure

```
WildBite-PangueJr-Garry-G01/
├── accounts/          # User accounts: registration, login, roles, profiles
├── menu/              # Categories and menu items, menu search
├── orders/            # Food ordering: orders, order items, status history, payments
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

## Core Feature: Food Ordering

Students order food from the canteen ahead of time and pick it up when it's ready. They pay in cash on pickup.

**Students**
- Browse the menu, search by name and filter by category or availability
- Place an order with one or more available items and get an order number (for example `WB-261118-001`)
- Track the order status (Pending → Preparing → Ready for pickup → Completed) and see its history
- Edit or cancel an order while it is still Pending
- See past orders under **My Orders → Order history**

**Canteen staff**
- Add, edit and delete categories and menu items, and mark items available or unavailable
- View all orders, search by order number and filter by status or date
- Move an order to the next status (each change is saved with the staff member and time)
- Record the cash payment when the student picks up the order, then mark it Completed

**Rules**
- Only available items can be ordered, and each order needs at least one item
- Each order item keeps the price at the time of ordering, so later price changes don't affect it
- Status only moves forward, and an order can only be Completed after it is paid
- Students can only see and change their own orders
- A category with items, or a menu item that is part of an order, can't be deleted (mark the item unavailable instead)

The data is stored in Supabase in the `categories`, `menu_items`, `orders`, `order_items`, `order_status_history` and `payments` tables.

### Try the ordering flow

1. Finish the Local Setup steps above, including `python manage.py migrate`.
2. Create a staff account: run `python manage.py createsuperuser` (superusers have the STAFF role), or add a user with the **Staff** role in http://127.0.0.1:8000/admin/.
3. Log in as staff, open **Categories** and add a few (for example Rice Meals and Drinks), then open **Menu Items** and add items.
4. Register a student account, open **Menu**, click **Order now**, enter quantities and place the order.
5. Log in as staff again, open **Orders**, and move the order to Preparing and then Ready for pickup.
6. Click **Record cash payment**, then **Mark as Completed**. The student sees each change under **My Orders**.

## Running the Tests

With the virtual environment active and `.env` filled in, run:

```
python manage.py test
```

This runs every test in `accounts`, `menu` and `orders`. To run one app only, add its name, for example `python manage.py test orders`.

The tests use a separate Supabase test database (`test_` + your `DB_NAME`), never your real data and never SQLite. The first run creates it. After that it is reused, because the Supabase connection pooler doesn't allow dropping it (see `wildbite/test_runner.py`). A full run takes a few minutes because every query goes to Supabase.

A passing run ends with:

```
Ran ... tests in ...s

OK
```
