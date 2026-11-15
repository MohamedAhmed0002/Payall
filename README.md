# PayAll

**Current stage:** Milestone 3 – integration. The dashboard and the add-subscription
workflow are connected to the API. Login comes after the security lecture.

**Getting started:** See the [backend setup guide](backend/README.md).

## How to run
Requirements: Python 3.10+. Install once in a virtual environment:
`pip install -r backend/requirements-test.txt` (see [backend/README.md](backend/README.md)
for details). Node is only needed to rebuild Tailwind:

```sh
cd Frontend/tailwind
npx tailwindcss@3 -c tailwind.config.js -i input.css -o ../static/tailwind.css --minify
```

From the project root, run `python start_all.py`. Keep both processes running:
the FastAPI backend uses port 8000 (API docs at
http://127.0.0.1:8000/docs), and the frontend uses port 3000 (open
http://127.0.0.1:3000). Stop both with Ctrl+C.

Without the launcher, run `python run.py` in `backend/` and `python server.py` in
`Frontend/`, each in its own terminal.

In Codespaces, start as above and open forwarded port 3000 in the Ports tab.
Port 8000 plus `/docs` opens Swagger. This has not yet been tested in Codespaces.
**[TODO Hoi]** Test the start in Codespaces and update this paragraph.

On first start, `backend/data/payall.sqlite` is created from `backend/seed.json`.
It contains fictional user Lena Müller, Netflix, SBB Halbtax, Spotify and a catalog
of about 58 Swiss services. To reset it, stop the app, delete `payall.sqlite`, and
start again.

Run the tests with `cd backend && pytest` (67 tests).

## Project overview

Payall is a web app to track spending, manage budgets and monitor subscriptions. People often forget which subscriptions they have, when they renew and how much they pay in total. For the first milestone we focus on subscriptions only: the user sees all subscriptions in one dashboard, with price, billing period, payment status and the total cost per month.

### Team and initial responsibilities

| Member | Initial responsibility | Next action | Integration work |
|---|---|---|---|
| Mohamed | Coordination and README | Keep decisions, questions and the milestone commit together | UI and API connection, proxy, launcher |
| Elpidio | Users and workflow | Describe needs and the steps of one workflow | Disable security features (open); login and security features after the security lecture |
| Polina | Sketches and interaction | Sketch the screens and feedback for that workflow | Edit/delete, history view, add form, menu labels, server allow-list |
| Hoi | Data and API exploration | Prepare sample JSON and clarify the proposed operations | Backend rules and data, summary cards, totals, currencies, errors, reminders, Tailwind, README |

We review each other's work so everyone understands the draft.

## 1. Analysis

### Scenario, users and goals

- Situation or problem: Students and working people have many subscriptions (Netflix, Spotify, SBB Halbtax). They forget which ones are active and get surprised by payments.
- Intended users:
  - Subscription owner: wants to know how much they spend per month.
  - Budget saver: wants to avoid payments for subscriptions they don't use.
- Proposed benefit: One clear overview of all subscriptions and the monthly total.
- Initial scope: First workflow is adding a subscription and seeing it in the dashboard. Editing and deleting come right after. The dashboard shows the monthly total, the next charge, and each subscription with its category, billing period, price and payment status. Budgets, spending tracking and charts can wait. No bank connection.

### User stories and first workflow

- As an admin, I want to log in, so that only I can access the subscriptions.
- As an admin, I want to see all subscriptions and the monthly total, so that I know what is spent.
- As an admin, I want to add a subscription, so that the overview stays complete.
- As an admin, I want to edit or delete a subscription, so that the data stays correct.
- As an admin, I want to see the payment status (paid/pending) of each subscription, so that I know which renewals need attention.
- As an admin, I want to see the next charge date, so that I am not surprised by upcoming payments.
- As an admin, I want to search and sort the subscriptions (e.g. by renewal date), so that I can find a subscription quickly.
- As an admin, I want to add a custom subscription, so that services not in the list (e.g. a gym membership) are also tracked.
- As an admin, I want to turn on reminders for selected subscriptions and get one combined in-app message a few days before they renew or when a manual payment is pending, so that I am not surprised by payments.

Outside the initial scope: bank connection, automatic cancellation, budgets.

| Step | User / role | Action | Information needed | Expected result or feedback |
|---|---|---|---|---|
| 1 | User | Opens the dashboard | – | Sees cards, the list and reminders |
| 2 | User | Clicks "+ Add subscription" | – | The add drawer opens |
| 3 | User | Chooses a catalog service or "+ Add custom service" | Service, price, currency, billing frequency, start date, reminder | The form shows the selected service |
| 4 | User | Chooses "Mark manually" or "Mark automatically" and clicks "+ Add subscription" | Payment choice | On success, the drawer closes, the row appears and totals update |
| 5 | User | Sends invalid data | For example, price `0` | On error, the API message appears under the field |

**[TODO Elpidio]** Check that this workflow table matches the app, then remove this marker.

The API rejects a zero or negative price with 422 `Price must be greater than 0.`
and nothing is saved.

## 2. Design

## Screens and navigation

Figma: https://www.figma.com/design/FitGxKHAvpqMSCX6qlc3aL/Web-Based-Apps

The design has four screens: Dashboard, Add a subscription, Edit my subscriptions and
Add a custom subscription. The Dashboard also has a state with the row menu (⋯) open.
The app is for tracking only, so no bank or service account is connected. The demo date in
the design is 17 Oct 2025.

### Navigation

The sidebar has Dashboard (start screen), Billing history and Settings. Billing history and
Settings are not designed yet.

- Dashboard → **Add subscription** → *Add a subscription* → **Link an App** → back to Dashboard
- *Add a subscription* → **Add custom** → *Add a custom subscription* → **Add subscription** → back to Dashboard
- Dashboard → **Edit subscriptions** (or ⋯ → *Edit subscription* on a row) → *Edit my subscriptions* → **Save** / **Cancel** / **Delete** → back to Dashboard
- Dashboard → ⋯ on a row → **Mark as paid** or **Delete from the list**

### 1. Dashboard (Current subscriptions)

- **Shows:**
  - Three summary cards: Monthly total (yearly plans ÷12, weekly ×52÷12), Annualized total, and Next charge (service and date).
  - A scrollable table "All subscriptions" with a count of active ones. Each row shows logo, name, category, billing period, price and status.
  - A sidebar box with the monthly spend.
- **Inputs:** search field (top bar, ⌘K) and a sort dropdown for the table.
- **Actions:** *Add subscription*, *Edit subscriptions*, and the ⋯ menu on each row
  (*Edit subscription*, *Mark as paid*, *Delete from the list*).
- **Feedback:**
  - Status badges: orange "Pending" and green "Paid". Pending rows have an orange background.
  - An orange notice above the table, e.g. "2 renewals need attention · Netflix and SBB Halbtax".
  - A grey note under the table explaining how the monthly total is calculated.

### 2. Add a subscription

- **Inputs:**
  - Search field and a list of services, with **Add custom** for services that are not in the list.
  - Source price and currency, billing frequency (Weekly / Monthly / Yearly), start date (YYYY-MM-DD)
    and an optional reminder checkbox.
- **Actions:** select a service or *Add custom*, *Link an App* to save, *Cancel* to go back.
- **Feedback:**
  - A step badge ("SELECT A SERVICE") and a "<Service> selected" label.
  - An amber warning if the service already exists.
  - A read-only "Demo equivalent" in CHF next to the price.
  - Required fields are marked with *, and a guidance line states the rules
    (price > 0, date format YYYY-MM-DD).
  - A note that the details are used for tracking only.

### 3. Edit my subscriptions

- **Inputs:** service dropdown, billing frequency, price and currency, start date,
  checkbox "Activate notification" (optional renewal reminder).
- **Actions:** *Change the name*, *Renew the billing period*, *Delete* (red), *Cancel*, *Save*.
  Save applies the changes, Cancel discards them.
- **Feedback:** ACTIVE badge, a "Total per year" box in the header, helper texts under the fields
  ("Price must be greater than 0") and a note showing how the annual amount is calculated
  (e.g. 9.90 USD ×12 ×0.80 = 95.04 CHF, demo rate).

### 4. Add a custom subscription

Opened from *Add a subscription* via **Add custom**, for services that are not in the list
(e.g. "Gym & wellness"). Duplicates are allowed.

- **Inputs:** custom name (required), billing frequency (Weekly / Monthly / Yearly), price and currency,
  start date, checkbox "Activate notification" and an optional category dropdown.
- **Actions:** *Add subscription* saves the entry and returns to the Dashboard, *Cancel* goes back.
- **Feedback:** NEW and CUSTOM badges, "Required" notes per section, a hint in the name field
  ("Enter a name you'll recognize") and helper text under frequency and price
  ("Positive price required · Editable amount and currency").
### Domain concepts and example data

The main domain concepts are a **user** and the user's **subscriptions**. A user owns
subscriptions, and each subscription records the service, category, price, currency,
billing frequency, next renewal date, payment status and notification preference shown
on the dashboard. New subscriptions use the same request structure as listed services
and store their service name directly in `usersubscription`. The
following examples use fictional user data and realistic Swiss prices as of the design
draft; they are not connected to real accounts.

IDs are integers generated by SQL `AUTOINCREMENT`, so deleted IDs are never reused.
The examples below use `1`, `2`, and `3`, matching the implemented system.

#### User

```json
{
  "id": 1,
  "name": "Lena Müller",
  "email": "lena.mueller@example.com",
  "currency": "CHF",
  "created_at": "2025-09-01T08:30:00Z"
}
```

#### Subscriptions

`next_charge_date` is calculated by the API from `start_date` and `billing_period`.

```json
[
  {
    "id": 1,
    "user_id": 1,
    "service": "Netflix",
    "category_id": 1,
    "category": "Entertainment",
    "price": 18.90,
    "currency": "CHF",
    "billing_period": "monthly",
    "start_date": "2025-09-12",
    "next_charge_date": "2026-11-12",
    "auto_pay": true,
    "payment_status": "paid",
    "notification_enabled": true
  },
  {
    "id": 2,
    "user_id": 1,
    "service": "SBB Halbtax",
    "category_id": 3,
    "category": "Transport",
    "price": 190.00,
    "currency": "CHF",
    "billing_period": "yearly",
    "start_date": "2026-02-01",
    "next_charge_date": "2027-02-01",
    "auto_pay": false,
    "payment_status": "pending",
    "notification_enabled": true
  },
  {
    "id": 3,
    "user_id": 1,
    "service": "Spotify",
    "category_id": 2,
    "category": "Music",
    "price": 14.95,
    "currency": "CHF",
    "billing_period": "monthly",
    "start_date": "2025-10-03",
    "next_charge_date": "2026-11-03",
    "auto_pay": true,
    "payment_status": "paid",
    "notification_enabled": false
  }
]
```

`price` is the amount charged for the selected `billing_period`; the API or app can
normalise yearly and weekly prices to calculate the monthly dashboard total. CHF, USD
and EUR are supported. Exchange rates come from the European Central Bank through the
Frankfurter API and are stored once per day. Totals in CHF are approximate when other
currencies are involved; only currency codes and dates are sent to the rate service.
Autopay is assumed to succeed on each charge date; it has no bank connection.
Manual subscriptions can be marked paid through the payments endpoint. Payment status
is calculated from recorded payments, with at most one payment per subscription period.
Payments store the CHF amount and the exchange rate from the payment date, so history
stays correct when rates change later.

Prices are stored internally as whole Rappen to avoid rounding errors, but the API
always uses CHF amounts such as `18.90` (returned as the JSON number `18.9`).
### Business rules and possible operations

Rules: prices must be positive, `currency` must be `CHF`, `USD` or `EUR`,
`billing_period` must be `weekly`, `monthly` or `yearly`, dates must use `YYYY-MM-DD`.
Autopay records a successful payment on the charge date; manual subscriptions are
paid through the payments endpoint. Payment status is calculated and there is one
payment per period. Switching to autopay only covers charges from that day on; earlier
periods can still be paid manually. Cancelling keeps a subscription until the end of its paid period;
deleting removes the subscription and its payments. The monthly total excludes
cancelled subscriptions. Periods that started before a subscription was added to Payall
count as paid; Payall tracks payments from that day on. Service names are limited to
100 characters, prices to CHF 100000.00, and start dates must be between 2000-01-01
and one year after today. The `subscription` table is the seeded service catalog. It provides a category,
suggested default price and billing period that the user may override. Catalog
prices are suggestions and may be out of date. Custom subscriptions are private
user rows with no catalog link. Calculated values are never stored.
Dashboard summaries include `monthly_total`, `annual_total` (monthly costs ×12,
yearly costs ×1 and weekly costs ×52) and the next active charge, calculated with
decimal arithmetic from Rappen and rounded to two decimals. These summaries ignore
the search filter. Every business-rule error response contains `error`, `field` and
a short user-facing `message`.
The API returns only the authenticated user's subscriptions. Search and sorting are
handled by query parameters, and notification activation is updated through the same
partial-update operation as other editable fields.

The request examples use the subscription fields defined above. Authentication is
represented by a bearer token after login; password storage and payment integration are
outside this milestone.

| User goal | Method | Path | Example JSON / parameters | Success status and response | Meaningful failure | Open question |
|---|---|---|---|---|---|---|
| Log in | `POST` | `/login` | `{ "email": "lena.mueller@example.com", "password": "example-password" }` | `200 OK` — `{ "access_token": "<token>", "user": { "id": 1, "email": "lena.mueller@example.com" } }` | `401 Unauthorized` — `{ "error": "invalid_credentials" }` | How long should the bearer token remain valid, and do we need logout or refresh-token operations? |
| Browse services | `GET` | `/catalog` | No request body | `200 OK` — catalog entries with `id`, `name`, `category_id`, `category`, `default_price` and `billing_period` | – | Prices and billing periods come from the seeded catalog. |
| See, search and sort subscriptions | `GET` | `/subscriptions?search=netflix&sort=next_charge_date&order=asc` | Optional parameters: `search` (case-insensitive substring of service or category), `sort` (`next_charge_date`, `price`, `service`) and `order` (`asc`, `desc`). | `200 OK` — `{ "subscriptions": [ ... ], "monthly_total": 49.68, "annual_total": 596.20, "next_charge": { "subscription_id": 1, "service": "Netflix", "date": "2026-11-12", "amount": 18.90, "currency": "CHF" }, "currency": "CHF", "cancelled_excluded": 0 }` | `422 Unprocessable Entity` — `{ "error": "invalid_input", "field": "sort", "message": "The input is invalid." }` | Summary cards always include all active subscriptions, even when search filters the list. |
| Add a subscription | `POST` | `/subscriptions` | Catalog: `{ "catalog_id": 1, "start_date": "2025-09-12", "auto_pay": false }`; custom: `{ "service": "Local Gym", "category_id": 4, "price": 60, "billing_period": "monthly", "start_date": "2025-09-12", "auto_pay": false }` | `201 Created` — catalog values default when omitted and user values override them; custom subscriptions require service, category, price and billing period | `422 Unprocessable Entity` — `{ "error": "catalog_item_not_found", "field": "catalog_id" }`, `{ "error": "price_required", "field": "price" }`, or `{ "error": "billing_period_required", "field": "billing_period" }` | Custom subscriptions do not create catalog rows. |
| Read one subscription | `GET` | `/subscriptions/{id}` | No request body. Example path: `/subscriptions/1` | `200 OK` — subscription object | `404 Not Found` — `{ "error": "subscription_not_found", "field": "id" }` | – |
| List categories | `GET` | `/categories` | No request body | `200 OK` — ordered list of `{ "id": 1, "name": "Entertainment" }` objects | – | The frontend uses this list for the category dropdown. |
| Change a subscription or activate its notification | `PATCH` | `/subscriptions/{id}` | `{ "price": 19.90, "category_id": 5, "notification_enabled": true }` | `200 OK` — updated subscription object; changing `billing_period` restarts the period from the next charge date. | `404 Not Found` — `{ "error": "subscription_not_found", "field": "id" }`, `409 Conflict` — `{ "error": "subscription_cancelled", "field": "id" }`, or `422 Unprocessable Entity` — `{ "error": "price_too_high", "field": "price" }`, `{ "error": "service_name_too_long", "field": "service" }`, `{ "error": "start_date_out_of_range", "field": "start_date" }` | Reminder timing: default 7 days, changed in `/settings` |
| Mark a manual payment | `POST` | `/subscriptions/{id}/payments` | No request body | `201 Created` — payment object | `404 Not Found` — `{ "error": "subscription_not_found", "field": "id" }` or `409 Conflict` — `{ "error": "auto_pay_subscription", "field": "auto_pay" }` / `{ "error": "nothing_due", "field": "start_date" }` / `{ "error": "already_paid", "field": "id" }` | – |
| Cancel a subscription | `POST` | `/subscriptions/{id}/cancel` | No request body | `200 OK` — cancelled subscription object | `404 Not Found` — `{ "error": "subscription_not_found", "field": "id" }` or `409 Conflict` — `{ "error": "already_cancelled", "field": "id" }` | – |
| Remove a subscription | `DELETE` | `/subscriptions/{id}` | No request body. Example path: `/subscriptions/1` | `204 No Content` | `404 Not Found` — `{ "error": "subscription_not_found", "field": "id" }` | Deletion is permanent and also removes the subscription's payments; use cancel to keep the history. |
| Read settings | `GET` | `/settings` | No request body | `200 OK` — `{ "reminder_days": 7, "currency": "CHF" }` | – | – |
| Update reminder timing | `PATCH` | `/settings` | `{ "reminder_days": 3 }` | `200 OK` — updated settings | `422 Unprocessable Entity` — `{ "error": "invalid_input", "field": "reminder_days" }` | – |
| List in-app notifications | `GET` | `/notifications` | No request body | `200 OK` — manual-payment notifications with `payment_overdue` or `upcoming_payment`, combined into one message | – | Only enabled, active subscriptions whose current period is not covered by autopay are considered. Overdue payments take priority; dismissed dates are hidden until a new charge date. |
| Dismiss a notification | `POST` | `/notifications/{subscription_id}/dismiss` | No request body | `200 OK` — updated notification list | `404 Not Found` — subscription not found; `409 Conflict` — `{ "error": "nothing_to_dismiss", "field": "subscription_id", "message": "There is no current notification to dismiss." }` | Stores the displayed notification date for that subscription. |
| List payment history | `GET` | `/history` | Optional `type=payment` or `type=cancellation` | `200 OK` — newest payment and cancellation events first | `422 Unprocessable Entity` — `{ "error": "invalid_input", "field": "type" }` | – |

For the list operation, `monthly_total` and `annual_total` are calculated by the API from each
subscription's Rappen price and `billing_period`; for the three seeded subscriptions they are
`49.68` CHF and `596.20` CHF. Notifications only cover manual or not-yet-autopay-covered
periods, and a dismissal applies until the next charge date. All API business-rule errors
include a short English `message` alongside `error` and `field`.
An unpaid manual charge is 'upcoming' on its charge day and 'overdue' from the next day.
CHF, USD and EUR are supported; totals are converted to CHF with daily ECB rates and marked approximate. Duplicate services are allowed because a user
may have more than one plan, but the UI should warn before creating an apparent duplicate.

### Data storage

**Decision:** We store the data in a **relational SQL database** (SQLite), not in a JSON file.
In code, we use the ORM **SQLModel** (built on SQLAlchemy), following the
`extensions/orm/` example from the lecture's bar project.

**Why relational SQL fits Payall:**

- **Related records:** a user owns many subscriptions. In SQL, each subscription row
  stores a `user_id` foreign key that points to the user's row, so the link is enforced by
  the database.
- **Querying only what we need:** the dashboard must show only the logged-in user's
  subscriptions, and support search and sorting (e.g. by `next_charge_date`). A database query
  can filter and sort directly, instead of loading and rewriting one whole JSON file.
- **Rules enforced in more than one place:** the API checks the business rules first
  (positive price, allowed billing periods, `paid`/`pending`), and database constraints
  such as `CHECK (price > 0)` protect the data as a second layer.
  Search and sorting by price or service run as database queries, while
  `next_charge_date` is calculated and sorted in Python.
- **Safe changes:** each create, update or delete runs in a transaction, so a failed
  request does not leave half-saved data.

**Tables:**

| Table | Main columns | Relationship |
|---|---|---|
| `user` | `id`, `name`, `email`, `currency`, `reminder_days`, `created_at` | One user has many subscriptions |
| `category` | `id`, `name` | Fixed unique category list |
| `subscription` | `id`, `name`, `category_id`, `default_price_rappen`, `billing_period` | Catalog with suggested default price and billing period; `category_id` → `category.id` |
| `usersubscription` | `id`, `user_id`, `service`, `category_id`, `subscription_id`, `price_rappen`, `currency`, `billing_period`, `start_date`, `tracked_since`, `auto_pay`, `auto_pay_since`, `cancelled_at`, `ends_on`, `notification_enabled`, `reminder_dismissed_for` | User-owned data; `user_id` → `user.id`, `category_id` → `category.id`, optional `subscription_id` → `subscription.id`; calculated values are never stored |
| `payment` | `id`, `subscription_id`, `period_start`, `amount_rappen`, `currency`, `amount_chf_rappen`, `chf_per_unit_millionths`, `rate_date`, `paid_on`, `method` | `subscription_id` → `usersubscription.id`; `amount_rappen` remains in the subscription currency |
| `exchange_rate` | `id`, `currency`, `rate_date`, `chf_per_unit_millionths`, `fetched_at` | One stored ECB/Frankfurter rate per currency and date |

`next_charge_date`, `payment_status`, `status`, `monthly_total`, `annual_total`,
`next_charge` and notification items are calculated from the user's subscription dates
and payment history when data is read. Only real payments and notification dismissal
dates are persisted.

SQLite keeps the whole database in one local file, which is enough for development and the
course demo. Moving to a server database (e.g. PostgreSQL) later would mainly change the
connection setting, not the models.

All table IDs use SQLite `AUTOINCREMENT`, so deleted IDs are never reused. Money is
stored as whole Rappen in `price_rappen`; API amounts remain CHF values with at most
two decimal places. Catalog defaults are also stored as whole Rappen.

Known limitation: an automatic charge is recorded with the price at the time it is
recorded, so a price change shortly before a charge may be reflected in that charge.

### Inspiration from existing apps or APIs (optional)

We looked at normal subscription tracker apps. We like the simple dashboard with a list of services, their status and a total at the top.

## 3. Implementation and integration

### Current workflow and frontend choice

The workflow serves a subscription owner who adds a subscription and immediately sees it
in the dashboard with the updated monthly and annual total and next charge.

We use the browser + API approach from lecture 07. One static page,
`Frontend/index.html`, uses browser JavaScript (`ApiService`) to call the API with
`fetch` through `/api`. `Frontend/server.py` serves the page and forwards only
allow-listed API routes to FastAPI. This fits because the API returns JSON with
calculated values such as totals, next charge, payment status and reminders. The page
only displays them and updates parts of one page. The same origin avoids CORS setup.
Server-rendered Jinja pages and a frontend framework from lectures 07A/07B were not
needed for one dashboard workflow.

#### Changes from the design (Figma, design coaching 5 Oct)

**[TODO Polina]** Confirm or edit this list against the Figma file, then remove this marker.

1. Navigation is a top bar (Dashboard, Settings, History, About us), not a sidebar.
   There is no sidebar box with monthly spend.
2. Billing history and Settings now exist. Settings has reminder days and CSV export.
3. Add subscription and add custom subscription use one drawer. It has a catalog
   dropdown with about 58 Swiss services and a `+ Add custom service` link. The save
   button is `+ Add subscription`. The payment choice is `Mark manually` or
   `Mark automatically`. There is no read-only Demo equivalent in CHF.
4. Edit my subscriptions uses the same drawer. Renew the billing period was removed,
   and there is no Total per year box.
5. The row menu has Edit, Mark as paid, Cancel and Delete. Cancel is new: the row
   shows `Cancelled (Ends <date>)` until the paid period ends.
6. The reminders banner lists each reminder and its reason. Its buttons are
   `Dismiss for this charge` and `Turn off reminders`.
7. Totals show `≈` and the ECB rate date when other currencies are used.

#### Changes after the backend coaching (26 Oct)

1. A shared read-only `subscription` catalog table is separate from the user's
   `usersubscription` rows. POST uses `catalog_id`; custom subscriptions leave it out.
2. Calculated values (`next_charge_date`, `payment_status`, `status`, totals) are never stored.
3. Payments support autopay or manual payment at `POST /subscriptions/{id}/payments`;
   cancel and delete are different operations.
4. Notifications with dismiss, settings, history, catalog and categories endpoints
   were added, together with search and sort.
5. CHF, USD and EUR use daily ECB rates. Money is stored in Rappen.
6. Every error has `error`, `field` and a readable message. The page displays it.
7. `GET /subscriptions` also returns `annual_total` and `next_charge`.
8. A charge is upcoming on its charge day and overdue from the next day.
9. `Frontend/server.py` has an allow-list, `start_all.py` is the launcher, and
   Tailwind CSS is local.

| Part | Status | Note |
|---|---|---|
| Connected | Done | Dashboard (cards, list, search and sort), add (catalog and custom), edit, mark as paid, cancel, delete, reminders (dismiss and turn off), billing history and reminder days in Settings |
| Simulated | Done | Payments have no bank connection; autopay is assumed successful on the charge date |
| Interface only | Open | Password change, 2FA, sign out other devices and delete account show a success message but call no API and save nothing |
| **[TODO Elpidio]** | Open | Disable the interface-only security actions and label them `Available after login` |
| Planned | Open | Login after the security lecture |

### Trace one interaction: adding a subscription

| Step | What happens in our project | Relevant code or data |
|---|---|---|
| User action | Chooses Disney+ from the catalog, start date `15 Nov 2026`, `Mark manually`, and clicks `+ Add subscription` | Drawer form and `handleSubscriptionSubmit()` in `Frontend/index.html` |
| Request | Browser sends `POST /api/subscriptions` with `catalog_id: 2`, `start_date: "2026-11-15"` and `auto_pay: false`. The server checks the allow-list and forwards it to FastAPI | `ApiService.request()` in `Frontend/index.html`; `ProxyHandler` in `Frontend/server.py`; route in `backend/main.py` |
| Input validation | FastAPI/Pydantic checks types and formats. Invalid input returns 422 with `error`, `field` and `message` | `SubscriptionInput` in `backend/models.py`; error handlers in `backend/main.py` and `backend/errors.py` |
| Business rules | Price is greater than 0 and at most 100000, the date is in range, and the catalog item exists. Catalog name, category, price and period are copied unless sent; the catalog is not changed | `create_subscription()` in `backend/service.py` |
| Storage | One `usersubscription` row is saved in SQLite in one transaction. The price is 1490 Rappen | `backend/models.py`, `backend/database.py`, `backend/data/payall.sqlite` |
| Response | `201 Created` returns the subscription, calculated `next_charge_date: "2026-11-15"`, `payment_status: "pending"` and `status: "active"` | API response JSON |
| Visible result | The drawer closes, a success message appears, and `GET /api/subscriptions` is loaded again. Disney+ appears, totals and next charge update, and the reminder says `Payment due on 15 Nov 2026` | `loadDashboardSubscriptions()` and `renderSubscriptionRows()` in `Frontend/index.html` |

For the error path, price `0` returns 422:
`{"error": "price_must_be_positive", "field": "price", "message": "Price must be greater than 0."}`.
Nothing is saved. The page shows the message under Price with a red border through
`showFieldError()`. The browser keeps only the last loaded list in `loadedSubscriptions`
and `server.py` keeps nothing. Everything that must survive a restart is in SQLite.
Calculated values are never stored.

### Check the saved result

Reload the page; the data comes from the API, not the browser. Alternatively, call
`GET /api/subscriptions`, open Swagger at http://127.0.0.1:8000/docs, or open
`backend/data/payall.sqlite` with DB Browser for SQLite and inspect `usersubscription`.

### What we checked

| Case | Action or input | Expected result | Observed result / remaining issue |
|---|---|---|---|
| Success | Browser, 15 Nov 2026: add Disney+ from the catalog | 201, saved row and updated totals | Disney+ appeared as the fourth row; monthly total changed from 49.68 to 64.58 CHF, annual total from 596.20 to 775.00 CHF, next charge was 14.90 CHF on 15 Nov 2026, and the reminder appeared |
| Saved data | Same POST through the API and database | New row in `usersubscription` | Database had 4 rows, up from 3 |
| Error | Price `0` | 422, message under Price, nothing saved | Message and red border appeared; database still had 3 subscriptions |
| Reminders | `Turn off reminders`, then `No, keep it`, 13 Nov 2026 | Reminder disappears and subscription stays | As expected |
| Limitation | Settings: change password, 2FA, sign out, delete account | Disabled until login exists | They still show a success message but send nothing to the API or save nothing. Open: Elpidio disables them and labels them `Available after login` **[TODO Elpidio]** |

Automated tests: [`backend/tests`](backend/tests) (67 tests, `pytest`).

Screenshots:

- [Dashboard cards before adding](docs/screenshots/dashboard-before-cards.png)
- [Dashboard list before adding](docs/screenshots/dashboard-before-list.png)
- [Add subscription form](docs/screenshots/add-form.png)
- [Price validation error](docs/screenshots/price-error.png)
- [Successful add, cards](docs/screenshots/add-success-cards.png)
- [Successful add, list](docs/screenshots/add-success-list.png)

### Progress and questions for coaching

- **Changed since Milestone 2:** The frontend uses the real API instead of mock data.
  Errors are readable. Currencies, reminder actions, local Tailwind and the server
  allow-list are connected.
- **Working now:** Dashboard and add-subscription workflow, edit, cancel, delete,
  mark as paid, history and reminders.
- **Open issue:** Login is not implemented. Security features in Settings are interface-only.
- **Question:** For our page and API on the same origin through `server.py`, should
  login use a session cookie or a bearer token stored in the browser?
- **Next step:** Elpidio disables the security features and labels them `Available after
  login`; check that the buttons are disabled in the browser. Elpidio adds login after
  the security lecture and checks it with pytest and a manual login test.

## 4. Project management

### Open team tasks

Search this README for `TODO <your name>`.

- **Polina:** Confirm or edit the design changes against Figma, then remove the marker ([Changes from the design](#changes-from-the-design-figma-design-coaching-5-oct)).
- **Elpidio:** Check the workflow table against the app, disable interface-only security actions, decide about shared household users, and implement login after the security lecture ([User stories and first workflow](#user-stories-and-first-workflow), [Current workflow and frontend choice](#current-workflow-and-frontend-choice), [Decisions, open questions and next steps](#decisions-open-questions-and-next-steps)).
- **Mohamed:** Update implemented next steps and confirm the first-version and budgeting decisions ([Decisions, open questions and next steps](#decisions-open-questions-and-next-steps)).
- **Hoi:** Test the start in Codespaces and update the run instructions ([How to run](#how-to-run)).

### Decisions, open questions and next steps

| Question / decision | Current position | Next step / person |
|---|---|---|
| How big is the first version? | Subscriptions only, no bank connection | Confirm with the group (Mohamed) |
| Budgets and spending tracking | Later | Confirm with the group (Mohamed) |
| Edit screen | Decided: edit button in the overview opens the detailed form | Implement in the frontend (Polina) |
| Payment | Decided: two options, autopay or manual; no bank connection, mock data only | Implement mock choices later |
| Delete vs cancel | Decided: delete removes a wrong entry completely; cancel ends a subscription, it stays on the dashboard as "Cancelled, ends <date>" until the end of the paid period, then only appears in the history | Define cancellation workflow |
| Changing the plan | Decided: a new billing period starts from the next charge date | Keep this rule in the API |
| Renew the billing period button | Decided: removed from the design (Polina) | – |
| Notifications | Decided: one combined in-app message, default 7 days before, user can change the number of days | Implement notification settings |
| Categories | Decided: fixed list including "Other" | Keep the fixed category table |
| Money | Decided: stored as whole Rappen to avoid rounding errors | Keep API amounts in CHF |
| Login | After the security lecture | **[TODO Elpidio]** Implement login after the security lecture |
| Which currencies? | Decided: CHF, USD and EUR are supported | Group decision (Hoi) |
| Shared household user needed? | Undecided | **[TODO Elpidio]** Decide with the group or move to 'Later' |
| How do we store data? | Decided: relational SQL (SQLite) with SQLModel ORM | Implement the first workflow (Hoi) |
| Frontend technology | Decided: static HTML + JavaScript calling the API (browser + API approach, lecture 07) | Done (team) |

**[TODO Mohamed]** Update the 'Next step / person' column: several rows are already implemented (Payment, Notifications, Edit screen, Delete vs cancel); confirm the rows 'How big is the first version?' and 'Budgets and spending tracking'.

### Milestone progress

| Milestone | Available evidence | Status / next step |
|---|---|---|
| 1 – Design draft | Analysis, workflow, sketches, example JSON and proposed operations | Draft done, open questions listed above |
| 2 – Contract and available implementation | OpenAPI contract, subscriptions, payments, settings, notifications, history, search and sort endpoints; pytest passes | Implemented and tested |
| 3 – Integration | Dashboard and add-subscription workflow connected to the API; trace, checks and screenshots in section 3 | Ready for coaching on 16 Nov; login open |

## 5. References and acknowledgements

- Figma design: link above.
- Template: FHNW Web-based Applications, Milestone 1 README.
- FHNW Web-based Applications lectures 07, 07A, 07B and the Station Bar reference
  repositories (`backend extensions/orm`, `frontend extensions/frontend`).
- AI assistance: we used AI assistants (GitHub Copilot, Claude) to help with code and
  README wording; we reviewed and tested the results.
