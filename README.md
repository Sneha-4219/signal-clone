# Signal Clone

Secure Messaging Platform built for the SDE Fullstack assignment: a **Signal-inspired** desktop messaging app, not a production Signal client.

**Stack:** Next.js (App Router) · TypeScript · FastAPI · Python · SQLite · WebSockets · Lucide React · HTTP-only cookie sessions

**Cryptography:** Signal Protocol / end-to-end encryption is **not implemented**. Persistence is plaintext SQLite, as permitted for this assignment.

```
signal-clone/
├── backend/          # FastAPI + SQLite
├── frontend/         # Next.js UI
└── README.md
```

---

## Overview

The app provides:

- Signal-like **Windows desktop** layout (navigation rail, chats list, conversation pane)
- Mocked OTP **authentication** with **persistent HTTP-only cookie sessions**
- **Direct** and **group** messaging stored in SQLite
- **REST** send/history plus **WebSocket** live delivery
- **Delivery/read receipts**, **typing**, and **presence**
- **Groups** with admin add/remove
- Light/dark appearance stored in `localStorage`

---

## Features

### Authentication (functional)

- Register with username and/or phone, display name, optional avatar URL, and fixed OTP
- Login with username or phone + OTP
- Logout (deletes the DB session and cookie)
- `GET /auth/me` restores the session across refresh
- Profile fields shown in Settings (display name, username, phone, about). **Profile editing is a placeholder** (“Coming Soon”)

### Contacts and conversations (functional)

- User search (`/contacts/search`)
- Add / list / remove contacts
- Direct conversations (one unique pair per two users)
- Conversation list with last-message preview, unread counts, timestamps
- Online / last-seen for direct chats (from WebSocket presence)

### Messaging (functional)

- One-to-one and group text messages
- Persist to SQLite; send via **REST** (`POST .../messages`)
- Live updates via **WebSocket** (`/ws/conversations/{id}`)
- History with `limit` / `offset` (API default 50, max 100; UI loads up to 100)
- Timestamps; sent → delivered → read receipts (per recipient, including groups)
- Typing indicators (ephemeral, not stored)
- Presence (`is_online` / `last_seen`)
- Own vs incoming bubbles by **current user ID vs `sender_id`** (not by receipt status)
- Group sender names on incoming group messages

### Groups (functional)

- Create group (name + member IDs); creator is **admin**
- List members; **admin** can add/remove; members can leave
- Last remaining admin cannot be removed
- History remains after a member is removed
- WebSocket events: `group_member_added`, `group_member_removed`

### UI / UX (functional)

- Signal-inspired Windows layout: rail, chats column, chat canvas
- Chats / Calls / Stories rail; Settings gear
- Compact conversation list, search, composer (Enter send, Shift+Enter newline)
- Hover/focus tooltips on Chats, Calls, Stories
- Show / Hide Tabs (hamburger)
- Settings + profile + Appearance (Light / Dark, persisted as `signal-theme`)
- Responsive: on small screens the chat pane can hide the list until Back

### Placeholders (not implemented)

| Area | Behavior |
| --- | --- |
| **Calls** | UI tab + empty pane only |
| **Stories** | UI tab + empty pane only |
| **Linked devices / other settings rows** | “Coming Soon” |
| **Attachments, GIFs, stickers, reactions, replies, disappearing messages, E2EE, real calls** | Not implemented |

---

## Architecture

**Frontend:** Next.js App Router, TypeScript, React. `AuthProvider` (session cookie + `/auth/me`). `lib/api.ts` talks to `http://127.0.0.1:8000` with `credentials: "include"`. `useConversationSockets` opens `ws://127.0.0.1:8000/ws/conversations/{id}`. `ThemeProvider` uses CSS variables + `localStorage` (no backend).

**Backend:** FastAPI routers (`auth`, `contacts`, `conversations`, `messages`, WebSocket). SQLAlchemy + SQLite (`backend/signal.db`). In-process `ConnectionManager` for sockets (no Redis).

**Message send path:** Composer → REST `POST /conversations/{id}/messages` → persist + broadcast `type: "message"`. Typing/read go over WebSocket; read falls back to REST if the socket is not open.

---

## Authentication

Assignment/demo auth — **not production-grade**.

