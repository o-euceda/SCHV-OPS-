const baseUrl = "http://127.0.0.1:8000";
let currentUser = null;
let adminPilots = [];
let adminFlights = [];
let availablePilots = [];

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, { credentials: 'same-origin', ...options });
  if (!response.ok) {
    const errorText = await response.text();
    let message = 'Error inesperado.';
    try {
      const parsed = JSON.parse(errorText);
      message = parsed.detail || parsed.message || message;
    } catch {
      message = errorText || message;
    }
    throw new Error(message || `Error HTTP ${response.status}`);
  }

  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    return null;
  }
  return response.json();
}

function clearSelect(element) {
  if (!element) return;
  element.innerHTML = '';
}

function updateFlightPilotGrade() {
  const pilot = availablePilots.find((item) => item.id === Number(document.getElementById('id_piloto').value));
  document.getElementById('grado_piloto').value = pilot ? pilot.grado : '';
}

function showLoginScreen() {
  document.getElementById('loginSection').classList.remove('d-none');
  document.getElementById('appSection').classList.add('d-none');
  document.getElementById('userBadge').classList.add('d-none');
  document.getElementById('logoutBtn').classList.add('d-none');
  document.getElementById('loginError').classList.add('d-none');
}

function showAppScreen() {
  document.getElementById('loginSection').classList.add('d-none');
  document.getElementById('appSection').classList.remove('d-none');
}

function applyRoleUi() {
  const roleNotice = document.getElementById('roleNotice');
  const userBadge = document.getElementById('userBadge');
  const logoutBtn = document.getElementById('logoutBtn');
  const adminOnly = document.querySelectorAll('[data-admin-only]');
  const tabAdmin = document.getElementById('tab-admin');
  const tabGestion = document.getElementById('tab-gestion');

  if (!currentUser) return;

  userBadge.textContent = `${currentUser.username} (${currentUser.rol})`;
  userBadge.classList.remove('d-none');
  logoutBtn.classList.remove('d-none');

  const isAdmin = currentUser.rol === 'admin';
  roleNotice.classList.remove('d-none');
  roleNotice.textContent = isAdmin
    ? 'Sesión activa como administrador: tienes permisos completos de gestión.'
    : 'Sesión activa como usuario: solo puedes crear registros nuevos.';

  adminOnly.forEach((element) => {
    element.classList.toggle('d-none', !isAdmin);
  });

  tabAdmin.parentElement.classList.toggle('d-none', !isAdmin);
  tabGestion.parentElement.classList.toggle('d-none', !isAdmin);
}

