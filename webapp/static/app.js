/* Planillas · lógica del flujo: Opciones -> Generando (archivos integrados) */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);

  // La parte de "Generar planilla" está guardada por ahora: la web abre
  // directo en "Convertir planilla antigua". Para volver a mostrarla,
  // poner en true y recargar (nada se borra, todo sigue funcionando).
  const MOSTRAR_GENERAR = false;

  const state = {
    bases: [],          // [{nombre, archivo, activa}]
    complementos: [],   // [archivo]
    fotos: '',
    plantilla: '',
    plantillasCat: [],   // plantillas VACÍAS por categoría (lo que se elige)
    disponibles: { bases: [], complementos: [], fotos: [], plantillas: [],
                   'plantillas-categorias': [] },
    categorias: [],
    prefijos: [],
    convFuentes: [],     // planillas convertibles al formato nuevo
    convArchivos: [],    // planillas viejas subidas, esperando convertir
    plantillaOk: false,  // hay plantilla nueva de ML cargada en el servidor
    plantillaNombre: '',
    plantillaCategorias: [],  // categorías (hojas) de esa plantilla nueva
    pollTimer: null,
    categoriaGuardada: '',
    prefijoGuardado: '',
  };

  /* ---------- helpers ---------- */
  async function api(url, opts) {
    const r = await fetch(url, opts);
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || ('HTTP ' + r.status));
    return j;
  }
  function post(url, body) {
    return api(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
  }
  function mostrar(paso) {
    // la sección de generación está guardada: no se muestra sola
    if (!MOSTRAR_GENERAR && (paso === 'paso1' || paso === 'paso2')) return;
    ['paso1', 'paso2'].forEach((p) => $(p).classList.toggle('oculto', p !== paso));
    // el progreso queda debajo del formulario: si se muestra, bajamos hasta él
    if (paso === 'paso2') {
      $('paso2').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }
  function aviso(msg) {
    const el = $('upload-estado');
    el.textContent = msg || '';
    el.classList.toggle('mal', !!msg && msg.startsWith('Error'));
  }

  /* ---------- toasts ---------- */
  function toast(msg, tipo) {
    const cont = $('toasts');
    if (!cont) return;
    const t = document.createElement('div');
    t.className = 'toast ' + (tipo || 'info');
    t.textContent = msg;
    cont.appendChild(t);
    setTimeout(() => {
      t.classList.add('saliendo');
      setTimeout(() => t.remove(), 320);
    }, 3600);
    while (cont.children.length > 5) cont.firstChild.remove();
  }

  /* ---------- badge del paso 3 ---------- */
  function badgeGen(texto, clase) {
    const b = $('badge-gen');
    if (!b) return;
    b.textContent = texto;
    b.className = 'badge ' + clase;
  }

  /* ---------- init ---------- */
  async function init() {
    try {
      const d = await api('/api/init');
      if (!d.disponible) {
        // sin RellenarPlanilla la conversión funciona igual (va incluida
        // en la webapp); solo la generación necesita la carpeta
        if (MOSTRAR_GENERAR) {
          $('estado-rp').textContent = 'RellenarPlanilla no encontrada';
          $('estado-rp').classList.add('mal');
          alert(d.error_rp);
        } else {
          $('estado-rp').textContent = 'conversión lista · sin RellenarPlanilla';
          $('estado-rp').classList.add('ok');
        }
      } else {
        $('estado-rp').textContent = 'conectado a RellenarPlanilla';
        $('estado-rp').classList.add('ok');
      }
      const sel = $('f-marketplace');
      (d.marketplaces || []).forEach((m) => {
        const o = document.createElement('option');
        o.value = m.nombre;
        o.textContent = m.etiqueta;
        sel.appendChild(o);
      });
      sel.value = d.opciones.marketplace || '';

      state.bases = d.archivos.bases || [];
      state.complementos = d.archivos.complementos || [];
      state.fotos = d.archivos.fotos || '';
      state.plantilla = d.archivos.plantilla || '';
      state.plantillasCat = d.plantillas_categoria || [];
      state.disponibles = d.disponibles || state.disponibles;
      state.categoriaGuardada = d.opciones.categoria || '';

      $('f-cuenta').value = d.opciones.cuenta || '';
      $('f-prefijo-sku').value = d.opciones.prefijo_sku || '';
      $('f-limite').value = d.opciones.limite || '0';
      $('f-modelos').value = d.opciones.modelos || '';
      $('f-usar-ml').checked = d.opciones.usar_ml !== false && d.opciones.usar_ml !== 'false';
      $('f-max-ml').value = d.opciones.max_ml || '30';
      $('f-predecir-cat').checked = d.opciones.predecir_cat === true || d.opciones.predecir_cat === 'true';

      renderBases();
      renderCompl();
      renderSimples();
      cargarFuentes();   // lista de planillas convertibles (no corta el init)

      // los archivos ya están integrados: si falta alguno, se abre el panel
      // (solo cuando la sección de generación está visible)
      if (MOSTRAR_GENERAR &&
          (!state.plantilla || !state.bases.some((b) => b.activa))) {
        $('panel-archivos').open = true;
        toast('Faltan archivos: revisá el panel de archivos.', 'error');
      }
      // el prefijo guardado se pre-carga para que el 1er análisis ya lo use
      state.prefijoGuardado = d.opciones.prefijo || '';
      if (state.prefijoGuardado) {
        const o = document.createElement('option');
        o.value = state.prefijoGuardado;
        o.textContent = state.prefijoGuardado + '-';
        $('f-prefijo').appendChild(o);
        $('f-prefijo').value = state.prefijoGuardado;
      }

      // análisis automático: la app arranca lista para generar
      // (si la sección de generación está guardada, no hace falta)
      if (MOSTRAR_GENERAR) analizar();
    } catch (e) {
      $('estado-rp').textContent = 'error: ' + e.message;
      $('estado-rp').classList.add('mal');
      $('estado-analisis').textContent =
        'No pude conectar con el servidor. ¿Está abierta la app? ' +
        'Recargá la página (F5).';
      $('estado-analisis').classList.add('mal');
      toast('Sin conexión con el servidor: recargá (F5).', 'error');
    }
  }

  /* ---------- botón del header: panel de archivos ---------- */
  // el panel vive dentro de la sección de generación: si está guardada,
  // el botón no tiene dónde abrirse
  if (!MOSTRAR_GENERAR) $('btn-archivos').classList.add('oculto');
  $('btn-archivos').onclick = () => {
    const p = $('panel-archivos');
    p.open = !p.open;
    if (p.open) p.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  /* ---------- catálogo de bases ---------- */
  function renderBases() {
    const ul = $('lista-bases');
    ul.innerHTML = '';
    if (!state.bases.length) {
      const li = document.createElement('li');
      li.className = 'vacio';
      li.textContent = 'Ninguna base registrada todavía.';
      ul.appendChild(li);
    }
    state.bases.forEach((b, i) => {
      const li = document.createElement('li');
      li.className = 'cat-fila' + (b.activa ? '' : ' inactiva');

      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = !!b.activa;
      cb.title = 'Activar/desactivar para el análisis';
      cb.onchange = () => { b.activa = cb.checked; guardarBases(); renderBases(); };

      const nom = document.createElement('input');
      nom.type = 'text';
      nom.value = b.nombre;
      nom.className = 'cat-nombre';
      nom.title = 'Renombrar';
      nom.onblur = () => {
        const v = nom.value.trim();
        if (v && v !== b.nombre) { b.nombre = v; guardarBases(); }
        else nom.value = b.nombre;
      };
      nom.onkeydown = (e) => { if (e.key === 'Enter') nom.blur(); };

      const arc = document.createElement('span');
      arc.className = 'cat-archivo';
      arc.textContent = b.archivo;
      arc.title = b.archivo;

      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'cat-x';
      del.textContent = '×';
      del.title = 'Quitar del catálogo (el archivo queda en el servidor)';
      del.onclick = () => { state.bases.splice(i, 1); guardarBases(); renderBases(); };

      li.append(cb, nom, arc, del);
      ul.appendChild(li);
    });
    // "ya subidos" disponibles para reincorporar
    const sel = $('sel-bases-libres');
    const enCatalogo = new Set(state.bases.map((b) => b.archivo));
    sel.innerHTML = '<option value="">—</option>';
    (state.disponibles.bases || []).forEach((n) => {
      if (enCatalogo.has(n)) return;
      const o = document.createElement('option');
      o.value = n;
      o.textContent = n;
      sel.appendChild(o);
    });
  }

  async function guardarBases() {
    try {
      const d = await post('/api/bases', { bases: state.bases });
      state.bases = d.bases;
    } catch (e) {
      aviso('Error guardando catálogo: ' + e.message);
    }
  }

  $('sel-bases-libres').onchange = async () => {
    const archivo = $('sel-bases-libres').value;
    if (!archivo) return;
    state.bases.push({
      nombre: archivo.replace(/\.(xlsx|xlsm)$/i, ''),
      archivo: archivo,
      activa: true,
    });
    $('sel-bases-libres').value = '';
    await guardarBases();
    renderBases();
  };

  /* ---------- complementos: los ya incluidos, con checkbox de uso ---------- */
  function renderCompl() {
    const ul = $('lista-compl');
    ul.innerHTML = '';
    const disp = state.disponibles.complementos || [];
    if (!disp.length) {
      const li = document.createElement('li');
      li.className = 'vacio';
      li.textContent = 'Sin complementos en el servidor todavía.';
      ul.appendChild(li);
      return;
    }
    disp.forEach((n) => {
      const activo = state.complementos.includes(n);
      const li = document.createElement('li');
      li.className = 'cat-fila' + (activo ? '' : ' inactiva');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = activo;
      cb.title = 'Usar este complemento al generar';
      cb.onchange = () => {
        if (cb.checked) {
          if (!state.complementos.includes(n)) state.complementos.push(n);
        } else {
          state.complementos = state.complementos.filter((x) => x !== n);
        }
        guardarPaths({ complementos: state.complementos });
        renderCompl();
      };
      const nom = document.createElement('span');
      nom.className = 'cat-nombre solo';
      nom.textContent = n;
      nom.title = n;
      li.append(cb, nom);
      ul.appendChild(li);
    });
  }

  /* ---------- fotos / plantilla: selects con lo ya incluido ---------- */
  function nombreBonito(n) {
    return String(n).replace(/\.(xlsx|xlsm)$/i, '')
      .replace(/[-_]+/g, ' ')
      .replace(/\b\p{L}/gu, (c) => c.toUpperCase());
  }

  function renderSimples() {
    const disp = state.disponibles;

    const sf = $('sel-fotos');
    sf.innerHTML = '<option value="">— Sin fotos URL —</option>';
    (disp.fotos || []).forEach((n) => {
      const o = document.createElement('option');
      o.value = n;
      o.textContent = n;
      sf.appendChild(o);
    });
    if (state.fotos && !(disp.fotos || []).includes(state.fotos)) state.fotos = '';
    sf.value = state.fotos;
    $('fotos-actual').textContent = state.fotos
      ? 'Se usan las fotos de: ' + state.fotos
      : 'Se genera sin fotos URL.';

    const sp = $('sel-plantilla');
    const cat = state.plantillasCat || [];
    // si la elegida es una plantilla de EJEMPLO (fuera de la lista de
    // categorías) se muestra igual, marcada, para no perder la selección
    const lista = cat.slice();
    const esEjemplo = !!state.plantilla && !cat.includes(state.plantilla);
    if (esEjemplo) lista.push(state.plantilla);

    sp.innerHTML = '<option value="">— Elegí una categoría —</option>';
    lista.forEach((n) => {
      const o = document.createElement('option');
      o.value = n;
      o.textContent = nombreBonito(n) + (cat.includes(n) ? '' : '  (ejemplo)');
      sp.appendChild(o);
    });
    sp.value = state.plantilla || '';

    const hint = $('plantilla-actual');
    hint.classList.toggle('mal', !state.plantilla);
    hint.textContent = !state.plantilla
      ? (cat.length
          ? 'Vacías por categoría: ' + cat.map(nombreBonito).join(' · ')
          : 'No hay plantillas por categoría en el servidor.')
      : (esEjemplo
          ? 'Ejemplo (rellena): ' + state.plantilla + ' — cambiá por una vacía.'
          : 'Plantilla vacía: ' + state.plantilla);
  }

  async function guardarPaths(datos) {
    try {
      await post('/api/paths', datos);
    } catch (e) {
      toast('No pude guardar: ' + e.message, 'error');
    }
  }

  $('sel-fotos').onchange = () => elegir('fotos', $('sel-fotos').value);
  $('sel-plantilla').onchange = () => elegir('plantilla', $('sel-plantilla').value);

  async function elegir(campo, valor) {
    state[campo] = valor;
    await guardarPaths({ [campo]: valor });
    renderSimples();
  }

  /* ---------- subida (drag & drop + diálogo) ---------- */
  async function subir(tipo, fileList) {
    const files = Array.from(fileList || []).filter((f) => f && f.name);
    if (!files.length) return;
    aviso('Subiendo ' + files.length + ' archivo(s)…');
    const fd = new FormData();
    fd.append('tipo', tipo);
    files.forEach((f) => fd.append('archivos', f));
    try {
      const d = await api('/api/upload', { method: 'POST', body: fd });
      if (d.avisos && d.avisos.length) aviso(d.avisos.join(' · '));
      else aviso('');
      if (tipo === 'bases') state.bases = d.bases || state.bases;
      else if (tipo === 'complementos') state.complementos = d.complementos || state.complementos;
      else if (tipo === 'fotos') state.fotos = d.fotos || '';
      else if (tipo === 'plantilla' || tipo === 'plantillas-categorias') {
        state.plantilla = d.plantilla || '';
      }
      if (d.disponibles) state.disponibles = d.disponibles;
      if (state.disponibles['plantillas-categorias']) {
        state.plantillasCat = state.disponibles['plantillas-categorias'];
      }
      renderBases();
      renderCompl();
      renderSimples();
      if (!d.avisos || !d.avisos.length) {
        aviso('Subido');
        toast('Subido: ' + files.map((f) => f.name).join(', '), 'ok');
      }
      setTimeout(() => { if ($('upload-estado').textContent === 'Subido') aviso(''); }, 2500);
    } catch (e) {
      aviso('Error: ' + e.message);
      toast('Error al subir: ' + e.message, 'error');
    }
  }

  document.querySelectorAll('.drop:not([data-convertir]):not([data-plantilla])').forEach((z) => {
    const tipo = z.dataset.tipo;
    const input = z.querySelector('input[type=file]');
    const btn = z.querySelector('button.link');
    btn.onclick = () => input.click();
    input.onchange = () => { subir(tipo, input.files); input.value = ''; };
    z.onclick = (e) => {
      if (e.target === input || e.target.tagName === 'BUTTON') return;
      input.click();
    };
    ['dragover', 'dragenter'].forEach((ev) =>
      z.addEventListener(ev, (e) => { e.preventDefault(); z.classList.add('drag'); }));
    ['dragleave', 'dragend'].forEach((ev) =>
      z.addEventListener(ev, () => z.classList.remove('drag')));
    z.addEventListener('drop', (e) => {
      e.preventDefault();
      z.classList.remove('drag');
      subir(tipo, e.dataTransfer.files);
    });
  });
  // evitar que soltar fuera de una zona abra el archivo en el navegador
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => e.preventDefault());

  /* ---------- analizar (automático al abrir y con Reanalizar) ---------- */
  async function analizar() {
    $('estado-analisis').textContent = 'Analizando…';
    $('btn-analizar').disabled = true;
    $('btn-generar').disabled = true;   // se rehabilita en finally
    let listo = false;
    try {
      const d = await post('/api/analyze', {
        marketplace: $('f-marketplace').value,
        prefijo: $('f-prefijo').value,
        predecir_cat: $('f-predecir-cat').checked,
      });
      state.categorias = d.categorias;
      state.prefijos = d.prefijos || [];
      $('mp-detectado').textContent =
        'Marketplace: ' + (d.marketplace_detectado || '?');
      const sel = $('f-categoria');
      sel.innerHTML = '';
      d.categorias.forEach((c) => {
        const o = document.createElement('option');
        o.value = c.ruta;
        o.textContent = c.ruta + '  (' + c.modelos + ' modelos · ' + c.variantes + ' variantes)';
        sel.appendChild(o);
      });
      if (!d.categorias.length) {
        const o = document.createElement('option');
        o.textContent = '(sin categorías)';
        sel.appendChild(o);
      }
      if (state.categoriaGuardada &&
          Array.from(sel.options).some((o) => o.value === state.categoriaGuardada)) {
        sel.value = state.categoriaGuardada;
      }
      const sp = $('f-prefijo');
      sp.innerHTML = '<option value="">Todos</option>';
      state.prefijos.forEach((p) => {
        const o = document.createElement('option');
        o.value = p;
        o.textContent = p + '-';
        sp.appendChild(o);
      });
      if (state.prefijoGuardado &&
          Array.from(sp.options).some((o) => o.value === state.prefijoGuardado)) {
        sp.value = state.prefijoGuardado;
      }
      let txt = 'OK · ' + d.total_modelos + ' modelos · ' +
        d.categorias.length + ' categorías';
      if (d.avisos && d.avisos.length) txt += ' · Avisos: ' + d.avisos.join(' · ');
      $('estado-analisis').textContent = txt;
      toast('Listo · ' + d.total_modelos + ' modelos', 'ok');
      listo = true;
    } catch (e) {
      $('estado-analisis').textContent = 'Error: ' + e.message;
      toast('Error al analizar: ' + e.message, 'error');
    } finally {
      $('btn-analizar').disabled = false;
      // el botón de generar queda activo solo si el análisis salió bien
      $('btn-generar').disabled = !listo;
    }
  }
  $('btn-analizar').onclick = analizar;
  // cambiar el prefijo o el marketplace re-analiza solo (la lista cambia)
  $('f-prefijo').onchange = () => {
    state.prefijoGuardado = $('f-prefijo').value;
    analizar();
  };
  $('f-marketplace').onchange = analizar;

  /* ---------- generar ---------- */
  $('btn-generar').onclick = async () => {
    if (!state.plantilla) {
      toast('Elegí una plantilla.', 'error');
      $('sel-plantilla').focus();
      return;
    }
    try {
      await post('/api/generate', {
        marketplace: $('f-marketplace').value,
        categoria: $('f-categoria').value,
        prefijo: $('f-prefijo').value,
        limite: $('f-limite').value === '0' ? '' : $('f-limite').value,
        modelos: $('f-modelos').value,
        usar_ml: $('f-usar-ml').checked,
        max_ml: $('f-max-ml').value,
        predecir_cat: $('f-predecir-cat').checked,
        cuenta: $('f-cuenta').value,
        prefijo_sku: $('f-prefijo-sku').value.trim(),
      });
      mostrar('paso2');
      badgeGen('En curso', 'badge-curso');
      $('resultado').classList.add('oculto');
      $('btn-reintentar').classList.add('oculto');
      $('btn-cancelar').classList.remove('oculto');
      $('log').textContent = '';
      poll();
    } catch (e) {
      toast('No pude iniciar: ' + e.message, 'error');
    }
  };
  $('btn-nuevo').onclick = () => mostrar('paso1');
  $('btn-reintentar').onclick = () => $('btn-generar').click();
  $('btn-cancelar').onclick = () => post('/api/cancel').catch(() => {});

  function poll() {
    clearTimeout(state.pollTimer);
    state.pollTimer = setTimeout(async () => {
      try {
        const p = await api('/api/progress');
        $('barra').style.width = (p.pct || 0) + '%';
        $('fase').textContent = p.fase || '';
        $('detalle').textContent = p.detalle || '';
        $('log').textContent = (p.log || []).join('\n');
        $('log').scrollTop = $('log').scrollHeight;

        if (p.error) {
          $('fase').textContent = 'Error';
          $('detalle').textContent = p.error;
          badgeGen('Error', 'badge-error');
          toast('Generación falló: ' + p.error, 'error');
          $('btn-cancelar').classList.add('oculto');
          $('btn-reintentar').classList.remove('oculto');
          return;
        }
        if (!p.activo && p.resultado) {
          mostrarResultado(p.resultado);
          return;
        }
        if (!p.activo && !p.resultado && p.fase !== 'Iniciando') {
          return;
        }
        poll();
      } catch (e) {
        poll();
      }
    }, 500);
  }

  function mostrarResultado(r) {
    $('barra').style.width = '100%';
    $('fase').textContent = 'Completado';
    badgeGen('Completado', 'badge-listo');
    toast('Planilla generada (' + r.filas + ' filas)', 'ok');
    $('btn-cancelar').classList.add('oculto');
    $('resultado').classList.remove('oculto');
    $('resumen').textContent =
      r.modelos + ' modelos · ' + r.filas + ' filas · ' +
      (r.bytes ? Math.round(r.bytes / 1024) + ' KB' : '') +
      (r.cuenta ? ' · cuenta: ' + r.cuenta : '') +
      (r.marketplace ? ' · ' + r.marketplace : '') +
      (r.color_ajustadas ? ' · ' + r.color_ajustadas + ' colores ajustados' : '') +
      (r.prefijos_sku ? ' · SKU con prefijo aplicado' : '');
    $('btn-descargar').href = '/descargas/' + encodeURIComponent(r.archivo);

    const v = [];
    const falt = r.faltantes || {};
    Object.entries(falt).forEach(([campo, n]) => {
      if (n > 0) v.push(campo + ' vacío en ' + n + ' filas');
    });
    if ((r.sin_fotos || []).length) v.push(r.sin_fotos.length + ' sin fotos');
    if ((r.sin_precio || []).length) v.push(r.sin_precio.length + ' sin precio');
    if ((r.sin_guia || []).length) v.push(r.sin_guia.length + ' sin guía');
    if ((r.color_sin_lista || []).length) {
      v.push('sin color de la lista: ' + r.color_sin_lista.join(', '));
    }
    $('validacion').innerHTML = v.length
      ? '<p class="warn">Revisar: ' + v.join(' · ') + '</p>'
      : '<p class="ok">Sin campos obligatorios vacíos.</p>';
    $('preview').classList.add('oculto');
    // la planilla cambió: los paneles de revisión y edición se reinician
    cerrarRevisiones();
  }

  /* ---------- vista previa ---------- */
  async function cargarPreview() {
    const d = await api('/api/preview?rows=20');
    const t = $('tabla-preview');
    t.innerHTML = '';
    const trh = document.createElement('tr');
    d.encabezados.forEach((h) => {
      const th = document.createElement('th');
      th.textContent = h;
      trh.appendChild(th);
    });
    t.appendChild(trh);
    d.filas.forEach((f) => {
      const tr = document.createElement('tr');
      f.forEach((c) => {
        const td = document.createElement('td');
        td.textContent = c;
        tr.appendChild(td);
      });
      t.appendChild(tr);
    });
    $('preview').classList.remove('oculto');
  }

  $('btn-preview').onclick = async () => {
    if (!$('preview').classList.contains('oculto')) {
      $('preview').classList.add('oculto');
      return;
    }
    try {
      await cargarPreview();
    } catch (e) {
      toast('Preview: ' + e.message, 'error');
    }
  };

  /* ---------- revisión de fotos ---------- */
  function abrirLightbox(url, pie) {
    $('lightbox-img').src = url;
    $('lightbox-cap').textContent = pie || '';
    $('lightbox').classList.remove('oculto');
  }
  $('lightbox').onclick = () => $('lightbox').classList.add('oculto');
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') $('lightbox').classList.add('oculto');
  });

  function renderFotos(d) {
    const cont = $('fotos-lista');
    cont.innerHTML = '';
    const sin = d.sin_fotos || [];
    $('fotos-resumen').textContent =
      d.filas.length + ' producto(s) · ' + (d.total_fotos || 0) + ' foto(s)' +
      (sin.length ? ' · ' + sin.length + ' sin fotos' : '');

    $('fotos-sin').innerHTML = sin.length
      ? '<p class="warn">Sin fotos: ' + sin.slice(0, 12).join(', ') +
        (sin.length > 12 ? ' · y ' + (sin.length - 12) + ' más' : '') + '</p>'
      : '';

    if (!d.filas.length) {
      cont.innerHTML = '<p class="hint">No hay fotos cargadas en esta planilla.</p>';
      return;
    }
    d.filas.forEach((f) => {
      const card = document.createElement('div');
      card.className = 'foto-card';

      const h = document.createElement('div');
      h.className = 'foto-card-h';
      h.textContent = [f.sku, f.color, f.talla].filter(Boolean).join(' · ') ||
        ('fila ' + f.fila);
      h.title = h.textContent;
      card.appendChild(h);

      const g = document.createElement('div');
      g.className = 'foto-grid';
      f.urls.forEach((u) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'foto';
        b.title = 'Ampliar';
        const img = document.createElement('img');
        img.loading = 'lazy';
        img.alt = '';
        img.src = u;
        img.onerror = () => {
          b.classList.add('rota');
          b.textContent = 'No cargó';
          b.title = u;
          b.onclick = null;
        };
        b.appendChild(img);
        b.onclick = () => abrirLightbox(u, h.textContent);
        g.appendChild(b);
      });
      card.appendChild(g);
      cont.appendChild(card);
    });
  }

  $('btn-fotos').onclick = async () => {
    const p = $('fotos-panel');
    if (!p.classList.contains('oculto')) {
      p.classList.add('oculto');
      return;
    }
    $('fotos-lista').innerHTML = '<p class="hint">Cargando fotos…</p>';
    $('fotos-sin').innerHTML = '';
    p.classList.remove('oculto');
    try {
      renderFotos(await api('/api/fotos'));
    } catch (e) {
      p.classList.add('oculto');
      toast('Fotos: ' + e.message, 'error');
    }
  };

  /* ---------- editor de la planilla ---------- */
  const edit = { enc: [], orig: new Map(), cambios: new Map(), cargando: false };

  function estadoEdicion(txt) {
    if (txt) {
      $('editor-estado').textContent = txt;
      return;
    }
    const n = edit.cambios.size;
    $('editor-estado').textContent = n
      ? n + ' cambio(s) sin guardar'
      : 'Sin cambios pendientes';
    $('btn-guardar').disabled = !n;
  }

  async function cargarEditor() {
    // mientras carga, los focusout del DOM viejo no deben registrar cambios
    edit.cargando = true;
    try {
      const d = await api('/api/planilla/edit');
      edit.enc = d.encabezados;
      edit.orig.clear();
      edit.cambios.clear();

      const t = $('tabla-editor');
      t.innerHTML = '';
      const trh = document.createElement('tr');
      const th0 = document.createElement('th');
      th0.className = 'fila-num';
      th0.textContent = '#';
      trh.appendChild(th0);
      d.encabezados.forEach((e) => {
        const th = document.createElement('th');
        th.textContent = e.texto;
        th.title = e.texto;
        trh.appendChild(th);
      });
      t.appendChild(trh);

      d.filas.forEach((f) => {
        const tr = document.createElement('tr');
        const td0 = document.createElement('td');
        td0.className = 'fila-num';
        td0.textContent = f.fila;
        tr.appendChild(td0);
        f.celdas.forEach((v, j) => {
          const col = d.encabezados[j].col;
          const td = document.createElement('td');
          td.contentEditable = 'true';
          td.spellcheck = false;
          td.textContent = v;
          td.dataset.fila = f.fila;
          td.dataset.col = col;
          td.title = d.encabezados[j].texto;
          edit.orig.set(f.fila + ':' + col, v);
          tr.appendChild(td);
        });
        t.appendChild(tr);
      });
      estadoEdicion();
    } finally {
      edit.cargando = false;
    }
  }

  const te = $('tabla-editor');
  te.addEventListener('focusin', (e) => {
    const td = e.target.closest && e.target.closest('td[contenteditable]');
    if (td) td.classList.add('editando');
  });
  te.addEventListener('focusout', (e) => {
    const td = e.target.closest && e.target.closest('td[contenteditable]');
    // si la celda ya no vive en la tabla actual (se recargó el editor),
    // su focusout no debe registrar ningún cambio
    if (!td || !te.contains(td) || edit.cargando) return;
    td.classList.remove('editando');
    const key = td.dataset.fila + ':' + td.dataset.col;
    const nuevo = td.textContent.replace(/\s+$/, '');
    const orig = edit.orig.has(key) ? edit.orig.get(key) : '';
    td.textContent = nuevo;
    if (nuevo === orig) {
      edit.cambios.delete(key);
      td.classList.remove('editado');
    } else {
      edit.cambios.set(key, {
        fila: parseInt(td.dataset.fila, 10),
        col: parseInt(td.dataset.col, 10),
        valor: nuevo,
      });
      td.classList.add('editado');
    }
    estadoEdicion();
  });
  te.addEventListener('keydown', (e) => {
    const td = e.target.closest && e.target.closest('td[contenteditable]');
    if (!td) return;
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      td.blur();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      const key = td.dataset.fila + ':' + td.dataset.col;
      td.textContent = edit.orig.has(key) ? edit.orig.get(key) : '';
      td.blur();
    }
  });
  te.addEventListener('paste', (e) => {
    const td = e.target.closest && e.target.closest('td[contenteditable]');
    if (!td) return;
    e.preventDefault();
    const txt = (e.clipboardData || window.clipboardData).getData('text');
    document.execCommand('insertText', false, txt);
  });

  $('btn-editar').onclick = async () => {
    const p = $('editor-panel');
    if (!p.classList.contains('oculto')) {
      if (edit.cambios.size &&
          !confirm('Hay cambios sin guardar. ¿Cerrar el editor igual?')) return;
      p.classList.add('oculto');
      return;
    }
    p.classList.remove('oculto');
    $('tabla-editor').innerHTML =
      '<tr><td colspan="99">Cargando la planilla…</td></tr>';
    try {
      await cargarEditor();
    } catch (e) {
      p.classList.add('oculto');
      toast('Editor: ' + e.message, 'error');
    }
  };

  $('btn-descartar').onclick = async () => {
    try {
      await cargarEditor();
      toast('Cambios descartados', 'ok');
    } catch (e) {
      toast('No pude recargar: ' + e.message, 'error');
    }
  };

  $('btn-guardar').onclick = async () => {
    const cambios = Array.from(edit.cambios.values());
    if (!cambios.length) return;
    $('btn-guardar').disabled = true;
    $('btn-descartar').disabled = true;   // nada de recargar mientras se escribe
    estadoEdicion('Guardando…');
    try {
      const d = await post('/api/planilla/edit', { cambios: cambios });
      cambios.forEach((c) => {
        const key = c.fila + ':' + c.col;
        const td = te.querySelector(
          'td[data-fila="' + c.fila + '"][data-col="' + c.col + '"]');
        const actual = td ? td.textContent : c.valor;
        // el nuevo "original" es lo que se acaba de guardar
        edit.orig.set(key, c.valor);
        if (actual === c.valor) {
          edit.cambios.delete(key);
          if (td) td.classList.remove('editado');
        } else {
          // se volvió a editar mientras se guardaba: queda como cambio pendiente
          edit.cambios.set(key, { fila: c.fila, col: c.col, valor: actual });
          if (td) td.classList.add('editado');
        }
      });
      estadoEdicion();
      toast('Guardados ' + d.guardados + ' cambio(s) en la planilla', 'ok');
      if (!$('preview').classList.contains('oculto')) cargarPreview();
    } catch (e) {
      estadoEdicion();
      toast('No pude guardar: ' + e.message, 'error');
    } finally {
      $('btn-descartar').disabled = false;
    }
  };

  function cerrarRevisiones() {
    $('fotos-panel').classList.add('oculto');
    $('editor-panel').classList.add('oculto');
    edit.cambios.clear();
    edit.orig.clear();
  }

  /* ---------- conversión: planilla vieja -> formato nuevo de ML ---------- */
  async function cargarFuentes() {
    try {
      const d = await api('/api/conversion');
      state.convFuentes = d.fuentes || [];
      const sel = $('sel-fuente');
      sel.innerHTML = '';
      const vacia = document.createElement('option');
      vacia.value = '';
      vacia.textContent = '— elegir una planilla —';
      sel.appendChild(vacia);
      const grupos = [
        ['salida', 'Generadas (salida/)'],
        ['subida', 'Subidas para convertir'],
      ];
      let n = 0;
      grupos.forEach(([clave, titulo]) => {
        const items = state.convFuentes.filter((f) => f.origen === clave);
        if (!items.length) return;
        const g = document.createElement('optgroup');
        g.label = titulo;
        state.convFuentes.forEach((f, i) => {
          if (f.origen !== clave) return;
          const o = document.createElement('option');
          o.value = String(i);
          o.textContent = f.nombre;
          g.appendChild(o);
          n++;
        });
        sel.appendChild(g);
      });
      if (!n) {
        const o = document.createElement('option');
        o.disabled = true;
        o.textContent = '(no hay planillas todavía)';
        sel.appendChild(o);
      }
      state.plantillaOk = !!(d.plantilla && d.plantilla.existe);
      state.plantillaNombre = (d.plantilla && d.plantilla.nombre) || '';
      state.plantillaCategorias =
        (d.plantilla && d.plantilla.categorias) || [];
      pintarPlantilla();
      actualizarBotonConvertir();
      actualizarBotonesBorrar();
    } catch (e) {
      $('fuente-hint').textContent = 'No pude listar las planillas: ' + e.message;
      actualizarBotonConvertir();
    }
  }

  function pintarPlantilla() {
    if (!state.plantillaOk) {
      $('plantilla-hint').textContent =
        'Falta subir la plantilla nueva descargada de Mercado Libre.';
      return;
    }
    let txt = 'Plantilla cargada: ' + (state.plantillaNombre || 'sí');
    if (state.plantillaCategorias.length) {
      // el nombre corto de cada categoría (último tramo del árbol)
      const cats = state.plantillaCategorias.map((c) => {
        const p = String(c).split('>');
        return p[p.length - 1].trim();
      });
      txt += ' · categorías: ' + cats.join(', ');
    }
    $('plantilla-hint').textContent = txt + ' · lista para convertir';
  }

  function actualizarBotonesBorrar() {
    // el de borrar plantilla solo si hay plantilla cargada;
    // el de borrar planillas, si hay subidas en el servidor o pendientes
    $('btn-borrar-plantilla').classList.toggle('oculto', !state.plantillaOk);
    const subidas = state.convFuentes.some((f) => f.origen === 'subida');
    $('btn-borrar-planillas').classList.toggle(
      'oculto', !(subidas || state.convArchivos.length));
  }

  async function borrarPlantilla() {
    if (!window.confirm('¿Borrar la plantilla nueva cargada?')) return;
    try {
      await api('/api/plantilla', { method: 'DELETE' });
      state.plantillaOk = false;
      state.plantillaNombre = '';
      state.plantillaCategorias = [];
      pintarPlantilla();
      actualizarBotonConvertir();
      actualizarBotonesBorrar();
      toast('Plantilla borrada', 'ok');
    } catch (e) {
      toast('No pude borrar la plantilla: ' + e.message, 'error');
    }
  }

  async function borrarPlanillasSubidas() {
    if (!window.confirm('¿Borrar todas las planillas viejas subidas?')) return;
    try {
      const d = await api('/api/planillas-antiguas', { method: 'DELETE' });
      state.convArchivos = [];
      $('sel-fuente').value = '';
      await cargarFuentes();
      toast('Planillas borradas: ' + (d.borradas || 0), 'ok');
    } catch (e) {
      toast('No pude borrar las planillas: ' + e.message, 'error');
    }
  }

  function pintarPendientes() {
    const n = state.convArchivos.length;
    $('conv-pendientes').textContent = !n
      ? ''
      : n + ' planilla(s) lista(s) para convertir: ' +
        state.convArchivos.map((f) => f.name).join(', ');
    actualizarBotonesBorrar();
  }

  function actualizarBotonConvertir() {
    const sel = $('sel-fuente');
    const hayFuente = state.convArchivos.length > 0 ||
      (sel && sel.value !== '');
    $('btn-convertir').disabled = !(state.plantillaOk && hayFuente);
  }

  function resultadosConversion(resultados) {
    const cont = $('conversion-resumen');
    const desc = $('conversion-descargas');
    cont.innerHTML = '';
    desc.innerHTML = '';
    const descartadas = [];
    resultados.forEach((r) => {
      const p = document.createElement('p');
      if (r.ok) {
        p.className = 'ok';
        p.textContent = r.origen + ' -> ' + r.archivo + ' · ' + r.filas +
          ' fila(s)' +
          (r.planillas > 1
            ? ' · ' + r.planillas + ' planillas en 1 archivo'
            : ' · hoja: ' + r.hoja) +
          (r.ean_nuevos ? ' · EAN nuevos: ' + r.ean_nuevos : '') +
          (r.sin_h ? ' · SKU sin H-: ' + r.sin_h : '') +
          (r.titulos_ajustados
            ? ' · títulos a 60 caracteres: ' + r.titulos_ajustados : '') +
          (r.duplicadas
            ? ' · SKU repetidos omitidos: ' + r.duplicadas : '') +
          (r.aviso ? ' · ' + r.aviso : '');
        const a = document.createElement('a');
        a.className = 'secundario';
        a.href = '/descargas/' + encodeURIComponent(r.archivo);
        a.textContent = 'Descargar ' + r.archivo;
        desc.appendChild(a);
        (r.descartadas || []).forEach((c) => {
          if (descartadas.indexOf(c) < 0) descartadas.push(c);
        });
      } else {
        p.className = 'warn';
        p.textContent = r.origen + ': ' + (r.mensaje || r.error);
      }
      cont.appendChild(p);
      if (r.ok) {
        (r.detalle || []).forEach((d) => {
          const q = document.createElement('p');
          q.className = 'ok';
          q.textContent = '   ' + d.origen + ': ' + d.filas + ' fila(s)' +
            (d.hoja ? ' · hoja: ' + d.hoja : '') +
            (d.duplicadas ? ' · repetidos: ' + d.duplicadas : '') +
            (d.aviso ? ' · ' + d.aviso : '');
          cont.appendChild(q);
        });
      }
    });
    if (descartadas.length) {
      const p = document.createElement('p');
      p.className = 'warn';
      p.textContent = 'Columnas descartadas (no existen en la plantilla ' +
        'nueva): ' + descartadas.join(', ');
      cont.appendChild(p);
    }
    $('resultado-conversion').classList.remove('oculto');
  }

  function estadoConversion(res) {
    const ok = res.filter((r) => r.ok);
    const mal = res.length - ok.length;
    const n = ok.reduce((a, r) => a + (r.planillas || 1), 0);
    $('estado-conversion').textContent = mal
      ? n + ' convertida(s) · ' + mal + ' con error'
      : n + ' convertida(s)';
    toast(mal ? 'Conversión con errores' : 'Conversión lista',
          mal ? 'error' : 'ok');
  }

  async function convertirPlanillas(datos, fd) {
    $('estado-conversion').textContent = 'Convirtiendo…';
    $('btn-convertir').disabled = true;
    try {
      const d = fd
        ? await api('/api/convertir', { method: 'POST', body: fd })
        : await post('/api/convertir', datos);
      const res = d.resultados || [];
      if (fd) {
        state.convArchivos = [];   // lo subido ya se convirtió
        pintarPendientes();
      }
      resultadosConversion(res);
      estadoConversion(res);
      cargarFuentes();
    } catch (e) {
      $('estado-conversion').textContent = 'Error: ' + e.message;
      toast('Conversión: ' + e.message, 'error');
      actualizarBotonConvertir();
    }
  }

  async function subirPlantilla(fileList) {
    const todos = Array.from(fileList || []).filter((f) => f && f.name);
    const files = todos.filter((f) => /\.(xlsx|xlsm)$/i.test(f.name));
    if (!files.length) {
      if (todos.length) toast('Solo se pueden subir archivos .xlsx', 'error');
      return;
    }
    if (files.length > 1) {
      toast('La plantilla se usa de a una: se cargó la última (' +
            files[files.length - 1].name + ')', 'info');
    }
    const f = files[files.length - 1];
    const hint = $('plantilla-hint');
    hint.textContent = 'Subiendo ' + f.name + '…';
    try {
      const fd = new FormData();
      fd.append('plantilla', f);
      const d = await api('/api/plantilla', { method: 'POST', body: fd });
      state.plantillaOk = true;
      state.plantillaNombre = d.archivo || f.name;
      state.plantillaCategorias = d.categorias || [];
      pintarPlantilla();
      toast('Plantilla cargada: ' + state.plantillaNombre, 'ok');
    } catch (e) {
      state.plantillaOk = false;
      hint.textContent = 'No pude guardar ' + f.name + ': ' + e.message;
      toast('Plantilla: ' + e.message, 'error');
    }
    actualizarBotonConvertir();
    actualizarBotonesBorrar();
  }

  function agregarAPendientes(fileList) {
    const todos = Array.from(fileList || []).filter((f) => f && f.name);
    const files = todos.filter((f) => /\.(xlsx|xlsm)$/i.test(f.name));
    if (!files.length) {
      if (todos.length) toast('Solo se pueden convertir archivos .xlsx', 'error');
      return;
    }
    if (files.length < todos.length) {
      toast('Ignorado(s) ' + (todos.length - files.length) +
            ' archivo(s) que no son .xlsx', 'info');
    }
    // solo una fuente a la vez: subir archivos limpia el selector y elegir
    // del selector limpia lo subido
    files.forEach((f) => {
      const i = state.convArchivos.findIndex((x) => x.name === f.name);
      if (i >= 0) state.convArchivos.splice(i, 1);
      state.convArchivos.push(f);
    });
    $('sel-fuente').value = '';
    pintarPendientes();
    actualizarBotonConvertir();
  }

  document.querySelectorAll('.drop[data-convertir]').forEach((z) => {
    const input = z.querySelector('input[type=file]');
    const btn = z.querySelector('button.link');
    btn.onclick = () => input.click();
    input.onchange = () => { agregarAPendientes(input.files); input.value = ''; };
    z.onclick = (e) => {
      if (e.target === input || e.target.tagName === 'BUTTON') return;
      input.click();
    };
    ['dragover', 'dragenter'].forEach((ev) =>
      z.addEventListener(ev, (e) => { e.preventDefault(); z.classList.add('drag'); }));
    ['dragleave', 'dragend'].forEach((ev) =>
      z.addEventListener(ev, () => z.classList.remove('drag')));
    z.addEventListener('drop', (e) => {
      e.preventDefault();
      z.classList.remove('drag');
      agregarAPendientes(e.dataTransfer.files);
    });
  });

  document.querySelectorAll('.drop[data-plantilla]').forEach((z) => {
    const input = z.querySelector('input[type=file]');
    const btn = z.querySelector('button.link');
    btn.onclick = () => input.click();
    input.onchange = () => { subirPlantilla(input.files); input.value = ''; };
    z.onclick = (e) => {
      if (e.target === input || e.target.tagName === 'BUTTON') return;
      input.click();
    };
    ['dragover', 'dragenter'].forEach((ev) =>
      z.addEventListener(ev, (e) => { e.preventDefault(); z.classList.add('drag'); }));
    ['dragleave', 'dragend'].forEach((ev) =>
      z.addEventListener(ev, () => z.classList.remove('drag')));
    z.addEventListener('drop', (e) => {
      e.preventDefault();
      z.classList.remove('drag');
      subirPlantilla(e.dataTransfer.files);
    });
  });

  $('sel-fuente').onchange = () => {
    // solo una fuente a la vez: elegir del selector limpia lo subido
    state.convArchivos = [];
    pintarPendientes();
    actualizarBotonConvertir();
  };
  $('btn-borrar-plantilla').onclick = borrarPlantilla;
  $('btn-borrar-planillas').onclick = borrarPlanillasSubidas;
  $('btn-convertir').onclick = () => {
    if (state.convArchivos.length) {
      const fd = new FormData();
      state.convArchivos.forEach((f) => fd.append('archivos', f));
      convertirPlanillas(null, fd);
      return;
    }
    const f = state.convFuentes[parseInt($('sel-fuente').value, 10)];
    if (!f) return;
    convertirPlanillas({ archivo: f.nombre, origen: f.origen }, null);
  };

  init();
})();
