import html as H, math, re

W, HGT = 2440, 1900
E = []
def add(s): E.append(s)
C = dict(p5='#d62828', n5='#1d4ed8', gnd='#111111', A='#d97706', B='#7b2cbf',
         ctl='#1f8a4c', i2c='#0f7c8d', ana='#8b5a2b', grey='#6b7280', w='#222222', mot='#555555')
def esc(s): return H.escape(s)
def line(x1,y1,x2,y2,c=C['w'],w=1.6,dash=None):
    d=f' stroke-dasharray="{dash}"' if dash else ''
    add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" stroke-width="{w}" stroke-linecap="round"{d}/>')
def pl(pts,c=C['w'],w=1.6):
    add('<polyline points="'+' '.join(f'{x:.1f},{y:.1f}' for x,y in pts)+f'" fill="none" stroke="{c}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"/>')
def pgon(pts,fill,c=C['w'],w=1.6,dash=None):
    d=f' stroke-dasharray="{dash}"' if dash else ''
    add('<polygon points="'+' '.join(f'{x:.1f},{y:.1f}' for x,y in pts)+f'" fill="{fill}" stroke="{c}" stroke-width="{w}" stroke-linejoin="round"{d}/>')
def T(x,y,s,size=11,anchor='start',weight='normal',c='#111'):
    add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{c}">{esc(s)}</text>')
def dot(x,y,c=C['w']): add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="{c}"/>')
def box(x,y,w,h,fill='#fff',stroke=C['w'],sw=1.6,r=4):
    add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
def gnd(x,y,c=C['gnd']):
    line(x,y,x,y+8,c); line(x-9,y+8,x+9,y+8,c,2.2); line(x-6,y+12,x+6,y+12,c,1.9); line(x-3,y+16,x+3,y+16,c,1.6)
def tint(c,f=0.86):
    r,g,b=int(c[1:3],16),int(c[3:5],16),int(c[5:7],16)
    return '#%02x%02x%02x'%tuple(int(v+(255-v)*f) for v in (r,g,b))
def tag(x,y,s,c,d='right',size=11):
    w=6.9*len(s)+16
    if d=='right': pts=[(x,y),(x+8,y-9),(x+w,y-9),(x+w,y+9),(x+8,y+9)]; tx=x+8+(w-8)/2
    else: pts=[(x,y),(x-8,y-9),(x-w,y-9),(x-w,y+9),(x-8,y+9)]; tx=x-8-(w-8)/2
    pgon(pts,tint(c),c,1.4); T(tx,y+4,s,size,'middle','bold',c)
def res_h(x1,x2,y,label=None,dy=-10,c=C['w']):
    bw=min(30,(x2-x1)-8); cx=(x1+x2)/2
    line(x1,y,cx-bw/2,y,c); line(cx+bw/2,y,x2,y,c); box(cx-bw/2,y-6,bw,12,r=1)
    if label: T(cx,y+dy,label,10,'middle')
def res_v(x,y1,y2,label=None,side='left'):
    bh=min(30,(y2-y1)-8); cy=(y1+y2)/2
    line(x,y1,x,cy-bh/2); line(x,cy+bh/2,x,y2); box(x-6,cy-bh/2,12,bh,r=1)
    if label: T(x-10 if side=='left' else x+10, cy+4, label, 10, 'end' if side=='left' else 'start')
def cap_h(x1,x2,y,label=None):
    cx=(x1+x2)/2
    line(x1,y,cx-3.5,y); line(cx+3.5,y,x2,y)
    line(cx-3.5,y-9,cx-3.5,y+9,w=2.4); line(cx+3.5,y-9,cx+3.5,y+9,w=2.4)
    if label: T(cx,y-13,label,10,'middle')
def cap_v(x,y1,y2):
    cy=(y1+y2)/2
    line(x,y1,x,cy-3.5); line(x,cy+3.5,x,y2)
    line(x-9,cy-3.5,x+9,cy-3.5,w=2.4); line(x-9,cy+3.5,x+9,cy+3.5,w=2.4)
