// Browser mechanics only. Validation status, permissions, paging and row content are Python-owned.
function initializeUI() {
  document.querySelectorAll('dialog[data-required]').forEach((dialog) => {
    if (!dialog.open) dialog.showModal();
    dialog.addEventListener('cancel', (event) => event.preventDefault());
  });
  updateSelection();
  initializeUpload();
}

function initializeUpload() {
  const form = document.getElementById('ifc_dropzone');
  if (!form || form.dropzone) return;
  const panel = form.closest('#upload-panel');
  const progress = form.querySelector('progress');
  const errors = panel.querySelector('[data-upload-errors]');
  const buttons = panel.querySelectorAll('.upload-actions button');
  const showError = (message) => {
    const alert = document.createElement('p');
    alert.className = 'error';
    alert.setAttribute('role', 'alert');
    alert.textContent = message;
    errors.replaceChildren(alert);
  };
  // Same queue and acceptance options as React's Dz.js; limits come from UploadPolicy.
  const dz = new Dropzone(form, {
    uploadMultiple: true,
    acceptedFiles: '.ifc',
    parallelUploads: 100,
    maxFiles: Number(form.dataset.maxFiles),
    maxFilesize: Number(form.dataset.maxSize),
    autoProcessQueue: false,
    addRemoveLinks: true,
    withCredentials: true,
    headers: { 'X-CSRFToken': form.elements.csrfmiddlewaretoken.value, 'HX-Request': 'true' },
    // Django's existing multipart endpoint accepts repeated `file` fields.
    paramName: () => 'file',
  });
  dz.hiddenFileInput.setAttribute('aria-label', 'Select IFC files');
  dz.on('addedfile', () => errors.replaceChildren());
  dz.on('totaluploadprogress', (value) => { progress.value = value; });
  dz.on('sendingmultiple', () => {
    progress.hidden = false;
    buttons.forEach((button) => { button.disabled = true; });
  });
  dz.on('queuecomplete', () => buttons.forEach((button) => { button.disabled = false; }));
  dz.on('successmultiple', (files) => {
    const redirect = files[0].xhr.getResponseHeader('HX-Redirect');
    if (redirect) window.location.assign(redirect);
  });
  dz.on('error', (file, message, xhr) => {
    if (xhr) {
      const document = new DOMParser().parseFromString(xhr.responseText, 'text/html');
      const messages = [...document.querySelectorAll('[data-upload-errors] [role=alert]')];
      message = messages.map((item) => item.textContent).join(' ') || 'We could not upload this file. Please try again.';
    }
    file.previewElement.querySelector('[data-dz-errormessage]').textContent = message;
    if (!xhr && file.size > dz.options.maxFilesize * 1024 * 1024) {
      dz.removeFile(file);
      showError(`Oops! File Size Limit Reached. You've attempted to upload a file larger than ${dz.options.maxFilesize} MB. Need assistance with larger files? Contact our support team for tailored solutions.`);
    } else {
      showError(message);
    }
  });
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (dz.getQueuedFiles().length) dz.processQueue();
    else showError('Select at least one IFC file to validate.');
  });
  form.addEventListener('reset', () => {
    dz.removeAllFiles();
    errors.replaceChildren();
    progress.hidden = true;
    progress.value = 0;
  });
}

function updateSelection() {
  const form = document.getElementById('dashboard-form');
  if (!form) return;
  const choices = [...form.querySelectorAll('input[type=checkbox][name=selected]:not(:disabled)')];
  const selected = form.querySelectorAll('input[name=selected]:checked, input[type=hidden][name=selected]').length;
  form.querySelector('[data-selection-count]').textContent = selected ? `${selected} selected` : '';
  form.querySelector('[data-delete-selected]').disabled = !selected;
  form.querySelector('.table-toolbar').style.visibility = selected ? 'visible' : 'hidden';
  const all = form.querySelector('[data-select-all]');
  all.checked = choices.length > 0 && choices.every((input) => input.checked);
  all.indeterminate = choices.some((input) => input.checked) && !all.checked;
}

document.addEventListener('DOMContentLoaded', initializeUI);
document.addEventListener('htmx:afterSwap', initializeUI);

document.addEventListener('change', (event) => {
  if (event.target.matches('[data-select-all]')) {
    document.querySelectorAll('#dashboard-form input[type=checkbox][name=selected]:not(:disabled)').forEach((input) => { input.checked = event.target.checked; });
  }
  if (event.target.matches('[name=selected], [data-select-all]')) updateSelection();
});

document.addEventListener('click', (event) => {
  const row = event.target.closest('[data-select-row]');
  if (!row || event.target.closest('a,button,input,label')) return;
  const input = row.querySelector('input[name=selected]');
  if (!input.disabled) { input.checked = !input.checked; updateSelection(); }
});

for (const name of ['htmx:responseError', 'htmx:sendError']) {
  document.addEventListener(name, () => {
    const error = document.getElementById('request-error');
    error.textContent = 'We could not complete this request. Please try again.';
    error.hidden = false;
  });
}
