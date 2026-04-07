# CareCircle Deep Dive (5th Grader Friendly, Technical)

## 1) What This App Is, In One Sentence
CareCircle is a team-care web app where one admin (circle owner) and members coordinate tasks, voice updates, alerts, and messages for one care recipient.

Think of it like:
- A shared care notebook (feed)
- A team chore board (tasks)
- A health signal recorder (voice logs + insights)
- A private group chat system (notifications)

---

## 2) The Main Tech Stack
- Backend framework: Django
- API framework: Django REST Framework (DRF)
- Database: SQLite locally (or Postgres when DATABASE_URL is set)
- Frontend style: Django templates + JavaScript fetch calls (single-page dashboard behavior)
- Audio intelligence: faster-whisper (local speech-to-text), then keyword signal extraction

---

## 3) How MVT Works Here (Model-View-Template)

Django uses MVT:
- Model = data shapes and rules in database (core/models.py)
- View = Python request handlers (core/views.py)
- Template = HTML pages (templates/core/*.html)

Important: this app also has API views.
- For page routes, View returns HTML template.
- For API routes, View returns JSON data.
- Templates use JavaScript fetch() to call API routes and paint live UI.

So the real flow is often:
Template page -> JavaScript fetch -> API View -> Model/Serializer -> JSON -> Template updates screen

---

## 4) Startup and Routing Pipeline

### 4.1 Entry point
File: manage.py
- main() sets DJANGO_SETTINGS_MODULE = config.settings
- execute_from_command_line(sys.argv) runs Django command server/migrate/test/etc.

### 4.2 Project URL router
File: config/urls.py
- path('', include('core.urls')) means most app routes live in core/urls.py
- path('admin/', admin.site.urls) is Django admin
- if DEBUG true, media files served from MEDIA_ROOT

### 4.3 App URL router
File: core/urls.py
This maps URL strings to exact handlers in core/views.py.

Examples:
- '/' -> landing_page
- '/login/' -> landing_login
- '/dashboard/' -> dashboard_demo
- '/api/tasks/' -> TaskListCreateAPIView
- '/api/voice-logs/' -> VoiceLogListCreateAPIView
- '/api/circles/<circle_id>/members/available/' -> AvailableMembersAPIView

---

## 5) Authentication and Session Flow (Login)

## Plain English
1. User submits login form from landing page.
2. Django checks credentials.
3. If correct, Django creates session cookie.
4. User is shown dashboard HTML.
5. Dashboard JS starts calling API endpoints.

## Exact code path
1. Template form in templates/core/landing.html posts to /login/ with fields:
   - identifier
   - password
   - CSRF token
2. Route /login/ goes to landing_login() in core/views.py.
3. landing_login() does:
   - if method not POST -> render landing template again
   - gets identifier and password from request.POST
   - if identifier contains '@', resolves email to username
   - authenticate(request, username, password)
   - if user is None, render page with login_error
   - auth_login(request, user) to attach session
   - return render_dashboard_page(request, 'dashboard')
4. From now on, request.user is authenticated for future requests using session cookie.

---

## 6) The Data Models (Database Tables)
File: core/models.py

## Circle
- Represents one care group.
- Key fields: name, care_recipient, created_by, created_at.

## CircleMembership
- Links users to circles with a role.
- Roles: owner or member.
- unique_together(user, circle) prevents duplicate membership in same circle.

## MemberAvailability
- Availability windows for members.
- Fields: membership, available_from, available_until, notes.
- Used to decide if admin can create task and who can be assigned.

## Task
- A care task card.
- Fields:
  - assigned_to (required at creation by business rule in view)
  - status: open, claimed, verified
  - claimed_by, claimed_expires_at, verified_by
- New policy: only assigned member (or admin) can claim.

## VoiceLog
- Stores voice transcript/audio processing status.
- status: queued, processing, completed, failed
- extracted_signals: keyword-based detected health signals.

## Alert
- Health-level alert cards.
- severity: info/watch/urgent
- status: active/addressed/dismissed

## Notification
- Message from sender to recipient in same circle.
- Supports read_at timestamp.

## FeedEntry
- Timeline entries posted by members/system/AI source.

---

## 7) Serializers (JSON Translators)
File: core/serializers.py

Serializers convert Python model objects <-> JSON safely.

Important serializer classes:
- CircleCreateSerializer / CircleListSerializer / CircleDetailSerializer
- CircleMemberSerializer (includes nested availabilities)
- MemberAvailabilitySerializer (validates available_until > available_from)
- TaskSerializer (adds assigned_to_name and actor display names)
- TaskCreateUpdateSerializer (input fields for creating/updating task)
- VoiceLogSerializer + VoiceLogCreateSerializer
- AlertSerializer + AlertUpdateSerializer
- Notification serializers and profile serializer

Why this matters:
- Prevents client from writing forbidden fields.
- Gives frontend exactly shaped data.
- Central place for field validation.

---

## 8) Permissions (Who Can Do What)
File: core/permissions.py

## IsCircleMember
- Allows only authenticated users who belong to target circle_id.

## IsCircleOwner
- Allows only authenticated owner role for target circle_id.

Views can combine DRF built-in permissions and these custom classes.

---

## 9) The View Layer (Business Logic Brain)
File: core/views.py

This file has helper functions and many class-based API views.

## 9.1 Helper functions
- get_request_circle_membership(request)
  - Finds current user's circle and role.
  - Has demo fallback behavior.
- get_member_circle_context(request)
  - Strict member-only context for feed/voice.
- get_available_members_now(circle, at_time)
  - Returns members with active availability window at given time.
- cleanup_expired_task_claims(circle)
  - Auto-reopens claimed tasks after expiration.
- build_insights_payload(circle)
  - Aggregates trend cards, confidence, watch highlights.

## 9.2 Page-rendering views (Template responses)
- landing_page
- landing_login
- dashboard_demo / tasks_page / logs_page / alerts_page
- members_management_page / profile_page / notifications_page

These return render(request, template_name, context).

## 9.3 API views (JSON responses)

### Dashboard and health
- DashboardAPIView.get
- InsightsAPIView.get
- HealthAPIView.get

### Voice logs
- VoiceLogListCreateAPIView.get/post
- VoiceLogRetryAPIView.post

### Feed
- FeedEntryListCreateAPIView.get/post

### Tasks
- TaskListCreateAPIView.get/post
- TaskDetailAPIView.patch/delete
- TaskActionAPIView.post (claim, release, verify)

### Alerts
- AlertListAPIView.get
- AlertDetailAPIView.patch

### Circle management
- CircleListCreateAPIView (list and create circle)
- CircleDetailAPIView
- CircleMemberListAPIView
- CircleMemberInviteAPIView
- CircleMemberDeleteAPIView
- MemberAvailabilityAPIView (get/post availability)
- MemberAvailabilityDeleteAPIView.delete
- AvailableMembersAPIView.get
- CircleNotificationSendAPIView.post

### User-level
- UserProfileAPIView
- UserNotificationsAPIView
- NotificationMarkReadAPIView

---

## 10) Full Flow Example A: Loading Dashboard Page

1. Browser requests /dashboard/.
2. core/urls.py routes to dashboard_demo().
3. dashboard_demo() calls render_dashboard_page(request, 'dashboard').
4. Django renders templates/core/dashboard.html with context:
   - user_role
   - initial_page
5. Browser receives HTML.
6. JavaScript in dashboard.html runs openInitialPage() and loadDashboardData().
7. JS calls fetch('/api/dashboard/').
8. DashboardAPIView.get() computes counts and recent activity using models.
9. API returns JSON.
10. JS paints cards/stats/activity with returned JSON.
11. Same page then fetches tasks/feed/voice/insights as user navigates tabs.

This is key: one HTML shell, many API calls for live data.

---

## 11) Full Flow Example B: Admin Creates a Task (Current Rules)

1. Admin opens New Task modal in dashboard template.
2. JS calls /api/circles/<id>/members/available/ to fill assignee dropdown.
3. Admin fills title/type/urgency/due_at and assigned_to.
4. JS POSTs JSON to /api/tasks/.
5. TaskListCreateAPIView.post runs checks in order:
   - Must have a circle
   - Must be owner role
   - Pick check time = due_at if provided else now
   - Query get_available_members_now(circle, at_time)
   - If none available -> HTTP 400 with message
   - Validate serializer fields
   - assigned_to required
   - assigned_to must be member in same circle
   - assigned_to must be in currently available_qs
6. If all pass, serializer.save(circle, created_by) creates Task row.
7. Response returns TaskSerializer JSON (includes assigned_to_name).
8. Frontend refreshes board via /api/tasks/.

---

## 12) Full Flow Example C: Assigned Member Claims and Admin Verifies

### Claim
1. Member clicks Claim.
2. JS POST /api/tasks/<task_id>/claim/.
3. TaskActionAPIView.post checks:
   - task must be open
   - if user is not owner and not assigned_to -> PermissionDenied 403
4. On success:
   - status becomes claimed
   - claimed_by set
   - claimed_at set
   - claimed_expires_at = now + 4 hours

### Verify
1. Admin clicks Verify.
2. JS POST /api/tasks/<task_id>/verify/.
3. View checks task must be claimed.
4. status becomes verified, verified_by and verified_at set.

---

## 13) Voice Transcript Processing Flow
Files: core/views.py and core/services.py

1. Frontend submits transcript/audio to /api/voice-logs/.
2. VoiceLogListCreateAPIView.post creates VoiceLog with status queued.
3. If transcript or audio exists, process_voice_log() is called immediately.
4. process_voice_log() in core/services.py:
   - if audio_file: transcribe_audio_file()
   - else uses transcript directly
   - if error and no transcript -> status failed
   - else -> status completed
   - extracted_signals = extract_signals_from_transcript(transcript)
   - saves processed_at/error_message/etc
5. Response returns final VoiceLog JSON.

Signal extraction is keyword-based, local, no paid API.

---

## 14) Insights Flow
Files: core/views.py and core/insights.py

1. Frontend fetches /api/insights/.
2. InsightsAPIView.get calls build_insights_payload(circle).
3. build_insights_payload uses:
   - recent voice logs
   - active watch alerts
   - feed volume
   - task activity
4. It also calls build_characteristic_trends(circle, days=14) in core/insights.py.
5. Response includes:
   - trend_cards
   - characteristic_trends history arrays
   - watch_highlights
   - confidence score + reason

The language is assistive/non-diagnostic, intentionally cautious.

---

## 15) One-Circle-Only Rule (Important)

Where enforced:
- Circle creation: CircleListCreateAPIView.perform_create
  - blocks if user already has any CircleMembership
- Member invite: CircleInviteSerializer.validate_email
  - blocks if invited user already belongs to any circle

This guarantees one user belongs to only one circle in the system.

---

## 16) How Frontend and Backend Stay in Sync

Frontend dashboard JavaScript calls API endpoints like:
- /api/dashboard/
- /api/tasks/
- /api/feed/
- /api/voice-logs/
- /api/insights/

Backend returns JSON from serializer classes.

This contract means:
- If serializer adds/removes fields, frontend must adapt.
- If frontend sends wrong field names, serializer validation fails cleanly.

---

## 17) How to Explain This App in Interviews or Team Reviews

Use this simple script:
1. Django serves initial HTML templates for pages.
2. After login session is set, dashboard runs as a JS-driven interface.
3. JS calls DRF APIViews for every live section.
4. APIViews enforce role and circle rules, then read/write models.
5. Serializers validate input and shape output JSON.
6. Templates repaint using returned JSON.

That is the practical MVT + API hybrid architecture.

---

## 18) Fast Technical Q and A Cheat Sheet

Q: Where is login logic?
A: core/views.py -> landing_login

Q: Where is role access enforced?
A: core/permissions.py custom permissions + role checks inside views

Q: Where is task assignment rule enforced?
A: core/views.py -> TaskListCreateAPIView.post and TaskActionAPIView.post

Q: Where are availability windows stored?
A: core/models.py -> MemberAvailability

Q: Where is transcript processing done?
A: core/services.py -> process_voice_log and transcribe_audio_file

Q: Where is API route mapping?
A: core/urls.py

Q: Where is dashboard page behavior?
A: templates/core/dashboard.html JavaScript fetch calls

Q: Where is data validation?
A: core/serializers.py + view-level business checks

---

## 19) If You Want True Line-by-Line Mastery

Best order to read in code:
1. core/urls.py (route map)
2. core/views.py (request logic)
3. core/serializers.py (input/output schema)
4. core/models.py (data truth)
5. templates/core/dashboard.html (how UI calls APIs)
6. core/services.py + core/insights.py (intelligence features)

Read one endpoint at a time from URL -> View -> Serializer -> Model -> Template fetch call.
That gives a complete mental movie for each feature.
