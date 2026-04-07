# CareCircle Focus Guide: Login + Task Creation Flow

Audience: You explaining to technical people, but in simple language.
Goal: Understand one complete path deeply.

## Big Picture in 20 Seconds

- User opens landing page and submits login form.
- Django authenticates and creates a session.
- Dashboard HTML loads.
- Dashboard JavaScript calls task APIs.
- Admin creates task.
- Backend enforces role, circle membership, availability, and assignment rules.
- Task is saved and returned as JSON.
- Frontend re-renders task board.

---

## Part A: Login Flow (Exact Path)

## Step A1: Browser requests landing page

- URL: /
- Route: core/urls.py -> landing_page
- Handler: core/views.py -> landing_page(request)
- What it returns: render(request, "core/landing.html", {"login_error": ""})

What this means simply:

- Django sends HTML page to browser.
- No login yet, just page display.

## Step A2: User submits login form

- Template file: templates/core/landing.html
- Form posts to /login/
- Form sends:
  - identifier (email or username)
  - password
  - CSRF token

## Step A3: /login/ route runs login logic

- Route: core/urls.py -> landing_login
- Handler: core/views.py -> landing_login(request)

Inside landing_login, line-by-line behavior:

1. If request is not POST, show landing page again.
2. Read identifier and password from request.POST.
3. If either is empty, return landing page with error.
4. If identifier contains @, look up matching User by email.
5. If email found, convert to username for authenticate.
6. Call authenticate(request, username, password).
7. If user is None, return landing page with Invalid credentials.
8. If valid, call auth_login(request, user) to create session.
9. Return render_dashboard_page(request, "dashboard").

Why this matters:

- Session cookie is now attached.
- Future requests can use request.user.

## Step A4: Dashboard HTML is returned

- Function: render_dashboard_page(request, initial_page)
- Template: templates/core/dashboard.html
- Context includes:
  - user_role
  - initial_page

How user_role is computed:

- get_demo_user_role_label(request)
- Checks first membership for request.user in CircleMembership
- owner role -> admin label
- else member label

---

## Part B: Dashboard-to-API Bridge

After HTML loads, dashboard JavaScript runs fetch calls:

- /api/dashboard/
- /api/tasks/
- and other endpoints for feed/voice/alerts/insights

This is the key architecture pattern:

- Django template gives shell HTML.
- JavaScript fetch gets live JSON.
- API views are source of truth for business rules.

---

## Part C: Task Creation Flow (Admin)

## Step C1: Admin opens task modal

- Template file: templates/core/dashboard.html
- JS function: openTaskModal(taskId = null)
- For new task:
  - Resets form
  - Calls loadAvailableMembers()

## Step C2: Frontend loads available assignees

- JS function: loadAvailableMembers()
- Calls endpoint:
  - /api/circles/<circle_id>/members/available/
  - Optional query param at=<due_at_iso>

Backend endpoint mapping:

- Route: core/urls.py -> AvailableMembersAPIView
- Handler: core/views.py -> AvailableMembersAPIView.get
- Permission: IsCircleOwner

AvailableMembersAPIView.get behavior:

1. Finds circle by ID.
2. Reads optional query param at.
3. Parses datetime.
4. Calls get_available_members_now(circle, at_time).
5. Returns CircleMemberSerializer JSON list.

get_available_members_now behavior:

- Filters CircleMembership by:
  - same circle
  - role == member
  - availability window contains at_time

Result:

- Dropdown only shows members currently available at chosen time.

## Step C3: Frontend submits new task

- JS function: saveTask(event)
- Endpoint: POST /api/tasks/
- Payload includes:
  - title
  - description
  - task_type
  - urgency
  - due_at
  - assigned_to

Frontend guard:

- If no assignee selected on create, alert and stop.

## Step C4: Backend validates create request

- Route: core/urls.py -> TaskListCreateAPIView
- Handler: core/views.py -> TaskListCreateAPIView.post

Exact checks in order:

1. Get active circle + membership role via get_request_circle_membership.
2. If no circle -> PermissionDenied.
3. If role is not owner -> PermissionDenied.
4. Decide availability check time:

- if due_at in request, parse and use that
- else use now

5. Compute available_qs = get_available_members_now(circle, at_time).
6. If no available members exist -> 400 with detail message.
7. Validate payload with TaskCreateUpdateSerializer.
8. assigned_to must not be null -> else 400.
9. assigned_to must belong to same circle as member role -> else 400.
10. assigned_to must be inside available_qs -> else 400.
11. Save task with serializer.save(circle=circle, created_by=actor).
12. Return TaskSerializer(task) with 201 Created.

## Step C5: Serializer and model roles

- Input serializer: TaskCreateUpdateSerializer
  - Accepts create/update fields.
  - Includes assigned_to as PrimaryKeyRelatedField(User).
- Output serializer: TaskSerializer
  - Includes assigned_to_id and assigned_to_name for UI display.
- Model: Task in core/models.py
  - Stores assigned_to, status, timestamps, claim/verify actors.

## Step C6: Frontend refreshes board

After success in saveTask:

- closeTaskModal()
- loadTasksData()
- loadDashboardData()

loadTasksData calls GET /api/tasks/ and re-renders columns.

---

## Part D: Claim + Verify Mini Flow (Because It Is Connected)

## Claim

- Endpoint: POST /api/tasks/<task_id>/claim/
- Handler: TaskActionAPIView.post action=claim
- Rules:
  - task must be open
  - if not admin, user must be assigned_to
- Effects:
  - status -> claimed
  - claimed_by/claimed_at/claimed_expires_at set

## Verify

- Endpoint: POST /api/tasks/<task_id>/verify/
- Handler: TaskActionAPIView.post action=verify
- Rule:
  - task must be claimed
- Effects:
  - status -> verified
  - verified_by/verified_at set

---

## Part E: Where Each Concern Lives

- URL mapping: core/urls.py
- Page rendering views: core/views.py function views
- API business logic: core/views.py APIView/generics classes
- Data validation and JSON shape: core/serializers.py
- Database schema: core/models.py
- Access control: core/permissions.py
- Frontend API caller: templates/core/dashboard.html JavaScript

---

## Part F: MVT + API Hybrid Explained Simply

Classic MVT:

- Model: stores data
- View: decides what to do with request
- Template: shows HTML

This app adds DRF APIs:

- Template is still used to send the first page.
- Then JavaScript calls API views for live data and actions.
- So it behaves like a modern SPA, but still Django-template based.

Short phrase to remember:

- Server-rendered shell + API-driven interactivity.

---

## Part G: Fast Interview-Style Answers

Q: Where is login handled?
A: core/views.py -> landing_login

Q: How does user role reach dashboard UI?
A: render_dashboard_page passes user_role context into dashboard template.

Q: Where is admin-only task create enforced?
A: TaskListCreateAPIView.post checks membership role owner.

Q: Where is availability rule enforced?
A: TaskListCreateAPIView.post with get_available_members_now.

Q: Where is assignee validation enforced?
A: TaskListCreateAPIView.post + TaskCreateUpdateSerializer.

Q: Who can claim a task?
A: Assigned member or owner, enforced in TaskActionAPIView.post.

---

## Part H: One-Slide Summary You Can Say Out Loud

- Login is a normal Django form POST to landing_login.
- Successful auth_login creates session.
- Dashboard template loads once.
- JavaScript fetches task APIs.
- Admin task create is guarded by four checks:
  - owner role
  - at least one available member
  - selected assignee is circle member
  - selected assignee is currently available
- Task lifecycle then continues through claim and verify endpoints.
