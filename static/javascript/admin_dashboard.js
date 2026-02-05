// 0. API endpoint (update if your Django URL differs)
const API_ENDPOINT = '/update-user-status/';


// 1. Data Initialization
let pendingRequests = JSON.parse(document.getElementById('pending-users-data').textContent || '[]');

// global flag at the top
let isRequestInProgress = false;

// NEW: bulk tracking (single boolean)
let isBulkAction = false;

function lockActionButtons() {
    document.querySelectorAll('.approve-btn, .reject-btn').forEach(btn => {
        btn.disabled = true;
        btn.classList.add('opacity-50', 'cursor-not-allowed');
    });
}

function unlockActionButtons() {
    document.querySelectorAll('.approve-btn, .reject-btn').forEach(btn => {
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
    });
}

// Helper: toggle role selects disabled state + visual cue
function toggleRoleSelects(disabled) {
    document.querySelectorAll('.role-select').forEach(s => {
        s.disabled = disabled;
        s.classList.toggle('opacity-50', disabled);
    });
}

// 2. CSRF Token Helper
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// 3. Database API Call
async function updateStatusInDatabase(payload) {
    try {
        const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        return data.status === 'success';

    } catch (error) {
        console.error("Error:", error);
        return false;
    }
    // NOTE: do NOT set isRequestInProgress here — caller controls the lock
}

// 4. Formatting Helpers
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: 'numeric' };
    return new Date(dateString).toLocaleDateString('en-US', options);
}

// 5. Render Table
function renderTable(data) {
    const tableBody = document.getElementById('registrationTableBody');
    const noRequestsMessage = document.getElementById('no-requests-message');
    if (!tableBody) return;
    tableBody.innerHTML = '';

    if (!data || data.length === 0) {
        if (noRequestsMessage) noRequestsMessage.classList.remove('hidden');
        return;
    } else {
        if (noRequestsMessage) noRequestsMessage.classList.add('hidden');
    }

    data.forEach(r => {
        const row = document.createElement('tr');
        row.classList.add('border-t', 'dark:border-gray-800');
        row.innerHTML = `
            <td class="py-3"><input type="checkbox" class="registration-checkbox" data-id="${r.id}"></td>
            <td class="py-3 font-medium">${r.full_name || ''}</td>
            <td class="py-3">${r.email || ''}</td>
            <td class="py-3">${r.phone_number || ''}</td>
            <td class="py-3">
                <select class="role-select px-2 py-1 rounded-lg text-xs border border-gray-300 bg-white text-gray-900 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 " data-id="${r.id}">
                    <option value="student" ${r.role === 'student' ? 'selected' : ''}>Student</option>
                    <option value="teacher" ${r.role === 'teacher' ? 'selected' : ''}>Teacher</option>
                    <option value="parent" ${r.role === 'parent' ? 'selected' : ''}>Parent</option>
                    <option value="admin" ${r.role === 'admin' ? 'selected' : ''}>Admin</option>
                </select>
            </td>
            <td class="py-3 text-xs text-gray-500">${r.date_joined ? formatDate(r.date_joined) : ''}</td>
            <td class="py-3 flex gap-2">
                <button class="px-3 py-1 rounded-lg bg-green-600 text-white text-xs approve-btn" data-id="${r.id}">Approve</button>
                <button class="px-3 py-1 rounded-lg border border-gray-200 text-xs reject-btn" data-id="${r.id}">Reject</button>
            </td>
        `;
        tableBody.appendChild(row);
    });
}

// 6. Modal and Action Logic
const confirmModal = document.getElementById('confirmModal');
const modalMessage = document.getElementById('modalMessage');
const confirmModalBtn = document.getElementById('confirmModalBtn');
const cancelModalBtn = document.getElementById('cancelModalBtn');
// reject reason references (must exist in the HTML)
const rejectReasonWrapper = document.getElementById('rejectReasonWrapper');
const rejectReasonInput = document.getElementById('rejectReasonInput');