async function loadOptions() {
  const [pilotos, aeronaves, misiones] = await Promise.all([
    fetchJson(`${baseUrl}/api/pilotos`),
    fetchJson(`${baseUrl}/api/aeronaves`),
    fetchJson(`${baseUrl}/api/misiones`),
  ]);
  availablePilots = pilotos;

  const idMision = document.getElementById('id_mision');
  const idAeronave = document.getElementById('id_aeronave');
  const idPiloto = document.getElementById('id_piloto');
  const idCopiloto = document.getElementById('id_copiloto');
  const filterPiloto = document.getElementById('filterPiloto');
  const filterAeronave = document.getElementById('filterAeronave');
  const adminPilotsList = document.getElementById('adminPilotsList');
  const adminAircraftList = document.getElementById('adminAircraftList');
  const adminMissionList = document.getElementById('adminMissionList');
  const certPiloto = document.getElementById('certPiloto');
  const certAeronave = document.getElementById('certAeronave');
  const adminCertList = document.getElementById('adminCertList');

  clearSelect(idMision);
  clearSelect(idAeronave);
  clearSelect(idPiloto);
  clearSelect(idCopiloto);
  clearSelect(filterPiloto);
  clearSelect(filterAeronave);
  clearSelect(certPiloto);
  clearSelect(certAeronave);

  idMision.add(new Option('Seleccione una misión', ''));
  idAeronave.add(new Option('Seleccione una aeronave', ''));
  idPiloto.add(new Option('Seleccione un piloto', ''));
  idCopiloto.add(new Option('Sin copiloto', ''));
  filterPiloto.add(new Option('Todos', ''));
  filterAeronave.add(new Option('Todas', ''));
  certPiloto.add(new Option('Seleccione un piloto', ''));
  certAeronave.add(new Option('Sin aeronave específica', ''));

  for (const item of misiones) {
    idMision.add(new Option(`${item.codigo} - ${item.tipo_mision}`, item.id));
  }

  for (const item of aeronaves) {
    idAeronave.add(new Option(`${item.matricula} - ${item.modelo}`, item.id));
    filterAeronave.add(new Option(`${item.matricula}`, item.id));
    certAeronave.add(new Option(`${item.matricula} - ${item.modelo}`, item.id));
  }

  for (const item of pilotos) {
    idPiloto.add(new Option(item.nombre_completo, item.id));
    idCopiloto.add(new Option(item.nombre_completo, item.id));
    filterPiloto.add(new Option(item.nombre_completo, item.id));
    certPiloto.add(new Option(item.nombre_completo, item.id));
  }

  adminPilotsList.innerHTML = pilotos.length
    ? pilotos.map((item) => `<li class="list-group-item">${item.grado} ${item.nombres} ${item.apellidos}</li>`).join('')
    : '<li class="list-group-item text-muted">Sin pilotos registrados</li>';

  adminAircraftList.innerHTML = aeronaves.length
    ? aeronaves.map((item) => `<li class="list-group-item">${item.matricula} - ${item.modelo}</li>`).join('')
    : '<li class="list-group-item text-muted">Sin aeronaves registradas</li>';

  adminMissionList.innerHTML = misiones.length
    ? misiones.map((item) => `<li class="list-group-item">${item.codigo} - ${item.tipo_mision}</li>`).join('')
    : '<li class="list-group-item text-muted">Sin misiones registradas</li>';

  try {
    const certs = await fetchJson(`${baseUrl}/api/certificaciones`);
    adminCertList.innerHTML = certs.length
      ? certs.map((item) => `<li class="list-group-item"><strong>${item.tipo_cualificacion}</strong> · ${item.piloto} · ${item.aeronave || item.modelo_aeronave || 'Sin aeronave específica'}</li>`).join('')
      : '<li class="list-group-item text-muted">Sin cualificaciones registradas</li>';
  } catch (error) {
    adminCertList.innerHTML = '<li class="list-group-item text-muted">Sin cualificaciones registradas</li>';
  }
}

