"""Graph explorer HTML/JS/CSS: D3 force-directed visualization."""

EXPLORER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Cortex Explorer</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; display: flex; height: 100vh; overflow: hidden; }
#sidebar { width: 260px; background: #161b22; padding: 16px; overflow-y: auto; border-right: 1px solid #30363d; display: flex; flex-direction: column; gap: 16px; }
#sidebar h1 { font-size: 18px; color: #58a6ff; }
#sidebar h2 { font-size: 13px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
#search { width: 100%; padding: 6px 10px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-size: 14px; outline: none; }
#search:focus { border-color: #58a6ff; }
.filter-group { display: flex; flex-direction: column; gap: 4px; }
.filter-item { display: flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; }
.filter-item input { cursor: pointer; }
.color-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
#summary { font-size: 13px; color: #8b949e; line-height: 1.6; }
#main { flex: 1; display: flex; flex-direction: column; position: relative; }
svg { flex: 1; }
#tooltip { position: absolute; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; font-size: 13px; pointer-events: none; opacity: 0; transition: opacity 0.15s; max-width: 280px; z-index: 10; }
#tooltip .name { font-size: 15px; font-weight: 600; color: #58a6ff; margin-bottom: 4px; }
#tooltip .detail { color: #8b949e; line-height: 1.5; }
#replay-bar { height: 40px; background: #161b22; border-top: 1px solid #30363d; display: flex; align-items: center; padding: 0 16px; gap: 12px; }
#replay-bar label { font-size: 12px; color: #8b949e; white-space: nowrap; }
#replay-slider { flex: 1; accent-color: #58a6ff; }
#replay-btn { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }
#replay-btn:hover { background: #30363d; }
#replay-date { font-size: 12px; color: #58a6ff; min-width: 80px; }
#replay-counts { font-size: 12px; color: #8b949e; }
/* CORRECTION_STYLES */
</style>
</head>
<body>
<div id="sidebar">
  <h1>Cortex Explorer</h1>
  <input type="text" id="search" placeholder="Search concepts...">
  <div>
    <h2>Kind</h2>
    <div id="kind-filters" class="filter-group"></div>
  </div>
  <div>
    <h2>Confidence</h2>
    <div id="confidence-filters" class="filter-group"></div>
  </div>
  <div>
    <h2>Summary</h2>
    <div id="summary"></div>
  </div>
  <!-- CORRECTION_PANEL -->
</div>
<div id="main">
  <svg id="graph"></svg>
  <div id="tooltip"><div class="name"></div><div class="detail"></div></div>
  <div id="replay-bar">
    <button id="replay-btn">Play</button>
    <label>Timeline</label>
    <input type="range" id="replay-slider" min="0" max="100" value="100">
    <span id="replay-date"></span>
    <span id="replay-counts"></span>
  </div>
</div>
<script>
const KIND_COLORS = {topic:'#58a6ff',tool:'#3fb950',pattern:'#d2a8ff',decision:'#f0883e',person:'#f778ba',project:'#79c0ff'};
const CONF_OPACITY = {tentative:0.5,established:0.75,settled:1.0};
const REL_COLORS = {'related-to':'#8b949e','depends-on':'#f0883e','conflicts-with':'#f85149','enables':'#3fb950'};
const filters = {kinds: new Set(), confidences: new Set(), search: '', maxDate: null};
let allConcepts = [], allEdges = [], timelineDates = [], clusters = [];
let simulation, nodeEls, linkEls, labelEls, hullEls, selectedNode = null;

function clearChildren(el) { while (el.firstChild) el.removeChild(el.firstChild); }

function buildFilters(concepts) {
  const kindSet = new Set(concepts.map(c => c.kind));
  const confSet = new Set(concepts.map(c => c.confidence));
  const kf = document.getElementById('kind-filters');
  clearChildren(kf);
  kindSet.forEach(k => {
    filters.kinds.add(k);
    const label = document.createElement('label');
    label.className = 'filter-item';
    const cb = document.createElement('input');
    cb.type = 'checkbox'; cb.checked = true;
    cb.addEventListener('change', () => { cb.checked ? filters.kinds.add(k) : filters.kinds.delete(k); applyFilters(); });
    const dot = document.createElement('span');
    dot.className = 'color-dot';
    dot.style.background = KIND_COLORS[k] || '#8b949e';
    const txt = document.createTextNode(k);
    label.appendChild(cb); label.appendChild(dot); label.appendChild(txt);
    kf.appendChild(label);
  });
  const cf = document.getElementById('confidence-filters');
  clearChildren(cf);
  confSet.forEach(c => {
    filters.confidences.add(c);
    const label = document.createElement('label');
    label.className = 'filter-item';
    const cb = document.createElement('input');
    cb.type = 'checkbox'; cb.checked = true;
    cb.addEventListener('change', () => { cb.checked ? filters.confidences.add(c) : filters.confidences.delete(c); applyFilters(); });
    const txt = document.createTextNode(c);
    label.appendChild(cb); label.appendChild(txt);
    cf.appendChild(label);
  });
}

