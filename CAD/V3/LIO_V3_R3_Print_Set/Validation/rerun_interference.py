from pathlib import Path
import subprocess, concurrent.futures, time, json, re
import trimesh
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'Validation/interference'; OUT.mkdir(exist_ok=True)
tests=[]
def add(name,a,b,extra=''):
 tests.append((name,a,b,extra))
A='at(0,0,locator_bottom_z) base_adapter();'
C='at(0,0,chamber_z) chamber();'
D='at(0,0,chamber_z) door();'
N='at(0,0,chamber_z) sample_nest();'
B='retained_v2_base();'
ax='for(s=[-1,1]) translate([s*screw_x,0,axial_bridge_bottom_z]) scale([s,1,1]) axial_bridge();'
add('01_adapter_base',A,B)
add('02_chamber_base',C,B)
add('03_chamber_axial_supports',C,ax)
add('04_chamber_nest',C,N)
for shift in [0,0.5,2,8,25,60]:
 add(f'door_clearance_{shift:g}',f'at(0,-{shift},chamber_z) door();',C)
add('door_envelope',D,'difference(){at(0,0,chamber_z-1) cylinder(d=160,h=chamber_h+2); at(0,0,chamber_z-2) cylinder(d=chamber_od,h=chamber_h+4);}')
for zz in ['min_deck_h','mid_h','max_measure_h','loading_h']:
 add('shroud_base_'+zz, f'at(0,0,{zz}) shroud();', B)
 add('shroud_chamber_'+zz, f'at(0,0,{zz}) shroud();', C)
 add('shroud_support_'+zz, f'at(0,0,{zz}) shroud();', ax)
for shift in [0,10,40,75]:
 add(f'door_vs_loading_tube_{shift}',f'at(0,-{shift},chamber_z) door();','at(0,0,loading_h) shroud();')
# The cup is lifted by 5 mm before straight removal, above the 4 mm nest rim.
for shift in [0,10,25,45,75,110]:
 add(f'cup_lifted_path_{shift}', f'at(0,-{shift},chamber_z+sample_seat_h+5) cylinder(d=cup_od,h=cup_h);', 'union(){'+C+N+'}')
add('keeper_deck','optical_deck();','at(0,0,deck_t) led_retainer();')
add('keeper_detector','at(0,0,deck_t) led_retainer();','installed_detector();')
add('keeper_cover','at(0,0,deck_t) led_retainer();','at(0,0,deck_t+head_cover_h) rotate([180,0,0]) head_cover();')
add('detector_deck','installed_detector();','optical_deck();')
add('deck_shroud','optical_deck();','shroud();')
# Nominal full LED profile, not just a marker cylinder.
for i in [0,1,4,8,12,15]:
 add(f'led_{i+1:02d}_deck',f'led_package_ref({i});','optical_deck();')
 add(f'led_{i+1:02d}_retainer',f'led_package_ref({i});','at(0,0,deck_t) led_retainer();')
add('carriage_tube','at(0,0,-shroud_flange_t-carriage_t) carriage();','shroud();')
add('carrier_tube','for(s=[-1,1]) at(s*screw_x,0,-shroud_flange_t-carriage_t-carrier_t) nut_carrier();','shroud();')
add('nut_fit','nut_carrier();','at(0,0,-lead_nut_flange_t) metal_nut_ref();')
add('guide_bearing_fit','guide_housing(0);','at(0,0,guide_flange_t-bearing_length) ring(bearing_od,rod_d,bearing_length);')
add('guide_rod_fit','guide_housing(0);','at(0,0,-bearing_length-2) cylinder(d=rod_d,h=bearing_length+guide_flange_t+4);')
add('guide_carriage','for(i=[0:3]) let(p=rod_pts[i]) at(p[0],p[1],0) guide_housing(i==0?0:i==1?1:2);','at(0,0,-carriage_t) carriage();')
add('axial_bearing_fit','axial_bridge();','at(0,0,axial_bridge_t-axial_bearing_h) ring(axial_bearing_od,axial_bearing_id,axial_bearing_h);')
add('axial_collar_fit','union(){axial_bridge();at(0,0,axial_bridge_t) axial_cap();}', 'at(0,0,axial_bridge_t) ring(shaft_collar_od,screw_d,shaft_collar_h);')
# Door screws at the documented example length, including their heads.
pin='''for(a=panel_angles,z=panel_screw_z) radial(a,panel_or-panel_head_depth-panel_screw_length,z){ cylinder(d=3,h=panel_screw_length); at(0,0,panel_screw_length) cylinder(d=5.7,h=1.8); }'''
add('door_metal_screw_fit','door();',pin)
add('door_screw_blind_end','chamber();',pin)

def run(t):
 name,a,b,extra=t; f=OUT/(name+'.scad'); out=OUT/(name+'.stl')
 f.write_text('part_override="none";\ninclude <../../LIO_V3_R3_master.scad>\n'+extra+'\nintersection(){\n'+a+'\n'+b+'\n}\n')
 start=time.monotonic()
 try:
  r=subprocess.run(['openscad','--export-format','binstl','-o',str(out),str(f)],capture_output=True,text=True,timeout=180)
  text=r.stdout+r.stderr; (OUT/(name+'.log')).write_text(text)
  vol=0.; wat=None; count=0
  if out.exists() and out.stat().st_size>84:
   m=trimesh.load_mesh(out); vol=abs(float(m.volume)); wat=bool(m.is_watertight); count=len(m.faces)
  empty='Current top level object is empty' in text
  contact='Current top level object is not a 3D object' in text
  err=[line for line in text.splitlines() if 'ERROR' in line or 'WARNING' in line]
  passed=not err and (empty or contact or (r.returncode==0 and vol<0.001))
  result=dict(test=name,pass_no_positive_volume=passed,intersection_mm3=round(vol,7),empty=empty,contact_only=contact,watertight=wat,faces=count,return_code=r.returncode,diagnostics=err,seconds=round(time.monotonic()-start,2))
 except subprocess.TimeoutExpired:
  result=dict(test=name,pass_no_positive_volume=False,timeout=True)
 print(name,result,flush=True)
 return result
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex: results=list(ex.map(run,tests))
(ROOT/'Validation/nominal_interference_checks.json').write_text(json.dumps(results,indent=2))
print('PASS',sum(x['pass_no_positive_volume'] for x in results),'/',len(results),flush=True)
