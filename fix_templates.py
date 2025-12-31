import os

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Fixed {path}")

# 1. settings_panel.html - Fix syntax
settings_panel_content = """<c-vars playlist />

<div class="bg-white rounded-xl shadow-sm border border-slate-100 p-5 w-80 flex-shrink-0 space-y-6 overflow-y-auto">
    
    <!-- Header -->
    <div>
        <h3 class="font-bold text-slate-900">Settings</h3>
        <p class="text-xs text-slate-500 mt-1">Configure playlist behavior</p>
    </div>

    <form method="post" action="{% url 'playlist_builder' %}?playlist={{ playlist.id }}" class="space-y-6">
        {% csrf_token %}
        <input type="hidden" name="save_settings" value="true">

        <!-- Name Input -->
        <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Playlist Name</label>
            <input type="text" name="name" value="{{ playlist.name }}"
                class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none">
        </div>

        <!-- Schedule Mode -->
        <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">Schedule</label>
            <select name="schedule_type"
                class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none cursor-pointer">
                <option value="ALWAYS" {% if playlist.schedule_type == 'ALWAYS' %}selected{% endif %}>Always On</option>
                <option value="SCHEDULED" {% if playlist.schedule_type == 'SCHEDULED' %}selected{% endif %}>Specific Date/Time
                </option>
                <option value="RECURRING" {% if playlist.schedule_type == 'RECURRING' %}selected{% endif %}>Recurring (Weekly)
                </option>
            </select>
        </div>

        <!-- Date Range (Show if not ALWAYS) -->
        <div class="space-y-3 p-3 bg-slate-50 rounded-lg border border-slate-100">
            <div class="grid grid-cols-2 gap-2">
                <div>
                    <label class="block text-xs font-medium text-slate-500 mb-1">Start Date</label>
                    <input type="date" name="start_date" value="{{ playlist.start_date|date:'Y-m-d' }}"
                        class="w-full px-2 py-1.5 bg-white border border-slate-200 rounded text-xs focus:border-primary outline-none">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-500 mb-1">End Date</label>
                    <input type="date" name="end_date" value="{{ playlist.end_date|date:'Y-m-d' }}"
                        class="w-full px-2 py-1.5 bg-white border border-slate-200 rounded text-xs focus:border-primary outline-none">
                </div>
            </div>
            <div class="grid grid-cols-2 gap-2">
                <div>
                    <label class="block text-xs font-medium text-slate-500 mb-1">Start Time</label>
                    <input type="time" name="start_time" value="{{ playlist.start_time|time:'H:i' }}"
                        class="w-full px-2 py-1.5 bg-white border border-slate-200 rounded text-xs focus:border-primary outline-none">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-500 mb-1">End Time</label>
                    <input type="time" name="end_time" value="{{ playlist.end_time|time:'H:i' }}"
                        class="w-full px-2 py-1.5 bg-white border border-slate-200 rounded text-xs focus:border-primary outline-none">
                </div>
            </div>
        </div>

        <!-- Transition Effect -->
        <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">Transition Effect</label>
            <div class="grid grid-cols-2 gap-2">
                <label
                    class="cursor-pointer border border-slate-200 rounded-lg p-3 hover:border-primary hover:bg-slate-50 transition-all {% if playlist.transition_effect == 'FADE' %}border-primary bg-primary/5{% endif %}">
                    <input type="radio" name="transition_effect" value="FADE" class="sr-only" {% if playlist.transition_effect == 'FADE' %}checked{% endif %}>
                    <div class="text-sm font-medium text-slate-900">Fade</div>
                    <div class="text-xs text-slate-500">Smooth crossfind</div>
                </label>
                <label
                    class="cursor-pointer border border-slate-200 rounded-lg p-3 hover:border-primary hover:bg-slate-50 transition-all {% if playlist.transition_effect == 'SLIDE' %}border-primary bg-primary/5{% endif %}">
                    <input type="radio" name="transition_effect" value="SLIDE" class="sr-only" {% if playlist.transition_effect == 'SLIDE' %}checked{% endif %}>
                    <div class="text-sm font-medium text-slate-900">Slide</div>
                    <div class="text-xs text-slate-500">Horizontal move</div>
                </label>
            </div>
        </div>

        <!-- Options -->
        <div class="space-y-3">
            <label class="flex items-center gap-3 p-3 border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-50">
                <input type="checkbox" name="is_loop" class="w-4 h-4 text-primary rounded border-slate-300 focus:ring-primary"
                    {% if playlist.is_loop %}checked{% endif %}>
                <div>
                    <span class="block text-sm font-medium text-slate-900">Loop Playlist</span>
                    <span class="block text-xs text-slate-500">Repeat when finished</span>
                </div>
            </label>
        </div>

        <!-- Assigned Screens (Read Only for now) -->
        <div>
            <div class="flex justify-between items-center mb-2">
                <label class="block text-sm font-medium text-slate-700">Assigned Screens</label>
                <button type="button" class="text-xs text-primary font-medium hover:underline">Manage</button>
            </div>
            <div class="bg-slate-50 rounded-lg border border-slate-200 p-3">
                <p class="text-xs text-slate-500 italic text-center">No screens assigned yet.</p>
            </div>
        </div>

        <!-- Save Button -->
        <div class="pt-4 border-t border-slate-100">
            <button type="submit"
                class="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-primary hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary transition-colors">
                <svg class="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
                Save Settings
            </button>
        </div>
    </form>
</div>"""

