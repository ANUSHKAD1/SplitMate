# 💸 SplitMate

### Smart group expense tracking, simplified.

SplitMate is a full-stack group expense-splitting application built with **React, FastAPI, PostgreSQL, and WebSockets**.

Create groups, add shared expenses, split bills fairly, see exactly who owes whom, settle balances, and watch changes appear in real time.

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-tech-stack">Tech Stack</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-getting-started">Getting Started</a> •
  <a href="#-demo-data">Demo Data</a> •
  <a href="#-api-overview">API</a>
</p>

---

## ✨ Why SplitMate?

Keeping track of group expenses manually becomes messy quickly.

SplitMate is designed around one simple idea:

> **Record the expense once. Let the backend calculate the truth.**

The application keeps financial calculations authoritative on the server while giving users a simple, responsive interface for groups, expenses, balances, settlements, and live activity.

---

## 🚀 Features

| Feature                                     | Status |
| ------------------------------------------- | ------ |
| 🔐 User registration & login                | ✅      |
| ♻️ JWT access + rotating refresh tokens     | ✅      |
| 👥 Group creation & membership management   | ✅      |
| 💰 Expense creation & editing               | ✅      |
| ➗ Equal & custom splits                     | ✅      |
| 📊 Canonical balance calculation            | ✅      |
| 🤝 Simplified who-owes-whom suggestions     | ✅      |
| 💳 Settlement recording & history           | ✅      |
| 📝 Group activity feed                      | ✅      |
| ⚡ Real-time WebSocket updates               | ✅      |
| 📈 Personal dashboard                       | ✅      |
| ⏳ Loading, error, retry & validation states | ✅      |
| 🌱 Repeatable demo seed data                | ✅      |
| 💵 Exact money handling                     | ✅      |

---

## 🧰 Tech Stack

### Frontend

* **React**
* **Vite**
* **React Router**
* **Axios**
* **Tailwind CSS**

### Backend

* **FastAPI**
* **SQLAlchemy**
* **Alembic**
* **PostgreSQL**
* **WebSockets**
* **JWT authentication**

### Development

* **Docker Compose**
* **Pytest**
* **Git / GitHub**

---

## 🏗️ Architecture

```text
┌──────────────────────────────────────┐
│              React UI                │
│  Dashboard • Groups • Expenses      │
│  Balances • Settlements • Activity  │
└──────────────────┬───────────────────┘
                   │
          REST / Axios + WebSocket
                   │
                   ▼
┌──────────────────────────────────────┐
│            FastAPI Backend            │
│                                      │
│ Authentication / Authorization       │
│ Expense Service                      │
│ Balance Service                      │
│ Settlement Service                   │
│ Activity Service                     │
│ WebSocket Event Layer                │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│             PostgreSQL               │
│                                      │
│ Users • Groups • Memberships          │
│ Expenses • Splits • Settlements      │
│ Refresh Tokens • Activity            │
└──────────────────────────────────────┘
```

The backend remains authoritative for authorization and financial calculations.

The frontend does not recreate the canonical balance engine.

WebSocket events are treated as invalidation signals, after which the frontend refetches authoritative REST data.

---

## 📁 Project Structure

```text
SplitMate/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── realtime/
│   │
│   ├── alembic/
│   ├── scripts/
│   ├── tests/
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── activities/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── components/
│   │   ├── dashboard/
│   │   ├── expenses/
│   │   ├── groups/
│   │   ├── pages/
│   │   ├── realtime/
│   │   ├── routes/
│   │   ├── settlements/
│   │   └── utils/
│   └── package.json
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## 🎯 Core User Flow

```text
Register / Login
       ↓
   Dashboard
       ↓
     Groups
       ↓
   Group Detail
       ↓
 ┌─────┼───────────────┐
 │     │               │
 ▼     ▼               ▼
Expenses Balances   Settlements
 │                     │
 └──────────┬──────────┘
            ▼
       Activity Feed
            │
            ▼
     Live WebSocket Updates
