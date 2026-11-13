// Standalone structure/data check: no Redmine, plugin or Three.js imports.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';

const base = process.argv[2] ? pathToFileURL(resolve(process.argv[2]) + '/') : new URL('../../../examples/Altaz_C/', import.meta.url);
const binary = await readFile(new URL('Altaz_C.glb', base));
assert.equal(binary.toString('ascii', 0, 4), 'glTF');
assert.equal(binary.readUInt32LE(4), 2);
assert.equal(binary.readUInt32LE(8), binary.length);
assert.equal(binary.readUInt32LE(16), 0x4e4f534a);
const doc = JSON.parse(binary.toString('utf8', 20, 20 + binary.readUInt32LE(12)));
const controls = {};
for (const node of doc.nodes) {
  for (const [key, value] of Object.entries(node.extras?.cosmosys_controls || {})) {
    assert(!Object.hasOwn(controls, key), `Duplicate control: ${key}`);
    controls[key] = value;
  }
}
const yaml = JSON.parse(execFileSync('ruby', ['-ryaml', '-rjson', '-e',
  'puts JSON.generate(YAML.safe_load(File.read(ARGV.fetch(0))).fetch("models").fetch("Altaz_C.glb").fetch("controls"))',
  fileURLToPath(new URL('Altaz_C.yaml', base))], {encoding: 'utf8'}));
assert.deepEqual(controls, yaml, 'GLB extras and YAML differ');
assert.equal(Object.keys(controls).length, 4);
assert.equal(doc.scenes.length, 1);
assert.equal(new Set(doc.nodes.map(node => node.name)).size, doc.nodes.length);
assert(!doc.animations?.length && !doc.cameras?.length);
assert.equal(doc.nodes.find(node => node.name === 'Observatory_Root').extras.cosmosys_model.version, 1);
for (const [key, control] of Object.entries(controls)) {
  assert(doc.nodes.some(node => node.name === control.target_node), `Missing target: ${key}`);
  assert(['rotation', 'position'].includes(control.transform));
  assert.equal(control.space, 'local');
  assert(['x', 'y', 'z'].includes(control.axis));
  assert([control.min, control.max, control.step].every(Number.isFinite));
  assert(control.min <= 0 && control.max >= 0 && control.min < control.max && control.step > 0);
}
assert.equal(controls.azimuth.min, -300);
assert.equal(controls.azimuth.max, 300);
assert.equal(controls.elevation.min, 0);
assert.equal(controls.elevation.max, 90);
assert.equal(controls.shutter_open.transform, 'position');
assert.equal(controls.shutter_open.axis, 'x');
assert.equal(controls.shutter_open.max, 3.6);
console.log(`PASS: ${doc.nodes.length} GLB nodes; 4 matching GLB/YAML controls; valid targets, limits and scene structure`);
