from pathlib import Path
import subprocess, concurrent.futures, json, time, re
import trimesh
root=Path(__file__).resolve().parents[1]; logs=root/'Validation/render_logs'; logs.mkdir(exist_ok=True)
parts=['base_adapter','sample_nest','guide_primary','guide_secondary','guide_float','guide_cap','nut_carrier','axial_bridge','axial_cap','axial_spacer','chamber','door','carriage','shroud','optical_deck','led_retainer','detector_mount','head_cover','guide_tie','datum_template','cylinder_coupon','closure_coupon','hardware_coupon','led_coupon']
expected={'cylinder_coupon':2,'closure_coupon':2,'hardware_coupon':4,'led_coupon':2}
tasks=[]
for name in parts:
 tasks.append((name,root/'LIO_V3_R3_master.scad',root/'Individual_STL'/f'{name}.stl',['-D',f'part="{name}"'],expected.get(name,1)))
for f,count in zip(sorted(root.glob('0[1-8]_*.scad')),[2,18,2,1,1,3,1,1]):
 tasks.append((f.stem,f,root/'STL'/f'{f.stem}.stl',[],count))
def run(t):
 name,src,out,defs,n=t; start=time.monotonic()
 r=subprocess.run(['openscad','--export-format','binstl','-o',str(out),*defs,str(src)],capture_output=True,text=True,timeout=300)
 text=r.stdout+r.stderr; (logs/(name+'.log')).write_text(text)
 report={'name':name,'return_code':r.returncode,'seconds':round(time.monotonic()-start,2),'expected_bodies':n,'warnings':[x for x in text.splitlines() if re.search('WARNING|ERROR',x)]}
 if out.exists() and out.stat().st_size>100:
  m=trimesh.load_mesh(out,process=True); comps=m.split(only_watertight=False)
  report.update(watertight=bool(m.is_watertight),positive_volume=bool(m.volume>0),bodies=len(comps),all_bodies_watertight=all(c.is_watertight for c in comps),bounds=m.bounds.round(4).tolist(),volume_mm3=round(float(m.volume),3),faces=len(m.faces))
  if name[:2].isdigit(): report['bed_fit_centered_220']=bool((m.bounds[0,:2]>=-105).all() and (m.bounds[1,:2]<=105).all() and m.bounds[0,2]>-0.01 and m.bounds[1,2]<=245)
 report['pass']=r.returncode==0 and not report['warnings'] and report.get('watertight',False) and report.get('bodies')==n and report.get('positive_volume',False)
 print(name, report['pass'],report.get('bodies'),report.get('bounds'),flush=True)
 return report
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex: result=list(ex.map(run,tasks))
(root/'Validation/mesh_and_bed_checks.json').write_text(json.dumps(result,indent=2))
print('PASS',sum(r['pass'] for r in result),'OF',len(result),flush=True)