def arrow(x1,y1,x2,y2,c=C['w'],w=1.2,hs=5):
    line(x1,y1,x2,y2,c,w); a=math.atan2(y2-y1,x2-x1)
    pgon([(x2,y2),(x2-hs*math.cos(a-0.45),y2-hs*math.sin(a-0.45)),(x2-hs*math.cos(a+0.45),y2-hs*math.sin(a+0.45))],c,c,1)
def hline_hop(x1,x2,y,hops,c=C['w'],w=1.6):
    xs=sorted(hops); a,b=min(x1,x2),max(x1,x2); cur=a
    for h in xs:
        line(cur,y,h-6,y,c,w)
        add(f'<path d="M{h-6:.1f},{y:.1f} A6,6 0 0 1 {h+6:.1f},{y:.1f}" fill="none" stroke="{c}" stroke-width="{w}"/>')
        cur=h+6
    line(cur,y,b,y,c,w)
def led_v(x,y1,y2,fill='#fff',dash=None):
    ya=y1+9; yb=y2-9
    line(x,y1,x,ya); line(x,yb,x,y2)
    pgon([(x-9,ya),(x+9,ya),(x,yb)],fill,dash=dash); line(x-10,yb,x+10,yb,w=2.2)
    arrow(x+11,ya+6,x+21,ya-2); arrow(x+11,ya+15,x+21,ya+7)
def pd_v(x,y1,y2):
    yk=y1+10; ya=y2-10
    line(x,y1,x,yk); line(x,ya,x,y2)
    pgon([(x-9,ya),(x+9,ya),(x,yk)],'#fff'); line(x-10,yk,x+10,yk,w=2.2)
    arrow(x-30,yk-6,x-14,yk+4); arrow(x-30,yk+6,x-14,yk+16)
def nmos(x,yd,ys,xg):
    ym=(yd+ys)/2; xc=x-12; xp=x-18
    line(x,yd,x,yd+12); line(x,yd+12,xc,yd+12)
    line(x,ys,x,ys-12); line(x,ys-12,xc,ys-12)
    line(xc,ym,x,ym); line(x,ym,x,ys-12)
    pgon([(xc+1,ym),(xc+8,ym-4),(xc+8,ym+4)],C['w'])
    for a,b in ((yd+6,yd+18),(ym-6,ym+6),(ys-18,ys-6)): line(xc,a,xc,b,w=2.6)
    line(xp,yd+8,xp,ys-8,w=2.2); line(xg,ym,xp,ym)
def opamp(x,yt,yb):  # left edge x, top yt, bottom yb; returns (inv,noninv,out)
    h=yb-yt; tip=(x+h*0.9,(yt+yb)/2)
    pgon([(x,yt),(x,yb),tip],'#fff')
    inv=(x,yt+h*0.25); non=(x,yt+h*0.75)
    T(x+8,inv[1]+5,'−',13,'middle','bold'); T(x+8,non[1]+5,'+',13,'middle','bold')
    return inv,non,tip
def region(x,y,w,h,title):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#f6f7fa" stroke="#c9ced8" stroke-width="1.2"/>')
    T(x+12,y+22,title,14,'start','bold','#2b3445')

# ======================= REGIONS (drawn first) =======================
region(20,190,325,575,'Controller')
region(20,775,325,275,'Stepper motors (existing)')
region(470,200,1475,530,'LED bank 1 — U1 drives CH1–CH8 (all on RAIL A)')
region(470,790,1475,550,'LED bank 2 — U2 drives CH9–CH16 (CH9 on RAIL A, CH10–16 on RAIL B)')
region(2000,310,430,820,'')
T(2250,336,'LED drivers',14,'start','bold','#2b3445')
region(2080,45,350,250,'Power')
region(470,1390,1490,330,'Detectors + ADC')
region(20,1060,365,205,'Decoupling capacitors (100 nF)')
region(20,1275,365,612,'Build notes')
region(470,1735,1960,145,'Legend')

T(20,36,'LIO V3 Optical Head — Full Electronics Schematic',22,'start','bold')
T(20,60,'Arduino Nano · 2× 74HC595 · 16× 2N7000 · 2× LD06AJSA · 2× ULN2003 + 28BYJ-48 · OPT101 · InGaAs MTPD1346D + TL072 · ADS1115 · ±5 V from two power banks',12,'start',c=C['grey'])

