const resumeInput = document.getElementById('resume');
const browseBtn = document.getElementById('browse');
const dropzone = document.getElementById('dropzone');
const fileName = document.getElementById('file-name');
const optimizeBtn = document.getElementById('optimize');
const progressWrap = document.getElementById('progress-wrap');
const progressBar = document.getElementById('progress-bar');
const progressLabel = document.getElementById('progress-label');
const results = document.getElementById('results');

browseBtn.addEventListener('click', () => resumeInput.click());
resumeInput.addEventListener('change', () => {
  fileName.textContent = resumeInput.files[0] ? resumeInput.files[0].name : 'No file selected';
});

['dragenter', 'dragover'].forEach(evt => {
  dropzone.addEventListener(evt, e => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
});
['dragleave', 'drop'].forEach(evt => {
  dropzone.addEventListener(evt, e => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
  });
});
dropzone.addEventListener('drop', e => {
  const file = e.dataTransfer.files[0];
  if (file) {
    resumeInput.files = e.dataTransfer.files;
    fileName.textContent = file.name;
  }
});

function renderSummary(summary, message) {
  const summaryEl = document.getElementById('summary');
  summaryEl.innerHTML = `
    <p><strong>Status:</strong> ${message}</p>
    <p><strong>Detected Sections:</strong> ${Object.keys(summary.sections_detected).join(', ') || 'None'}</p>
    <p><strong>Top Keywords Applied:</strong> ${summary.top_keywords.join(', ') || 'No keywords found'}</p>
    <p><strong>Changes Applied:</strong> ${summary.changes_applied}</p>
    <p><strong>Target Profile:</strong> ${summary.target_profile.industry} • ${summary.target_profile.role_level} • ${summary.target_profile.company_size}</p>
    <p><strong>Formatting:</strong> ${summary.format_integrity}</p>
  `;
}

optimizeBtn.addEventListener('click', async () => {
  if (!resumeInput.files[0]) {
    alert('Please upload a DOCX resume first.');
    return;
  }

  const formData = new FormData();
  formData.append('resume', resumeInput.files[0]);
  formData.append('job_description', document.getElementById('job-description').value);
  formData.append('industry', document.getElementById('industry').value);
  formData.append('role_level', document.getElementById('role-level').value);
  formData.append('company_size', document.getElementById('company-size').value);

  progressWrap.classList.remove('hidden');
  progressBar.style.width = '25%';
  progressLabel.textContent = 'Parsing DOCX...';

  try {
    setTimeout(() => (progressBar.style.width = '55%'), 300);
    setTimeout(() => (progressLabel.textContent = 'Optimizing content...'), 350);

    const response = await fetch('/api/optimize', { method: 'POST', body: formData });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || 'Optimization failed');
    }

    progressBar.style.width = '100%';
    progressLabel.textContent = 'Complete';

    renderSummary(payload.summary, payload.message);
    document.getElementById('preview').innerHTML = payload.preview_html;
    document.getElementById('download').href = `/api/download/${payload.document_id}`;
    results.classList.remove('hidden');
  } catch (err) {
    alert(err.message);
    progressBar.style.width = '0%';
    progressLabel.textContent = 'Error';
  }
});