async function loadAdminManagement() {
  if (!currentUser || currentUser.rol !== 'admin') return;

  const [usuarios, pilotos, vuelos, aeronaves, misiones] = await Promise.all([
    fetchJson(`${baseUrl}/api/usuarios`),
    fetchJson(`${baseUrl}/api/pilotos`),
    fetchJson(`${baseUrl}/api/vuelos`),
    fetchJson(`${baseUrl}/api/aeronaves`),
    fetchJson(`${baseUrl}/api/misiones`),
  ]);

  adminPilots = pilotos;
  adminFlights = vuelos;
  renderPilotSearchResults();
  renderFlightSearchResults();

  const adminUsersTableBody = document.getElementById('adminUsersTableBody');
  const adminPilotsTableBody = document.getElementById('adminPilotsTableBody');
  const adminFlightsTableBody = document.getElementById('adminFlightsTableBody');
  const adminAircraftTableBody = document.getElementById('adminAircraftTableBody');

  adminUsersTableBody.innerHTML = usuarios.length
    ? usuarios.map((usuario) => `
        <tr>
          <td>${escapeHtml(usuario.id)}</td>
          <td>${escapeHtml(usuario.username)}</td>
          <td><span class="badge ${usuario.rol === 'admin' ? 'bg-danger' : 'bg-secondary'}">${escapeHtml(usuario.rol)}</span></td>
          <td>${escapeHtml(usuario.estado)}</td>
          <td><button class="btn btn-sm btn-outline-danger" data-user-delete="${usuario.id}">Borrar</button></td>
        </tr>
      `).join('')
    : '<tr><td colspan="5" class="text-center text-muted py-3">Sin usuarios</td></tr>';

  adminPilotsTableBody.innerHTML = pilotos.length
    ? pilotos.map((piloto) => `
        <tr>
          <td>${escapeHtml(piloto.id)}</td>
          <td>${escapeHtml(`${piloto.grado} ${piloto.nombres} ${piloto.apellidos}`)}</td>
          <td>${escapeHtml(piloto.funcion_habitual)}</td>
          <td>
            <button class="btn btn-sm btn-outline-primary me-2" data-pilot-edit="${piloto.id}">Editar</button>
            <button class="btn btn-sm btn-outline-danger" data-pilot-delete="${piloto.id}">Borrar</button>
          </td>
        </tr>
      `).join('')
    : '<tr><td colspan="4" class="text-center text-muted py-3">Sin pilotos</td></tr>';

  adminFlightsTableBody.innerHTML = vuelos.length
    ? vuelos.map((vuelo) => `
        <tr>
          <td>${escapeHtml(vuelo.id)}</td>
          <td>${escapeHtml(vuelo.fecha_vuelo)}</td>
          <td>${escapeHtml(vuelo.piloto)}</td>
          <td>${escapeHtml(vuelo.mision)}</td>
          <td>
            <button class="btn btn-sm btn-outline-primary me-2" data-flight-edit="${vuelo.id}">Editar</button>
            <button class="btn btn-sm btn-outline-danger" data-flight-delete="${vuelo.id}">Borrar</button>
          </td>
        </tr>
      `).join('')
    : '<tr><td colspan="5" class="text-center text-muted py-3">Sin vuelos</td></tr>';

  adminAircraftTableBody.innerHTML = aeronaves.length
    ? aeronaves.map((aeronave) => `
        <tr>
          <td>${escapeHtml(aeronave.matricula)}</td>
          <td>${escapeHtml(aeronave.modelo)}</td>
          <td>${escapeHtml(aeronave.horas_actuales)} h</td>
          <td><button class="btn btn-sm btn-outline-primary" data-aircraft-edit="${aeronave.id}">Editar tipo</button></td>
        </tr>
      `).join('')
    : '<tr><td colspan="4" class="text-center text-muted py-3">Sin aeronaves</td></tr>';

  const flightAdminMission = document.getElementById('flightAdminMission');
  const flightAdminAeronave = document.getElementById('flightAdminAeronave');
  const flightAdminPiloto = document.getElementById('flightAdminPiloto');
  const flightAdminCopiloto = document.getElementById('flightAdminCopiloto');

  if (flightAdminMission) {
    flightAdminMission.innerHTML = '<option value="">Seleccione misión</option>' + misiones.map((item) => `<option value="${item.id}">${escapeHtml(item.codigo)} - ${escapeHtml(item.tipo_mision)}</option>`).join('');
  }

  if (flightAdminAeronave) {
    flightAdminAeronave.innerHTML = '<option value="">Seleccione aeronave</option>' + aeronaves.map((item) => `<option value="${item.id}">${escapeHtml(item.matricula)} - ${escapeHtml(item.modelo)}</option>`).join('');
  }

  if (flightAdminPiloto) {
    flightAdminPiloto.innerHTML = '<option value="">Seleccione piloto</option>' + pilotos.map((item) => `<option value="${item.id}">${escapeHtml(`${item.grado} ${item.nombres} ${item.apellidos}`)}</option>`).join('');
  }

  if (flightAdminCopiloto) {
    flightAdminCopiloto.innerHTML = '<option value="">Sin copiloto</option>' + pilotos.map((item) => `<option value="${item.id}">${escapeHtml(`${item.grado} ${item.nombres} ${item.apellidos}`)}</option>`).join('');
  }
}

function populateAircraftAdminForm(aircraft) {
  document.getElementById('aircraftAdminId').value = aircraft.id;
  document.getElementById('aircraftAdminMatricula').value = aircraft.matricula;
  document.getElementById('aircraftAdminModelo').value = aircraft.modelo;
  document.getElementById('aircraftAdminForm').classList.remove('d-none');
}

