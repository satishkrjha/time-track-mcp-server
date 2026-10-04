// TimeTrack frontend -- talks only to this app's own REST API (/api/...).

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('view-' + tab.dataset.view).classList.add('active');
  });
});

let currentEntries = [];

async function loadEntries() {
  const params = new URLSearchParams();
  const employee = document.getElementById('employeeFilter')?.value.trim();
  const project = document.getElementById('projectFilter')?.value.trim();
  const startDate = document.getElementById('startDateFilter')?.value;
  const endDate = document.getElementById('endDateFilter')?.value;

  if (employee) params.set('employee_name', employee);
  if (project) params.set('project', project);
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);

  const url = params.toString() ? `/api/entries?${params.toString()}` : '/api/entries';
  const res = await fetch(url);
  currentEntries = await res.json();
  const tbody = document.querySelector('#entriesTable tbody');

  tbody.innerHTML = currentEntries.length
    ? currentEntries.map(e => `
      <tr>
        <td>${e.entry_date}</td>
        <td>${escapeHtml(e.employee_name)}</td>
        <td>${escapeHtml(e.project)}</td>
        <td>${e.hours}</td>
        <td>${escapeHtml(e.description)}</td>
        <td>
          <div class="table-actions">
            <button class="row-action edit-btn" data-id="${e.id}" type="button">Edit</button>
            <button class="row-action delete-btn" data-id="${e.id}" type="button">Delete</button>
          </div>
        </td>
      </tr>
    `).join('')
    : '<tr><td colspan="6">No entries match the current filters.</td></tr>';
}

async function loadProjectOptions() {
  const res = await fetch('/api/projects');
  const projects = await res.json();
  const select = document.getElementById('projectSelect');
  select.innerHTML = projects.map(p => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join('');
}

document.getElementById('loadEntriesBtn').addEventListener('click', loadEntries);

async function loadProjectAlerts() {
  const res = await fetch('/api/projects/alerts');
  const alerts = await res.json();
  const container = document.getElementById('projectAlerts');

  container.innerHTML = alerts.length
    ? alerts.map(item => `
        <div class="alert-row ${item.is_over_budget ? 'alert-danger' : item.budget_status === 'near limit' ? 'alert-warning' : 'alert-ok'}">
          <span>${escapeHtml(item.project)}</span>
          <span>${item.budget_status}</span>
          <span>${item.remaining_hours}h left</span>
        </div>
      `).join('')
    : '<p>No project alerts available.</p>';
}

document.getElementById('loadSummaryBtn').addEventListener('click', async () => {
  const project = document.getElementById('projectSelect').value;
  const res = await fetch(`/api/projects/${encodeURIComponent(project)}/summary`);
  const summary = await res.json();
  const rows = Object.entries(summary.by_employee)
    .map(([name, hours]) => `<div class="row"><span>${escapeHtml(name)}</span><span>${hours}h</span></div>`)
    .join('');
  const budget = summary.budget_hours ?? 0;
  const remaining = summary.remaining_hours ?? 0;
  const status = summary.budget_status || (remaining < 0 ? 'over budget' : remaining <= 10 ? 'near limit' : 'on track');
  const statusClass = remaining < 0 ? 'status-danger' : remaining <= 10 ? 'status-warning' : 'status-ok';

  document.getElementById('summaryResult').innerHTML = `
    <div class="total">${summary.total_hours}h total</div>
    <p style="color:#64748b;font-size:13px;margin:4px 0 16px">${escapeHtml(summary.project)}</p>
    <div class="status-pill ${statusClass}">${status}</div>
    <div class="row"><span>Budget</span><span>${budget}h</span></div>
    <div class="row"><span>Remaining</span><span>${remaining}h</span></div>
    ${rows}
  `;
  document.getElementById('projectBudgetInput').value = budget;
});

document.getElementById('setBudgetBtn').addEventListener('click', async () => {
  const project = document.getElementById('projectSelect').value;
  const budgetHours = parseFloat(document.getElementById('projectBudgetInput').value);
  if (!project || Number.isNaN(budgetHours)) {
    showToast('Please select a project and enter a valid budget.', 'error');
    return;
  }

  const res = await fetch(`/api/projects/${encodeURIComponent(project)}/budget?budget_hours=${encodeURIComponent(budgetHours)}`, {
    method: 'PUT',
  });

  if (!res.ok) {
    showToast('Failed to save project budget.', 'error');
    return;
  }

  showToast('Project budget saved', 'success');
  document.getElementById('loadSummaryBtn').click();
});

document.getElementById('exportCsvBtn').addEventListener('click', async () => {
  const params = new URLSearchParams();
  const employee = document.getElementById('employeeFilter')?.value.trim();
  const project = document.getElementById('projectFilter')?.value.trim();
  const startDate = document.getElementById('startDateFilter')?.value;
  const endDate = document.getElementById('endDateFilter')?.value;

  if (employee) params.set('employee_name', employee);
  if (project) params.set('project', project);
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);

  const url = params.toString() ? `/api/entries/export?${params.toString()}` : '/api/entries/export';
  const res = await fetch(url);
  const csv = await res.text();
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'time_entries.csv';
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
});

document.getElementById('importCsvBtn').addEventListener('click', async () => {
  const fileInput = document.getElementById('importCsvInput');
  const file = fileInput.files[0];
  if (!file) {
    showToast('Choose a CSV file first.', 'error');
    return;
  }

  const csvText = await file.text();
  const res = await fetch('/api/entries/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ csv: csvText }),
  });

  if (!res.ok) {
    showToast('CSV import failed.', 'error');
    return;
  }

  const payload = await res.json();
  showToast(`${payload.imported.length} entries imported`, 'success');
  fileInput.value = '';
  loadEntries();
  loadProjectOptions();
});

