# PayAll

**Current stage:** Milestone 1 – design draft. We update this README during the whole project.

## Project overview

Payall is a web app to track spending, manage budgets and monitor subscriptions. People often forget which subscriptions they have, when they renew and how much they pay in total. For the first milestone we focus on subscriptions only: the user sees all subscriptions in one dashboard, with price, billing period, payment status and the total cost per month.

### Team and initial responsibilities

| Member | Initial responsibility | Next action |
|---|---|---|
| Mohamed | Coordination and README | Keep decisions, questions and the milestone commit together |
| Elpidio | Users and workflow | Describe needs and the steps of one workflow |
| Polina | Sketches and interaction | Sketch the screens and feedback for that workflow |
| Hoi | Data and API exploration | Prepare sample JSON and clarify the proposed operations |

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
- As an admin, I want to activate a notification for a subscription, so that I get a reminder before it renews.

Outside the initial scope: bank connection, automatic cancellation, budgets.

**[TODO: Elpidio, check and complete the workflow]**

| Step | User / role | Action | Information needed | Expected result or feedback |
|---|---|---|---|---|
| 1 | User | Opens the dashboard | – | Sees the list of subscriptions and the total |
| 2 | User | Clicks "Add a subscription" | – | Add screen opens |
| 3 | User | Chooses a service and enters price and billing period | Service, price, currency, billing period | – |
| 4 | User | Clicks save | – | Subscription appears in the dashboard and the total updates |

Question to discuss: what happens if the user enters a price that is zero or negative?

## 2. Design

## Screens and navigation

Figma: https://www.figma.com/design/FitGxKHAvpqMSCX6qlc3aL/Web-Based-Apps

The file contains low-fidelity wireframes (Dashboard, Add a subscription, Edit option 1, Edit option 2)
and high-fidelity versions of the Dashboard, Add a subscription and Edit (based on option 2).

### Navigation

Dashboard is the start screen. From there the user can:
- **Add subscription** → opens *Add a subscription* → after linking, returns to the Dashboard with the new entry in the list
- **Edit subscriptions** → opens *Edit my subscriptions* → *Save* or *Cancel* returns to the Dashboard
- **Add subscription → Add custom** → opens *Add a custom subscription* → *Add subscription* returns to the Dashboard

In the high-fi version a sidebar (Dashboard, Subscriptions, Add subscription, Billing history, Settings)
gives direct access to the same screens. Billing history and Settings are not designed yet.

### 1. Dashboard (Current subscriptions)

- **Shows:** list of all subscriptions with service name and logo, category, current billing period,
  price with currency and payment status (`paid` / `pending`). Above the list: total amount;
  the high-fi version adds summary cards for monthly total, total recurring commitments and next charge.
- **Inputs:** search field (high-fi), sort dropdown (e.g. by renewal date), row menu (⋯) per subscription.
- **Actions:** *Add subscription*, *Edit subscriptions*, *Review billing*.
- **Feedback:** status badges (yellow = pending, green = paid), count of active subscriptions,
  a notice banner when renewals are still pending (e.g. "2 renewals need attention").

### 2. Add a subscription

- **Inputs:** search field to filter services; scrollable list of popular services
  (Netflix, Spotify, SBB Halbtax, U-Abo) plus *Add custom* for services not in the list.
- **Actions:** select a service, *Link an App* to add it, *Cancel* to go back without changes.
- **Feedback:** the selected row is highlighted and a "<Service> selected" label appears above the list;
  *Link an App* is the primary (green) button.

### 3. Edit my subscriptions (two options, not decided yet)

**Option 1 – edit all in one table.** Every subscription is a row with an inline Month/Year toggle,
an editable price field and a *Delete* button. *Save* applies all changes at once, *Cancel* discards them.
Fast for quick changes across several subscriptions, but limited to frequency and price.

**Option 2 – edit one subscription in a form** (also the basis of the high-fi design).
- **Inputs:** service dropdown, billing frequency (Yearly / Monthly / Weekly), price and currency,
  start date (date picker), checkbox "Activate notification" (reminder before renewal).
- **Actions:** *Change the name*, *Renew the billing period*, *Delete*, *Cancel*, *Save*.
- **Feedback:** status badge (e.g. ACTIVE), total per year shown in the header,
  "All fields required" note and helper text under the fields; *Delete* is styled red as a destructive action.
  More fields than option 1, but only one subscription at a time.

