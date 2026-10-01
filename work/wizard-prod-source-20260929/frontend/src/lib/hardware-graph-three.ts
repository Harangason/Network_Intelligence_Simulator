import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { kindColors, graphLinkEndpoints, graphNodeRadius, hasCommunicationFlow, communicationColor, type GraphNode, type GraphLink } from './hardware-graph.ts';
import { busProfile } from './topology.ts';

export type ThreeGraphData = { nodes: GraphNode[]; links: GraphLink[]; selected: string; labels: boolean; focusIds: Set<string>; lighting: boolean; animate: boolean };
export type ThreeGraphHandle = ReturnType<typeof createThreeGraph>;

/** The renderer owns only disposable view resources; project objects are never modified. */
export function createThreeGraph(host: HTMLElement, callbacks: { select: (id: string) => void; link: (id: string) => void; error: () => void; rotation: (active: boolean) => void }) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  const canvas = renderer.domElement;
  canvas.tabIndex = 0;
  canvas.setAttribute('aria-label', '3D Hardware-Topologie. Ziehen dreht, Umschalt und Ziehen verschiebt, Mausrad zoomt.');
  canvas.setAttribute('role', 'application');
  host.appendChild(canvas);
  const labelLayer = document.createElement('div'); labelLayer.className = 'hardware-three-labels'; host.appendChild(labelLayer);
  const scene = new THREE.Scene();
  const lights = new THREE.Group();
  const key = new THREE.DirectionalLight('#fff4df', 2.4); key.position.set(600, 1200, 1800);
  const fill = new THREE.DirectionalLight('#83bcff', 1.2); fill.position.set(-1600, 200, -800);
  lights.add(new THREE.HemisphereLight('#c7e5ff', '#1c283d', 1.5), key, fill); scene.add(lights);
  const camera = new THREE.PerspectiveCamera(45, 1, 1, 20000);
  camera.position.set(1600, 1100, 1900);
  const controls = new OrbitControls(camera, canvas);
  controls.minDistance = 60; controls.maxDistance = 14000; controls.autoRotateSpeed = .65;
  controls.listenToKeyEvents(canvas);
  const raycaster = new THREE.Raycaster();
  let group = new THREE.Group(); scene.add(group);
  let instances: THREE.InstancedMesh | undefined;
  let data: ThreeGraphData = { nodes: [], links: [], selected: '', labels: true, focusIds: new Set(), lighting: false, animate: true };
  let flows: { source: THREE.Vector3; target: THREE.Vector3; phase: number }[] = [];
  let flowGeometry: THREE.BufferGeometry | undefined;
  let flowTime = 0;
  let frame = 0, disposed = false, visible = true, autoRotate = false, lastTime = 0;
  let width = Math.max(1, host.clientWidth), height = Math.max(1, host.clientHeight), first = true;
  camera.aspect = width / height; camera.updateProjectionMatrix(); renderer.setSize(width, height);
  const labelButtons = new Map<string, HTMLButtonElement>();
  const world = new THREE.Vector3(), projected = new THREE.Vector3();
  const releaseGroup = () => {
    group.traverse(object => {
      const drawable = object as THREE.Mesh;
      if ((object as THREE.InstancedMesh).isInstancedMesh) (object as THREE.InstancedMesh).dispose();
      drawable.geometry?.dispose();
      if (Array.isArray(drawable.material)) drawable.material.forEach(m => m.dispose()); else drawable.material?.dispose();
    });
    scene.remove(group); group = new THREE.Group(); scene.add(group);
  };
  function render(time: number) {
    frame = 0;
    if (disposed || !visible || document.hidden) return;
    controls.autoRotate = autoRotate;
    const delta = lastTime ? Math.min((time - lastTime) / 1000, .1) : 0;
    controls.update(delta); lastTime = time;
    if (data.animate && flowGeometry) {
      flowTime += delta;
      const positions = flowGeometry.getAttribute('position');
      flows.forEach((flow, i) => {
        world.lerpVectors(flow.source, flow.target, (flowTime / 3.2 + flow.phase) % 1);
        positions.setXYZ(i, world.x, world.y, world.z);
      });
      positions.needsUpdate = true;
    }
    renderer.render(scene, camera);
    // Labels remain screen-sized. Cull off-screen/overlapping labels before touching the DOM.
    const candidates = data.labels ? data.nodes.map(node => {
      world.fromArray(node.space); projected.copy(world).project(camera);
      return { node, x: (projected.x + 1) * width / 2, y: (1 - projected.y) * height / 2, z: projected.z, distance: camera.position.distanceToSquared(world) };
    }).filter(p => p.z > -1 && p.z < 1 && p.x > 0 && p.x < width - 35 && p.y > 18 && p.y < height - 18)
      .sort((a, b) => Number(b.node.id === data.selected) - Number(a.node.id === data.selected) || Number(data.focusIds.has(b.node.id)) - Number(data.focusIds.has(a.node.id)) || a.distance - b.distance) : [];
    const used: { x: number; y: number }[] = [], shown = new Set<string>();
    for (const p of candidates) {
      if (used.length >= 65 || used.some(q => Math.abs(q.x - p.x) < 145 && Math.abs(q.y - p.y) < 26)) continue;
      used.push(p); shown.add(p.node.id);
      let label = labelButtons.get(p.node.id);
      if (!label) {
        label = document.createElement('button'); label.type = 'button'; label.textContent = p.node.name; label.title = p.node.name;
        label.dataset.graphNodeId = p.node.id;
        label.addEventListener('click', () => callbacks.select(p.node.id));
        labelLayer.appendChild(label); labelButtons.set(p.node.id, label);
      }
      label.hidden = false; label.style.transform = `translate(${p.x + 10}px, ${p.y - 10}px)`;
      label.className = p.node.id === data.selected ? 'selected' : '';
      if (p.node.children.length) label.setAttribute('aria-expanded', String(data.nodes.some(n => p.node.children.includes(n.id))));
      label.style.borderColor = kindColors[p.node.kind];
    }
    for (const [id, label] of labelButtons) label.hidden = !shown.has(id);
    if (autoRotate || data.animate && flows.length) schedule();
  }
  function schedule() { if (!frame && !disposed && visible && !document.hidden) frame = requestAnimationFrame(render); }
  function fit() {
    const box = new THREE.Box3(); data.nodes.forEach(n => box.expandByPoint(new THREE.Vector3(...n.space)));
    if (box.isEmpty()) box.setFromCenterAndSize(new THREE.Vector3(), new THREE.Vector3(100, 100, 100));
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const halfFov = Math.min(camera.fov * Math.PI / 360, Math.atan(Math.tan(camera.fov * Math.PI / 360) * camera.aspect));
    const distance = Math.max(200, (sphere.radius + 65) / Math.sin(halfFov));
    const direction = camera.position.clone().sub(controls.target).normalize();
    controls.target.copy(sphere.center); camera.position.copy(direction.multiplyScalar(distance).add(sphere.center));
    controls.update(); schedule();
  }
  function zoom(factor: number) {
    const direction = camera.position.clone().sub(controls.target);
    direction.setLength(Math.min(controls.maxDistance, Math.max(controls.minDistance, direction.length() / factor)));
    camera.position.copy(controls.target).add(direction); controls.update(); schedule();
  }
  function focus(id: string) {
    const node = data.nodes.find(n => n.id === id); if (!node) return;
    const offset = camera.position.clone().sub(controls.target).normalize().multiplyScalar(650);
    controls.target.fromArray(node.space); camera.position.copy(controls.target).add(offset); controls.update(); schedule();
  }
  function update(next: ThreeGraphData) {
    data = next; releaseGroup(); flows = []; flowGeometry = undefined;
    lights.visible = data.lighting;
    for (const button of labelButtons.values()) button.remove(); labelButtons.clear();
    const matrix = new THREE.Matrix4(), quaternion = new THREE.Quaternion(), scale = new THREE.Vector3();
    instances = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 20, 14), data.lighting
      ? new THREE.MeshStandardMaterial({ roughness: .35, metalness: .12 }) : new THREE.MeshBasicMaterial(), data.nodes.length);
    data.nodes.forEach((node, index) => {
      const radius = graphNodeRadius(node, true);
      matrix.compose(new THREE.Vector3(...node.space), quaternion, scale.setScalar(radius * (node.id === data.selected ? 1.6 : 1)));
      instances!.setMatrixAt(index, matrix);
      const color = new THREE.Color(node.id === data.selected ? '#ffffff' : kindColors[node.kind]);
      if (data.selected && !data.focusIds.has(node.id) && node.id !== data.selected) color.multiplyScalar(.35);
      instances!.setColorAt(index, color);
    });
    group.add(instances);
    const byId = new Map(data.nodes.map(n => [n.id, n]));
    const positions: number[] = [], colors: number[] = [], flowColors: number[] = [];
    for (const link of data.links) {
      const source = byId.get(link.source), target = byId.get(link.target); if (!source || !target) continue;
      const ends = graphLinkEndpoints(source, target, true, data.selected);
      positions.push(...ends.source, ...ends.target);
      const color = new THREE.Color(link.kind === 'communication' ? communicationColor(link) : link.bus ? busProfile(link.bus).color : link.kind === 'mapping' ? '#bc9bff' : '#496373');
      if (data.selected && link.source !== data.selected && link.target !== data.selected) color.multiplyScalar(.5);
      colors.push(color.r, color.g, color.b, color.r, color.g, color.b);
      if (data.animate && hasCommunicationFlow(link)) {
        for (let i = 0; i < 3; i++) {
          flows.push({ source: new THREE.Vector3(...ends.source), target: new THREE.Vector3(...ends.target), phase: i / 3 });
          flowColors.push(color.r, color.g, color.b);
        }
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3)); geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    group.add(new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: .7 })));
    if (flows.length) {
      flowGeometry = new THREE.BufferGeometry();
      flowGeometry.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(flows.length * 3), 3).setUsage(THREE.DynamicDrawUsage));
      flowGeometry.setAttribute('color', new THREE.Float32BufferAttribute(flowColors, 3));
      const particles = new THREE.Points(flowGeometry, new THREE.PointsMaterial({ vertexColors: true, size: 4, sizeAttenuation: false, transparent: true, opacity: .95, depthWrite: false }));
      particles.frustumCulled = false; group.add(particles);
    }
    canvas.dataset.nodeCount = String(data.nodes.length); canvas.dataset.linkCount = String(data.links.length);
    canvas.dataset.communicationCount = String(data.links.filter(l => l.kind === 'communication').length);
    canvas.dataset.flowCount = String(flows.length); canvas.dataset.lighting = String(data.lighting);
    if (first && data.nodes.length) { first = false; fit(); } else schedule();
  }
  function selectAt(event: PointerEvent) {
    const box = canvas.getBoundingClientRect();
    const point = new THREE.Vector2((event.clientX - box.left) / box.width * 2 - 1, -(event.clientY - box.top) / box.height * 2 + 1);
    raycaster.setFromCamera(point, camera);
    const hit = instances && raycaster.intersectObject(instances)[0];
    if (hit?.instanceId !== undefined) { callbacks.select(data.nodes[hit.instanceId].id); return; }
    // Screen-space edge hit testing has a constant click tolerance at every zoom.
    const mouse = { x: event.clientX - box.left, y: event.clientY - box.top };
    const project = (n: GraphNode) => { const p = new THREE.Vector3(...n.space).project(camera); return { x: (p.x + 1) * width / 2, y: (1 - p.y) * height / 2, z: p.z }; };
    const byId = new Map(data.nodes.map(n => [n.id, n]));
    let closest: GraphLink | undefined, distance = 6;
    for (const link of data.links) {
      if (link.kind === 'hierarchy') continue;
      const a = project(byId.get(link.source)!), b = project(byId.get(link.target)!);
      if (Math.abs(a.z) >= 1 || Math.abs(b.z) >= 1) continue;
      const dx = b.x - a.x, dy = b.y - a.y, size = dx * dx + dy * dy;
      const t = size ? Math.max(0, Math.min(1, ((mouse.x - a.x) * dx + (mouse.y - a.y) * dy) / size)) : 0;
      const d = Math.hypot(mouse.x - a.x - t * dx, mouse.y - a.y - t * dy);
      if (d < distance) { closest = link; distance = d; }
    }
    if (closest) callbacks.link(closest.id);
  }
  let down: { x: number; y: number; id: number; moved: boolean } | undefined;
  const pointerDown = (event: PointerEvent) => { if (event.button === 0) down = { x: event.clientX, y: event.clientY, id: event.pointerId, moved: false }; };
  const pointerMove = (event: PointerEvent) => { if (down && Math.hypot(event.clientX - down.x, event.clientY - down.y) > 5) down.moved = true; };
  const pointerUp = (event: PointerEvent) => { if (down?.id === event.pointerId && !down.moved) selectAt(event); down = undefined; };
  const pointerCancel = () => { down = undefined; };
  const rotate = (value: boolean) => { autoRotate = value; callbacks.rotation(value); schedule(); };
  const keydown = (event: KeyboardEvent) => {
    if (event.key.toLowerCase() === 'r') { event.preventDefault(); fit(); }
    if (event.code === 'Space') { event.preventDefault(); rotate(!autoRotate); }
    if (event.key === '+' || event.key === '=') { event.preventDefault(); zoom(1.2); }
    if (event.key === '-') { event.preventDefault(); zoom(1 / 1.2); }
  };
  const contextLost = (event: Event) => { event.preventDefault(); autoRotate = false; cancelAnimationFrame(frame); frame = 0; visible = false; callbacks.error(); };
  canvas.addEventListener('pointerdown', pointerDown); canvas.addEventListener('pointermove', pointerMove); canvas.addEventListener('pointerup', pointerUp); canvas.addEventListener('pointercancel', pointerCancel);
  canvas.addEventListener('keydown', keydown); canvas.addEventListener('webglcontextlost', contextLost);
  controls.addEventListener('change', schedule);
  const resize = new ResizeObserver(() => { width = Math.max(1, host.clientWidth); height = Math.max(1, host.clientHeight); camera.aspect = width / height; camera.updateProjectionMatrix(); renderer.setSize(width, height); schedule(); }); resize.observe(host);
  const intersection = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? true; lastTime = 0; schedule(); }); intersection.observe(host);
  const visibility = () => { lastTime = 0; schedule(); }; document.addEventListener('visibilitychange', visibility);
  return { update, fit, focus, zoom, rotate, dispose() {
    disposed = true; cancelAnimationFrame(frame); resize.disconnect(); intersection.disconnect(); document.removeEventListener('visibilitychange', visibility);
    controls.removeEventListener('change', schedule); controls.dispose();
    canvas.removeEventListener('pointerdown', pointerDown); canvas.removeEventListener('pointermove', pointerMove); canvas.removeEventListener('pointerup', pointerUp); canvas.removeEventListener('pointercancel', pointerCancel);
    canvas.removeEventListener('keydown', keydown); canvas.removeEventListener('webglcontextlost', contextLost);
    releaseGroup(); renderer.dispose(); renderer.forceContextLoss(); canvas.remove(); labelLayer.remove();
  } };
}