function renderPilotSearchResults() {
  const container = document.getElementById('pilotSearchResults');
  const query = document.getElementById('pilotSearch').value.trim().toLowerCase();
  const results = adminPilots.filter((pilot) => [
    pilot.grado,
    pilot.nombres,
    pilot.apellidos,
    pilot.identificacion,
  ].join(' ').toLowerCase().includes(query));

  container.innerHTML = results.length
    ? results.map((pilot) => `
        <div class="list-group-item d-flex justify-content-between align-items-center gap-2">
          <div><strong>${escapeHtml(`${pilot.grado} ${pilot.nombres} ${pilot.apellidos}`)}</strong><br><small class="text-muted">${escapeHtml(pilot.identificacion)} · ${escapeHtml(pilot.funcion_habitual)}</small></div>
          <button type="button" class="btn btn-sm btn-outline-primary" data-pilot-edit="${pilot.id}">Editar</button>
        </div>
      `).join('')
    : '<div class="text-muted small py-2">No se encontraron pilotos.</div>';
}

function renderFlightSearchResults() {
  const container = document.getElementById('flightSearchResults');
  const query = document.getElementById('flightSearch').value.trim().toLowerCase();
  const results = adminFlights.filter((flight) => [
    flight.piloto,
    flight.fecha_vuelo,
    flight.mision,
    flight.aeronave,
    flight.origen,
    flight.destino,
  ].join(' ').toLowerCase().includes(query));

  container.innerHTML = results.length
    ? results.map((flight) => `
        <div class="list-group-item d-flex justify-content-between align-items-center gap-2">
          <div><strong>${escapeHtml(flight.fecha_vuelo)} · ${escapeHtml(flight.piloto)}</strong><br><small class="text-muted">${escapeHtml(flight.mision)} · ${escapeHtml(flight.aeronave)} · ${escapeHtml(flight.origen)} a ${escapeHtml(flight.destino)}</small></div>
          <button type="button" class="btn btn-sm btn-outline-primary" data-flight-edit="${flight.id}">Editar</button>
        </div>
      `).join('')
    : '<div class="text-muted small py-2">No se encontraron vuelos.</div>';
}

function populatePilotAdminForm(pilot) {
  document.getElementById('pilotAdminId').value = pilot.id;
  document.getElementById('pilotAdminGrado').value = pilot.grado;
  document.getElementById('pilotAdminNombres').value = pilot.nombres;
  document.getElementById('pilotAdminApellidos').value = pilot.apellidos;
  document.getElementById('pilotAdminIdentificacion').value = pilot.identificacion;
  document.getElementById('pilotAdminFuncion').value = pilot.funcion_habitual;
  document.querySelectorAll('.pilot-cert-edit').forEach((checkbox) => {
    checkbox.checked = (pilot.cualificaciones || []).includes(checkbox.value);
  });
  document.querySelectorAll('.pilot-aircraft-edit').forEach((checkbox) => {
    checkbox.checked = (pilot.habilitaciones_aeronave || []).includes(checkbox.value);
  });
}

function populateFlightAdminForm(vuelo) {
  document.getElementById('flightAdminId').value = vuelo.id;
  document.getElementById('flightAdminMission').value = vuelo.id_mision;
  document.getElementById('flightAdminAeronave').value = vuelo.id_aeronave;
  document.getElementById('flightAdminPiloto').value = vuelo.id_piloto;
  document.getElementById('flightAdminGrado').value = vuelo.grado_piloto || '';
  document.getElementById('flightAdminCopiloto').value = vuelo.id_copiloto || '';
  document.getElementById('flightAdminOrigen').value = vuelo.origen;
  document.getElementById('flightAdminDestino').value = vuelo.destino;
  document.getElementById('flightAdminFecha').value = vuelo.fecha_vuelo;
  document.getElementById('flightAdminHoras').value = vuelo.horas_vuelo;
  document.getElementById('flightAdminDiurnas').value = vuelo.horas_diurnas;
  document.getElementById('flightAdminNocturnas').value = vuelo.horas_nocturnas;
  document.getElementById('flightAdminNvg').value = vuelo.horas_nvg;
  document.getElementById('flightAdminInstrumentos').value = vuelo.horas_instrumentos;
}