```

---

## 💵 Money Handling

SplitMate deliberately separates the **user-facing money representation** from the **internal money representation**.

### User-facing / API

Money is entered and returned in **rupees**, with up to two decimal places.

Examples:

```text
250       → ₹250.00
250.50    → ₹250.50
```

### Internal / Database

Money is stored and calculated as **integer paise**.

Examples:

```text
₹250.00   → 25000 paise
₹250.50   → 25050 paise
```

The conversion uses Python `Decimal` rather than binary floating-point arithmetic.

This keeps monetary calculations exact and prevents common floating-point errors.

### Equal split rounding

Equal splits use integer division plus remainder distribution so the final shares always add up exactly to the original amount.

Example:

```text
₹100 split among 3 people

₹34
₹33
₹33
```

The extra smallest unit is assigned according to the existing request-order rule.

---

## 🔐 Authentication

SplitMate uses:

* a short-lived JWT access token
* an opaque refresh token

The access token is valid for **15 minutes** by default.

The refresh token is valid for **7 days** by default and is rotated during refresh.

### Refresh-token storage

PostgreSQL stores only the **SHA-256 hash** of the refresh token rather than the raw token.

Each refresh-token record contains:

* user ID
* token hash
* creation time
* expiry time
* optional revocation time

### Frontend token strategy

The frontend:

* keeps the access token **in memory**
* stores the refresh token in **`sessionStorage`**
* attaches the access token through Axios
* shares one refresh request when multiple requests receive `401`
* retries the original request once after successful refresh
* clears authentication state when refresh fails

Logout revokes the refresh token and clears local authentication state.

---

## ⚡ WebSockets & Live Updates

Group updates use:

```text
WS /ws/groups/{groupId}?token=<accessToken>
```

The socket is:

* authenticated
* group-scoped
* closed when leaving the group
* reconnected after unexpected disconnects
* reconnected with the latest access token

### Event types

```text
expense_added
expense_edited
expense_deleted
settlement_recorded
activity_added
balances_updated
overall_balance_updated
```

The frontend treats these events as **invalidation signals**, not as a replacement for authoritative REST responses.

For example:

```text
expense_added
     ↓
WebSocket event
     ↓
Refetch expenses
Refetch balances
Refetch activity
Refetch settlements
```

After reconnecting, the frontend refetches current REST state because missed events are not replayed.

---

## 📊 Dashboard

The dashboard summarizes the user's current financial position using backend-produced values:

* total you owe
* total owed to you
* net balance
* number of groups
* group where you owe the most
* recent personal activity

No canonical balance calculation is performed in the frontend.

---

## 👥 Groups & Memberships

Users can:

* create groups
* view their groups
* open a group
* view members
* add registered users by email
* remove members when allowed

The backend remains authoritative for membership and authorization.

A member with a non-zero balance cannot be removed until the outstanding financial relationship is resolved.

---

## 🧾 Expenses

Expenses support:

* description
* amount
* payer
* date
* equal split
* custom split
* editing
* deletion
* pagination
* sorting

### Equal split example

```text
₹500 expense
2 participants

Rosy → ₹250.00
Anu  → ₹250.00
```

### Custom split example

```text
₹250.50 expense