# ======================= POWER =======================
box(2280,75,130,70,'#fff'); T(2345,105,'Power bank A',12,'middle','bold'); T(2345,122,'USB 5 V',10,'middle',c=C['grey'])
box(2280,185,130,70,'#fff'); T(2345,215,'Power bank B',12,'middle','bold'); T(2345,232,'USB 5 V',10,'middle',c=C['grey'])
T(2290,99,'+',12,'start','bold',C['p5']); T(2290,135,'−',13,'start','bold')
T(2290,209,'+',12,'start','bold',C['p5']); T(2290,245,'−',13,'start','bold',C['n5'])
line(2280,95,2200,95); tag(2200,95,'+5V',C['p5'],'left')
pl([(2280,130),(2240,130),(2240,205),(2280,205)]); dot(2240,168); line(2240,168,2200,168); gnd(2200,168)
T(2190,165,'GND (0 V)',10.5,'end','bold')
line(2280,240,2200,240); tag(2200,240,'−5V',C['n5'],'left')
T(2092,282,'A(−) tied to B(+) = common ground',10,c=C['grey'])

# ======================= NANO =======================
NX,NY,NW,NH=160,220,160,500
box(NX,NY,NW,NH,'#eaf2ff')
T(NX+80,NY+24,'Arduino Nano',13,'middle','bold'); T(NX+80,NY+40,'USB → laptop',10,'middle'); T(NX+80,NY+53,'(power + serial)',9.5,'middle',c=C['grey'])
rp={'A3':260,'D10':290,'A0':480,'A1':508,'A2':536,'A4':600,'A5':630,'5V':660,'GND':690}
for nm,y in rp.items():
    line(NX+NW,y,NX+NW+20,y); T(NX+NW-6,y+4,nm,11,'end','bold')
lp={'D2':380,'D3':410,'D4':440,'D5':470}
for nm,y in lp.items():
    line(NX,y,NX-20,y); T(NX+6,y+4,nm,11,'start','bold')
bp={'D6':200,'D7':230,'D8':260,'D9':290}
for nm,x in bp.items():
    line(x,NY+NH,x,NY+NH+20); T(x,NY+NH-8,nm,10,'middle','bold')
T(NX+80,NY+120,'D2–D5 → motor 1',9.5,'middle',c=C['grey']); T(NX+80,NY+134,'D6–D9 → motor 2',9.5,'middle',c=C['grey'])
# 5V NC, GND
x=NX+NW+20
line(x-4,656,x+4,664,'#b91c1c',1.8); line(x-4,664,x+4,656,'#b91c1c',1.8)
T(NX+NW-50,676,'NC on USB',8.5,'middle',c='#b91c1c')
gnd(x,690)

# ---- CE lanes to drivers ----
CE1L,CE2L=360,375
pl([(340,260),(CE1L,260),(CE1L,150),(2030,150),(2030,360),(2050,360)],C['ctl'],1.8)
pl([(340,290),(CE2L,290),(CE2L,165),(2015,165)],C['ctl'],1.8)
T(600,145,'CE1  (Nano A3 → DRV1 CE)',10.5,'start','bold',C['ctl'])
T(900,180,'CE2  (Nano D10 → DRV2 CE)',10.5,'start','bold',C['ctl'])

# ---- DATA / CLOCK / LATCH ----
line(340,480,590,480,C['ctl'],1.8); T(460,474,'DATA',10,'start','bold',C['ctl'])
line(340,508,590,508,C['ctl'],1.8); T(470,502,'CLOCK',10,'start','bold',C['ctl'])
hline_hop(340,590,536,[455],C['ctl'],1.8); T(470,530,'LATCH',10,'start','bold',C['ctl'])
LTAP,CTAP=440,455
dot(LTAP,536,C['ctl']); pl([(LTAP,536),(LTAP,1136),(590,1136)],C['ctl'],1.8)
dot(CTAP,508,C['ctl']); pl([(CTAP,508),(CTAP,1108),(590,1108)],C['ctl'],1.8)
# ---- I2C lanes ----
SCLL,SDAL=400,415
pl([(340,600),(SDAL,600),(SDAL,1550),(590,1550)],C['i2c'],1.8)
pl([(340,630),(SCLL,630),(SCLL,1580),(590,1580)],C['i2c'],1.8)
T(SDAL+5,1000,'SDA',10,'start','bold',C['i2c']); T(SCLL-5,1000,'SCL',10,'end','bold',C['i2c'])