let currentAction = ''; // single-row actions
let currentId = null;   // single-row actions

// Delegated click: use closest() so clicks on inner elements still register
const registrationTableBody = document.getElementById('registrationTableBody');
if (registrationTableBody) {
    registrationTableBody.addEventListener('click', (e) => {
        if (isRequestInProgress) return;

        const btn = e.target.closest('.approve-btn, .reject-btn');
        if (!btn) return;

        // This is a single-row action — ensure bulk mode is off
        isBulkAction = false;

        currentAction = btn.classList.contains('approve-btn') ? 'approve' : 'reject';
        currentId = btn.dataset.id;

        // Show/hide reject reason depending on action (do NOT lock buttons here)
        if (currentAction === 'reject') {
            if (rejectReasonWrapper) {
                rejectReasonWrapper.classList.remove('hidden');
                if (rejectReasonInput) rejectReasonInput.value = '';
            }
            // disable role selects during reject
            toggleRoleSelects(true);
        } else {
            if (rejectReasonWrapper) {
                rejectReasonWrapper.classList.add('hidden');
                if (rejectReasonInput) rejectReasonInput.value = '';
            }
            // ensure role selects are enabled for approve
            toggleRoleSelects(false);
        }

        modalMessage.textContent = `Are you sure you want to ${currentAction} this registration?`;
        if (confirmModalBtn) confirmModalBtn.disabled = false;
        if (cancelModalBtn) cancelModalBtn.disabled = false;
        if (confirmModalBtn) confirmModalBtn.textContent = currentAction.charAt(0).toUpperCase() + currentAction.slice(1);
        if (confirmModalBtn) confirmModalBtn.className =
            `px-4 py-2 rounded-xl text-white ${currentAction === 'approve' ? 'bg-green-600' : 'bg-red-600'}`;

        // Open modal (no locking)
        if (confirmModal) confirmModal.classList.remove('hidden');
    });
}

