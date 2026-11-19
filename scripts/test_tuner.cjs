const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function element(dataset = {}) {
  const classes = new Set();
  return {dataset, textContent: '', style: {setProperty() {}}, addEventListener() {}, setAttribute() {}, classList: {
    add: (...names) => names.forEach(name => classes.add(name)),
    remove: (...names) => names.forEach(name => classes.delete(name)),
    toggle: (name, active) => active ? classes.add(name) : classes.delete(name),
    contains: name => classes.has(name),
  }};
}
const elements = new Map();
const segments = Array.from({length:25}, (_, index) => element({pos:index - 12}));
const refs = [432,440].map(pitch => element({referencePitch:String(pitch)}));
const context = {console, performance, navigator:{}, window:{localStorage:{getItem(){return null;},setItem(){}}}, document:{
  documentElement:{lang:'en'},
  getElementById(id){if(!elements.has(id)) elements.set(id,element()); return elements.get(id);},
  querySelector(){return element();},
  querySelectorAll(selector){return selector === '#tuneLedStrip span' ? segments : selector === '.reference-pitch-button' ? refs : [];},
}};
let source = fs.readFileSync('tuner/static/tuner/js/tuner.js','utf8');
source = source.replace(/\}\)\(\);\s*$/, 'globalThis.probe = {updateTuneLedStrip,setHint,smoothCents,applyReferencePitch,autoCorrelate,calculateRms,strings:STRINGS,reset(){centsHistory=[];displayedCents=0;}};})();');
vm.runInNewContext(source,context);
const probe = context.probe;
for(const cents of [-40,-9,-4,0,4,9,40]) {
  probe.updateTuneLedStrip(cents);
  probe.setHint(cents);
  const active = ['on-lock','on-near','on-flat','on-sharp'].filter(name => segments.some(segment => segment.classList.contains(name)));
  assert.equal(active.length,1,`Contradicting indications at ${cents}`);
  assert.equal(active[0],Math.abs(cents)<=4?'on-lock':Math.abs(cents)<=9?'on-near':cents<0?'on-flat':'on-sharp');
}
probe.applyReferencePitch(440);
assert.equal(probe.strings[1].frequency,110);
probe.applyReferencePitch(432);
assert.equal(probe.strings[1].frequency,108);
probe.reset();
for(let index=0;index<20;index++) probe.smoothCents(0);
assert.equal(probe.smoothCents(49),0,'Median rejects a single outlier');
for(let index=0;index<30;index++) probe.smoothCents(30);
assert.ok(Math.abs(probe.smoothCents(30)-30)<1,'Smoothing converges');
const samples=Float32Array.from({length:2048},(_,index)=>0.2*Math.sin(2*Math.PI*110*index/48000));
assert.ok(Math.abs(probe.autoCorrelate(samples,48000,probe.calculateRms(samples))-110)<1);
assert.equal(probe.autoCorrelate(new Float32Array(2048),48000,0),null);
console.log('PASS: exclusive hints/LED states, 432/440 reference, smoothing, synthetic 110Hz and silence');