# ======================= MOTORS =======================
def uln(x,y,ins,label,motlabel):
    box(x,y,110,70,'#f3f3f3')
    T(x+55,y+40,'ULN2003',10.5,'middle','bold'); T(x+55,y+54,'board',9,'middle',c=C['grey'])
    for i,xi in enumerate(ins): T(xi,y+14,f'IN{i+1}',7.5,'middle',c=C['grey'])
    # + on left, - on right
    line(x,y+50,x-12,y+50); T(x+4,y+62,'+',9,'start','bold',C['p5'])
    line(x+110,y+50,x+122,y+50); gnd(x+122,y+50); T(x+104,y+64,'−',10,'end','bold')
    cx=x+55; line(cx,y+70,cx,y+112,C['mot'],4)
    T(cx+6,y+95,'5-wire plug',8.5,c=C['grey'])
    add(f'<circle cx="{cx}" cy="{y+138}" r="26" fill="#fff" stroke="{C["w"]}" stroke-width="1.8"/>')
    T(cx,y+144,'M',15,'middle','bold'); T(cx,y+182,motlabel,9.5,'middle')
    return (x-12,y+50)
for nm,(xi) in zip(['D2','D3','D4','D5'],[55,80,105,130]):
    pl([(NX-20,lp[nm]),(xi,lp[nm]),(xi,830)],C['mot'],1.6)
for nm,xi in bp.items():
    line(xi,NY+NH+20,xi,830,C['mot'],1.6)
p=uln(40,830,[55,80,105,130],'U6','Motor 1 · 28BYJ-48')
tag(p[0],p[1],'+5V',C['p5'],'left') if False else None
line(p[0],p[1],p[0],p[1]-14); T(p[0],p[1]-18,'+5V',9,'middle','bold',C['p5'])
p=uln(185,830,[200,230,260,290],'U7','Motor 2 · 28BYJ-48')
line(p[0],p[1],p[0],p[1]-14); T(p[0]-2,p[1]-18,'+5V',9,'middle','bold',C['p5'])

# ======================= SHIFT REGISTERS =======================
def sr(Yo,name):
    x,y,w=620,Yo+450,140
    h=30+7*28+26
    box(x,y,w,h,'#fffdf5'); T(x+w/2,y+18,name,11,'middle','bold')
    L=[(14,'SER'),(11,'SRCLK'),(12,'RCLK'),(10,'/SRCLR'),(13,'/OE'),(9,"Q7'")]
    pins={}
    for i,(n,nm) in enumerate(L):
        py=Yo+480+28*i; line(x-30,py,x,py); T(x+6,py+4,nm,10.5); T(x-4,py-4,str(n),9,'end',c='#777'); pins[nm]=(x-30,py)
    for k in range(8):
        py=Yo+480+28*k; line(x+w,py,x+w+30,py); T(x+w-6,py+4,f'Q{k}',10.5,'end')
        n=15 if k==0 else k; T(x+w+4,py-4,str(n),9,'start',c='#777'); pins[f'Q{k}']=(x+w+30,py)
    # VCC top, GND bottom
    line(x+70,y,x+70,y-18); line(x+70,y-18,x+82,y-18); tag(x+82,y-18,'+5V',C['p5']); T(x+64,y-4,'16',9,'end',c='#777')
    line(x+70,y+h,x+70,y+h+4); gnd(x+70,y+h+4); T(x+64,y+h+12,'8',9,'end',c='#777')
    # /SRCLR -> +5V, /OE -> GND
    xx,yy=pins['/SRCLR']; tag(xx,yy,'+5V',C['p5'],'left')
    xx,yy=pins['/OE']; gnd(xx,yy)
    return pins
p1=sr(0,'U1 · 74HC595 #1')
p2=sr(600,'U2 · 74HC595 #2')
pl([p1["Q7'"],(560,620),(560,1080),p2['SER']],C['ctl'],1.8)
T(566,850,'Q7′ → SER',9.5,'start','bold',C['ctl'])
xx,yy=p2["Q7'"]; T(xx-4,yy+4,'NC',9.5,'end',c=C['grey'])