// Modal Confirm Click
if (confirmModalBtn) {
    confirmModalBtn.addEventListener('click', async () => {
        if (isRequestInProgress) return;

        // Caller controls the lock now
        isRequestInProgress = true;
        lockActionButtons(); // lock only when request starts

        // Lock modal UI buttons
        confirmModalBtn.disabled = true;
        if (cancelModalBtn) cancelModalBtn.disabled = true;
        confirmModalBtn.textContent = 'Processing...';

        // Build payload depending on flow
        let payload;

        if (isBulkAction) {
            // BULK-REJECT flow (modal opened only for bulk reject)
            const selectedCheckboxes = document.querySelectorAll('.registration-checkbox:checked');

            if (selectedCheckboxes.length === 0) {
                showToast('Select at least one user.');
                // restore UI
                isRequestInProgress = false;
                confirmModalBtn.disabled = false;
                if (cancelModalBtn) cancelModalBtn.disabled = false;
                confirmModalBtn.textContent = 'Reject';
                unlockActionButtons();
                toggleRoleSelects(false);
                return;
            }

            const rejectReason = rejectReasonInput ? rejectReasonInput.value.trim() : '';
            if (!rejectReason) {
                showToast('Rejection reason is required.');
                isRequestInProgress = false;
                confirmModalBtn.disabled = false;
                if (cancelModalBtn) cancelModalBtn.disabled = false;
                confirmModalBtn.textContent = 'Reject';
                unlockActionButtons();
                toggleRoleSelects(false);
                return;
            }

            payload = {
                action: 'reject',
                reason: rejectReason,
                users: Array.from(selectedCheckboxes).map(cb => ({
                    id: cb.dataset.id,
                    role: null
                }))
            };

        } else {
            // SINGLE action path
            const roleSelect = currentId ? document.querySelector(`.role-select[data-id="${currentId}"]`) : null;
            const selectedRole = roleSelect ? roleSelect.value : null;

            let singleRejectReason = null;
            if (currentAction === 'reject') {
                singleRejectReason = rejectReasonInput ? rejectReasonInput.value.trim() : null;
                if (!singleRejectReason) {
                    showToast('Rejection reason is required.');
                    isRequestInProgress = false;
                    confirmModalBtn.disabled = false;
                    if (cancelModalBtn) cancelModalBtn.disabled = false;
                    confirmModalBtn.textContent = 'Reject';
                    unlockActionButtons();
                    toggleRoleSelects(false);
                    return;
                }
            }

            payload = {
                action: currentAction,
                reason: currentAction === 'reject' ? singleRejectReason : null,
                users: [{
                    id: currentId,
                    role: currentAction === 'approve' ? selectedRole : null
                }]
            };
        }

        // If this is a bulk or single approve, validate roles before sending
        if (payload.action === 'approve') {
            const invalid = payload.users.some(u => !u.role);
            if (invalid) {
                showToast('Please select a role for all users before approving.');
                isRequestInProgress = false;
                confirmModalBtn.disabled = false;
                if (cancelModalBtn) cancelModalBtn.disabled = false;
                confirmModalBtn.textContent = 'Approve';
                unlockActionButtons();
                toggleRoleSelects(false);
                return;
            }
        }

        // Call backend
        const success = await updateStatusInDatabase(payload);

        // choose human-friendly action text
        const actionText = payload.action === 'reject' ? 'rejected' : 'approved';

        if (success) {
            const affectedIds = payload.users ? payload.users.map(u => u.id) : [];
            pendingRequests = pendingRequests.filter(r => !affectedIds.includes(r.id));
            renderTable(pendingRequests);
            showToast(`${affectedIds.length} user${affectedIds.length > 1 ? 's' : ''} ${actionText}.`);

            // Clear selection and UI states
            const selectAll = document.getElementById('selectAllCheckbox');
            if (selectAll) selectAll.checked = false;

            if (rejectReasonInput) rejectReasonInput.value = '';
            if (rejectReasonWrapper) rejectReasonWrapper.classList.add('hidden');

        } else {
            showToast("Server error. Please try again.");
        }

        // Restore modal & UI state
        confirmModalBtn.disabled = false;
        if (cancelModalBtn) cancelModalBtn.disabled = false;
        confirmModalBtn.textContent = 'Confirm';

        if (confirmModal) confirmModal.classList.add('hidden');

        // re-enable role selects (they were disabled during reject modal)
        toggleRoleSelects(false);

        unlockActionButtons();

        // Reset bulk tracking and single action tracking
        isBulkAction = false;
        currentAction = '';
        currentId = null;

        // Clear global lock
        isRequestInProgress = false;
    });
}

// Cancel button handler
if (cancelModalBtn) {
    cancelModalBtn.addEventListener('click', () => {
        if (confirmModal) confirmModal.classList.add('hidden');

        // Clear reject reason UI when cancelling
        if (rejectReasonWrapper) rejectReasonWrapper.classList.add('hidden');
        if (rejectReasonInput) rejectReasonInput.value = '';

        // Reset bulk tracking and single action tracking
        isBulkAction = false;
        currentAction = '';
        currentId = null;

        // re-enable role selects in case they were disabled
        toggleRoleSelects(false);

        // No request started, no need to unlock action buttons
        isRequestInProgress = false;
    });
}

// 7. Bulk Actions
const bulkApproveBtn = document.getElementById('bulkApprove');
const bulkRejectBtn = document.getElementById('bulkReject');

/**
 * IMPORTANT: handleBulkAction is approve-only.
 * Bulk reject must go through the Bulk Reject modal (so admin provides a reason).
 */
