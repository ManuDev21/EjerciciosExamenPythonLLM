async function api(ruta, opciones = {}) {
  if (opciones.body && typeof opciones.body !== 'string') {
    opciones.body = JSON.stringify(opciones.body);
    opciones.headers = { 'Content-Type': 'application/json', ...(opciones.headers || {}) };
  }
  const r = await fetch(ruta, opciones);
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json() : await r.text();
  if (!r.ok) {
    const msg = (data && data.error) ? data.error : `Error ${r.status}`;
    const err = new Error(msg);
    err.detalle = data && data.detalle;
    throw err;
  }
  return data;
}

function toast(mensaje, tipo = 'success', ms = 3500) {
  let cont = document.getElementById('toasts');
  if (!cont) {
    cont = document.createElement('div');
    cont.id = 'toasts';
    cont.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    document.body.appendChild(cont);
  }
  const el = document.createElement('div');
  el.className = `toast align-items-center text-bg-${tipo} border-0`;
  el.innerHTML = `<div class="d-flex"><div class="toast-body">${mensaje}</div>
    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  cont.appendChild(el);
  const t = new bootstrap.Toast(el, { delay: ms });
  t.show();
  el.addEventListener('hidden.bs.toast', () => el.remove());
}

function fmtFecha(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? String(iso).slice(0, 16) : d.toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' });
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function badgePrioridad(p) {
  const map = { critica: 'danger', alta: 'warning', media: 'info', baja: 'secondary' };
  return `<span class="badge text-bg-${map[p] || 'secondary'}">${esc(p)}</span>`;
}

function badgeEstado(e) {
  const map = { nuevo: 'primary', en_atencion: 'warning', cerrado: 'success' };
  return `<span class="badge text-bg-${map[e] || 'secondary'}">${esc(e || '—')}</span>`;
}

function badgeDecision(d) {
  const map = { acceso_estandar: 'success', inspeccion_especial: 'warning', retenido_horario: 'dark', denegado: 'danger' };
  const txt = { acceso_estandar: 'Acceso estándar', inspeccion_especial: 'Inspección especial', retenido_horario: 'Retenido (horario)', denegado: 'Denegado' };
  return `<span class="badge text-bg-${map[d] || 'secondary'}">${txt[d] || esc(d)}</span>`;
}

function badgeNivel(n) {
  const map = { critico: 'danger', alto: 'warning', medio: 'info', bajo: 'success' };
  return `<span class="badge text-bg-${map[n] || 'secondary'}">${esc(n || '—')}</span>`;
}

async function pintarEstadoGlobal() {
  try {
    const d = await api('/api/estado');
    const db = document.getElementById('estadoDb');
    const lm = document.getElementById('estadoLlm');
    if (db) {
      db.className = 'badge text-bg-' + (d.persistencia.conectado ? 'success' : 'danger');
      db.title = d.persistencia.conectado ? d.persistencia.uri : (d.persistencia.error || 'modo local');
      db.innerHTML = `<i class="bi bi-database"></i> ${d.persistencia.motor}`;
    }
    if (lm) {
      lm.className = 'badge text-bg-' + (d.ollama.disponible ? 'success' : 'secondary');
      lm.title = d.ollama.disponible ? 'Modelo: ' + d.ollama.modelo_actual : 'Ollama no responde';
      lm.innerHTML = `<i class="bi bi-cpu"></i> ${d.ollama.disponible ? d.ollama.modelo_actual : 'LLM off'}`;
    }
  } catch (e) {  }
}

function spinnerBtn(btn, on, txt = 'Procesando…') {
  if (on) {
    btn.dataset.orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>${txt}`;
  } else {
    btn.disabled = false;
    if (btn.dataset.orig) btn.innerHTML = btn.dataset.orig;
  }
}