# ======================= LED CHANNELS =======================
holes=[('395 nm UV','#8e44ad'),('405 nm violet','#9b59b6'),('blue','#2e86de'),('green','#27ae60'),('yellow','#f1c40f'),
       ('orange','#e67e22'),('red','#e74c3c'),('850 nm IR','#95a5a6'),('940 nm IR','#7f8c8d'),('reserved*','#ffffff'),
       ('reserved*','#ffffff'),('1450 nm','#34495e'),('1550 nm','#34495e'),('1650 nm','#34495e'),('1760 nm','#34495e'),('1850 nm','#34495e')]
def cell(col,Yo,n,pins,qk):
    X=900+130*col; Yr=Yo+260; xa=X+85
    rc=C['A'] if n<=9 else C['B']
    dot(xa,Yr,rc)
    wl,fill=holes[n-1]
    led_v(xa,Yr,Yr+70,fill,'3 2' if n in (10,11) else None)
    T(xa-14,Yr+28,f'H{n}',11,'end','bold'); T(xa-14,Yr+42,wl,9.5,'end')
    T(xa-14,Yr+56,'LED',8.5,'end',c=C['grey'])
    line(xa,Yr+70,xa,Yr+100)
    xg=X+54; ym=Yr+130
    nmos(xa,Yr+100,Yr+160,xg); T(xa+6,ym+16,f'Q{n}',9,c=C['grey']); T(xa+6,ym+28,'2N7000',7.5,c=C['grey'])
    T(xa+5,Yr+106,'D',8,c='#777'); T(xa+5,Yr+158,'S',8,c='#777'); T(xg+2,ym-5,'G',8,c='#777')
    gnd(xa,Yr+160)
    dot(xg,ym); res_h(X+14,xg,ym,'220Ω'); res_v(xg,ym,ym+42,'10k','left'); gnd(xg,ym+42)
    yk=Yo+480+28*qk
    xs,ys=pins[f'Q{qk}']
    pl([(X+14,ym),(X+14,yk),(xs,yk)],C['ctl'],1.6)
    T(X+18,Yr+212,f'CH{n}',11,'start','bold',C['ctl'])
for k in range(8): cell(k,0,k+1,p1,k)
for k in range(8): cell(k,600,k+9,p2,k)
# rails
xa=lambda col:900+130*col+85
line(xa(0),260,1960,260,C['A'],3.2)
T(xa(0)+30,250,"RAIL A  ←  DRV1 'LED' output (≈30 mA)",11.5,'start','bold',C['A'])
line(xa(1),860,1990,860,C['B'],3.2)
T(xa(1)+30,852,"RAIL B  ←  DRV2 'LED' output (≈45 mA)",11.5,'start','bold',C['B'])
pl([(1960,440),(1960,830),(xa(0),830),(xa(0),860)],C['A'],3.2)
T(1500,824,'RAIL A continues → CH9 (940 nm)',10.5,'start','bold',C['A'])
dot(1960,440,C['A'])
line(1960,260,1960,440,C['A'],3.2)

# ======================= DRIVERS =======================
def drv(y,name):
    x=2080; box(x,y,140,140,'#fff7ec')
    T(x+70,y+60,name,12.5,'middle','bold'); T(x+70,y+76,'LD06AJSA',9.5,'middle',c=C['grey']); T(x+70,y+89,'constant-current',9,'middle',c=C['grey'])
    for yy,nm in ((y+30,'CE'),(y+110,'LED')):
        line(x-30,yy,x,yy); T(x+6,yy+4,nm,11)
    for yy,nm in ((y+30,'V1'),(y+110,'G')):
        line(x+140,yy,x+170,yy); T(x+134,yy+4,nm,11,'end')
    tag(x+170,y+30,'+5V',C['p5']); gnd(x+170,y+110)