async function loadReport() {
  const params = new URLSearchParams();
  const piloto = document.getElementById('filterPiloto').value;
  const aeronave = document.getElementById('filterAeronave').value;
  const desde = document.getElementById('fechaDesde').value;
  const hasta = document.getElementById('fechaHasta').value;
  const tipo = document.getElementById('filterTipo').value;

  if (piloto) params.append('id_piloto', piloto);
  if (aeronave) params.append('id_aeronave', aeronave);
  if (desde) params.append('fecha_desde', desde);
  if (hasta) params.append('fecha_hasta', hasta);
  if (tipo) params.append('tipo_vuelo', tipo);

  const rows = await fetchJson(`${baseUrl}/api/report?${params.toString()}`);
  const tbody = document.getElementById('reportTableBody');
  tbody.innerHTML = '';

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="13" class="text-center text-muted py-4">Sin resultados</td></tr>';
    return;
  }

  for (const row of rows) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.fecha}</td>
      <td>${row.mision}</td>
      <td>${row.matricula}</td>
      <td>${row.piloto}</td>
      <td>${row.grado_piloto}</td>
      <td>${row.origen}</td>
      <td>${row.destino}</td>
      <td>${row.duracion_vuelo || row.hora_salida || '00:00'}</td>
      <td>${row.tiempo_total}</td>
      <td>${row.diurna}</td>
      <td>${row.nocturna}</td>
      <td>${row.nvg}</td>
      <td>${row.instrumentos}</td>
    `;
    tbody.appendChild(tr);
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value;
  const errorBox = document.getElementById('loginError');

  try {
    const result = await fetchJson(`${baseUrl}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    currentUser = result.user;
    errorBox.classList.add('d-none');
    showAppScreen();
    applyRoleUi();
    await loadOptions();
    await loadReport();
    await loadAdminManagement();
  } catch (error) {
    errorBox.textContent = error.message || 'No se pudo iniciar sesión.';
    errorBox.classList.remove('d-none');
  }
}

async function handleLogout() {
  try {
    await fetchJson(`${baseUrl}/logout`, { method: 'POST' });
  } catch (error) {
    console.warn('Logout falló', error);
  }
  currentUser = null;
  showLoginScreen();
  document.getElementById('loginForm').reset();
}

async function ensureAuth() {
  try {
    const result = await fetchJson(`${baseUrl}/me`);
    currentUser = result.user;
    showAppScreen();
    applyRoleUi();
    await loadOptions();
    await loadReport();
    await loadAdminManagement();
  } catch (error) {
    currentUser = null;
    showLoginScreen();
  }
}

async function seedDemoData() {
  try {
    const result = await fetchJson(`${baseUrl}/api/seed-demo`, { method: 'POST' });
    alert(result.mensaje || 'Datos cargados.');
    await loadOptions();
    await loadReport();
  } catch (error) {
    alert(error.message || 'No se pudieron cargar los datos de prueba.');
  }
}

async function handleExportExcel(event) {
  event.preventDefault();
  const params = new URLSearchParams();
  const piloto = document.getElementById('filterPiloto').value;
  const aeronave = document.getElementById('filterAeronave').value;
  const desde = document.getElementById('fechaDesde').value;
  const hasta = document.getElementById('fechaHasta').value;
  const tipo = document.getElementById('filterTipo').value;

  if (piloto) params.append('id_piloto', piloto);
  if (aeronave) params.append('id_aeronave', aeronave);
  if (desde) params.append('fecha_desde', desde);
  if (hasta) params.append('fecha_hasta', hasta);
  if (tipo) params.append('tipo_vuelo', tipo);

  window.open(`${baseUrl}/export/report?${params.toString()}`);
}

