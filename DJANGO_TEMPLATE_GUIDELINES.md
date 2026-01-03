# Django Template Guidelines

This document outlines best practices and common pitfalls to avoid when writing Django templates to prevent `TemplateSyntaxError` and other template-related issues.

## Table of Contents
1. [Template Tag Syntax Rules](#template-tag-syntax-rules)
2. [Comparison Operators](#comparison-operators)
3. [Template Tag Placement](#template-tag-placement)
4. [Block Tags](#block-tags)
5. [Common Errors and Solutions](#common-errors-and-solutions)
6. [Validation Checklist](#validation-checklist)

---

## Template Tag Syntax Rules

### Rule 1: Always use spaces around comparison operators

**❌ WRONG:**
```django
{% if status=='ACTIVE' %}
{% if count==0 %}
{% if value=='something' %}
```

**✅ CORRECT:**
```django
{% if status == 'ACTIVE' %}
{% if count == 0 %}
{% if value == 'something' %}
```

**Why:** Django's template parser requires spaces around operators (`==`, `!=`, `>`, `<`, `>=`, `<=`) to properly tokenize the expression.

### Rule 2: Never split template tags across lines

**This applies to BOTH template tags (`{% %}`) AND variable tags (`{{ }}`)**

**❌ WRONG: Template tags**
```django
{% if condition
%}

{% if condition %}content{%
endif %}
```

**❌ WRONG: Variable tags**
```django
<span>{{ variable.name|filter
}}</span>

<p>Updated {{
    playlist.updated_at|timesince }} ago</p>

<span>{{
    item.media.media_type }}</span>
```

**Why this breaks:** When Django encounters `{{` or `{%` without the closing `}}` or `%}` on the same line during parsing, it treats everything after as literal text instead of processing it as a template. This causes template code to be rendered as plain text on your page.

**✅ CORRECT:**
```django
<!-- Template tags -->
{% if condition %}
content
{% endif %}

{% if condition %}content{% else %}other{% endif %}

<!-- Variable tags -->
<span>{{ variable.name|filter }}</span>

<p>Updated {{ playlist.updated_at|timesince }} ago</p>

<span>{{ item.media.media_type }}</span>
```

**Why:** Django reads template tags as complete units. Splitting the `{%` and `%}` delimiters or tag names across lines breaks the parser.

### Rule 3: Keep inline template tags on a single line

**❌ WRONG:**
```django
<option value="X" {% if filter==
'X' %}selected{% endif %}>Label</option>
```

**✅ CORRECT:**
```django
<option value="X" {% if filter == 'X' %}selected{% endif %}>Label</option>
```

Or for better readability:
```django
<option value="X"
    {% if filter == 'X' %}selected{% endif %}>
    Label
</option>
```

---

## Comparison Operators

### Supported Operators (all require spaces)

| Operator | Usage | Example |
|----------|-------|---------|
| `==` | Equality | `{% if x == 'value' %}` |
| `!=` | Inequality | `{% if x != 'value' %}` |
| `>` | Greater than | `{% if x > 5 %}` |
| `<` | Less than | `{% if x < 10 %}` |
| `>=` | Greater or equal | `{% if x >= 5 %}` |
| `<=` | Less or equal | `{% if x <= 10 %}` |
| `in` | Membership | `{% if 'x' in list %}` |
| `not in` | Not in | `{% if 'x' not in list %}` |

### Boolean Operators

| Operator | Usage | Example |
|----------|-------|---------|
| `and` | Logical AND | `{% if x == 1 and y == 2 %}` |
| `or` | Logical OR | `{% if x == 1 or y == 2 %}` |
| `not` | Logical NOT | `{% if not x %}` |

---

## Template Tag Placement

### Rule 4: `{% empty %}` only works inside `{% for %}` loops

**❌ WRONG:**
```django
{% if items %}
    {% for item in items %}
        {{ item.name }}
    {% endfor %}
{% empty %}
    No items found
{% endif %}
```

**✅ CORRECT:**
```django
{% for item in items %}
    {{ item.name }}
{% empty %}
    No items found
{% endfor %}
```

**Why:** The `{% empty %}` tag is specifically for `{% for %}` loops to handle the case when the iterable is empty. Use `{% else %}` for `{% if %}` blocks.

### Rule 5: Match block tags correctly

Every opening tag must have a corresponding closing tag:

| Opening Tag | Closing Tag |
|-------------|-------------|
| `{% if %}` | `{% endif %}` |
| `{% for %}` | `{% endfor %}` |
| `{% block %}` | `{% endblock %}` |
| `{% with %}` | `{% endwith %}` |
| `{% comment %}` | `{% endcomment %}` |

---

## Block Tags

### If-Elif-Else Structure

**✅ CORRECT:**
```django
{% if status == 'ACTIVE' %}
    <span class="active">Active</span>
{% elif status == 'DRAFT' %}
    <span class="draft">Draft</span>
{% elif status == 'ARCHIVED' %}
    <span class="archived">Archived</span>
{% else %}
    <span class="unknown">Unknown</span>
{% endif %}
```

### For Loop with Empty

**✅ CORRECT:**
```django
{% for item in items %}
    <div>{{ item.name }}</div>
{% empty %}
    <div>No items available</div>
{% endfor %}
```

### Nested Blocks

**✅ CORRECT:**
```django
{% for playlist in playlists %}
    <div>
        {% if playlist.status == 'ACTIVE' %}
            <span class="active">{{ playlist.name }}</span>
        {% else %}
            <span class="inactive">{{ playlist.name }}</span>
        {% endif %}
    </div>
{% empty %}
    <div>No playlists found</div>
{% endfor %}
```

---

## Common Errors and Solutions

### Error 1: "Could not parse the remainder"

**Error Message:**
```
Could not parse the remainder: '=='ACTIVE'' from 'status=='ACTIVE''
```

**Cause:** Missing spaces around the `==` operator.

**Solution:** Add spaces around the operator.
```django
# Before
{% if status=='ACTIVE' %}

# After
{% if status == 'ACTIVE' %}
```

### Error 2: "Invalid block tag: 'empty', expected 'endif'"

**Error Message:**
```
Invalid block tag on line 90: 'empty', expected 'endif'
```

**Cause:** Using `{% empty %}` inside an `{% if %}` block or having an unclosed `{% if %}` tag before a `{% for %}` loop.

**Solutions:**

1. If using with a for loop, ensure it's inside the loop:
```django
{% for item in items %}
    {{ item }}
{% empty %}
    No items
{% endfor %}
```

2. If you meant to use `{% else %}`:
```django
{% if items %}
    {% for item in items %}
        {{ item }}
    {% endfor %}
{% else %}
    No items
{% endif %}
```

3. Check for unclosed `{% if %}` tags before your `{% for %}` loop.

### Error 3: "Invalid block tag: 'endif'"

**Cause:** Template tag split across multiple lines or extra `{% endif %}` without matching `{% if %}`.

**Solution:** Ensure all template tags are complete on their lines:
```django
# Before (WRONG)
{% if condition %}text{% else %}other{%
endif %}

# After (CORRECT)
{% if condition %}text{% else %}other{% endif %}
```

---

## Validation Checklist

Before committing template changes, verify:

- [ ] All comparison operators have spaces around them (`==`, `!=`, `>`, `<`, etc.)
- [ ] No template tags are split across lines
- [ ] Every `{% if %}` has a matching `{% endif %}`
- [ ] Every `{% for %}` has a matching `{% endfor %}`
- [ ] `{% empty %}` is only used inside `{% for %}` loops
- [ ] `{% else %}` is used for `{% if %}` blocks, not `{% empty %}`
- [ ] All block tags are properly nested
- [ ] Inline template tags (in HTML attributes) are on a single line or properly formatted

---

## Quick Reference: Common Patterns

### Select Dropdown with Conditional Selection
```django
<select name="status">
    <option value="All" {% if status_filter == 'All' %}selected{% endif %}>
        All
    </option>
    <option value="ACTIVE" {% if status_filter == 'ACTIVE' %}selected{% endif %}>
        Active
    </option>
</select>
```

### Conditional CSS Classes
```django
<div class="card {% if item.is_active %}active{% else %}inactive{% endif %}">
    {{ item.name }}
</div>
```

### Loop with Empty State
```django
<div class="items-list">
    {% for item in items %}
        <div class="item">{{ item.name }}</div>
    {% empty %}
        <div class="empty-state">No items found</div>
    {% endfor %}
</div>
```

### Nested Conditions
```django
{% if user.is_authenticated %}
    {% if user.is_staff %}
        <a href="{% url 'admin' %}">Admin Panel</a>
    {% else %}
        <a href="{% url 'dashboard' %}">Dashboard</a>
    {% endif %}
{% else %}
    <a href="{% url 'login' %}">Login</a>
{% endif %}
```

---

## Automated Validation

Consider using these tools to catch template errors early:

1. **Django Template Linter:**
   ```bash
   pip install djlint
   djlint templates/ --check
   ```

2. **Pre-commit Hook:**
   Add to `.pre-commit-config.yaml`:
   ```yaml
   - repo: https://github.com/Riverside-Healthcare/djLint
     rev: v1.34.0
     hooks:
       - id: djlint-django
   ```

3. **IDE Setup:**
   - PyCharm: Enable Django template syntax checking
   - VS Code: Install "Django" extension
   - Configure template language to Django in IDE settings

---

## Resources

- [Django Template Language Documentation](https://docs.djangoproject.com/en/stable/ref/templates/language/)
- [Built-in Template Tags and Filters](https://docs.djangoproject.com/en/stable/ref/templates/builtins/)
- [Cotton Component Library Docs](https://django-cotton.com/) (if using Cotton components)

---

**Last Updated:** 2026-01-03
**Version:** 1.0
