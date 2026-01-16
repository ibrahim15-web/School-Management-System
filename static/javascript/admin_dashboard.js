// 1. Data Initialization
let pendingRequests = JSON.parse(document.getElementById('pending-users-data').textContent);

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
async function updateStatusInDatabase(userIds, action) {
    try {
        const response = await fetch('/update-user-status/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({ 'user_ids': userIds, 'action': action })
        });
        const data = await response.json();
        return data.status === 'success';
    } catch (error) {
        console.error("Error:", error);
        return false;
    }
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
    tableBody.innerHTML = '';

    if (data.length === 0) {
        noRequestsMessage.classList.remove('hidden');
    } else {
        noRequestsMessage.classList.add('hidden');
        data.forEach(r => {
            const row = document.createElement('tr');
            row.classList.add('border-t', 'dark:border-gray-800');
            row.innerHTML = `
                <td class="py-3"><input type="checkbox" class="registration-checkbox" data-id="${r.id}"></td>
                <td class="py-3 font-medium">${r.full_name}</td>
                <td class="py-3">${r.email}</td>
                <td class="py-3">${r.phone_number}</td> 
                <td class="py-3 text-xs text-gray-500">${formatDate(r.date_joined)}</td>
                <td class="py-3 flex gap-2">
                    <button class="px-3 py-1 rounded-lg bg-green-600 text-white text-xs approve-btn" data-id="${r.id}">Approve</button>
                    <button class="px-3 py-1 rounded-lg border border-gray-200 text-xs reject-btn" data-id="${r.id}">Reject</button>
                </td>
            `;
            tableBody.appendChild(row);
        });
    }
}

// 6. Modal and Action Logic
const confirmModal = document.getElementById('confirmModal');
const modalMessage = document.getElementById('modalMessage');
const confirmModalBtn = document.getElementById('confirmModalBtn');
const cancelModalBtn = document.getElementById('cancelModalBtn');
let currentAction = '';
let currentId = null;

// Listen for clicks on Approve/Reject buttons
document.getElementById('registrationTableBody').addEventListener('click', (e) => {
    if (e.target.classList.contains('approve-btn') || e.target.classList.contains('reject-btn')) {
        currentAction = e.target.classList.contains('approve-btn') ? 'approve' : 'reject';
        currentId = e.target.dataset.id; // NO parseInt here (UUID is a string)
        modalMessage.textContent = `Are you sure you want to ${currentAction} this registration?`;
        confirmModalBtn.textContent = currentAction.charAt(0).toUpperCase() + currentAction.slice(1);
        confirmModalBtn.className = `px-4 py-2 rounded-xl text-white ${currentAction === 'approve' ? 'bg-green-600' : 'bg-red-600'}`;
        confirmModal.classList.remove('hidden');
    }
});

// Modal Confirm Click
confirmModalBtn.addEventListener('click', async () => {
    confirmModalBtn.disabled = true;
    const success = await updateStatusInDatabase([currentId], currentAction);
    if (success) {
        pendingRequests = pendingRequests.filter(r => r.id !== currentId);
        renderTable(pendingRequests);
        showToast(`User successfully ${currentAction}d.`);
    } else {
        showToast("Server error. Please try again.");
    }
    confirmModalBtn.disabled = false;
    confirmModal.classList.add('hidden');
});

cancelModalBtn.addEventListener('click', () => confirmModal.classList.add('hidden'));

// 7. Bulk Actions
const bulkApproveBtn = document.getElementById('bulkApprove');
const bulkRejectBtn = document.getElementById('bulkReject');

async function handleBulkAction(action) {
    const selectedIds = Array.from(document.querySelectorAll('.registration-checkbox:checked')).map(cb => cb.dataset.id);
    if (selectedIds.length === 0) return;

    const success = await updateStatusInDatabase(selectedIds, action);
    if (success) {
        pendingRequests = pendingRequests.filter(r => !selectedIds.includes(r.id));
        renderTable(pendingRequests);
        showToast(`${selectedIds.length} users ${action}d.`);
        document.getElementById('selectAllCheckbox').checked = false;
    }
    document.getElementById('bulkActionsMenu').classList.add('hidden');
}