document.getElementById('flightForm').addEventListener('submit', async (event) => {
  event.preventDefault();

  const form = document.getElementById('flightForm');
  const errorBox = document.getElementById('flightFormError');
  const totalHoras = document.getElementById('horas_vuelo').value.trim();

  if (!/^\d{1,2}:\d{2}$/.test(totalHoras)) {
    errorBox.textContent = 'La cantidad de horas debe estar en formato HH:MM (por ejemplo: 01:30).';
    errorBox.classList.remove('d-none');
    return;
  }

  errorBox.textContent = '';
  errorBox.classList.add('d-none');

  const payload = {
    id_mision: Number(document.getElementById('id_mision').value),
    id_aeronave: Number(document.getElementById('id_aeronave').value),
    id_piloto: Number(document.getElementById('id_piloto').value),
    grado_piloto: document.getElementById('grado_piloto').value,
    id_copiloto: document.getElementById('id_copiloto').value ? Number(document.getElementById('id_copiloto').value) : null,
    origen: document.getElementById('origen').value,
    destino: document.getElementById('destino').value,
    fecha_vuelo: document.getElementById('fecha_vuelo').value,
    horas_vuelo: totalHoras,
    horas_diurnas: document.getElementById('horas_diurnas').value === '' ? 0 : Number(document.getElementById('horas_diurnas').value || 0),
    horas_nocturnas: document.getElementById('horas_nocturnas').value === '' ? 0 : Number(document.getElementById('horas_nocturnas').value || 0),
    horas_nvg: document.getElementById('horas_nvg').value === '' ? 0 : Number(document.getElementById('horas_nvg').value || 0),
    horas_instrumentos: document.getElementById('horas_instrumentos').value === '' ? 0 : Number(document.getElementById('horas_instrumentos').value || 0),
  };

  try {
    await fetchJson(`${baseUrl}/api/vuelos/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    alert('Vuelo registrado correctamente');
    form.reset();
    errorBox.classList.add('d-none');
    loadReport();
  } catch (error) {
    errorBox.textContent = error.message || 'No se pudo registrar el vuelo.';
    errorBox.classList.remove('d-none');
  }
});

document.getElementById('pilotForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const cualificaciones = Array.from(document.querySelectorAll('.pilot-cert-new:checked')).map((checkbox) => checkbox.value);
  const habilitaciones_aeronave = Array.from(document.querySelectorAll('.pilot-aircraft-new:checked')).map((checkbox) => checkbox.value);
  const payload = {
    grado: document.getElementById('pilotGrado').value,
    nombres: document.getElementById('pilotNombres').value,
    apellidos: document.getElementById('pilotApellidos').value,
    identificacion: document.getElementById('pilotIdentificacion').value,
    funcion_habitual: document.getElementById('pilotFuncion').value || 'Tripulante',
    estado: 'Activo',
    cualificaciones,
    habilitaciones_aeronave,
  };

  try {
    await fetchJson(`${baseUrl}/pilotos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    alert('Piloto registrado correctamente');
    document.getElementById('pilotForm').reset();
    await loadOptions();
  } catch (error) {
    alert(error.message || 'No se pudo guardar el piloto.');
  }
});

document.getElementById('aircraftForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    matricula: document.getElementById('aircraftMatricula').value,
    modelo: document.getElementById('aircraftModelo').value,
    horas_vuelo_iniciales: Number(document.getElementById('aircraftHoras').value || 0),
    estado: 'Servicial',
  };

  try {
    await fetchJson(`${baseUrl}/aeronaves`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    alert('Aeronave registrada correctamente');
    document.getElementById('aircraftForm').reset();
    await loadOptions();
  } catch (error) {
    alert(error.message || 'No se pudo guardar la aeronave.');
  }
});

document.getElementById('missionForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    codigo: document.getElementById('missionCode').value,
    tipo_mision: document.getElementById('missionTipo').value,
    fecha_salida: document.getElementById('missionFecha').value,
    observaciones: document.getElementById('missionObs').value,
  };

  try {
    await fetchJson(`${baseUrl}/misiones`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    alert('Misión registrada correctamente');
    document.getElementById('missionForm').reset();
    await loadOptions();
  } catch (error) {
    alert(error.message || 'No se pudo guardar la misión.');
  }
});

document.getElementById('certForm').addEventListener('submit', async (event) => {
  event.preventDefault();

  const selectedQualifications = Array.from(document.querySelectorAll('.cert-type:checked')).map((checkbox) => checkbox.value);
  if (!selectedQualifications.length) {
    alert('Selecciona al menos una habilitación operacional.');
    return;
  }

  const commonPayload = {
    id_piloto: Number(document.getElementById('certPiloto').value),
    id_aeronave: document.getElementById('certAeronave').value ? Number(document.getElementById('certAeronave').value) : null,
    modelo_aeronave: document.getElementById('certModelo').value || null,
    nivel: document.getElementById('certNivel').value || 'Tipo',
    estado: 'Activo',
    observaciones: document.getElementById('certObs').value || null,
  };

  try {
    await Promise.all(selectedQualifications.map((tipo_cualificacion) => fetchJson(`${baseUrl}/api/certificaciones`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...commonPayload, tipo_cualificacion }),
    })));

    alert('Habilitaciones registradas correctamente');
    document.getElementById('certForm').reset();
    await loadOptions();
  } catch (error) {
    alert(error.message || 'No se pudo guardar la cualificación.');
  }
});