document.getElementById('loadReportBtn').addEventListener('click', async () => {
  const employee = document.getElementById('employeeReportInput').value.trim();
  const weekStart = document.getElementById('weekStartInput').value;

  if (!employee || !weekStart) {
    document.getElementById('reportResult').innerHTML = '<p>Please choose an employee and a week start date.</p>';
    return;
  }

  const res = await fetch(`/api/reports/weekly/${encodeURIComponent(employee)}?week_start=${encodeURIComponent(weekStart)}`);
  const report = await res.json();
  const rows = Object.entries(report.by_project)
    .map(([project, hours]) => `<div class="row"><span>${escapeHtml(project)}</span><span>${hours}h</span></div>`)
    .join('');

  document.getElementById('reportResult').innerHTML = `
    <div class="total">${report.total_hours}h total</div>
    <p class="meta">${escapeHtml(report.employee_name)} • ${escapeHtml(report.week_start)} to ${escapeHtml(report.week_end)}</p>
    ${rows || '<p>No entries for this date range.</p>'}
  `;
});

document.getElementById('loadDashboardBtn').addEventListener('click', async () => {
  const month = document.getElementById('monthDashboardInput').value;
  if (!month) {
    document.getElementById('dashboardResult').innerHTML = '<p>Please choose a month.</p>';
    return;
  }

  const res = await fetch(`/api/reports/monthly?month=${encodeURIComponent(month)}`);
  const dashboard = await res.json();

  const employeeRows = Object.entries(dashboard.by_employee)
    .map(([name, hours]) => `<div class="row"><span>${escapeHtml(name)}</span><span>${hours}h</span></div>`)
    .join('');
  const projectRows = Object.entries(dashboard.by_project)
    .map(([project, hours]) => `<div class="row"><span>${escapeHtml(project)}</span><span>${hours}h</span></div>`)
    .join('');

  document.getElementById('dashboardResult').innerHTML = `
    <div class="total">${dashboard.total_hours}h total</div>
    <p class="meta">Month: ${escapeHtml(dashboard.month)}</p>

    <div class="section-title">By Employee</div>
    ${employeeRows || '<p>No entries for this month.</p>'}

    <div class="section-title">By Project</div>
    ${projectRows || '<p>No project totals for this month.</p>'}
  `;
});

document.getElementById('logForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    employee_name: document.getElementById('employeeInput').value.trim(),
    project: document.getElementById('projectInput').value.trim(),
    entry_date: document.getElementById('dateInput').value,
    hours: parseFloat(document.getElementById('hoursInput').value),
    description: document.getElementById('descInput').value.trim(),
  };

  const res = await fetch('/api/entries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    showToast('Failed to log time. Please check the values and try again.', 'error');
    return;
  }

  document.getElementById('logForm').reset();

  const entriesTab = document.querySelector('.tab[data-view="entries"]');
  if (entriesTab) {
    entriesTab.click();
  }

  showToast('Entry saved successfully', 'success');
  loadEntries();
  loadProjectOptions();
});

function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  if (!toast) return;

  toast.textContent = message;
  toast.classList.remove('success', 'error');
  toast.classList.add(type, 'show');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove('show'), 2200);
}

function openEditForm(entry) {
  document.getElementById('editEntryId').value = entry.id;
  document.getElementById('editEmployeeInput').value = entry.employee_name;
  document.getElementById('editProjectInput').value = entry.project;
  document.getElementById('editDateInput').value = entry.entry_date;
  document.getElementById('editHoursInput').value = entry.hours;
  document.getElementById('editDescInput').value = entry.description;
  document.getElementById('editEntryForm').classList.remove('hidden');
}

function closeEditForm() {
  document.getElementById('editEntryForm').classList.add('hidden');
  document.getElementById('editEntryId').value = '';
  document.getElementById('editEmployeeInput').value = '';
  document.getElementById('editProjectInput').value = '';
  document.getElementById('editDateInput').value = '';
  document.getElementById('editHoursInput').value = '';
  document.getElementById('editDescInput').value = '';
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

const entriesTableBody = document.querySelector('#entriesTable tbody');
entriesTableBody.addEventListener('click', async (event) => {
  const editButton = event.target.closest('.edit-btn');
  if (editButton) {
    const entry = currentEntries.find(item => Number(item.id) === Number(editButton.dataset.id));
    if (entry) openEditForm(entry);
    return;
  }

  const deleteButton = event.target.closest('.delete-btn');
  if (deleteButton) {
    const id = Number(deleteButton.dataset.id);
    const res = await fetch(`/api/entries/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      showToast('Failed to delete entry.', 'error');
      return;
    }
    showToast('Entry deleted successfully', 'success');
    loadEntries();
  }
});

loadProjectAlerts();

document.getElementById('saveEditBtn').addEventListener('click', async () => {
  const id = document.getElementById('editEntryId').value;
  if (!id) return;

  const body = {
    employee_name: document.getElementById('editEmployeeInput').value.trim(),
    project: document.getElementById('editProjectInput').value.trim(),
    entry_date: document.getElementById('editDateInput').value,
    hours: parseFloat(document.getElementById('editHoursInput').value),
    description: document.getElementById('editDescInput').value.trim(),
  };

  const res = await fetch(`/api/entries/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    showToast('Failed to update entry.', 'error');
    return;
  }

  closeEditForm();
  showToast('Entry updated successfully', 'success');
  loadEntries();
});

document.getElementById('cancelEditBtn').addEventListener('click', closeEditForm);

loadEntries();
loadProjectOptions();
