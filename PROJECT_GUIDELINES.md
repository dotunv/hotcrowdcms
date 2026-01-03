# HotCrowd CMS - Complete Project Guidelines

This comprehensive guide covers all aspects of developing and maintaining the HotCrowd CMS project, including Django templates, Cotton components, HTMX, Alpine.js, and project architecture.

## Table of Contents

1. [Project Architecture](#project-architecture)
2. [Django Template Guidelines](#django-template-guidelines)
3. [Cotton Component System](#cotton-component-system)
4. [HTMX Integration](#htmx-integration)
5. [Alpine.js Usage](#alpinejs-usage)
6. [Styling with Tailwind CSS](#styling-with-tailwind-css)
7. [Common Patterns](#common-patterns)
8. [Pitfalls to Avoid](#pitfalls-to-avoid)
9. [Development Workflow](#development-workflow)

---

## Project Architecture

### Tech Stack Overview

```
Frontend:
├── Tailwind CSS 3.x - Utility-first CSS framework
├── Django Cotton - Component-based template system
├── HTMX - Dynamic interactions without JavaScript
├── Alpine.js - Minimal JavaScript framework for interactivity
└── SortableJS - Drag-and-drop functionality

Backend:
├── Django 6.0 - Web framework
├── Django Ninja - Fast API framework
├── PostgreSQL - Database
└── Django Allauth - Authentication
```

### Directory Structure

```
hotcrowdcms/
├── templates/
│   ├── base.html                    # Base template with head/body structure
│   ├── cotton/                      # Reusable Cotton components
│   │   ├── layouts/                 # Layout components
│   │   │   ├── sidebar.html         # Main sidebar layout
│   │   │   ├── auth.html            # Authentication layout
│   │   │   └── navbar.html          # Navbar component
│   │   ├── ui/                      # UI components
│   │   │   └── stat_card.html       # Statistic card component
│   │   └── playlist/                # Feature-specific components
│   │       ├── media_library.html
│   │       ├── sequence_editor.html
│   │       ├── settings_panel.html
│   │       └── preview_modal.html
│   ├── dashboard.html               # Page templates
│   ├── playlists.html
│   └── screens.html
├── cms/                             # CMS application
│   ├── views.py                     # View functions
│   └── urls.py                      # URL routing
├── core/                            # Core models
│   └── models.py                    # Screen, Playlist, MediaAsset, etc.
├── services/                        # Business logic layer
│   ├── instagram.py
│   └── playlist.py
└── api/                             # API endpoints
    └── api.py
```

---

## Django Template Guidelines

### Template Syntax Rules

#### 1. Always Use Spaces Around Operators

**❌ WRONG:**
```django
{% if status=='ACTIVE' %}
{% if count==0 %}
```

**✅ CORRECT:**
```django
{% if status == 'ACTIVE' %}
{% if count == 0 %}
```

#### 2. Never Split Template Tags Across Lines

**❌ WRONG:**
```django
{% if condition
%}

{% if condition %}text{%
endif %}
```

**✅ CORRECT:**
```django
{% if condition %}
    content
{% endif %}

<!-- For inline tags -->
{% if condition %}text{% else %}other{% endif %}
```

#### 3. Match Block Tags Correctly

| Opening Tag | Closing Tag |
|-------------|-------------|
| `{% if %}` | `{% endif %}` |
| `{% for %}` | `{% endfor %}` |
| `{% block %}` | `{% endblock %}` |
| `{% with %}` | `{% endwith %}` |

#### 4. Use {% empty %} Only Inside {% for %} Loops

**❌ WRONG:**
```django
{% if items %}
    {% for item in items %}
        {{ item }}
    {% endfor %}
{% empty %}
    No items
{% endif %}
```

**✅ CORRECT:**
```django
{% for item in items %}
    {{ item }}
{% empty %}
    No items
{% endfor %}
```

### Template Inheritance

**base.html Structure:**
```django
<!DOCTYPE html>
<html lang="en">
<head>
    {% block head %}
        <!-- Meta tags, CSS, etc. -->
    {% endblock %}
</head>
<body>
    {% block body %}
        <!-- Page content -->
    {% endblock %}

    {% block extra_js %}
        <!-- Page-specific JavaScript -->
    {% endblock %}
</body>
</html>
```

**Page Template Structure:**
```django
{% extends 'base.html' %}

{% block body %}
<c-layouts.sidebar>
    <!-- Page content here -->
</c-layouts.sidebar>
{% endblock %}

{% block extra_js %}
<script>
    // Page-specific JavaScript
</script>
{% endblock %}
```

---

## Cotton Component System

Cotton is a component library for Django that allows you to create reusable template components with props and slots.

### Creating a Cotton Component

**Location:** Place components in `templates/cotton/`

**Component Structure:**
```django
<!-- templates/cotton/ui/button.html -->
<c-vars label type="primary" />

<button class="btn btn-{{ type }}">
    {{ label }}
</button>
```

### Using Cotton Components

#### 1. Simple Component Usage

```django
<c-ui.button label="Click Me" type="primary" />
```

#### 2. Components with Slots

**Component Definition:**
```django
<!-- templates/cotton/layouts/sidebar.html -->
<div class="sidebar">
    <!-- Sidebar navigation -->
    {{ slot }}  <!-- Default slot content -->
</div>
```

**Usage:**
```django
<c-layouts.sidebar>
    <div class="content">
        <!-- This content fills the {{ slot }} -->
    </div>
</c-layouts.sidebar>
```

#### 3. Components with Props

**Component Definition:**
```django
<!-- templates/cotton/ui/stat_card.html -->
<c-vars label value icon color />

<div class="stat-card">
    <h3>{{ label }}</h3>
    <p class="text-{{ color }}-600">{{ value }}</p>
    <span class="material-symbols-outlined">{{ icon }}</span>
</div>
```

**Usage:**
```django
<c-ui.stat_card
    label="Total Screens"
    value="12"
    icon="monitor"
    color="blue" />
```

#### 4. Passing Django Variables to Components

**✅ CORRECT:**
```django
<!-- Using :variable syntax to pass Django context -->
<c-playlist.media_library :media_items="media_items" :playlist="playlist" />
```

**Inside Component:**
```django
<!-- templates/cotton/playlist/media_library.html -->
<c-vars media_items playlist />

{% for item in media_items %}
    <div>{{ item.name }}</div>
{% endfor %}
```

### Cotton Component Best Practices

1. **Declare Props at Top:**
   ```django
   <c-vars prop1 prop2="default_value" />
   ```

2. **Keep Components Small and Focused:**
   - One component per responsibility
   - Extract reusable UI patterns
   - Avoid deeply nested component hierarchies

3. **Use Descriptive Names:**
   - `stat_card.html` not `card.html`
   - `media_library.html` not `library.html`

4. **Organize by Feature or Type:**
   ```
   cotton/
   ├── layouts/     # Page layouts
   ├── ui/          # Reusable UI components
   └── playlist/    # Feature-specific components
   ```

### Common Cotton Pitfalls

**❌ WRONG: Forgetting to declare vars**
```django
<!-- Component will fail -->
<div>{{ title }}</div>
```

**✅ CORRECT:**
```django
<c-vars title />
<div>{{ title }}</div>
```

**❌ WRONG: Using component syntax in regular templates**
```django
<!-- This won't work in non-Cotton templates -->
<c-vars something />
```

**✅ CORRECT:**
```django
<!-- Only use <c-vars> in Cotton component files -->
```

---

## HTMX Integration

HTMX allows you to access AJAX, CSS Transitions, WebSockets and Server Sent Events directly in HTML, using attributes.

### Core HTMX Attributes

| Attribute | Purpose | Example |
|-----------|---------|---------|
| `hx-get` | Issue GET request | `hx-get="/api/data"` |
| `hx-post` | Issue POST request | `hx-post="/api/save"` |
| `hx-put` | Issue PUT request | `hx-put="/api/update"` |
| `hx-delete` | Issue DELETE request | `hx-delete="/api/delete"` |
| `hx-target` | Element to swap content into | `hx-target="#result"` |
| `hx-swap` | How to swap content | `hx-swap="innerHTML"` |
| `hx-trigger` | What triggers the request | `hx-trigger="click"` |

### HTMX Patterns in This Project

#### 1. Search with Debounce

```django
<input type="text"
    placeholder="Search media..."
    hx-get="{% url 'playlist_builder' %}"
    hx-trigger="keyup changed delay:500ms"
    hx-target="#media-grid"
    hx-select="#media-grid">
```

**How it works:**
- Triggers GET request on keyup
- Waits 500ms after typing stops (debounce)
- Replaces `#media-grid` content with response
- `hx-select` extracts only the `#media-grid` from response

#### 2. Form Submission with Swap

```django
<button type="button"
    hx-post="{% url 'remove_from_playlist' item.id %}"
    hx-target="#playlist-sequence-container"
    hx-swap="outerHTML">
    Remove
</button>
```

**How it works:**
- POST request to remove endpoint
- Replaces entire `#playlist-sequence-container` element
- Server returns new HTML for the container

#### 3. Update on Change

```django
<input type="number"
    name="duration"
    value="{{ item.duration }}"
    hx-post="{% url 'update_playlist_item' item.id %}"
    hx-trigger="change delay:500ms"
    hx-swap="none">
```

**How it works:**
- Triggers POST when value changes
- Waits 500ms after change
- `hx-swap="none"` means don't replace any content (silent update)

#### 4. Conditional Requests with CSRF

```django
<form hx-post="/api/save">
    {% csrf_token %}
    <input type="text" name="title">
    <button type="submit">Save</button>
</form>
```

**Important:** Always include `{% csrf_token %}` in forms!

### HTMX Swap Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `innerHTML` | Replace inner content (default) | Updating content area |
| `outerHTML` | Replace entire element | Replacing component |
| `beforeend` | Append inside, at end | Adding to list |
| `afterend` | Insert after element | Inserting sibling |
| `beforebegin` | Insert before element | Prepending sibling |
| `none` | Don't swap | Silent updates |

### HTMX Best Practices

1. **Use Meaningful Targets:**
   ```django
   <!-- Good: Specific target -->
   hx-target="#playlist-items"

   <!-- Avoid: Generic target -->
   hx-target="#content"
   ```

2. **Debounce User Input:**
   ```django
   <!-- Always debounce search and filters -->
   hx-trigger="keyup changed delay:500ms"
   ```

3. **Return Partial HTML:**
   ```python
   # views.py
   def update_playlist(request):
       # ... update logic ...
       return render(request, 'partials/playlist_items.html', context)
   ```

4. **Use hx-select for Partial Updates:**
   ```django
   <!-- Extract only needed part from full page response -->
   hx-get="{% url 'dashboard' %}"
   hx-target="#stats"
   hx-select="#stats"
   ```

### HTMX Common Pitfalls

**❌ WRONG: Forgetting CSRF token**
```django
<form hx-post="/save">
    <!-- Will fail with 403 -->
</form>
```

**✅ CORRECT:**
```django
<form hx-post="/save">
    {% csrf_token %}
    <!-- Now it works -->
</form>
```

**❌ WRONG: No debounce on frequent events**
```django
<!-- Will spam server -->
<input hx-get="/search" hx-trigger="keyup">
```

**✅ CORRECT:**
```django
<input hx-get="/search" hx-trigger="keyup changed delay:500ms">
```

---

## Alpine.js Usage

Alpine.js is a lightweight JavaScript framework for adding interactivity. Use it for client-side state and UI interactions.

### When to Use Alpine vs HTMX

| Use Alpine.js | Use HTMX |
|---------------|----------|
| Modal toggling | Form submission |
| Dropdown menus | Search with server |
| Tabs switching | Loading more items |
| Client-side filtering | Updating data |
| Animations | Real-time updates |

### Alpine.js Directives

| Directive | Purpose | Example |
|-----------|---------|---------|
| `x-data` | Define component state | `x-data="{ open: false }"` |
| `x-show` | Toggle visibility | `x-show="open"` |
| `x-if` | Conditional rendering | `x-if="count > 0"` |
| `@click` | Event listener | `@click="open = true"` |
| `x-bind` | Bind attributes | `:class="{ active: open }"` |
| `x-model` | Two-way binding | `x-model="search"` |

### Alpine.js Patterns in This Project

#### 1. Modal Management

```django
<div x-data="{
    showConnectModal: false,
    showSuccessModal: false
}">
    <!-- Trigger -->
    <button @click="showConnectModal = true">
        Connect Screen
    </button>

    <!-- Modal -->
    <div x-show="showConnectModal"
         x-transition
         class="modal">
        <div class="modal-content">
            <h2>Connect Screen</h2>
            <button @click="showConnectModal = false">
                Close
            </button>
        </div>
    </div>
</div>
```

#### 2. Tabs Component

```django
<div x-data="{ activeTab: 'all' }">
    <!-- Tab Buttons -->
    <button @click="activeTab = 'all'"
            :class="{ 'active': activeTab === 'all' }">
        All
    </button>
    <button @click="activeTab = 'videos'"
            :class="{ 'active': activeTab === 'videos' }">
        Videos
    </button>

    <!-- Tab Content -->
    <div x-show="activeTab === 'all'">
        All content
    </div>
    <div x-show="activeTab === 'videos'">
        Video content
    </div>
</div>
```

#### 3. Dropdown Menu

```django
<div x-data="{ open: false }" @click.away="open = false">
    <button @click="open = !open">
        Menu
    </button>

    <div x-show="open"
         x-transition
         class="dropdown">
        <a href="#">Item 1</a>
        <a href="#">Item 2</a>
    </div>
</div>
```

#### 4. Form Validation

```django
<div x-data="{
    email: '',
    isValid: false
}" x-init="$watch('email', value => isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value))">
    <input type="email"
           x-model="email"
           placeholder="Enter email">

    <span x-show="!isValid && email.length > 0"
          class="error">
        Invalid email
    </span>

    <button :disabled="!isValid">
        Submit
    </button>
</div>
```

### Alpine.js Best Practices

1. **Keep State Close to Usage:**
   ```django
   <!-- Good: Component-scoped -->
   <div x-data="{ open: false }">
       <button @click="open = !open">Toggle</button>
       <div x-show="open">Content</div>
   </div>
   ```

2. **Use @click.away for Dropdowns:**
   ```django
   <div x-data="{ open: false }" @click.away="open = false">
       <!-- Closes when clicking outside -->
   </div>
   ```

3. **Use x-transition for Smooth Animations:**
   ```django
   <div x-show="open" x-transition>
       <!-- Fades in/out smoothly -->
   </div>
   ```

4. **Combine with HTMX for Full-Stack Reactivity:**
   ```django
   <div x-data="{ loading: false }">
       <button @click="loading = true"
               hx-post="/save"
               hx-on::after-request="loading = false">
           <span x-show="!loading">Save</span>
           <span x-show="loading">Saving...</span>
       </button>
   </div>
   ```

### Alpine.js Common Pitfalls

**❌ WRONG: Using Alpine for server interactions**
```django
<!-- Don't use Alpine to fetch from server -->
<div x-data="{ items: [] }"
     x-init="fetch('/api/items').then(r => r.json()).then(d => items = d)">
```

**✅ CORRECT: Use HTMX for server interactions**
```django
<div hx-get="/api/items" hx-trigger="load">
    <!-- HTMX handles server communication -->
</div>
```

**❌ WRONG: Complex state management in Alpine**
```django
<!-- Too complex for Alpine -->
<div x-data="{
    users: [],
    filteredUsers: [],
    sortBy: 'name',
    // ... 20 more properties
}">
```

**✅ CORRECT: Keep Alpine state simple**
```django
<!-- Simple UI state only -->
<div x-data="{ open: false, selected: null }">
```

---

## Styling with Tailwind CSS

### Design System

This project uses a consistent design system with Tailwind CSS.

#### Color Palette

```javascript
// tailwind.config.js
colors: {
    primary: '#057A43',      // Green
    secondary: '#046835',    // Darker green

    // Backgrounds
    'background-light': '#F9F9F7',
    'background-dark': '#0F1419',

    // Surfaces
    'surface-light': '#FFFFFF',
    'surface-dark': '#1A1F25',

    // Borders
    'border-light': '#E5E7EB',
    'border-dark': '#374151',

    // Text
    'muted-light': '#6B7280',
    'muted-dark': '#9CA3AF',
}
```

#### Spacing Scale

Use Tailwind's default spacing scale consistently:
- `p-4` for small padding (1rem)
- `p-6` for medium padding (1.5rem)
- `p-8` for large padding (2rem)

#### Border Radius

- `rounded-lg` - Small elements (buttons, inputs)
- `rounded-xl` - Medium elements (cards)
- `rounded-2xl` - Large elements (modals, sections)

### Component Styling Patterns

#### 1. Card Component

```html
<div class="bg-white dark:bg-surface-dark
            rounded-2xl shadow-soft
            border border-border-light dark:border-border-dark
            p-6">
    <!-- Card content -->
</div>
```

#### 2. Button Styles

```html
<!-- Primary Button -->
<button class="inline-flex items-center
               px-4 py-2
               bg-primary text-white
               text-sm font-bold
               rounded-xl
               hover:bg-secondary
               transition-all
               shadow-sm hover:shadow-md">
    Button Text
</button>

<!-- Secondary Button -->
<button class="px-4 py-2
               bg-white dark:bg-surface-dark
               border border-border-light dark:border-border-dark
               text-gray-700 dark:text-gray-300
               text-sm font-medium
               rounded-xl
               hover:bg-gray-50 dark:hover:bg-gray-800
               transition-colors">
    Button Text
</button>
```

#### 3. Input Fields

```html
<input type="text"
       class="w-full
              px-3 py-2
              bg-gray-50 dark:bg-gray-800
              border border-border-light dark:border-border-dark
              rounded-xl
              text-sm
              focus:ring-2 focus:ring-primary/20
              focus:border-primary
              outline-none
              transition-all">
```

#### 4. Status Badges

```html
<!-- Active -->
<span class="px-2 py-1
             rounded
             bg-green-100 text-green-700
             text-xs font-bold">
    Active
</span>

<!-- Draft -->
<span class="px-2 py-1
             rounded
             bg-yellow-100 text-yellow-700
             text-xs font-bold">
    Draft
</span>
```

### Dark Mode

Always include dark mode classes:

```html
<!-- Background -->
class="bg-white dark:bg-surface-dark"

<!-- Text -->
class="text-gray-900 dark:text-white"

<!-- Borders -->
class="border-gray-200 dark:border-gray-700"
```

### Responsive Design

Use responsive prefixes consistently:

```html
<!-- Stack on mobile, row on desktop -->
<div class="flex flex-col md:flex-row gap-4">

<!-- Full width on mobile, fixed on desktop -->
<div class="w-full md:w-80">

<!-- Hide on mobile, show on desktop -->
<span class="hidden md:inline-block">
```

### Tailwind Best Practices

1. **Use @apply Sparingly:**
   - Prefer utility classes in HTML
   - Only use `@apply` for repeated complex patterns

2. **Follow Spacing Consistency:**
   - Use `gap-` for flex/grid spacing
   - Use `space-y-` for vertical spacing between children
   - Use `p-` and `m-` for padding/margin

3. **Group Related Classes:**
   ```html
   <!-- Layout classes first -->
   class="flex items-center gap-3
          <!-- Size classes -->
          w-full h-10
          <!-- Appearance classes -->
          bg-white rounded-xl border
          <!-- State classes -->
          hover:bg-gray-50 focus:ring-2"
   ```

---

## Common Patterns

### Pattern 1: Page with Sidebar Layout

```django
{% extends 'base.html' %}

{% block body %}
<c-layouts.sidebar>
    <div class="space-y-8">
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
                <nav class="flex text-sm text-gray-500 mb-1">
                    <a href="{% url 'dashboard' %}" class="hover:text-gray-900">Dashboard</a>
                    <span class="mx-2">/</span>
                    <span class="text-gray-900 font-medium">Page Title</span>
                </nav>
                <h1 class="text-3xl font-display font-bold text-gray-900 dark:text-white">
                    Page Title
                </h1>
                <p class="text-muted-light dark:text-muted-dark mt-1">
                    Page description
                </p>
            </div>

            <div class="flex items-center gap-3">
                <!-- Action buttons -->
            </div>
        </div>

        <!-- Content sections -->
    </div>
</c-layouts.sidebar>
{% endblock %}
```

### Pattern 2: Table with HTMX Updates

```django
<table class="w-full">
    <thead>
        <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody id="table-body">
        {% for item in items %}
        <tr>
            <td>{{ item.name }}</td>
            <td>
                <span class="badge">{{ item.status }}</span>
            </td>
            <td>
                <button hx-post="{% url 'delete_item' item.id %}"
                        hx-target="#table-body"
                        hx-swap="outerHTML">
                    Delete
                </button>
            </td>
        </tr>
        {% empty %}
        <tr>
            <td colspan="3">No items found</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

### Pattern 3: Search with Filter

```django
<form method="get" class="space-y-4">
    <!-- Search -->
    <input type="text"
           name="search"
           value="{{ request.GET.search }}"
           placeholder="Search..."
           hx-get="{% url 'list_view' %}"
           hx-trigger="keyup changed delay:500ms"
           hx-target="#results">

    <!-- Filters -->
    <select name="status"
            onchange="this.form.submit()">
        <option value="All" {% if status_filter == 'All' %}selected{% endif %}>
            All
        </option>
        <option value="ACTIVE" {% if status_filter == 'ACTIVE' %}selected{% endif %}>
            Active
        </option>
    </select>
</form>

<div id="results">
    <!-- Results rendered here -->
</div>
```

### Pattern 4: Modal with Alpine.js

```django
<div x-data="{ showModal: false }">
    <!-- Trigger -->
    <button @click="showModal = true">
        Open Modal
    </button>

    <!-- Modal Overlay -->
    <div x-show="showModal"
         x-transition.opacity
         class="fixed inset-0 bg-black/50 z-40"
         @click="showModal = false">
    </div>

    <!-- Modal Content -->
    <div x-show="showModal"
         x-transition
         class="fixed inset-0 z-50 flex items-center justify-center p-4"
         @click.away="showModal = false">
        <div class="bg-white rounded-2xl p-6 max-w-md w-full">
            <h2 class="text-xl font-bold mb-4">Modal Title</h2>

            <!-- Modal content -->

            <button @click="showModal = false">
                Close
            </button>
        </div>
    </div>
</div>
```

### Pattern 5: Drag and Drop with SortableJS

```django
<div id="sortable-list" class="space-y-2">
    {% for item in items %}
    <div class="sortable-item" data-id="{{ item.id }}">
        {{ item.name }}
    </div>
    {% endfor %}
</div>

<script>
new Sortable(document.getElementById('sortable-list'), {
    animation: 150,
    onEnd: function(evt) {
        // Get new order
        const items = Array.from(document.querySelectorAll('.sortable-item'))
            .map(el => el.dataset.id);

        // Save to server
        fetch('{% url "save_order" %}', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': '{{ csrf_token }}'
            },
            body: JSON.stringify({ items })
        });
    }
});
</script>
```

---

## Pitfalls to Avoid

### Django Templates

1. **❌ Missing spaces around operators**
   ```django
   {% if x=='value' %}  <!-- WRONG -->
   {% if x == 'value' %}  <!-- CORRECT -->
   ```

2. **❌ Splitting template tags**
   ```django
   {% if condition  <!-- WRONG -->
   %}

   {% if condition %}  <!-- CORRECT -->
   ```

3. **❌ Using {% empty %} outside {% for %}**
   ```django
   {% if items %}
       ...
   {% empty %}  <!-- WRONG -->

   {% for item in items %}
       ...
   {% empty %}  <!-- CORRECT -->
   ```

### Cotton Components

1. **❌ Not declaring variables**
   ```django
   <div>{{ title }}</div>  <!-- WRONG, will fail -->

   <c-vars title />  <!-- CORRECT -->
   <div>{{ title }}</div>
   ```

2. **❌ Using wrong prop syntax**
   ```django
   <c-component media_items="media_items" />  <!-- WRONG, passes string -->
   <c-component :media_items="media_items" />  <!-- CORRECT, passes variable -->
   ```

### HTMX

1. **❌ Forgetting CSRF token**
   ```django
   <form hx-post="/save"></form>  <!-- WRONG -->

   <form hx-post="/save">  <!-- CORRECT -->
       {% csrf_token %}
   </form>
   ```

2. **❌ No debounce on frequent events**
   ```django
   <input hx-get="/search" hx-trigger="keyup">  <!-- WRONG, spams server -->
   <input hx-get="/search" hx-trigger="keyup changed delay:500ms">  <!-- CORRECT -->
   ```

3. **❌ Missing hx-target**
   ```django
   <button hx-get="/data"></button>  <!-- WRONG, unclear where to put result -->
   <button hx-get="/data" hx-target="#result"></button>  <!-- CORRECT -->
   ```

### Alpine.js

1. **❌ Using for server communication**
   ```django
   <!-- WRONG -->
   <div x-data="{}" x-init="fetch('/api/data')">

   <!-- CORRECT: Use HTMX -->
   <div hx-get="/api/data" hx-trigger="load">
   ```

2. **❌ Complex state management**
   ```django
   <!-- WRONG: Too complex for Alpine -->
   <div x-data="{ items: [], filters: {}, sort: {}, ... }">

   <!-- CORRECT: Keep it simple -->
   <div x-data="{ open: false, selected: null }">
   ```

### Tailwind CSS

1. **❌ Forgetting dark mode classes**
   ```html
   <div class="bg-white text-gray-900">  <!-- WRONG -->
   <div class="bg-white dark:bg-gray-900 text-gray-900 dark:text-white">  <!-- CORRECT -->
   ```

2. **❌ Inconsistent spacing**
   ```html
   <div class="p-3">  <!-- WRONG: Inconsistent -->
   <div class="p-4">  <!-- CORRECT: Use 4, 6, 8 -->
   ```

3. **❌ Not using responsive prefixes**
   ```html
   <div class="flex">  <!-- WRONG: May not work on mobile -->
   <div class="flex flex-col md:flex-row">  <!-- CORRECT -->
   ```

---

## Development Workflow

### Before Committing

1. **Check Template Syntax:**
   ```bash
   # Test load all pages
   python manage.py check --deploy
   ```

2. **Run Django Checks:**
   ```bash
   python manage.py check
   ```

3. **Format Templates (if using djlint):**
   ```bash
   djlint templates/ --reformat
   ```

4. **Test in Browser:**
   - Test all CRUD operations
   - Test HTMX interactions
   - Test Alpine.js modals/dropdowns
   - Test responsive design
   - Test dark mode

### File Checklist

When creating a new page:

- [ ] Create view in `cms/views.py`
- [ ] Add URL in `cms/urls.py`
- [ ] Create template extending `base.html`
- [ ] Use `<c-layouts.sidebar>` for layout
- [ ] Add breadcrumb navigation
- [ ] Include dark mode classes
- [ ] Test responsive design
- [ ] Add to navigation in `sidebar.html`

When creating a component:

- [ ] Place in appropriate `cotton/` subdirectory
- [ ] Declare all props with `<c-vars>`
- [ ] Use consistent styling (Tailwind)
- [ ] Include dark mode support
- [ ] Document component usage
- [ ] Test with different prop values

### Debugging Tips

1. **Template Errors:**
   - Check spacing around operators
   - Verify all tags are closed
   - Look for split template tags

2. **HTMX Not Working:**
   - Check browser console for errors
   - Verify CSRF token is present
   - Check hx-target element exists
   - Inspect network tab for responses

3. **Alpine.js Issues:**
   - Check x-data is on parent
   - Verify syntax in expressions
   - Check browser console
   - Use Alpine DevTools extension

4. **Cotton Component Errors:**
   - Verify `<c-vars>` declarations
   - Check prop passing syntax (`:` for variables)
   - Ensure component file exists

---

## Quick Reference

### Template Tag Operators

```django
==  !=  >  <  >=  <=  (all require spaces)
in  not in  and  or  not
```

### HTMX Common Attributes

```html
hx-get="/url"
hx-post="/url"
hx-target="#element"
hx-swap="innerHTML|outerHTML|beforeend|afterend|none"
hx-trigger="click|load|keyup changed delay:500ms"
hx-select="#selector"
```

### Alpine.js Common Directives

```html
x-data="{ prop: value }"
x-show="condition"
x-if="condition"
@click="action"
:class="{ 'active': isActive }"
x-model="property"
x-transition
```

### Tailwind Common Classes

```html
<!-- Layout -->
flex flex-col md:flex-row items-center justify-between gap-4

<!-- Card -->
bg-white dark:bg-surface-dark rounded-2xl shadow-soft border border-border-light p-6

<!-- Button -->
px-4 py-2 bg-primary text-white rounded-xl hover:bg-secondary transition-all

<!-- Input -->
px-3 py-2 bg-gray-50 dark:bg-gray-800 border rounded-xl focus:ring-2 focus:ring-primary
```

---

**Last Updated:** 2026-01-03
**Version:** 1.0
**Maintainer:** HotCrowd CMS Team