document.getElementById('seedDemoBtn').addEventListener('click', seedDemoData);
document.getElementById('filterBtn').addEventListener('click', loadReport);
document.getElementById('exportExcelBtn').addEventListener('click', handleExportExcel);
document.getElementById('loginForm').addEventListener('submit', handleLogin);
document.getElementById('logoutBtn').addEventListener('click', handleLogout);

document.getElementById('userCreateForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    username: document.getElementById('newUserName').value.trim(),
    password: document.getElementById('newUserPassword').value,
    rol: document.getElementById('newUserRole').value,
    estado: 'Activo',
  };

  try {
    await fetchJson(`${baseUrl}/usuarios`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    document.getElementById('userCreateForm').reset();
    await loadAdminManagement();
    alert('Usuario creado correctamente.');
  } catch (error) {
    alert(error.message || 'No se pudo crear el usuario.');
  }
});

document.getElementById('pilotAdminForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const id = document.getElementById('pilotAdminId').value;
  if (!id) {
    alert('Primero selecciona un piloto para editar.');
    return;
  }

  const payload = {
    grado: document.getElementById('pilotAdminGrado').value,
    nombres: document.getElementById('pilotAdminNombres').value,
    apellidos: document.getElementById('pilotAdminApellidos').value,
    identificacion: document.getElementById('pilotAdminIdentificacion').value,
    funcion_habitual: document.getElementById('pilotAdminFuncion').value,
    estado: 'Activo',
    cualificaciones: Array.from(document.querySelectorAll('.pilot-cert-edit:checked')).map((checkbox) => checkbox.value),
    habilitaciones_aeronave: Array.from(document.querySelectorAll('.pilot-aircraft-edit:checked')).map((checkbox) => checkbox.value),
  };

  try {
    await fetchJson(`${baseUrl}/pilotos/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    document.getElementById('pilotAdminForm').classList.add('d-none');
    await loadOptions();
    await loadAdminManagement();
    alert('Piloto actualizado correctamente.');
  } catch (error) {
    alert(error.message || 'No se pudo actualizar el piloto.');
  }
});

document.getElementById('flightAdminForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const id = document.getElementById('flightAdminId').value;
  if (!id) {
    alert('Primero selecciona un vuelo para editar.');
    return;
  }

  const payload = {
    id_mision: Number(document.getElementById('flightAdminMission').value),
    id_aeronave: Number(document.getElementById('flightAdminAeronave').value),
    id_piloto: Number(document.getElementById('flightAdminPiloto').value),
    grado_piloto: document.getElementById('flightAdminGrado').value,
    id_copiloto: document.getElementById('flightAdminCopiloto').value ? Number(document.getElementById('flightAdminCopiloto').value) : null,
    origen: document.getElementById('flightAdminOrigen').value,
    destino: document.getElementById('flightAdminDestino').value,
    fecha_vuelo: document.getElementById('flightAdminFecha').value,
    horas_vuelo: document.getElementById('flightAdminHoras').value,
    horas_diurnas: Number(document.getElementById('flightAdminDiurnas').value || 0),
    horas_nocturnas: Number(document.getElementById('flightAdminNocturnas').value || 0),
    horas_nvg: Number(document.getElementById('flightAdminNvg').value || 0),
    horas_instrumentos: Number(document.getElementById('flightAdminInstrumentos').value || 0),
  };

  try {
    await fetchJson(`${baseUrl}/vuelos/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    document.getElementById('flightAdminForm').classList.add('d-none');
    await loadOptions();
    await loadReport();
    await loadAdminManagement();
    alert('Vuelo actualizado correctamente.');
  } catch (error) {
    alert(error.message || 'No se pudo actualizar el vuelo.');
  }
});

