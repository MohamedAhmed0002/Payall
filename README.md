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

### Screens and navigation

**[TODO: Polina]** Figma link: https://www.figma.com/design/FitGxKHAvpqMSCX6qlc3aL/Web-Based-Apps

Main screens: Dashboard, Add a subscription, Edit my subscriptions (two options in Figma, not decided yet). Short explanation of inputs, actions and feedback goes here.

### Domain concepts and example data

**[TODO: Hoi]** Link to the sample JSON files (fictional data), for example for user and subscription. Explain the important fields and mark what is still unclear (for example: CHF and USD).

### Business rules and possible operations

Rule: the price of a subscription must be positive. Exception to discuss: what happens if the user adds the same service twice.

**[TODO: Hoi, check this draft]**

| User goal | Proposed action | Example input | Expected output | Open question |
|---|---|---|---|---|
| See all subscriptions | Read a list | – | List of subscriptions and total | Do we calculate the total in the app or the API? |
| Add a subscription | Create | Service, price, currency, billing period | New subscription with an id | Which currencies? |
| Change a subscription | Change | Subscription id and new values | Updated subscription | Edit screen option 1 or 2? |
| Remove a subscription | Remove | Subscription id | Confirmation | Do we ask the user to confirm? |

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
- AI assistance: we used an AI assistant to help structure and phrase this README. **[TODO: confirm with the group]**