# 2. playlists.html - Fix encoding & syntax (already fixed syntax but re-writing to ensure encoding)
playlists_content = """{% extends 'base.html' %}

{% block content %}
<div class="space-y-6">
    <!-- Page Header -->
    <div class="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
        <div>
            <h1 class="text-2xl font-bold text-slate-900">Playlists</h1>
            <p class="text-slate-500 text-sm mt-1">Create and manage your screen content schedules.</p>
        </div>
        <div class="flex gap-3">
            <button
                class="px-3 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors hidden sm:inline-flex">
                <svg class="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                Settings
            </button>
            <button onclick="document.getElementById('createPlaylistModal').classList.remove('hidden')"
                class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors shadow-sm">
                <svg class="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                </svg>
                New Playlist
            </button>
        </div>
    </div>

    <!-- Filters & Search -->
    <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-100 flex flex-col md:flex-row gap-4 items-center">
        <div class="relative flex-1 w-full">
            <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24"
                stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input type="text" placeholder="Search by name..." value="{{ search_query|default:'' }}"
                onkeydown="if(event.key === 'Enter') updateQuery('search', this.value)"
                class="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all">
        </div>

        <div class="flex gap-3 w-full md:w-auto overflow-x-auto pb-2 md:pb-0">
            <select onchange="updateQuery('status', this.value)"
                class="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-600 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none cursor-pointer">
                <option value="All">Status: All</option>
                <option value="ACTIVE" {% if status_filter == 'ACTIVE' %}selected{% endif %}>Active</option>
                <option value="DRAFT" {% if status_filter == 'DRAFT' %}selected{% endif %}>Draft</option>
                <option value="SCHEDULED" {% if status_filter == 'SCHEDULED' %}selected{% endif %}>Scheduled</option>
                <option value="ARCHIVED" {% if status_filter == 'ARCHIVED' %}selected{% endif %}>Archived</option>
            </select>

            <select onchange="updateQuery('sort', this.value)"
                class="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-600 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none cursor-pointer">
                <option value="Recent" {% if sort_by == 'Recent' %}selected{% endif %}>Sort by: Recent</option>
                <option value="Name" {% if sort_by == 'Name' %}selected{% endif %}>Sort by: Name</option>
                <option value="Oldest" {% if sort_by == 'Oldest' %}selected{% endif %}>Sort by: Oldest</option>
            </select>

            <button
                class="px-3 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors whitespace-nowrap">
                <svg class="w-4 h-4 mr-1.5 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                View Calendar
            </button>
        </div>
    </div>

    <!-- Playlists Table -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
        <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr
                        class="bg-slate-50 border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                        <th class="px-6 py-4">Playlist Name</th>
                        <th class="px-6 py-4">Duration & Items</th>
                        <th class="px-6 py-4">Schedule</th>
                        <th class="px-6 py-4">Assigned Screens</th>
                        <th class="px-6 py-4">Status</th>
                        <th class="px-6 py-4 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                    {% for playlist in playlists %}
                    <tr class="hover:bg-slate-50/50 transition-colors group">
                        <!-- Name with Icon -->
                        <td class="px-6 py-4">
                            <div class="flex items-center gap-3">
                                <div
                                    class="w-10 h-10 rounded-lg bg-emerald-100 text-emerald-600 flex items-center justify-center flex-shrink-0">
                                    {% if playlist.items.first and playlist.items.first.media.media_type == 'VIDEO' %}
                                    <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                            d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                            d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    {% elif playlist.items.first and playlist.items.first.media.media_type == 'IMAGE' %}
                                    <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                    {% else %}
                                    <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                            d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                                    </svg>
                                    {% endif %}
                                </div>
                                <div>
                                    <h4 class="text-sm font-semibold text-slate-900">{{ playlist.name }}</h4>
                                    <p class="text-xs text-slate-500">Updated {{ playlist.updated_at|timesince }} ago
                                    </p>
                                </div>
                            </div>
                        </td>

                        <!-- Duration & Items -->
                        <td class="px-6 py-4">
                            <div class="flex flex-col">
                                <span class="text-sm font-medium text-slate-900">
                                    {% comment %} Rough estimate or need helper {% endcomment %}
                                    --
                                </span>
                                <span class="text-xs text-slate-500">{{ playlist.items.count }} Items</span>
                            </div>
                        </td>

                        <!-- Schedule -->
                        <td class="px-6 py-4">
                            {% if playlist.schedule_type == 'ALWAYS' %}
                            <span
                                class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-100">
                                <svg class="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                        d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                                </svg>
                                Always On
                            </span>
                            {% else %}
                            <div class="flex flex-col">
                                <span class="text-xs font-medium text-slate-700 flex items-center gap-1">
                                    <svg class="w-3 h-3 text-slate-400" fill="none" viewBox="0 0 24 24"
                                        stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                    {{ playlist.start_date|date:"M d" }} - {{ playlist.end_date|date:"M d" }}
                                </span>
                                <span class="text-[10px] text-slate-500 pl-4">{{ playlist.start_time|time:"g:i A" }} -
                                    {{ playlist.end_time|time:"g:i A" }}</span>
                            </div>
                            {% endif %}
                        </td>

                        <!-- Assigned Screens -->
                        <td class="px-6 py-4">
                            {% with count=playlist.assigned_screens.count %}
                            {% if count == 0 %}
                            <span class="text-xs text-slate-400 italic">No screens assigned</span>
                            {% else %}
                            <div class="flex items-center gap-1">
                                <span
                                    class="bg-indigo-50 text-indigo-700 border border-indigo-100 px-2 py-0.5 rounded text-xs font-medium">
                                    {{ count }} Screen{{ count|pluralize }}
                                </span>
                            </div>
                            {% endif %}
                            {% endwith %}
                        </td>

                        <!-- Status -->
                        <td class="px-6 py-4">
                            {% if playlist.status == 'ACTIVE' %}
                            <span
                                class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Active</span>
                            {% elif playlist.status == 'DRAFT' %}
                            <span
                                class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">Draft</span>
                            {% elif playlist.status == 'SCHEDULED' %}
                            <span
                                class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">Scheduled</span>
                            {% elif playlist.status == 'ARCHIVED' %}
                            <span
                                class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">Expired</span>
                            {% endif %}
                        </td>

                        <!-- Actions -->
                        <td class="px-6 py-4 text-right">
                            <div
                                class="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <a href="{% url 'playlist_builder' %}?playlist={{ playlist.id }}"
                                    class="p-1.5 text-slate-400 hover:text-primary hover:bg-primary/10 rounded-lg transition-colors"
                                    title="Edit">
                                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                            d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                    </svg>
                                </a>
                                <form action="{% url 'delete_playlist' playlist.id %}" method="post"
                                    onsubmit="return confirm('Delete this playlist?');">
                                    {% csrf_token %}
                                    <button type="submit"
                                        class="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                        title="Delete">
                                        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                        </svg>
                                    </button>
                                </form>
                            </div>
                        </td>
                    </tr>
                    {% empty %}
                    <tr>
                        <td colspan="6" class="px-6 py-12 text-center text-slate-500">
                            <p class="mb-2">No playlists found.</p>
                            <button onclick="document.getElementById('createPlaylistModal').classList.remove('hidden')"
                                class="text-primary hover:underline font-medium">Create your first playlist</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Pagination (Static for now) -->
        <div class="bg-white px-4 py-3 border-t border-slate-100 flex items-center justify-between sm:px-6">
            <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                <div>
                    <p class="text-sm text-slate-700">
                        Showing <span class="font-medium">1</span> to <span class="font-medium">{{ playlists.count
                            }}</span> of <span class="font-medium">{{ playlists.count }}</span> results
                    </p>
                </div>
                <div>
                    <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                        <a href="#"
                            class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-slate-300 bg-white text-sm font-medium text-slate-500 hover:bg-slate-50">
                            <span class="sr-only">Previous</span>
                            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                    d="M15 19l-7-7 7-7" />
                            </svg>
                        </a>
                        <a href="#"
                            class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-slate-300 bg-white text-sm font-medium text-slate-500 hover:bg-slate-50">
                            <span class="sr-only">Next</span>
                            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                    d="M9 5l7 7-7 7" />
                            </svg>
                        </a>
                    </nav>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Reused Create Playlist Modal -->
<!-- Create Playlist Modal -->
<div id="createPlaylistModal" class="hidden fixed inset-0 z-50 overflow-y-auto">
    <div class="flex items-center justify-center min-h-screen px-4 pt-4 pb-20">
        <div class="fixed inset-0 bg-black/50 transition-opacity"
            onclick="document.getElementById('createPlaylistModal').classList.add('hidden')"></div>

        <div class="relative bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <div class="flex justify-between items-center mb-6">
                <h3 class="text-lg font-semibold text-slate-900">Create Playlist</h3>
                <button onclick="document.getElementById('createPlaylistModal').classList.add('hidden')"
                    class="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100">
                    <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12">
                        </path>
                    </svg>
                </button>
            </div>

            <form action="{% url 'create_playlist' %}" method="post" class="space-y-4">
                {% csrf_token %}
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Playlist Name</label>
                    <input type="text" name="name" required placeholder="My Awesome Playlist"
                        class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none">
                </div>

                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Description (optional)</label>
                    <textarea name="description" rows="2" placeholder="A short description..."
                        class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none resize-none"></textarea>
                </div>

                <button type="submit"
                    class="w-full py-3 bg-primary text-white font-medium rounded-lg hover:bg-green-600 transition-colors">
                    Create Playlist
                </button>
            </form>
        </div>
    </div>
</div>

<script>
    function updateQuery(key, value) {
        const url = new URL(window.location.href);
        url.searchParams.set(key, value);
        window.location.href = url.toString();
    }
</script>
{% endblock %}
"""