document.addEventListener('click', async (event) => {
  const userDeleteButton = event.target.closest('[data-user-delete]');
  if (userDeleteButton) {
    const userId = Number(userDeleteButton.dataset.userDelete);
    if (!window.confirm('¿Borrar este usuario?')) return;
    if (!Number.isNaN(userId)) {
      try {
        await fetchJson(`${baseUrl}/usuarios/${userId}`, { method: 'DELETE' });
        await loadAdminManagement();
      } catch (error) {
        alert(error.message || 'No se pudo borrar el usuario.');
      }
    }
    return;
  }

  const pilotDeleteButton = event.target.closest('[data-pilot-delete]');
  if (pilotDeleteButton) {
    const pilotId = Number(pilotDeleteButton.dataset.pilotDelete);
    if (!window.confirm('¿Borrar este piloto?')) return;
    if (!Number.isNaN(pilotId)) {
      try {
        await fetchJson(`${baseUrl}/pilotos/${pilotId}`, { method: 'DELETE' });
        await loadOptions();
        await loadAdminManagement();
      } catch (error) {
        alert(error.message || 'No se pudo borrar el piloto.');
      }
    }
    return;
  }

  const pilotEditButton = event.target.closest('[data-pilot-edit]');
  if (pilotEditButton) {
    const pilotId = Number(pilotEditButton.dataset.pilotEdit);
    const pilot = adminPilots.find((item) => item.id === pilotId);
    if (pilot) {
      populatePilotAdminForm(pilot);
      document.getElementById('pilotAdminForm').classList.remove('d-none');
    }
    return;
  }

  const flightDeleteButton = event.target.closest('[data-flight-delete]');
  if (flightDeleteButton) {
    const flightId = Number(flightDeleteButton.dataset.flightDelete);
    if (!window.confirm('¿Borrar este vuelo?')) return;
    if (!Number.isNaN(flightId)) {
      try {
        await fetchJson(`${baseUrl}/vuelos/${flightId}`, { method: 'DELETE' });
        await loadReport();
        await loadAdminManagement();
      } catch (error) {
        alert(error.message || 'No se pudo borrar el vuelo.');
      }
    }
    return;
  }

  const flightEditButton = event.target.closest('[data-flight-edit]');
  if (flightEditButton) {
    const flightId = Number(flightEditButton.dataset.flightEdit);
    const vuelo = adminFlights.find((item) => item.id === flightId);
    if (vuelo) {
      populateFlightAdminForm(vuelo);
      document.getElementById('flightAdminForm').classList.remove('d-none');
    }
    return;
  }

  const aircraftEditButton = event.target.closest('[data-aircraft-edit]');
  if (aircraftEditButton) {
    const aircraftId = Number(aircraftEditButton.dataset.aircraftEdit);
    const aircraft = (await fetchJson(`${baseUrl}/api/aeronaves`)).find((item) => item.id === aircraftId);
    if (aircraft) populateAircraftAdminForm(aircraft);
  }
});

document.getElementById('pilotSearch').addEventListener('input', renderPilotSearchResults);
document.getElementById('flightSearch').addEventListener('input', renderFlightSearchResults);
document.getElementById('id_piloto').addEventListener('change', updateFlightPilotGrade);
document.getElementById('tab-gestion').addEventListener('shown.bs.tab', () => loadAdminManagement());

document.getElementById('aircraftAdminForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const id = document.getElementById('aircraftAdminId').value;
  const aircraft = (await fetchJson(`${baseUrl}/api/aeronaves`)).find((item) => item.id === Number(id));
  if (!aircraft) return;

  try {
    await fetchJson(`${baseUrl}/aeronaves/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        matricula: aircraft.matricula,
        modelo: document.getElementById('aircraftAdminModelo').value,
        horas_vuelo_iniciales: aircraft.horas_vuelo_iniciales,
        estado: aircraft.estado,
      }),
    });
    document.getElementById('aircraftAdminForm').classList.add('d-none');
    await loadOptions();
    await loadAdminManagement();
    alert('Tipo de aeronave actualizado correctamente.');
  } catch (error) {
    alert(error.message || 'No se pudo actualizar el tipo de aeronave.');
  }
});

ensureAuth();