bulkApproveBtn.addEventListener('click', () => handleBulkAction('approve'));
bulkRejectBtn.addEventListener('click', () => handleBulkAction('reject'));

// 8. Search Functionality
// 8. Search, Sort & Filter Functionality
const searchInput = document.getElementById('searchInput');
const sortSelect = document.getElementById('sortSelect');
const filterSelect = document.getElementById('filterSelect');

function applyFilters() {
    let results = [...pendingRequests]; // Start with full list

    // A. Apply Search
    const term = searchInput.value.toLowerCase();
    if (term) {
        results = results.filter(r => 
            (r.full_name && r.full_name.toLowerCase().includes(term)) || 
            (r.email && r.email.toLowerCase().includes(term)) ||
            (r.phone_number && r.phone_number.toLowerCase().includes(term))
        );
    }

    // B. Apply Time Filter
    const filterValue = filterSelect.value;
    const now = new Date();
    // Normalize "today" to start of day for accurate comparison
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    if (filterValue === 'today') {
        results = results.filter(r => new Date(r.date_joined) >= startOfToday);
    } else if (filterValue === 'week') {
        // Last 7 Days strategy
        const sevenDaysAgo = new Date(startOfToday);
        sevenDaysAgo.setDate(startOfToday.getDate() - 7);
        results = results.filter(r => new Date(r.date_joined) >= sevenDaysAgo);
    }

    // C. Apply Sorting
    const sortValue = sortSelect.value;
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

// Attach Event Listeners
searchInput.addEventListener('keyup', applyFilters);
sortSelect.addEventListener('change', applyFilters);
filterSelect.addEventListener('change', applyFilters);

// 9. Clock (Consolidated)
function updateClock() {
    const now = new Date();
    document.getElementById('current-time').textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    document.getElementById('current-date').textContent = now.toLocaleDateString([], { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
}
setInterval(updateClock, 1000);
updateClock();

// Initial Load
renderTable(pendingRequests);

// A. Toggle Bulk Actions Menu Visibility
const bulkActionsBtn = document.getElementById('bulkActionsBtn');
const bulkActionsMenu = document.getElementById('bulkActionsMenu');
const selectAllCheckbox = document.getElementById('selectAllCheckbox');

bulkActionsBtn.addEventListener('click', () => {
    bulkActionsMenu.classList.toggle('hidden');
});

// Close menu when clicking outside
document.addEventListener('click', (e) => {
    if (!bulkActionsBtn.contains(e.target) && !bulkActionsMenu.contains(e.target)) {
        bulkActionsMenu.classList.add('hidden');
    }
});

// Select All functionality
selectAllCheckbox.addEventListener('change', (e) => {
    document.querySelectorAll('.registration-checkbox').forEach(checkbox => {
        checkbox.checked = e.target.checked;
    });
});

// B. Chart.js Initialization Logic
function initAttendanceChart(canvasId, dataPoints, lineColor) {
    const ctx = document.getElementById(canvasId).getContext('2d');
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

// Initialize the charts with some dummy data (or real data from your backend later)
initAttendanceChart('studentsAttendanceChart', [85, 88, 92, 90, 87, 89, 88], '#0284c7');
initAttendanceChart('teachersAttendanceChart', [95, 94, 96, 92, 95, 93, 92], '#6d28d9');

// C. Toast Helper (Make sure this function exists for your success messages)
function showToast(message) {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toastMessage');
    toastMessage.textContent = message;
    toast.classList.remove('translate-y-10', 'opacity-0');
    toast.classList.add('translate-y-0', 'opacity-100');
    setTimeout(() => {
        toast.classList.remove('translate-y-0', 'opacity-100');
        toast.classList.add('translate-y-10', 'opacity-0');
    }, 3000);
}