Rosy → ₹125.25
Anu  → ₹125.25
```

Custom split totals must exactly match the expense total.

---

## 🤝 Balances & Settlements

SplitMate exposes:

* each member's net balance
* simplified debt suggestions
* actionable settlement relationships
* settlement history

Example:

```text
Anu owes Rosy ₹700.00
```

Recording a settlement updates the authoritative balances and produces an activity event.

---

## 📝 Activity Feed

Each group has a chronological activity feed covering events such as:

* member additions
* expense creation
* expense edits
* expense deletion
* settlements

The feed supports loading, empty, retry, and error states.

---

## 🌱 Demo Data

A repeatable seed script is included.

From the `backend` directory:

```powershell
python -m scripts.seed_demo
```

### Demo users

| Name | Email                 | Password            |
| ---- | --------------------- | ------------------- |
| Rosy | `rosy@splitmate.demo` | `SplitMateDemo123!` |
| Anu  | `anu@splitmate.demo`  | `SplitMateDemo123!` |

### Demo group

**Rosy Birthday Party**

The seeded data contains:

* Venue deposit — ₹3,000 — equal split
* Decorations — ₹1,200 — custom split
* Cake — ₹900 — equal split
* Settlement — ₹500 — Anu → Rosy

Expected remaining balance:

```text
Anu owes Rosy ₹700.00
```

The seed is repeatable and avoids creating duplicate demo data on subsequent runs.

---

## 🏃 Getting Started

### Prerequisites

Install:

* Docker Desktop
* Python
* Node.js
* npm

### 1. Start PostgreSQL

From the repository root:

```powershell
docker compose up -d
docker compose ps
```

### 2. Start the backend

Open a terminal:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
$env:PYTHONPATH="C:\Users\ANUSHKA\Desktop\SplitMate\backend"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

### 3. Start the frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Use the `Local:` URL printed by Vite.

### 4. Seed demo data

After migrations have been applied:

```powershell
cd backend
python -m scripts.seed_demo
```

---

## 🧪 Testing

### Backend

```powershell
cd backend
.\venv\Scripts\Activate.ps1
$env:PYTHONPATH="C:\Users\ANUSHKA\Desktop\SplitMate\backend"
pytest tests -q
```

### Frontend build

```powershell
cd frontend
npm run build
```

Current verified backend suite:

```text
116 passed
```

---

## 🔌 API Overview

### Authentication

```text
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
```

### Dashboard

```text
GET /dashboard
```

### Groups

```text
POST /groups
GET /groups
GET /groups/{groupId}
DELETE /groups/{groupId}
```

### Members

```text
POST /groups/{groupId}/members
DELETE /groups/{groupId}/members/{userId}
```

### Expenses

```text
POST /groups/{groupId}/expenses
GET /groups/{groupId}/expenses
PUT /expenses/{expenseId}
DELETE /expenses/{expenseId}
```

### Balances

```text
GET /groups/{groupId}/balances
```

### Settlements

```text
POST /groups/{groupId}/settlements
GET /groups/{groupId}/settlements
```

### Activity

```text
GET /groups/{groupId}/activity
```

### WebSockets

```text
WS /ws/groups/{groupId}?token=<accessToken>
```

For the complete contract, use:

```text
http://127.0.0.1:8000/docs
```

---

## 🖼️ Screenshots

### 📊 Login

![SplitMate Login](docs/screenshots/1.png)

### 📊 Dashboard

![SplitMate Dashboard](docs/screenshots/2.png)

### 👥 Create a group

![SplitMate Create a group](docs/screenshots/3.png)

### 👥 Add Members to group

![SplitMate Add Members to group](docs/screenshots/4.png)

### 💰 Add Expenses

![SplitMate Add Expenses](docs/screenshots/5.png)

### 🤝 Edit/Delete Expenses

![SplitMate Edit/Delete Expenses](docs/screenshots/6.png)

### ⚡ Settle Up Expenses

![SplitMate Settle Up Expenses](docs/screenshots/7.png)
![SplitMate Settle Up Expenses](docs/screenshots/8.png)

---

## ⚠️ Known Limitations

* WebSocket events are invalidation signals rather than replayable events.
* Missed events during disconnection are recovered through REST refetching after reconnect.
* The application is currently intended as a local development/demo project rather than a production deployment.
* Production HTTPS termination, secret management, deployment infrastructure, observability, and CI/CD are outside the current scope.

---

## 🎬 Demo Flow

Recommended demonstration sequence:

```text
Login
  ↓
Dashboard
  ↓
Rosy Birthday Party
  ↓
Review members
  ↓
Review expenses
  ↓
Show balances
  ↓
Record settlement
  ↓
Show updated balance
  ↓
Show activity
  ↓
Open the same group in another session
  ↓
Create/edit an expense
  ↓
Show live update without refreshing
```

---

## 📌 Project Status

**Feature-complete development build**

Core backend, frontend, financial logic, settlements, activity tracking, live updates, and demo seed data are implemented and verified.

---

## 👩‍💻 Built For

A full-stack expense-sharing project focused on:

**correct financial calculations · secure authentication · clear API boundaries · real-time collaboration · practical UX**
