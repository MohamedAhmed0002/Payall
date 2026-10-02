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
- Initial scope: First workflow is adding a subscription and seeing it in the dashboard. Editing and deleting come right after. The dashboard shows the monthly total, the next charge, and each subscription with its category, billing period, price and payment status. Budgets, spending tracking, reminders and charts can wait. No bank connection.

### User stories and first workflow

- As a user, I want to log in, so that only I can see my subscriptions.
- As a user, I want to see all my subscriptions and the monthly total, so that I know what I spend.
- As a user, I want to add a subscription, so that my overview stays complete.
- As a user, I want to edit or delete a subscription, so that my data stays correct.
- As a user, I want to use the app on laptop and phone, so that I can check it anywhere.

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
billing frequency, next renewal date and payment status shown on the dashboard. The
following examples use fictional user data and realistic Swiss prices as of the design
draft; they are not connected to real accounts.

The IDs are intentionally short because these are documentation examples. In the
implemented system, they must still be unique for their entity type.

#### User

```json
{
  "id": "00001",
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
    "id": "00001",
    "user_id": "00001",
    "service": "Netflix",
    "category": "Entertainment",
    "price": 18.90,
    "currency": "CHF",
    "billing_period": "monthly",
    "start_date": "2025-09-12",
    "next_charge_date": "2026-10-12",
    "payment_status": "paid",
    "notification_enabled": true
  },
  {
    "id": "00002",
    "user_id": "00001",
    "service": "SBB Halbtax",
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
    "id": "00003",
    "user_id": "00001",
    "service": "Spotify",
    "category": "Entertainment",
    "price": 14.95,
    "currency": "CHF",
    "billing_period": "monthly",
    "start_date": "2025-10-03",
    "next_charge_date": "2026-10-03",
    "payment_status": "paid",
    "notification_enabled": false
  }
]
```

`price` is the amount charged for the selected `billing_period`; the API or app can
normalise yearly and weekly prices to calculate the monthly dashboard total. `CHF` is
the user's default currency and is used for these Swiss examples. Currency conversion
for subscriptions billed in another currency (for example, USD) is still an open
question, as is whether `payment_status` is entered manually or supplied by a future
payment integration.

### Business rules and possible operations

Rule: the price of a subscription must be positive. Exception to discuss: what happens if the user adds the same service twice.

The HTTP method and endpoint are included in the **Proposed action** column so the
lecturer's five-column template remains unchanged. The request examples use the
subscription fields defined above; authentication details are not included yet.

| User goal | Proposed action | Example input | Expected output | Open question |
|---|---|---|---|---|
| See all subscriptions | `GET /subscriptions` — Read a list | Optional query parameters, for example `?status=active` | `200 OK` + list of subscriptions and monthly total | Do we calculate the total in the app or the API? |
| Add a subscription | `POST /subscriptions` — Create | `{ "service": "Netflix", "category": "Entertainment", "price": 18.90, "currency": "CHF", "billing_period": "monthly", "start_date": "2025-09-12", "notification_enabled": true }` | `201 Created` + new subscription object with its `id` | Which currencies and billing periods should be supported? |
| Change a subscription | `PATCH /subscriptions/{id}` — Change selected fields | Path `id` plus `{ "price": 19.90, "notification_enabled": false }` | `200 OK` + updated subscription object | Should the edit screen support partial updates or require all fields? |
| Remove a subscription | `DELETE /subscriptions/{id}` — Remove | Path `id`, for example `/subscriptions/00001` | `204 No Content` | Do we ask the user to confirm before deleting? |

### Inspiration from existing apps or APIs (optional)

We looked at normal subscription tracker apps. We like the simple dashboard with a list of services, their status and a total at the top.

## 3. Project management

### Decisions, open questions and next steps

| Question / decision | Current position | Next step / person |
|---|---|---|
| How big is the first version? | Subscriptions only, no bank connection | Confirm with the group (Mohamed) |
| Budgets and spending tracking | Later | Confirm with the group (Mohamed) |
| Edit screen: option 1 or 2 | Undecided | Group decision (Polina) |
| Which currencies? | Undecided (Figma shows CHF and USD) | Group decision (Hoi) |
| Shared household user needed? | Undecided | Group decision (Elpidio) |
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
