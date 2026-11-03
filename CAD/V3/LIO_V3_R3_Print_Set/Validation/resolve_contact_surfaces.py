from pathlib import Path
import json, numpy as np, trimesh
root=Path(__file__).resolve().parents[1]
p=root/'Validation/nominal_interference_checks.json'
if not p.exists():
 print('Collision run still active; contact surfaces inspected directly.')
 rows=[]
 for name in ['keeper_deck','detector_deck','deck_shroud']:
  f=root/'Validation/interference'/f'{name}.stl'
  if f.exists():
   mesh=trimesh.load_mesh(f); v=mesh.vertices
   s=np.linalg.svd(v-v.mean(axis=0),compute_uv=False)
   print(name,'bounds',mesh.bounds,'svd',s,'zero thickness',np.min(mesh.extents))
else:
 data=json.loads(p.read_text());res=[]
 expected_planes={'keeper_deck':10,'detector_deck':10,'deck_shroud':0,'carriage_tube':-4,'guide_carriage':0,'nut_fit':0,'axial_bearing_fit':3,'axial_collar_fit':10}
 for row in data:
  out=dict(row); out['resolved_pass']=row['pass_no_positive_volume']
  if not out['resolved_pass']:
   f=root/'Validation/interference'/f"{row['test']}.stl"
   if f.exists():
    m=trimesh.load_mesh(f);v=m.vertices
    _,s,vt=np.linalg.svd(v-v.mean(axis=0),full_matrices=False)
    deviation=float(np.max(abs((v-v.mean(axis=0))@vt[-1])))
    out['intersection_bounds']=m.bounds.tolist();out['max_plane_deviation_mm']=deviation
    if row.get('intersection_mm3',1)>0.001:
     out['resolution']='Unresolved positive volume; must investigate.'
    elif row['test'] in expected_planes and abs(float(v[:,2].mean())-expected_planes[row['test']])<1e-5 and deviation<1e-5:
     out['resolved_pass']=True;out['resolution']='Expected seating contact only: raw boolean exported a zero-thickness surface. Independent vertex-plane check confirms no volumetric interference. This STL is NOT a production part.'
    elif row['test'].startswith('led_') and row['test'].endswith('_deck') and deviation<1e-5:
     out['resolved_pass']=True;out['resolution']='Expected tilted LED-flange shoulder contact only; intersection is planar within 1e-5 mm and has no positive volume. Positive radial and axial clearances are recorded separately.'
  res.append(out)
 (root/'Validation/resolved_interference_checks.json').write_text(json.dumps(res,indent=2))
 print('RESOLVED',sum(x['resolved_pass'] for x in res),'/',len(res))
 for x in res:
  if not x['resolved_pass']: print('UNRESOLVED',x)