async function handleBulkAction(action) {
    // Protect: only allow 'approve' through this path. Reject must use modal.
    if (action !== 'approve') {
        showToast('Bulk reject must be performed via the Bulk Reject modal.');
        return;
    }

    if (isRequestInProgress) return;
    isRequestInProgress = true;
    lockActionButtons(); // lock because we will send immediately for approve
    const selectedCheckboxes = document.querySelectorAll('.registration-checkbox:checked');

    if (selectedCheckboxes.length === 0) {
        isRequestInProgress = false;
        unlockActionButtons();
        showToast('Select at least one user.');
        return;
    }

    let payload = {
        action,
        users: Array.from(selectedCheckboxes).map(cb => {
            const userId = cb.dataset.id;
            const roleSelect = document.querySelector(`.role-select[data-id="${userId}"]`);

            return {
                id: userId,
                role: action === 'approve'
                    ? (roleSelect ? roleSelect.value : null)
                    : null
            };
        })
    };

    // Validate roles for approve (prevent silent approvals)
    if (payload.action === 'approve') {
        const invalid = payload.users.some(u => !u.role);
        if (invalid) {
            showToast('Please select a role for all users before approving.');
            isRequestInProgress = false;
            unlockActionButtons();
            return;
        }
    }

    const success = await updateStatusInDatabase(payload);

    const actionText = payload.action === 'reject' ? 'rejected' : 'approved';

    if (success) {
        const affectedIds = payload.users ? payload.users.map(u => u.id) : [];

        pendingRequests = pendingRequests.filter(
            r => !affectedIds.includes(r.id)
        );

        renderTable(pendingRequests);
        showToast(`${affectedIds.length} user${affectedIds.length > 1 ? 's' : ''} ${actionText}.`);
        const selectAll = document.getElementById('selectAllCheckbox');
        if (selectAll) selectAll.checked = false;
    } else {
        showToast("Server error. Please try again.");
    }

    unlockActionButtons();
    const bulkMenu = document.getElementById('bulkActionsMenu');
    if (bulkMenu) bulkMenu.classList.add('hidden');

    // ensure flag cleared
    isRequestInProgress = false;
}

// Bulk approve remains immediate (preventDefault to avoid anchor navigation)
if (bulkApproveBtn) {
    bulkApproveBtn.addEventListener('click', (e) => {
        e.preventDefault();
        handleBulkAction('approve');
    });
}

// Bulk reject now OPENS modal so admin can type a single shared reason (preventDefault)
if (bulkRejectBtn) {
    bulkRejectBtn.addEventListener('click', (e) => {
        e.preventDefault();

        if (isRequestInProgress) return;

        const selected = document.querySelectorAll('.registration-checkbox:checked');
        if (selected.length === 0) {
            showToast('Select at least one user.');
            return;
        }

        // Set bulk state
        isBulkAction = true;

        modalMessage.textContent = `Reject ${selected.length} selected user${selected.length > 1 ? 's' : ''}?`;

        if (rejectReasonWrapper) {
            rejectReasonWrapper.classList.remove('hidden');
            if (rejectReasonInput) rejectReasonInput.value = '';
        }

        // disable role selects during bulk reject
        toggleRoleSelects(true);

        if (confirmModalBtn) {
            confirmModalBtn.textContent = 'Reject';
            confirmModalBtn.className = 'px-4 py-2 rounded-xl text-white bg-red-600';
        }

        if (confirmModal) confirmModal.classList.remove('hidden');
        // DO NOT lock here — locking occurs when request starts
    });
}

// 8. Search, Sort & Filter Functionality
const searchInput = document.getElementById('searchInput');
const sortSelect = document.getElementById('sortSelect');
const filterSelect = document.getElementById('filterSelect');