- No passwords, JWT, or SMS
- **Fixed OTP:** `123456`
- Cookie name: `session_token` (HTTP-only, `SameSite=Lax`, `secure=False` for local HTTP)
- Session row in `auth_sessions`, TTL **30 days**
- Use **`http://127.0.0.1:3000`** (and API `127.0.0.1:8000`) so the cookie matches the frontend origin (`frontend/lib/api.ts` and `next.config.ts` `allowedDevOrigins`)

---

## REST API

Source of truth: `backend/app/*/router.py` and `backend/app/main.py`.

### App

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/` | API running check |
| GET | `/health` | Health check |

### Authentication

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/auth/register` | Create user + session cookie |
| POST | `/auth/login` | Login + session cookie |
| GET | `/auth/me` | Current user |
| POST | `/auth/logout` | Delete session + cookie |

### Contacts

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/contacts/search?q=` | Search users |
| GET | `/contacts` | List contacts |
| POST | `/contacts` | Add contact (`user_id`) |
| DELETE | `/contacts/{user_id}` | Remove contact |

### Conversations / groups

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/conversations` | List memberships |
| POST | `/conversations/direct` | Get-or-create 1:1 (`target_user_id`) |
| POST | `/conversations/group` | Create group (`name`, `member_ids`) |
| GET | `/conversations/{id}` | Conversation detail |
| GET | `/conversations/{id}/members` | Group members |
| POST | `/conversations/{id}/members` | Admin add member |
| DELETE | `/conversations/{id}/members/{user_id}` | Admin remove / self-leave |

### Messages / receipts

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/conversations/{id}/messages` | Send text |
| GET | `/conversations/{id}/messages` | History (`limit`, `offset`) |
| POST | `/conversations/{id}/messages/{message_id}/read` | Mark read |

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## WebSocket

**Endpoint:** `ws://127.0.0.1:8000/ws/conversations/{conversation_id}`

Auth: same `session_token` cookie. Non-members are rejected. In-process room manager (assignment/MVP; not multi-server).

**Client → server:** `message` (`content`), `typing` (`is_typing`), `read` (`message_id`)

**Server → client:** `message`, `receipt`, `typing`, `presence`, `group_member_added`, `group_member_removed`, `error`

---

## Database

SQLite file: `backend/signal.db` (created on API startup). Models: `backend/app/models.py`.

| Table | Purpose |
| --- | --- |
| `users` | Accounts, profile, `is_online`, `last_seen` |
| `contacts` | One-way address book |
| `conversations` | `type` `direct` or `group`; unique `direct_pair_key` for 1:1 |
| `conversation_members` | Membership + `admin` / `member` + `last_read_at` |
| `messages` | Text body + sender |
| `message_receipts` | Per-recipient `sent` / `delivered` / `read` |
| `auth_sessions` | Cookie token + expiry |

**Relationships:** User → Contacts; User ↔ Conversations via ConversationMember; Conversation → Messages; Message → MessageReceipts; User → AuthSessions.

---

## Seed data

From `backend/`:

```powershell
python -m app.seed
```

Not run on API startup. Uses **get-or-create** (users by username, contacts, conversations, messages matched by conversation + sender + content) so re-runs do not blindly duplicate those rows.

**OTP for all seeded users:** `123456`

| Username | Display name | Phone |
| --- | --- | --- |
| `sneha` | Sneha | +15550001001 |
| `rahul` | Rahul | +15550001002 |
| `priya` | Priya | +15550001003 |
| `amit` | Amit | +15550001004 |
| `neha` | Neha | +15550001005 |

**Groups:** Project Team (sneha, rahul, priya, amit); Weekend Plans (sneha, priya, neha). Direct threads include sneha with each of the others, plus rahul–amit.

---

## Local setup

