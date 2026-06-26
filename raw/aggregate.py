import json, os
BASE=os.path.dirname(__file__)
meta=json.load(open(f"{BASE}/meta.json"))
pop=json.load(open(f"{BASE}/pop.json"))
chunks=[json.load(open(f"{BASE}/c{i}.json")) for i in (1,2,3,4)]

crime_order=meta['crime_area_order']      # 106 codes
pop_order=meta['pop_area_order']          # 104 codes
offenses=meta['offense_order']            # 8 codes
NOFF=len(offenses)
OI={o:i for i,o in enumerate(offenses)}

# validate chunk lengths
for ci,ch in enumerate(chunks,1):
    nt=len(ch['tid']); exp=len(crime_order)*NOFF*nt
    assert len(ch['value'])==exp, f"c{ci} len {len(ch['value'])} != {exp}"

# accessor for a chunk: value index = (area_i*NOFF + off_i)*ntime + t
def cval(ch, area_i, off_i, t):
    nt=len(ch['tid'])
    return ch['value'][(area_i*NOFF+off_i)*nt + t]

# Build quarter -> we need annual per area per offense across all chunks
# Map year -> (chunk_index, [t indices])
yearmap={}
for ci,ch in enumerate(chunks):
    for t,q in enumerate(ch['tid']):
        y=int(q[:4]); yearmap.setdefault(y,[]).append((ci,t))
years=sorted(yearmap)              # 2016..2025
assert years==list(range(2016,2026)), years
for y in years:
    assert len(yearmap[y])==4, (y,len(yearmap[y]))

area_idx={c:i for i,c in enumerate(crime_order)}

def annual(code, off, year):
    ai=area_idx[code]; oi=OI[off]; s=0
    for ci,t in yearmap[year]:
        s+=cval(chunks[ci], ai, oi, t)
    return s

# population accessor
pop_idx={c:i for i,c in enumerate(pop_order)}
def popv(code, year):
    if code not in pop_idx: return None
    return pop[pop_idx[code]*len(meta['pop_tid']) + (year-2016)]

non_muni={'000','084','085','083','082','081','411','998'}
munis=[c for c in crime_order if c not in non_muni]
assert len(munis)==98, len(munis)

# Danish names from chunk metadata would be nicer; use English-friendly from a name map we build from geojson later.
# We'll store Danish names from a small lookup using the area labels we have (English not stored). Use codes; names added in build step.

out={'years':years,
     'categories':['total','violence','burglary','theft','drugs','weapons'],
     'cat_labels':{'total':'All offences','violence':'Violence','burglary':'Burglary','theft':'Theft','drugs':'Drugs','weapons':'Weapons'},
     'source':'Danmarks Statistik, StatBank STRAF11 & FOLK1A',
     'munis':{}}

def series(code, mapper):
    return [mapper(code,y) for y in years]

for code in munis:
    rec={
      'pop':[popv(code,y) for y in years],
      'total':[annual(code,'TOT',y) for y in years],
      'violence':[annual(code,'12',y) for y in years],
      'burglary':[annual(code,'1316',y)+annual(code,'1320',y) for y in years],
      'theft':[annual(code,'1332',y)+annual(code,'1336',y) for y in years],
      'drugs':[annual(code,'3210',y) for y in years],
      'weapons':[annual(code,'3410',y) for y in years],
    }
    out['munis'][code]=rec

# ---- VALIDATION against known national (Hele landet=000) quarter sums ----
# Known 2025 quarterly TOT national: 104078+102752+103457+104624
nat2025=annual('000','TOT',2025)
assert nat2025==414911, nat2025
# spot: national violence 2025 = 6739+7631+7482+7556
assert annual('000','12',2025)==29408, annual('000','12',2025)
# Sum of municipalities + non-stated should be <= national; national includes 'Uoplyst' 998
nat_tot={y:annual('000','TOT',y) for y in years}
muni_sum={y:sum(out['munis'][c]['total'][i] for c in munis) for i,y in enumerate(years)}
uoplyst={y:annual('998','TOT',y) for y in years}
christ={y:annual('411','TOT',y) for y in years}
for y in years:
    diff=nat_tot[y]-(muni_sum[y]+uoplyst[y]+christ[y])
    assert diff==0, f"{y}: national {nat_tot[y]} != muni {muni_sum[y]} + uoplyst {uoplyst[y]} + christiansø {christ[y]} (diff {diff})"

# region sum check: sum of 5 regions == national
regions=['084','085','083','082','081']
for y in years:
    rs=sum(annual(r,'TOT',y) for r in regions)+uoplyst[y]
    assert rs==nat_tot[y], f"region sum {rs} != national {nat_tot[y]} ({y})"

print("VALIDATION PASSED")
print("National TOT by year:", nat_tot)
print("Muni count:", len(munis))
# sample
for c in ['101','851','461','741']:
    print(c, 'pop2025', out['munis'][c]['pop'][-1], 'total2025', out['munis'][c]['total'][-1],
          'theft2025', out['munis'][c]['theft'][-1], 'burg2025', out['munis'][c]['burglary'][-1])

json.dump(out, open(f"{BASE}/../crime_data.json",'w'), separators=(',',':'), ensure_ascii=False)
print('wrote crime_data.json', round(os.path.getsize(f"{BASE}/../crime_data.json")/1024,1),'KB')