drv(330,'DRV1'); drv(930,'DRV2')
# DRV1: CE at 360, LED at 440
dot(2042,360,C['ctl']); res_v(2042,360,402,'10k','right'); gnd(2042,402)
hline_hop(1960,2050,440,[2015],C['A'],3.2)
T(2080,492,'Set to minimum (≈30 mA)',10.5); T(2080,508,'Feeds RAIL A (holes 1–9)',10.5,c=C['A'],weight='bold')
# DRV2: CE at 960, LED at 1040
pl([(2015,165),(2015,960),(2050,960)],C['ctl'],1.8)
dot(2032,960,C['ctl']); res_v(2032,960,1002,'10k','right'); gnd(2032,1002)
pl([(2050,1040),(1990,1040),(1990,860)],C['B'],3.2)
T(2080,1092,'Set ≈45 mA (≤ SWIR LED rating)',10.5); T(2080,1108,'Feeds RAIL B (holes 10–16)',10.5,c=C['B'],weight='bold')

# ======================= ADS1115 =======================
ax,ay,aw,ah=620,1460,160,220
box(ax,ay,aw,ah,'#eefbf9'); T(ax+aw/2,ay+18,'U3 · ADS1115',11.5,'middle','bold'); T(ax+aw/2,ay+31,'I²C 0x48',9.5,'middle',c=C['grey'])
Lp=[('VDD',1490),('GND',1520),('SDA',1550),('SCL',1580),('ADDR',1610),('ALRT',1640)]
for nm,y in Lp: line(ax-30,y,ax,y); T(ax+6,y+4,nm,10.5)
Rp=[('A0',1520),('A1',1560),('A2',1600),('A3',1640)]
for nm,y in Rp: line(ax+aw,y,ax+aw+30,y); T(ax+aw-6,y+4,nm,10.5,'end')
tag(590,1490,'+5V',C['p5'],'left'); gnd(590,1520); gnd(590,1610); T(586,1644,'NC',9.5,'end',c=C['grey'])
T(814,1604,'NC',9.5,c=C['grey']); T(814,1644,'NC',9.5,c=C['grey'])

# ======================= OPT101 =======================
ox,oy,ow,oh=960,1500,140,160
box(ox,oy,ow,oh,'#fff'); T(ox+ow/2,oy+18,'U4 · OPT101',11.5,'middle','bold'); T(ox+ow/2,oy+31,'CJMCU-101 module',9,'middle',c=C['grey'])
for nm,y in (('OUT',1560),('1M',1600)): line(ox-30,y,ox,y); T(ox+6,y+4,nm,10.5)
for nm,y in (('VCC',1530),('GND',1565),('−V',1600),('COM',1635)): line(ox+ow,y,ox+ow+30,y); T(ox+ow-6,y+4,nm,10.5,'end')
line(930,1560,810,1560,C['ana'],1.8); pl([(930,1600),(905,1600),(905,1560)]); dot(905,1560)
T(870,1590,'1M↔OUT',8.5,'middle',c=C['grey']); T(870,1553,'OPT101 → A1',9,'middle','bold',C['ana'])
tag(1130,1530,'+5V',C['p5'])
for y in (1565,1600,1635): line(1130,y,1150,y)
line(1150,1565,1150,1635); dot(1150,1600); dot(1150,1635); gnd(1150,1635)