No `.env` files are required for this local setup. API and WS URLs are hardcoded to `127.0.0.1:8000` in the frontend.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.seed
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open **[http://127.0.0.1:3000](http://127.0.0.1:3000)** (not `localhost` if cookies fail to attach).

---

## Environment variables

None required. Theme uses browser `localStorage` key `signal-theme`.

---

## Testing / verification

**Frontend** (from `frontend/`): `npm run lint` and `npm run build` (both pass as of this documentation).

**Backend** (from `backend/`, after activating `.venv`):

```powershell
python -m unittest discover -s tests
```

`unittest` suites (no extra test runner):

| File | Coverage |
| --- | --- |
| `test_auth.py` | Register/login/logout, OTP, cookie, `/me` |
| `test_contacts_conversations.py` | Search, contacts, direct/group create |
| `test_messages.py` | Persist, pagination, membership, receipts on send |
| `test_websocket.py` | Connect, broadcast, isolation, validation |
| `test_receipts.py` | sent → delivered → read, WS read |
| `test_typing.py` | Typing scope and disconnect |
| `test_presence.py` | Online/offline broadcasts |
| `test_group_members.py` | Admin add/remove, last admin, WS after remove |

**Manually verified:** login, DM, live WS, receipts, typing, presence, groups, Calls/Stories placeholders, Light/Dark, Show/Hide Tabs, session persist, logout/login.

---

## Security / limitations

- Signal-inspired assignment clone, **not** Signal Protocol / E2EE
- Fixed demo OTP; no SMS
- Calls and Stories are UI placeholders
- WebSocket manager is **in-process** (single API process)
- Local HTTP cookies use `secure=False`
- Unread badges are tracked in the browser for the current session (live WebSocket). They are not a SQLite conversation field, so a full page refresh resets counts to zero.
- Not production-ready messaging infrastructure

---

## Design / UI

The UI is **Signal-inspired** for **Windows desktop** (not a pixel-perfect clone): navigation rail, Chats / Calls / Stories, dense conversation list, blue own bubbles / gray incoming, composer, settings/profile, tooltips, section empty states, Light/Dark.

---

## Assignment requirements

| Requirement | Status | Implementation |
| --- | --- | --- |
| Authentication | Done | Mock OTP + HTTP-only `session_token` |
| Contacts / conversations | Done | Search, contacts, direct + group list |
| 1:1 messaging | Done | REST send + SQLite + WS live |
| Delivery / read receipts | Done | `message_receipts` + REST/WS |
| Typing indicators | Done | Ephemeral WS `typing` |
| Presence | Done | `users.is_online` / `last_seen` |
| Groups | Done | Create, members, admin add/remove |
| Signal-like UI | Done | Windows-inspired desktop layout |
| Calls / Stories | Placeholder | Tabs + empty panes only |
| SQLite schema | Done | Seven tables in `models.py` |
| WebSockets | Done | `/ws/conversations/{id}` |
| E2EE | Not implemented | Explicitly out of scope |

---

## Project structure

```
signal-clone/
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── signal.db                 # created at runtime
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── seed.py
│   │   ├── auth/                 # register, login, cookie session
│   │   ├── contacts/
│   │   ├── conversations/
│   │   ├── messages/             # send, history, receipts
│   │   └── websocket/            # router, manager, presence
│   └── tests/
└── frontend/
    ├── package.json
    ├── app/                      # layout, page, globals.css
    ├── components/
    │   ├── auth/
    │   ├── chat/
    │   ├── conversations/
    │   ├── groups/
    │   ├── settings/
    │   ├── shell/
    │   ├── theme/
    │   └── common/
    └── lib/                      # api.ts, sockets, ownership mapping
```

---

## Demo flow

1. Start backend (`127.0.0.1:8000`) and seed if needed.
2. Start frontend; open `http://127.0.0.1:3000`.
3. Log in as `sneha` (or another seeded user) with OTP `123456`.
4. Open a direct chat; send a message.
5. In another browser profile/window, log in as `rahul` (same OTP).
6. Confirm live messages, typing, and ticks (delivered/read).
7. Open **Project Team**; add/remove a member as admin (`sneha`).
8. Open Calls and Stories placeholders.
9. Settings → Appearance → Dark / Light; refresh to confirm persist.
10. Log out, then log in again.

---

## Future / optional (not implemented)

- Real Signal Protocol / E2EE
- Real voice/video calls and persistent Stories
- Attachments, reactions, replies, GIFs, stickers
- Disappearing messages
- Linked devices
- Multi-server WebSockets / Redis
- Production auth (real OTP, HTTPS cookies)

---

## GitHub / deployment

Not documented here. Hosting, repository URL, and production credentials will be added when they exist.

---

## License / context

Course assignment: **Secure Messaging Platform (Signal Clone)**. Not affiliated with Signal Messenger.