function applyFilters() {
  const q = filters.search.toLowerCase();
  const visible = new Set();
  allConcepts.forEach(c => {
    let show = filters.kinds.has(c.kind) && filters.confidences.has(c.confidence);
    if (q && !c.name.toLowerCase().includes(q)) show = false;
    if (filters.maxDate && c.first_seen > filters.maxDate) show = false;
    if (show) visible.add(c.id);
  });
  nodeEls.style('display', d => visible.has(d.id) ? null : 'none');
  labelEls.style('display', d => visible.has(d.id) ? null : 'none');
  linkEls.style('display', d => visible.has(d.from_concept_id) && visible.has(d.to_concept_id) ? null : 'none');
  const vc = visible.size;
  let ve = 0;
  allEdges.forEach(e => { if (visible.has(e.from_concept_id) && visible.has(e.to_concept_id)) ve++; });
  document.getElementById('replay-counts').textContent = vc + ' concepts, ' + ve + ' edges';
}

async function init() {
  const [graphData, timelineData, clusterData] = await Promise.all([
    fetch('/api/graph').then(r => r.json()),
    fetch('/api/timeline').then(r => r.json()),
    fetch('/api/clusters').then(r => r.json())
  ]);

  allConcepts = graphData.concepts;
  allEdges = graphData.edges;
  clusters = clusterData.clusters;

  const conceptMap = {};
  allConcepts.forEach(c => { conceptMap[c.id] = c; });

  buildFilters(allConcepts);

  const s = graphData.summary;
  const summaryEl = document.getElementById('summary');
  summaryEl.textContent = s.concepts + ' concepts, ' + s.edges + ' edges, ' + s.projects + ' projects';

  // Timeline setup
  const allDates = timelineData.concepts.map(c => c.first_seen).concat(timelineData.edges.map(e => e.first_seen)).sort();
  timelineDates = [...new Set(allDates)];
  const slider = document.getElementById('replay-slider');
  slider.max = timelineDates.length > 0 ? timelineDates.length - 1 : 0;
  slider.value = slider.max;
  if (timelineDates.length > 0) {
    document.getElementById('replay-date').textContent = timelineDates[timelineDates.length - 1].substring(0, 10);
  }

  slider.addEventListener('input', () => {
    const idx = parseInt(slider.value);
    if (idx < timelineDates.length) {
      filters.maxDate = timelineDates[idx];
      document.getElementById('replay-date').textContent = timelineDates[idx].substring(0, 10);
    } else {
      filters.maxDate = null;
    }
    applyFilters();
  });

  let playing = false, playInterval = null;
  const playBtn = document.getElementById('replay-btn');
  playBtn.addEventListener('click', () => {
    if (playing) {
      clearInterval(playInterval);
      playBtn.textContent = 'Play';
      playing = false;
    } else {
      if (parseInt(slider.value) >= parseInt(slider.max)) slider.value = 0;
      playing = true;
      playBtn.textContent = 'Pause';
      playInterval = setInterval(() => {
        const v = parseInt(slider.value) + 1;
        if (v > parseInt(slider.max)) { clearInterval(playInterval); playBtn.textContent = 'Play'; playing = false; return; }
        slider.value = v;
        slider.dispatchEvent(new Event('input'));
      }, 300);
    }
  });

  document.getElementById('search').addEventListener('input', e => {
    filters.search = e.target.value;
    applyFilters();
  });

  // D3 setup
  const svg = d3.select('#graph');
  const width = svg.node().clientWidth;
  const height = svg.node().clientHeight;

  const g = svg.append('g');

  const zoom = d3.zoom().scaleExtent([0.1, 8]).on('zoom', e => g.attr('transform', e.transform));
  svg.call(zoom);

  // Cluster hulls
  hullEls = g.append('g').attr('class', 'hulls').selectAll('path')
    .data(clusters.filter(c => c.length >= 3))
    .join('path')
    .attr('fill', (d, i) => d3.schemeTableau10[i % 10])
    .attr('fill-opacity', 0.05)
    .attr('stroke', (d, i) => d3.schemeTableau10[i % 10])
    .attr('stroke-opacity', 0.15)
    .attr('stroke-width', 1);

  const clusterNameSets = clusters.map(c => new Set(c));

  // Links
  const links = allEdges.map(e => ({...e, source: e.from_concept_id, target: e.to_concept_id}));
  linkEls = g.append('g').selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke', d => REL_COLORS[d.relation] || '#8b949e')
    .attr('stroke-width', d => Math.max(1, Math.min(d.strength, 5)))
    .attr('stroke-opacity', 0.5);

  // Nodes
  const nodeSize = d => Math.max(4, Math.sqrt(d.source_count || 1) * 3);
  nodeEls = g.append('g').selectAll('circle')
    .data(allConcepts)
    .join('circle')
    .attr('r', nodeSize)
    .attr('fill', d => KIND_COLORS[d.kind] || '#8b949e')
    .attr('fill-opacity', d => CONF_OPACITY[d.confidence] || 0.75)
    .attr('stroke', '#0d1117')
    .attr('stroke-width', 1)
    .attr('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
    );

  // Labels
  labelEls = g.append('g').selectAll('text')
    .data(allConcepts)
    .join('text')
    .text(d => d.name)
    .attr('font-size', 11)
    .attr('fill', '#c9d1d9')
    .attr('dx', d => nodeSize(d) + 4)
    .attr('dy', 4)
    .attr('pointer-events', 'none');

  // Tooltip
  const tooltip = document.getElementById('tooltip');
  const tooltipName = tooltip.querySelector('.name');
  const tooltipDetail = tooltip.querySelector('.detail');

  nodeEls.on('mouseover', (e, d) => {
    tooltipName.textContent = d.name;
    const edges = allEdges.filter(edge => edge.from_concept_id === d.id || edge.to_concept_id === d.id);
    tooltipDetail.textContent = d.kind + ' | ' + d.confidence + ' | ' + (d.source_count || 0) + ' sources | ' + edges.length + ' edges';
    tooltip.style.opacity = 1;
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY - 12) + 'px';
  })
  .on('mousemove', e => {
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY - 12) + 'px';
  })
  .on('mouseout', () => { tooltip.style.opacity = 0; });

  // Click to highlight neighbors
  nodeEls.on('click', (e, d) => {
    // CORRECTION_SELECT
    if (selectedNode === d.id) {
      selectedNode = null;
      nodeEls.attr('fill-opacity', nd => CONF_OPACITY[nd.confidence] || 0.75);
      linkEls.attr('stroke-opacity', 0.5);
      labelEls.attr('fill-opacity', 1);
      // CORRECTION_DESELECT
      return;
    }
    selectedNode = d.id;
    const neighborIds = new Set();
    allEdges.forEach(edge => {
      if (edge.from_concept_id === d.id) neighborIds.add(edge.to_concept_id);
      if (edge.to_concept_id === d.id) neighborIds.add(edge.from_concept_id);
    });
    neighborIds.add(d.id);
    nodeEls.attr('fill-opacity', nd => neighborIds.has(nd.id) ? 1 : 0.1);
    linkEls.attr('stroke-opacity', ld => (ld.from_concept_id === d.id || ld.to_concept_id === d.id) ? 0.8 : 0.05);
    labelEls.attr('fill-opacity', nd => neighborIds.has(nd.id) ? 1 : 0.1);
  });

  // Force simulation
  simulation = d3.forceSimulation(allConcepts)
    .force('link', d3.forceLink(links).id(d => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide().radius(d => nodeSize(d) + 8))
    .on('tick', () => {
      linkEls.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
             .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      nodeEls.attr('cx', d => d.x).attr('cy', d => d.y);
      labelEls.attr('x', d => d.x).attr('y', d => d.y);

      // Update cluster hulls
      hullEls.attr('d', (clusterNames, i) => {
        const nameSet = clusterNameSets[clusters.indexOf(clusterNames)];
        const points = allConcepts.filter(c => nameSet && nameSet.has(c.name)).map(c => [c.x, c.y]);
        if (points.length < 3) return null;
        const hull = d3.polygonHull(points);
        return hull ? 'M' + hull.map(p => p.join(',')).join('L') + 'Z' : null;
      });
    });

  applyFilters();
}

// CORRECTION_SCRIPT
init();
</script>
</body>
</html>"""