# ======================= TIA =======================
inv,non,out=opamp(1500,1530,1630)
T(1494,inv[1]-4,'2',9,'end',c='#777'); T(1494,non[1]-4,'3',9,'end',c='#777'); T(out[0]+5,out[1]-5,'1',9,'start',c='#777')
T(1530,1584,'TL072',8.5,'middle',c=C['grey']); T(1530,1594,'U5A',8,'middle',c=C['grey'])
S=(1430,inv[1]); line(inv[0],inv[1],S[0],S[1]); dot(*S)
pd_v(1430,S[1],1630); gnd(1430,1630)
T(1395,1575,'D1 InGaAs',10.5,'end','bold'); T(1395,1589,'MTPD1346D',9.5,'end')
T(1395,1603,'cathode → pin 2',9.5,'end',c=C['ana']); T(1395,1617,'anode → GND',9.5,'end',c=C['ana'])
pl([non,(1470,non[1]),(1470,1630)]); gnd(1470,1630)
line(1430,S[1],1430,1460); dot(1430,1495)
line(1430,1495,1470,1495); res_h(1470,1580,1495,'Rf 1 MΩ'); line(1580,1495,1640,1495); dot(1640,1495)
cap_h(1430,1640,1460,'Cf 10 pF'); line(1640,1460,1640,out[1])
line(out[0],out[1],1640,out[1]); dot(1640,out[1])
vx=1545; yt=1530+45*50/90
line(vx,yt,vx,yt-14); line(vx,yt-14,vx+10,yt-14); T(vx+12,yt-10,'+5V · pin 8',9,'start','bold',C['p5'])
yb=1630-45*50/90
line(vx,yb,vx,yb+16); line(vx,yb+16,vx+10,yb+16); T(vx+12,yb+20,'−5V · pin 4',9,'start','bold',C['n5'])
res_h(1640,1710,out[1],'10 kΩ'); T(1675,out[1]+18,'ADC protection',8,'middle',c=C['grey'])
pl([(1710,out[1]),(1730,out[1]),(1730,1420),(850,1420),(850,1520),(810,1520)],C['ana'],1.8)
T(1100,1414,'TIA output → ADS1115 A0',10,'start','bold',C['ana'])
# unused side B
i2,n2,o2=opamp(1790,1610,1690)
pl([(o2[0],o2[1]),(1885,o2[1]),(1885,1600),(1772,1600),(1772,i2[1]),i2])
pl([n2,(1772,n2[1]),(1772,1690)]); gnd(1772,1690)
T(1893,1662,'U5B unused',9,'start',c=C['grey']); T(1893,1675,'6→7, 5→GND',9,'start',c=C['grey'])
T(1784,i2[1]-3,'6',8,'end',c='#777'); T(1784,n2[1]-3,'5',8,'end',c='#777'); T(o2[0]+3,o2[1]-4,'7',8,'start',c='#777')

# ======================= DECOUPLING =======================
caps=[('C1','U1 16↔8'),('C2','U2 16↔8'),('C3','ADS VDD'),('C4','OPT VCC'),('C5','TL072 p8'),('C6','TL072 p4')]
for i,(nm,lab) in enumerate(caps):
    x=55+i*57
    neg = nm=='C6'
    tag(x,1095,'−5V' if neg else '+5V',C['n5'] if neg else C['p5'],'right',9.5) if False else None
    T(x,1103,'−5V' if neg else '+5V',9.5,'middle','bold',C['n5'] if neg else C['p5'])
    line(x,1109,x,1119); line(x-7,1109,x+7,1109,C['n5'] if neg else C['p5'],2)
    cap_v(x,1119,1165); gnd(x,1165)
    T(x,1205,nm,10.5,'middle','bold'); T(x,1219,lab,8.5,'middle',c=C['grey'])
T(32,1252,'Place each one right at its chip\'s power pins.',10.5,c='#333')

# ======================= NOTES =======================
notes=['Every ground symbol = the common GND (bank junction).',
 'Every "+5V" label = bank A +5V; "−5V" = bank B (TL072 pin 4 only).',
 '',
 'Nano stays on laptop USB (Python logging). Its 5V pin is',
 'NOT connected to +5V. Only GND is shared.',
 '',
 '2N7000 legs, flat face toward you: 1 S · 2 G · 3 D.',
 'LED long leg (anode) → rail; short leg (cathode) → drain.',
 '',
 'U1/U2: CLOCK and LATCH go to BOTH chips; DATA only to U1.',
 'Q0 is pin 15; Q1–Q7 are pins 1–7.',
 '',
 'DRV1 minimum is ≈30 mA (module range 30–1500 mA).',
 'CE 10k pull-downs keep both drivers OFF during boot.',
 'Never let RAIL A and RAIL B touch.',
 '',
 'InGaAs: cathode → pin 2, anode → GND (output goes +).',
 'Test the case lead first: tied to cathode → leave it NC.',
 'If the TIA sits near +3.5 V with a SWIR LED on, it is',
 'saturating → change Rf from 1 MΩ to 100 kΩ.',
 '',
 'Firmware: ONE channel at a time. setHole() first, then',
 'CE high, wait ~8 ms, read A0/A1, CE low.',
 'Don\'t run the motors during a sweep (rail noise).',
 '',
 '* Holes 10–11 empty. If you fit white/pink there,',
 '  wire their anodes to RAIL A and edit isRailB().']