# 3. sequence_editor.html - Fix encoding & syntax (already fixed syntax but re-writing to ensure encoding)
# NOTE: Verified content from Step 309/289
sequence_editor_content = """<c-vars playlist />

<div id="playlist-sequence-container" class="flex-1 flex flex-col bg-white rounded-xl shadow-sm border border-slate-100 min-w-0">
    <div class="px-5 py-4 border-b border-slate-100 flex justify-between items-center">
        <div class="flex items-center gap-2">
            <svg class="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M4 6h16M4 12h16M4 18h7" />
            </svg>
            <h3 class="font-bold text-slate-900">Sequence</h3>
            <span class="bg-slate-100 text-slate-600 text-xs font-semibold px-2 py-0.5 rounded-full">{{ playlist.items.count }} items</span>
        </div>
        <!-- Calculate total duration approximately in template or backend -->
        <div class="text-sm font-mono text-slate-500">
            Total: <span class="text-slate-900 font-bold">00:45</span>
        </div>
    </div>

    <div class="flex-1 overflow-y-auto p-4 bg-slate-50/50">
        <!-- Drop Zone / Sortable List -->
        <div id="playlist-sequence" class="space-y-3 min-h-[300px]">
            {% for item in playlist.items.all %}
            <div class="sequence-item bg-white p-3 rounded-xl border border-slate-200 shadow-sm flex items-center gap-4 group hover:border-green-500/50 transition-colors cursor-move"
                data-id="{{ item.id }}">
                <!-- Drag Handle -->
                <div class="text-slate-300 group-hover:text-slate-400 cursor-move">
                    <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M4 8h16M4 16h16"></path>
                    </svg>
                </div>

                <!-- Index -->
                <div class="text-xs font-mono text-slate-400 w-4">{{ forloop.counter|stringformat:"02d" }}
                </div>

                <!-- Thumbnail -->
                <div class="h-12 w-12 bg-slate-100 rounded-lg overflow-hidden flex-shrink-0">
                    {% if item.media.media_type == 'IMAGE' %}
                    <img src="{{ item.media.file_url }}" class="w-full h-full object-cover">
                    {% else %}
                    <div class="w-full h-full grid place-items-center bg-slate-800 text-white">
                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path
                                d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                        </svg>
                    </div>
                    {% endif %}
                </div>

                <!-- Details -->
                <div class="flex-1 min-w-0">
                    <h4 class="text-sm font-medium text-slate-900 truncate">
                        {% if item.media.media_type == 'IMAGE' %}Weekly Specials Banner{% else %}Fall Collection Promo{% endif %}
                    </h4>
                    <div class="flex items-center gap-2 mt-0.5">
                        <span
                            class="text-[10px] uppercase font-bold text-slate-500 bg-slate-100 px-1.5 rounded">{{ item.media.media_type }}</span>
                        <span class="text-xs text-slate-400">1920x1080</span>
                    </div>
                </div>

                <!-- Duration Control -->
                <div
                    class="flex items-center gap-2 bg-slate-50 rounded-lg px-2 py-1 border border-slate-200">
                    <svg class="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24"
                        stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <input type="number" 
                        name="duration_{{ item.id }}"
                        value="{{ item.custom_duration|default:item.media.duration }}"
                        hx-post="{% url 'update_playlist_item' item.id %}"
                        hx-trigger="change delay:500ms"
                        hx-swap="none"
                        class="w-8 text-sm bg-transparent border-none p-0 text-center focus:ring-0 font-medium text-slate-700"
                        title="Duration (s)">
                    <span class="text-xs text-slate-400">s</span>
                </div>

                <!-- Actions -->
                <button type="button"
                    hx-post="{% url 'remove_from_playlist' item.id %}"
                    hx-target="#playlist-sequence-container"
                    hx-swap="outerHTML"
                    class="p-2 text-slate-400 opacity-0 group-hover:opacity-100 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors">
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                </button>
            </div>
            {% empty %}
            <div
                class="flex flex-col items-center justify-center h-full text-slate-400 py-12 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50">
                <svg class="w-12 h-12 mb-3 text-slate-300" fill="none" viewBox="0 0 24 24"
                    stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M12 4v16m8-8H4" />
                </svg>
                <p class="font-medium text-slate-600">Drag items here to add</p>
            </div>
            {% endfor %}
        </div>
    </div>
</div>

<script>
    // Re-init Sortable if needed when content is swapped? 
    // Usually standard HTMX swap re-executes scripts in snippet.
    // Ideally put this in a load handler or use hyperscript _="on load initSortable"
    (function() {
        var el = document.getElementById('playlist-sequence');
        if (el && !el.sortable) {
            new Sortable(el, {
                animation: 150,
                ghostClass: 'bg-slate-50',
                handle: '.cursor-move',
                onEnd: function (evt) {
                    saveOrder();
                }
            });
            el.sortable = true; // Flag to prevent double init
        }
    })();
</script>"""

# Using explicit paths
write_file("c:/Users/Dotun/development/projects/hotcrowdcms/templates/cotton/playlist/settings_panel.html", settings_panel_content)
write_file("c:/Users/Dotun/development/projects/hotcrowdcms/templates/playlists.html", playlists_content)
write_file("c:/Users/Dotun/development/projects/hotcrowdcms/templates/cotton/playlist/sequence_editor.html", sequence_editor_content)
