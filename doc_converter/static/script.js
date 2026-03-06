// --- UI State ---
let selectedFile = null;
let previewPanel = null;

// --- Upload Logic ---
function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  setStatus('Uploading...');
  setProgress(10);
  fetch('/upload', {
    method: 'POST',
    body: formData
  })
    .then(res => res.json())
    .then(data => {
      setProgress(100);
      setStatus('Converting...');
      setTimeout(() => {
        setStatus('Done!');
        setProgress(0);
        loadFiles();
      }, 800);
    })
    .catch(() => {
      setStatus('Upload failed');
      setProgress(0);
    });
}

function setStatus(msg) {
  document.getElementById('status-message').textContent = msg;
}

function setProgress(val) {
  document.getElementById('progress').style.width = val + '%';
}

// --- Drag & Drop ---
const uploadArea = document.getElementById('upload-area');
uploadArea.addEventListener('dragover', e => {
  e.preventDefault();
  uploadArea.classList.add('dragover');
});
uploadArea.addEventListener('dragleave', e => {
  e.preventDefault();
  uploadArea.classList.remove('dragover');
});
uploadArea.addEventListener('drop', e => {
  e.preventDefault();
  uploadArea.classList.remove('dragover');
  if (e.dataTransfer.files.length) {
    uploadFile(e.dataTransfer.files[0]);
  }
});
uploadArea.addEventListener('click', () => {
  document.getElementById('file-input').click();
});
document.getElementById('file-input').addEventListener('change', e => {
  if (e.target.files.length) {
    uploadFile(e.target.files[0]);
  }
});

document.getElementById('convert-btn').addEventListener('click', () => {
  const input = document.getElementById('file-input');
  if (input.files.length) {
    uploadFile(input.files[0]);
  } else {
    setStatus('Please select a file to upload.');
  }
});

// --- File List ---
function loadFiles() {
  fetch('/files')
    .then(res => res.json())
    .then(data => {
      renderFileList('uploaded-files', data.uploaded, false);
      renderFileList('converted-files', data.converted, true);
    });
}

function renderFileList(containerId, files, isConverted) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';
  files.forEach(file => {
    const item = document.createElement('div');
    item.className = 'file-item';
    item.innerHTML = `
      <span class="file-icon">${getFileIcon(file.name)}</span>
      <div class="file-meta">
        <div class="file-name">${file.name}</div>
        <div class="file-time">${file.time}</div>
      </div>
      ${isConverted ? `<div class="file-actions">
        <button class="open-btn" onclick="previewFile('${file.name}')">Open</button>
        <button class="download-btn" onclick="downloadFile('${file.name}')">Download</button>
      </div>` : ''}
    `;
    container.appendChild(item);
  });
}

function getFileIcon(filename) {
  if (filename.endsWith('.pdf')) return '📄';
  if (filename.endsWith('.md')) return '📝';
  if (filename.endsWith('.txt')) return '📃';
  return '📁';
}

// --- Preview & Download ---
function previewFile(filename) {
  fetch(`/view/${filename}`)
    .then(res => res.text())
    .then(text => {
      showPreview(filename, text);
    });
}

function showPreview(filename, text) {
  if (!previewPanel) previewPanel = document.getElementById('preview-panel');
  previewPanel.innerHTML = `<div style="font-size:1.1rem;color:#00eaff;margin-bottom:0.7rem;">${filename}</div><pre>${escapeHtml(text)}</pre>`;
  previewPanel.scrollTop = 0;
}

function escapeHtml(text) {
  return text.replace(/[&<>]/g, tag => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[tag]));
}

function downloadFile(filename) {
  window.location = `/download/${filename}`;
}

// --- Init ---
window.onload = loadFiles;