### 4. Add a custom subscription

Opened from *Add a subscription* by choosing **Add custom**, for services that are not in the list
(e.g. a gym membership).

- **Inputs:** custom subscription name (free text with edit icon), billing frequency
  (Yearly / Monthly / Weekly), price and currency, start date (date picker),
  checkbox "Activate notification" (reminder before renewal).
- **Actions:** *Add subscription* saves the entry and returns to the Dashboard,
  *Cancel* goes back without saving.
- **Feedback:** NEW and CUSTOM badges show that this is a user-created entry,
  "Required" / "All fields required" notes and helper text under the fields,
  hint in the name field ("Enter a name you'll recognize"). *Add subscription* is the primary (green) button.
  The layout matches the Edit form (option 2), so users recognise the same fields.

### Domain concepts and example data

The main domain concepts are a **user** and the user's **subscriptions**. A user owns
subscriptions, and each subscription records the service, category, price, currency,
billing frequency, next renewal date, payment status and notification preference shown
on the dashboard. A custom subscription uses the same structure as a listed service and
sets `is_custom` to `true`. The
following examples use fictional user data and realistic Swiss prices as of the design
draft; they are not connected to real accounts.

IDs are integers generated by SQL autoincrement. The examples below use `1`, `2`,
and `3`, matching the implemented system and the bar example.

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

```json
[
  {
    "id": 1,
    "user_id": 1,
    "service": "Netflix",
    "is_custom": false,
    "category": "Entertainment",
    "price": 18.90,
    "currency": "CHF",
    "billing_period": "monthly",
    "start_date": "2025-09-12",
    "next_charge_date": "2025-10-12",
    "payment_status": "paid",
    "notification_enabled": true
  },
  {
    "id": 2,
    "user_id": 1,
    "service": "SBB Halbtax",
    "is_custom": false,
    "category": "Transport",
    "price": 190.00,
    "currency": "CHF",
    "billing_period": "yearly",
    "start_date": "2026-02-01",
    "next_charge_date": "2027-02-01",
    "payment_status": "pending",
    "notification_enabled": true
  },
  {
    "id": 3,
    "user_id": 1,
    "service": "Spotify",
    "is_custom": false,
    "category": "Entertainment",
    "price": 14.95,
    "currency": "CHF",
    "billing_period": "monthly",
    "start_date": "2025-10-03",
    "next_charge_date": "2025-10-03",
    "payment_status": "paid",
    "notification_enabled": false
  }
]
```

`price` is the amount charged for the selected `billing_period`; the API or app can
normalise yearly and weekly prices to calculate the monthly dashboard total. `CHF` is
the user's default currency and is the only supported currency for now; support for
additional currencies can be added later. New subscriptions start with
`payment_status` set to `pending`. Whether payment status is entered manually or
supplied by a future payment integration remains open.

### Business rules and possible operations

Rules: prices must be positive, `currency` is currently limited to `CHF`,
`billing_period` must be `weekly`, `monthly` or `yearly`, dates must use `YYYY-MM-DD`,
and `payment_status` must be `paid` or `pending`. New subscriptions start as
`pending`. A custom subscription uses `POST /subscriptions` with `is_custom: true`.
The API returns only the authenticated user's subscriptions. Search and sorting are
handled by query parameters, and notification activation is updated through the same
partial-update operation as other editable fields.

The request examples use the subscription fields defined above. Authentication is
represented by a bearer token after login; password storage and payment integration are
outside this milestone.