function applyFilters() {
    let results = [...pendingRequests]; // Start with full list

    // A. Apply Search
    const term = searchInput ? (searchInput.value || '').toLowerCase() : '';
    if (term) {
        results = results.filter(r => 
            (r.full_name && r.full_name.toLowerCase().includes(term)) || 
            (r.email && r.email.toLowerCase().includes(term)) ||
            (r.phone_number && r.phone_number.toLowerCase().includes(term))
        );
    }

    // B. Apply Time Filter
    const filterValue = filterSelect ? filterSelect.value : 'all';
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    if (filterValue === 'today') {
        results = results.filter(r => new Date(r.date_joined) >= startOfToday);
    } else if (filterValue === 'week') {
        const sevenDaysAgo = new Date(startOfToday);
        sevenDaysAgo.setDate(startOfToday.getDate() - 7);
        results = results.filter(r => new Date(r.date_joined) >= sevenDaysAgo);
    }

    // C. Apply Sorting
    const sortValue = sortSelect ? sortSelect.value : '';
    results.sort((a, b) => {
        const dateA = new Date(a.date_joined);
        const dateB = new Date(b.date_joined);
        const nameA = (a.full_name || '').toLowerCase();
        const nameB = (b.full_name || '').toLowerCase();

        switch (sortValue) {
            case 'recent':
                return dateB - dateA;
            case 'oldest':
                return dateA - dateB;
            case 'name_asc':
                return nameA.localeCompare(nameB);
            case 'name_desc':
                return nameB.localeCompare(nameA);
            default:
                return 0;
        }
    });

    renderTable(results);
}

if (searchInput) searchInput.addEventListener('keyup', applyFilters);
if (sortSelect) sortSelect.addEventListener('change', applyFilters);
if (filterSelect) filterSelect.addEventListener('change', applyFilters);

// 9. Clock (Consolidated)
function updateClock() {
    const now = new Date();
    const t = document.getElementById('current-time');
    const d = document.getElementById('current-date');
    if (t) t.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (d) d.textContent = now.toLocaleDateString([], { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
}
setInterval(updateClock, 1000);
updateClock();

// Initial Load
renderTable(pendingRequests);

// A. Toggle Bulk Actions Menu Visibility
const bulkActionsBtn = document.getElementById('bulkActionsBtn');
const bulkActionsMenu = document.getElementById('bulkActionsMenu');
const selectAllCheckbox = document.getElementById('selectAllCheckbox');

if (bulkActionsBtn) {
    bulkActionsBtn.addEventListener('click', () => {
        if (bulkActionsMenu) bulkActionsMenu.classList.toggle('hidden');
    });
}

// Close menu when clicking outside
document.addEventListener('click', (e) => {
    if (bulkActionsBtn && bulkActionsMenu && !bulkActionsBtn.contains(e.target) && !bulkActionsMenu.contains(e.target)) {
        bulkActionsMenu.classList.add('hidden');
    }
});

// Select All functionality
if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', (e) => {
        document.querySelectorAll('.registration-checkbox').forEach(checkbox => {
            checkbox.checked = e.target.checked;
        });
    });
}

// B. Chart.js Initialization Logic
function initAttendanceChart(canvasId, dataPoints, lineColor) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 120);
    gradient.addColorStop(0, lineColor + '33');
    gradient.addColorStop(1, lineColor + '00');

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datasets: [{
                data: dataPoints,
                borderColor: lineColor,
                backgroundColor: gradient,
                fill: true,
                tension: 0.4,
                borderWidth: 2,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { display: false },
                y: { display: false, min: 0, max: 100 }
            }
        }
    });
}

// Initialize the charts
initAttendanceChart('studentsAttendanceChart', [85, 88, 92, 90, 87, 89, 88], '#0284c7');
initAttendanceChart('teachersAttendanceChart', [95, 94, 96, 92, 95, 93, 92], '#6d28d9');

// C. Toast Helper
function showToast(message) {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toastMessage');
    if (!toast || !toastMessage) {
        alert(message);
        return;
    }
    toastMessage.textContent = message;
    toast.classList.remove('translate-y-10', 'opacity-0');
    toast.classList.add('translate-y-0', 'opacity-100');
    setTimeout(() => {
        toast.classList.remove('translate-y-0', 'opacity-100');
        toast.classList.add('translate-y-10', 'opacity-0');
    }, 3000);
}
