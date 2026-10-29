'use strict';
/* Local-only website helpers. No network requests, storage, or mining. */
function inputError(field, message) { const error = new Error(message); error.field = field; return error; }
function configFromValues(v) {
  if (!v || typeof v !== 'object') throw inputError('wallet', 'Enter your public payout address and pool settings.');
  for (const field of ['wallet', 'pool', 'worker']) {
    if (typeof v[field] !== 'string') throw inputError(field, 'Enter a valid ' + (field === 'wallet' ? 'public payout address.' : field + '.'));
  }
  const wallet = v.wallet.trim(), pool = v.pool.trim(), worker = v.worker.trim();
  if (!/^xel:[a-z0-9]{20,200}$/.test(wallet)) throw inputError('wallet', 'Enter a mainnet xel: public payout address. This checks syntax, not its checksum or ownership.');
  if (!/^[A-Za-z0-9_.-]{1,64}$/.test(worker)) throw inputError('worker', 'Worker name: 1–64 letters, numbers, dots, dashes or underscores.');
  const rawThreads = typeof v.threads === 'number' ? String(v.threads) : v.threads;
  if (typeof rawThreads !== 'string' || !/^[0-9]+$/.test(rawThreads) || !Number.isSafeInteger(Number(rawThreads)) || Number(rawThreads) < 1 || Number(rawThreads) > 1024) throw inputError('threads', 'Choose a whole thread count from 1 to 1024 that your computer supports.');
  if (!['ordinary', 'hugetlb'].includes(v.page_mode)) throw inputError('pages', 'Choose ordinary memory or preconfigured huge pages.');
  if (typeof v.password !== 'string' || v.password.length > 512 || /[\x00-\x1f\x7f]/.test(v.password)) throw inputError('password', 'Use a pool worker password of at most 512 characters, without control characters.');
  let u;
  try { u = new URL(pool); } catch (_) { throw inputError('pool', 'Enter the pool URL with its scheme, host, and port.'); }
  const m = pool.match(/^stratum\+(tcp|ssl|tls):\/\/([^/?#@\s]+):([0-9]+)\/?$/);
  if (pool.length > 512 || !m || !u.hostname || u.username || u.password || u.search || u.hash || Number(m[3]) < 1 || Number(m[3]) > 65535) throw inputError('pool', 'Use stratum+tcp://host:port or the pool’s TLS endpoint, without embedded credentials, paths, or query parameters.');
  return {pool, wallet, worker, password:v.password, threads:Number(rawThreads), page_mode:v.page_mode};
}
window.overxelisConfigFromValues = configFromValues;
function saveFile(name, content, type) {
  const blob = new Blob([content], {type}), url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = name;
  document.body.appendChild(a);
  try { a.click(); } finally { a.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000); }
}
for (const button of document.querySelectorAll('.copy')) {
  const code = button.parentElement.querySelector('code'); if (!code) continue;
  button.hidden = false;
  button.addEventListener('click', async () => {
    const notice = document.getElementById('copy-status');
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(code.textContent);
      button.textContent = 'Copied'; if (notice) notice.textContent = 'Command copied to clipboard.';
    } catch (_) {
      const selection = window.getSelection(), range = document.createRange(); range.selectNodeContents(code);
      selection.removeAllRanges(); selection.addRange(range); button.textContent = 'Select/copy';
      if (notice) notice.textContent = 'Clipboard access is unavailable. The command is selected; copy it with your keyboard.';
    }
    setTimeout(() => { button.textContent = 'Copy'; }, 1800);
  });
}
const form = document.getElementById('config-form');
if (form) {
  const status = document.getElementById('config-status'), fields = document.getElementById('config-fields');
  form.addEventListener('submit', event => {
    event.preventDefault(); status.textContent = ''; status.classList.remove('error');
    for (const el of form.querySelectorAll('[aria-invalid]')) el.removeAttribute('aria-invalid');
    const value = name => form.elements.namedItem(name).value;
    try {
      const cfg = configFromValues({wallet:value('wallet'), pool:value('pool'), worker:value('worker'), threads:value('threads'), page_mode:value('pages'), password:value('password')});
      saveFile('config.json', JSON.stringify(cfg, null, 2) + '\n', 'application/json');
      status.textContent = 'File download requested locally. Check your browser downloads, move config.json into the miner folder, run chmod 600 config.json, then --check. Nothing is mining.';
    } catch (error) {
      status.classList.add('error'); status.textContent = error.message;
      const el = error.field && document.getElementById(error.field);
      if (el && form.contains(el)) { el.setAttribute('aria-invalid', 'true'); el.focus(); }
    }
  });
  form.addEventListener('input', event => { event.target.removeAttribute('aria-invalid'); });
  /* Enable only after the submit handler is attached; all fields stay disabled on script failure. */
  form.noValidate = true;
  fields.disabled = false;
  const submit = form.querySelector('button[type="submit"]'); if (submit) submit.disabled = false;
  const note = document.getElementById('config-script-note'); if (note) note.hidden = true;
}