| User goal | Method | Path | Example JSON / parameters | Success status and response | Meaningful failure | Open question |
|---|---|---|---|---|---|---|
| Log in | `POST` | `/login` | `{ "email": "lena.mueller@example.com", "password": "example-password" }` | `200 OK` — `{ "access_token": "<token>", "user": { "id": 1, "email": "lena.mueller@example.com" } }` | `401 Unauthorized` — `{ "error": "invalid_credentials" }` | How long should the bearer token remain valid, and do we need logout or refresh-token operations? |
| See, search and sort subscriptions | `GET` | `/subscriptions?search=netflix&sort=next_charge_date&order=asc` | No request body. Supported parameters: `search`, `sort` (`next_charge_date`, `price`, `service`) and `order` (`asc`, `desc`). | `200 OK` — `{ "subscriptions": [ ... ], "monthly_total": 49.68, "currency": "CHF" }` | `400 Bad Request` — `{ "error": "invalid_sort_field" }` | Should search be case-insensitive, and do we need pagination when the list grows? |
| Add a listed subscription | `POST` | `/subscriptions` | `{ "service": "Netflix", "is_custom": false, "category": "Entertainment", "price": 18.90, "currency": "CHF", "billing_period": "monthly", "start_date": "2025-09-12", "notification_enabled": true }` | `201 Created` — new subscription object with its `id`, `next_charge_date` and `payment_status` (`pending` for new subscriptions) | `422 Unprocessable Entity` — `{ "error": "price_must_be_positive", "field": "price" }` or `{ "error": "category_required", "field": "category" }` | Which additional currencies should be supported later? |
| Add a custom subscription | `POST` | `/subscriptions` | `{ "service": "Local Gym", "is_custom": true, "category": "Health", "price": 45.00, "currency": "CHF", "billing_period": "monthly", "start_date": "2025-09-12", "notification_enabled": false }` | `201 Created` — new subscription object with `is_custom: true` and `payment_status: "pending"` | `422 Unprocessable Entity` — `{ "error": "service_name_required", "field": "service" }` or `{ "error": "category_required", "field": "category" }` | Should custom categories be free text, selected from the same category list, or optional? |
| Change a subscription or activate its notification | `PATCH` | `/subscriptions/{id}` | `{ "price": 19.90, "notification_enabled": true }` | `200 OK` — updated subscription object | `404 Not Found` — `{ "error": "subscription_not_found" }` | How many days before `next_charge_date` should a notification be sent, and should users choose that timing? |
| Remove a subscription | `DELETE` | `/subscriptions/{id}` | No request body. Example path: `/subscriptions/1` | `204 No Content` | `404 Not Found` — `{ "error": "subscription_not_found" }` | Is deletion permanent, or should the API keep an inactive/history record for billing history? |

For the list operation, `monthly_total` is calculated by the API from each subscription's
`price` and `billing_period`; for the three seeded subscriptions it is `49.68` CHF.
Currency conversion is deferred until currencies beyond CHF are supported. Duplicate services are allowed because a user
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
- **Safe changes:** each create, update or delete runs in a transaction, so a failed
  request does not leave half-saved data.

**Planned tables:**

| Table | Main columns | Relationship |
|---|---|---|
| `user` | `id`, `name`, `email`, `currency`, `created_at` | One user has many subscriptions |
| `subscription` | `id`, `user_id`, `service`, `is_custom`, `category`, `price`, `currency`, `billing_period`, `start_date`, `next_charge_date`, `payment_status`, `notification_enabled` | `user_id` → `user.id` (foreign key) |

SQLite keeps the whole database in one local file, which is enough for development and the
course demo. Moving to a server database (e.g. PostgreSQL) later would mainly change the
connection setting, not the models.

### Inspiration from existing apps or APIs (optional)

We looked at normal subscription tracker apps. We like the simple dashboard with a list of services, their status and a total at the top.

## 3. Project management

### Decisions, open questions and next steps

| Question / decision | Current position | Next step / person |
|---|---|---|
| How big is the first version? | Subscriptions only, no bank connection | Confirm with the group (Mohamed) |
| Budgets and spending tracking | Later | Confirm with the group (Mohamed) |
| Edit screen: option 1 or 2 | Undecided | Group decision (Polina) |
| Which currencies? | Decided: CHF only for now | Group decision (Hoi) |
| Shared household user needed? | Undecided | Group decision (Elpidio) |
| How do we store data? | Decided: relational SQL (SQLite) with SQLModel ORM | Implement the first workflow (Hoi) |
| Frontend technology | Undecided | Later |

### Milestone progress

| Milestone | Available evidence | Status / next step |
|---|---|---|
| 1 – Design draft | Analysis, workflow, sketches, example JSON and proposed operations | Draft done, open questions listed above |
| 2 – Contract and available implementation | OpenAPI contract and implemented/tested progress | Update later |
| Integration – later | Revised feature scope, frontend decision, architecture and a connected workflow | Update later |

## 4. References and acknowledgements

- Figma design: link above.
- Template: FHNW Web-based Applications, Milestone 1 README.
- AI assistance: we used an AI assistant to help structure and phrase this README.