for i,s in enumerate(notes): T(32,1315+i*20,s,10.5)

# ======================= LEGEND =======================
ly=1790; xx=490
for s,c,wd in [('+5V label',C['p5'],2),('−5V label',C['n5'],2),('RAIL A',C['A'],3.2),('RAIL B',C['B'],3.2),('logic / control',C['ctl'],1.8),('I²C',C['i2c'],1.8),('analog signal',C['ana'],1.8),('motor wiring',C['mot'],1.6)]:
    line(xx,ly,xx+28,ly,c,wd); T(xx+34,ly+4,s,11,c=c,weight='bold'); xx+=34+len(s)*7+30
gnd(xx+6,ly-8); T(xx+22,ly+4,'= GND',11); xx+=80
dot(xx,ly); T(xx+10,ly+4,'= wires joined',11); xx+=120
hline_hop(xx,xx+30,ly,[xx+15]); T(xx+36,ly+4,'= wires cross, NOT joined',11)
T(490,1830,'Pin numbers (small grey) are the physical chip pins. Symbols are drawn by function, inputs on the left, outputs on the right — wire by pin number.',11,c='#333')
T(490,1852,'All parts: 1× Nano · 2× 74HC595 · 16× 2N7000 · 16× 220 Ω · 19× 10 kΩ · 1× 1 MΩ · 1× 10 pF · 6× 100 nF · 2× LD06AJSA · ADS1115 · OPT101 · MTPD1346D · TL072 · 2× ULN2003 + 28BYJ-48 · 2 power banks',11,c='#333')

svg=f'<svg id="sch" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {HGT}" font-family="Helvetica, Arial, sans-serif"><rect width="{W}" height="{HGT}" fill="#fff"/>'+''.join(E)+'</svg>'
open('LIO_full_schematic.svg','w').write(svg)

page=open('page_template.html').read()
page=page.replace('<h1>LIO V3 Optical Head — Complete Circuit</h1>','<h1>LIO V3 Optical Head — Full Electronics Schematic</h1>')
page=re.sub(r'<div class="sub">.*?</div>','<div class="sub">Every part and every signal wire drawn: Arduino Nano, 2× 74HC595, 16× 2N7000 channels, 2× LD06AJSA drivers, ADS1115, OPT101, InGaAs + TL072 transimpedance amplifier, 2× ULN2003 + 28BYJ-48 motors, decoupling capacitors, and the ±5 V split supply from two power banks.</div>',page,flags=re.S)
page=page.replace('#sch { display:block; width:100%; min-width:1000px; height:auto; }','#sch { display:block; width:100%; min-width:1300px; height:auto; }')
page=page.replace('<h3>One measurement cycle</h3>','<h3>Stepper motors (existing)</h3>\n<p>Nano D2–D5 drive IN1–IN4 of the first ULN2003 board and D6–D9 drive IN1–IN4 of the second. Each board\'s + pin goes to +5V and its − pin to GND, and each motor plugs into its board\'s 5-wire connector. The motors share the +5V rail with the optics, so don\'t move them during a measurement sweep.</p>\n\n<h3>One measurement cycle</h3>')
page=page.replace('<tr><td>D2–D9</td><td>motors</td><td>Unchanged (two ULN2003 boards)</td></tr>','<tr><td>D2–D5</td><td>motor 1</td><td>ULN2003 board #1 IN1–IN4</td></tr>\n<tr><td>D6–D9</td><td>motor 2</td><td>ULN2003 board #2 IN1–IN4</td></tr>')
page=page.replace('<tr><td>5 V power banks (separate units)</td><td>2</td><td>±5 V split supply</td></tr>','<tr><td>ULN2003 driver board + 28BYJ-48 stepper</td><td>2 + 2</td><td>Chamber lift (existing)</td></tr>\n<tr><td>5 V power banks (separate units)</td><td>2</td><td>±5 V split supply</td></tr>')
page=page.replace('%%SVG%%',svg)
open('LIO_full_schematic.html','w').write(page)
print('ok')
