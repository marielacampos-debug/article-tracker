"""
Article Tracker Generator
Fetches data from the Content Team 2026 Editorial Calendar in Asana
and generates a self-contained article_tracker.html file.

Requirements:
  Python 3.8+, ASANA_TOKEN environment variable

Usage:
  ASANA_TOKEN=your_token python generate.py
"""

import json, os, re, base64, urllib.request, urllib.error
from datetime import datetime

PROJECT_GID = "1211512877220282"
ASANA_TOKEN = os.environ.get("ASANA_TOKEN")
if not ASANA_TOKEN:
    raise ValueError("ASANA_TOKEN environment variable is not set.")

SECTION_IDS = [
    ("1211516243546205","January"),    # Week 01: Dec 29-Jan 2
    ("1211516243546207","January"),    # Week 02: Jan 5-9
    ("1211516243546209","January"),    # Week 03: Jan 12-16
    ("1211516243546211","January"),    # Week 04: Jan 19-23
    ("1211516243546213","January"),    # Week 05: Jan 26-30
    ("1211516247179978","February"),   # Week 06: Feb 2-6
    ("1211516247179980","February"),   # Week 07: Feb 9-13
    ("1211516247179982","February"),   # Week 08: Feb 16-20
    ("1211516247179984","February"),   # Week 09: Feb 23-27
    ("1211516247179986","March"),      # Week 10: Mar 2-6
    ("1211516247179988","March"),      # Week 11: Mar 9-13
    ("1211516247179990","March"),      # Week 12: Mar 16-20
    ("1211516247179992","March"),      # Week 13: Mar 23-27
    ("1211516247179994","March"),      # Week 14: Mar 30-Apr 3
    ("1211516247179996","April"),      # Week 15: Apr 6-10
    ("1211516247179998","April"),      # Week 16: Apr 13-17
    ("1211516247180000","April"),      # Week 17: Apr 20-24
    ("1211516247180002","April"),      # Week 18: Apr 27-May 1
    ("1211516247180004","May"),        # Week 19: May 4-8
    ("1211516247180006","May"),        # Week 20: May 11-15
    ("1211516247180008","May"),        # Week 21: May 18-22
    ("1211516247195509","May"),        # Week 22: May 25-29
    ("1211516247195511","June"),       # Week 23: Jun 1-5
    ("1211516247195513","June"),       # Week 24: Jun 8-12
    ("1211516247195515","June"),       # Week 25: Jun 15-19
    ("1211516247195517","June"),       # Week 26: Jun 22-26
    ("1211516247195519","June"),       # Week 27: Jun 29-Jul 3
    ("1211516247195521","July"),       # Week 28: Jul 6-10
    ("1211516247195523","July"),       # Week 29: Jul 13-17
    ("1211516247195525","July"),       # Week 30: Jul 20-24
    ("1211516247195527","July"),       # Week 31: Jul 27-31
    ("1211516247195529","August"),     # Week 32: Aug 3-7
    ("1211516247195531","August"),     # Week 33: Aug 10-14
    ("1211516247195533","August"),     # Week 34: Aug 17-21
    ("1211516247195535","August"),     # Week 35: Aug 24-28
    ("1211516247195537","September"),  # Week 36: Aug 31-Sep 4
    ("1211516247195539","September"),  # Week 37: Sep 7-11
    ("1211516247210084","September"),  # Week 38: Sep 14-18
    ("1211516247210086","September"),  # Week 39: Sep 21-25
    ("1211516247210088","September"),  # Week 40: Sep 28-Oct 2
    ("1211516247210090","October"),    # Week 41: Oct 5-9
    ("1211516247210092","October"),    # Week 42: Oct 12-16
    ("1211516247210094","October"),    # Week 43: Oct 19-23
    ("1211516247210096","October"),    # Week 44: Oct 26-30
    ("1211516247210098","November"),   # Week 45: Nov 2-6
    ("1211516247210100","November"),   # Week 46: Nov 9-13
    ("1211516247210102","November"),   # Week 47: Nov 16-20
    ("1211516247210104","November"),   # Week 48: Nov 23-27
    ("1211516247210106","December"),   # Week 49: Nov 30-Dec 4
    ("1211516247210108","December"),   # Week 50: Dec 7-11
    ("1211516247210110","December"),   # Week 51: Dec 14-18
    ("1211516247210112","December"),   # Week 52: Dec 21-25
]

TYPE_MAP = {
    "Topic Center":"TC","Channel Sponsorship Topic Center":"CS",
    "Channel Sponsorship TC + AIDA":"CS","Member Portrait Topic Center":"Portrait TC",
    "Hot Topic":"Hot Topic","Hot Topic - Client":"Hot Topic (Client)",
    "News":"News","Treatment Page":"TP","Knowledge Center":"KC",
    "Condition Guide":"Condition Guide","Native Brand Integration Article":"NBI",
}
REMOVAL_CTS = {"TC Removal/Convert to Hot Topic","Discontinued Treatment"}
REMOVAL_PS  = {"ENDED","Discontinued Treatment"}
REFRESH_CTS = {"Refresh","Add to a TC - Refresh","Add to a CS - Refresh","Rewrite",
               "Versioned Article","Add to a TC - Audit","Audit"}

MONTH_FROM_DATE = {
    1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
    7:"July",8:"August",9:"September",10:"October",11:"November",12:"December",
}
# Week 01 straddles Dec 29-Jan 2 — December dates belong in January
MONTH_FROM_DATE[12] = "January"  # override: late Dec = January (Week 1)

OPT_FIELDS = "name,gid,due_on,notes,custom_fields.name,custom_fields.display_value"


def asana_get(path):
    url = f"https://app.asana.com/api/1.0{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {ASANA_TOKEN}","Accept":"application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Asana {e.code} for {path}: {e.read().decode()}") from e


def get_section_tasks(gid):
    return asana_get(f"/sections/{gid}/tasks?limit=100&opt_fields={OPT_FIELDS}").get("data",[])


def parse_dt(d):
    if not d: return None
    try:
        return datetime.fromisoformat(d.replace("Z","")) if "T" in d else datetime.strptime(d[:10],"%Y-%m-%d")
    except: return None


def fmt(dt): return dt.strftime("%-m/%-d/%Y") if dt else ""


def notes_date(notes):
    if not notes: return None
    m = re.search(r"Publish Date:\s*(\d{1,2})/(\d{1,2})/(\d{2,4})",notes,re.IGNORECASE)
    if m:
        mo,dy,yr = int(m.group(1)),int(m.group(2)),int(m.group(3))
        if yr<100: yr+=2000
        try: return datetime(yr,mo,dy)
        except: pass
    return None


def best_2026(candidates):
    for dt in candidates:
        if dt and dt.year==2026: return dt
    for dt in candidates:
        if dt: return dt
    return None


def process_task(task, section_month):
    name = task.get("name","").strip()
    gid  = task.get("gid","")
    due_on_raw = task.get("due_on") or ""
    notes      = task.get("notes") or ""
    cfs = {cf.get("name",""):cf.get("display_value") or ""
           for cf in task.get("custom_fields",[]) if cf.get("display_value")}
    ct  = cfs.get("Content Type","")
    ps  = cfs.get("Production Stage","")
    site= cfs.get("Site","")
    cg  = cfs.get("Content Group","")
    url = cfs.get("URL","").strip()
    posted_raw  = cfs.get("Posted On","")
    updated_raw = cfs.get("Updated On","")
    type_label  = TYPE_MAP.get(cg,cg)
    live_url = url if (url and ps=="Published") else ""
    due_dt    = parse_dt(due_on_raw)
    posted_dt = parse_dt(posted_raw)
    updated_dt= parse_dt(updated_raw)
    notes_dt  = notes_date(notes)
    if ct in REFRESH_CTS:
        dt = best_2026([due_dt,updated_dt,posted_dt,notes_dt])
    else:
        dt = best_2026([due_dt,posted_dt,notes_dt,updated_dt])
    date_str  = fmt(dt)
    tab_month = MONTH_FROM_DATE.get(dt.month,section_month) if dt else section_month
    row = [name,gid,site,type_label,live_url,date_str,tab_month]
    if ct in REMOVAL_CTS or ps in REMOVAL_PS:
        if not date_str or "2026" not in date_str:
            return None,None
        rt = ("TC Removal" if "TC Removal" in ct else
              "Discontinued" if "Discontinued" in (ct+ps) else "Ended")
        return "removed", row+[rt]
    elif ct in REFRESH_CTS:
        return "refreshed", row
    elif ct=="New":
        return "added", row
    return None,None


def fetch_all_data():
    added,refreshed,removed=[],[],[]
    refresh_date = datetime.today().strftime("%B %-d, %Y")
    for gid,section_month in SECTION_IDS:
        print(f"  Fetching {gid} ({section_month})...")
        for task in get_section_tasks(gid):
            cat,row = process_task(task,section_month)
            if cat=="added": added.append(row)
            elif cat=="refreshed": refreshed.append(row)
            elif cat=="removed": removed.append(row)
    print(f"\n  Added:{len(added)} Refreshed:{len(refreshed)} Removed:{len(removed)}")
    return added,refreshed,removed,refresh_date


def generate_html(added,refreshed,removed,refresh_date):
    packed = json.dumps({"a":added,"r":refreshed,"x":removed},ensure_ascii=True,separators=(",",":"))
    b64 = base64.b64encode(packed.encode("utf-8")).decode("ascii")
    return HTML_TEMPLATE.replace("__B64__",b64).replace("__REFRESH_DATE__",refresh_date)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Article Tracker 2026</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;background:#f8fafc;min-height:100vh;padding:20px 16px;color:#1e293b}
table{width:100%;border-collapse:collapse;font-size:13px}
th{padding:9px 12px;text-align:left;font-weight:600;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #e2e8f0;background:#f8fafc;white-space:nowrap}
td{padding:8px 12px;border-bottom:1px solid #f1f5f9;vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:nth-child(even) td{background:#fafafa}
tr:nth-child(odd) td{background:#fff}
input,select{font-family:inherit;border:1px solid #e2e8f0;border-radius:7px;padding:7px 10px;background:#fff;color:#475569;outline:none;cursor:pointer}
button{font-family:inherit;cursor:pointer;outline:none;border:none}
a{text-decoration:none}
.wrap{max-width:1120px;margin:0 auto}
.badge{display:inline-block;font-size:11px;font-weight:700;padding:2px 7px;border-radius:5px;white-space:nowrap;border:1px solid;line-height:1.6}
.stat{border-radius:8px;padding:10px 14px;text-align:center;cursor:pointer;transition:transform .12s;border:1px solid}
.stat:hover{transform:translateY(-1px)}
.stat-val{font-size:22px;font-weight:800;line-height:1}
.stat-lbl{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-top:3px}
.tabs{display:flex;gap:2px;background:#f1f5f9;border-radius:9px;padding:3px;width:fit-content}
.tab{padding:6px 14px;font-size:13px;font-weight:600;border-radius:7px;border:none;background:transparent;color:#64748b;display:flex;align-items:center;gap:6px;white-space:nowrap}
.tab.active{background:#fff;color:#1e293b;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.tab-count{font-size:11px;font-weight:700;padding:1px 6px;border-radius:10px;background:#e2e8f0;color:#94a3b8}
.tab.active .tab-count{background:var(--tab-bg);color:var(--tab-c)}
.filters{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center;position:relative;z-index:10}
.filters input{flex:1 1 180px;min-width:140px}
.legend-btn{width:100%;padding:10px 14px;display:flex;align-items:center;justify-content:space-between;background:none;border:none}
#legend-body{display:none;border-top:1px solid #f1f5f9;padding:10px 14px;flex-direction:column;gap:7px}
#legend-body.shown{display:flex}
.legend-row{display:flex;align-items:baseline;gap:10px}
.legend-desc{font-size:12px;color:#475569;line-height:1.5}
.live-banner{display:none;align-items:center;justify-content:space-between;background:#dbeafe;border:1px solid #93c5fd;border-radius:8px;padding:8px 14px;margin-bottom:10px}
.live-banner.shown{display:flex}
.empty{text-align:center;padding:40px;color:#94a3b8;font-size:13px}
/* Month selector */
.month-selector-wrap{position:relative;margin-bottom:14px}
.month-trigger{display:flex;align-items:center;gap:8px;padding:8px 14px;border:1px solid #e2e8f0;border-radius:9px;background:#fff;font-size:14px;font-weight:600;color:#1e293b;cursor:pointer;width:fit-content;min-width:200px;justify-content:space-between;font-family:inherit}
.month-trigger:hover{border-color:#c7d2fe;background:#fafbff}
.month-trigger.open{border-color:#c7d2fe;background:#fafbff}
.month-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.month-dropdown{position:absolute;top:calc(100% + 6px);left:0;background:#fff;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.1);z-index:200;padding:8px;display:none;width:320px}
.month-dropdown.open{display:grid;grid-template-columns:repeat(3,1fr);gap:4px}
.month-option{padding:8px 10px;border-radius:7px;cursor:pointer;font-size:13px;font-weight:500;color:#475569;text-align:center;transition:all .1s;border:1px solid transparent}
.month-option:hover{background:#f8fafc;border-color:#e2e8f0}
.month-option.active{background:#eef2ff;color:#4338ca;border-color:#c7d2fe;font-weight:700}
.month-option .month-counts{font-size:10px;color:#94a3b8;margin-top:2px}
.month-option.active .month-counts{color:#818cf8}
/* Multi-select type */
.type-wrap{position:relative;isolation:isolate}
.type-trigger{display:flex;align-items:center;gap:6px;padding:7px 10px;border:1px solid #e2e8f0;border-radius:7px;background:#fff;font-size:12px;color:#475569;cursor:pointer;white-space:nowrap;min-width:150px;justify-content:space-between;font-family:inherit}
.type-trigger.active{border-color:#c7d2fe;background:#eef2ff;color:#4338ca;font-weight:600}
.type-dropdown{position:absolute;top:calc(100% + 4px);right:0;left:auto;background:#fff;border:1px solid #e2e8f0;border-radius:9px;box-shadow:0 8px 24px rgba(0,0,0,.15);z-index:9999;min-width:230px;padding:6px 0;display:none;max-height:320px;overflow-y:auto}
.type-dropdown.open{display:block}
.type-option{display:flex;flex-direction:row;align-items:center;gap:10px;padding:8px 12px;cursor:pointer;font-size:13px;color:#475569;user-select:none;width:100%}
.type-option:hover{background:#f1f5f9}
.type-option input[type=checkbox]{width:15px;height:15px;cursor:pointer;accent-color:#6366f1;flex-shrink:0}
.type-count-pill{font-size:11px;font-weight:600;color:#94a3b8;background:#f1f5f9;padding:1px 7px;border-radius:10px;margin-left:auto}
.selected-count{background:#6366f1;color:#fff;font-size:10px;font-weight:700;padding:1px 6px;border-radius:10px;margin-left:2px}
</style>
</head>
<body>
<div class="wrap">

<!-- Header -->
<div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:14px">
  <div>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
      <div style="width:28px;height:28px;border-radius:7px;background:linear-gradient(135deg,#6366f1,#a855f7);display:flex;align-items:center;justify-content:center;font-size:14px">📋</div>
      <h1 style="font-size:18px;font-weight:800;color:#0f172a;letter-spacing:-.03em">Article Tracker: Added / Refreshed / Removed</h1>
    </div>
    <p style="font-size:12px;color:#64748b">Content Team 2026 Editorial Calendar &middot; January&ndash;December 2026
      <span style="margin-left:8px;background:#f1f5f9;color:#64748b;font-size:11px;font-weight:600;padding:1px 7px;border-radius:10px">Refreshed __REFRESH_DATE__</span>
    </p>
  </div>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-size:12px">
    <span class="badge" style="background:#f0fdfa;color:#0f766e;border-color:#99f6e4">Article &#8599;</span>
    <span style="color:#94a3b8">published &amp; live</span>
    <span class="badge" style="background:#faf5ff;color:#7c3aed;border-color:#e9d5ff">Asana &#8599;</span>
    <span style="color:#94a3b8">not yet live</span>
  </div>
</div>

<!-- Month selector -->
<div class="month-selector-wrap" id="month-selector-wrap">
  <button class="month-trigger" id="month-trigger" onclick="toggleMonthDropdown(event)">
    <div style="display:flex;align-items:center;gap:8px">
      <span class="month-dot" id="month-dot"></span>
      <span id="month-trigger-label">April</span>
    </div>
    <span style="font-size:10px;color:#94a3b8;margin-left:8px">&#9660;</span>
  </button>
  <div class="month-dropdown" id="month-dropdown"></div>
</div>

<!-- Legend -->
<div style="margin-bottom:14px;border:1px solid #e2e8f0;border-radius:9px;overflow:hidden;background:#fff">
  <button class="legend-btn" onclick="toggleLegend()">
    <div style="display:flex;align-items:center;gap:7px">
      <span>ℹ️</span>
      <span style="font-size:13px;font-weight:600;color:#475569">Content Type Legend</span>
      <span style="font-size:11px;color:#94a3b8">&mdash; TC, TP, CS, NBI, etc.</span>
    </div>
    <span id="legend-arrow" style="font-size:11px;color:#94a3b8">&#9660;</span>
  </button>
  <div id="legend-body"></div>
</div>

<!-- Stats -->
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px" id="stats"></div>

<!-- Tabs + Group toggle -->
<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:12px">
  <div class="tabs" id="tab-row"></div>
  <button id="group-btn" onclick="toggleGroup()" style="padding:6px 12px;font-size:12px;font-weight:600;color:#64748b;background:#fff;border:1px solid #e2e8f0;border-radius:7px">Group by Type</button>
</div>

<!-- Filters -->
<div class="filters">
  <input type="text" id="search" placeholder="Search articles or sites" oninput="render()" style="font-size:13px"/>
  <select id="site-sel" onchange="render()" style="font-size:12px;font-weight:500"></select>
  <div class="type-wrap" id="type-wrap">
    <button class="type-trigger" id="type-trigger" onclick="toggleTypeDropdown(event)">
      <span id="type-trigger-label">Content Type</span>
      <span style="font-size:10px;color:#94a3b8;margin-left:4px">&#9660;</span>
    </button>
    <div class="type-dropdown" id="type-dropdown"></div>
  </div>
  <button id="clear-btn" onclick="clearAll()" style="padding:7px 12px;font-size:12px;font-weight:600;color:#64748b;background:#fff;border:1px solid #e2e8f0;border-radius:7px;display:none">Clear all</button>
</div>

<!-- Live banner -->
<div class="live-banner" id="live-banner">
  <span style="font-size:12px;font-weight:600;color:#1d4ed8" id="live-text"></span>
  <button onclick="setLiveOnly(false)" style="font-size:11px;font-weight:700;color:#1d4ed8;background:none;border:1px solid #93c5fd;border-radius:5px;padding:2px 8px">Show all</button>
</div>

<!-- Table -->
<div id="table-area"></div>

<!-- Footer -->
<div style="margin-top:12px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
  <span style="font-size:11px;color:#94a3b8" id="footer-left"></span>
  <span style="font-size:11px;color:#94a3b8">Auto-refreshed daily via GitHub Actions</span>
</div>
</div>

<script>
const _D=JSON.parse(atob('__B64__'));
const ADDED=_D.a,REFRESHED=_D.r,REMOVED=_D.x;
const N=0,G=1,S=2,T=3,U=4,D=5,M=6,RT=7;
const AP="1211512877220282";
const MONTHS=["January","February","March","April","May","June","July","August","September","October","November","December"];
const MONTH_COLORS={January:"#6366f1",February:"#ec4899",March:"#10b981",April:"#f59e0b",May:"#06b6d4",June:"#8b5cf6",July:"#ef4444",August:"#f97316",September:"#14b8a6",October:"#a855f7",November:"#64748b",December:"#0ea5e9"};
const TYPE_ORDER=["TC","CS","Portrait TC","Hot Topic (Client)","Hot Topic","TP","News","KC","Condition Guide","NBI","PDx"];
const TYPE_COLORS={"TC":{bg:"#eff6ff",text:"#1d4ed8",border:"#bfdbfe"},"CS":{bg:"#faf5ff",text:"#7c3aed",border:"#e9d5ff"},"Portrait TC":{bg:"#f0fdf4",text:"#15803d",border:"#bbf7d0"},"Hot Topic":{bg:"#fff7ed",text:"#c2410c",border:"#fed7aa"},"Hot Topic (Client)":{bg:"#fef3c7",text:"#92400e",border:"#fde68a"},"News":{bg:"#f8fafc",text:"#475569",border:"#cbd5e1"},"TP":{bg:"#f0fdfa",text:"#0f766e",border:"#99f6e4"},"KC":{bg:"#ecfdf5",text:"#059669",border:"#6ee7b7"},"Condition Guide":{bg:"#fdf2f8",text:"#9d174d",border:"#fbcfe8"},"NBI":{bg:"#fff1f2",text:"#be123c",border:"#fecdd3"},"PDx":{bg:"#fff7ed",text:"#b45309",border:"#fed7aa"}};
const SITE_COLORS={MyMigraineTeam:"#7c3aed",ThisIsMenopause:"#db2777",MyAlopeciaTeam:"#0891b2",MyAtaxiaTeam:"#059669",myHSteam:"#d97706",MyOpioidRecoveryTeam:"#4f46e5",MyDesmoidTumorTeam:"#dc2626",MyHeartDiseaseTeam:"#e11d48",DiabetesTeam:"#2563eb",MyObesityTeam:"#9333ea",MySleepApneaTeam:"#0284c7",MyKidneyCancerTeam:"#be185d",MyOvarianCancerTeam:"#7c3aed",MyParkinsonsTeam:"#6d28d9",MyMyelomaTeam:"#b45309",MyEpilepsyTeam:"#b91c1c"};
const tc=t=>TYPE_COLORS[t]||{bg:"#f8fafc",text:"#475569",border:"#e2e8f0"};
const sc=s=>SITE_COLORS[s]||"#6b7280";
const LEGEND=[{type:"TC",desc:"Topic Center - group of related articles built around a condition, linked as a series"},{type:"CS",desc:"Channel Sponsorship - client-sponsored Topic Center, includes AIDA variants"},{type:"Portrait TC",desc:"Member Portrait TC - personal story articles featuring real community members"},{type:"Hot Topic",desc:"Standalone editorial or SEO-driven article"},{type:"Hot Topic (Client)",desc:"Standalone article commissioned and funded by a client"},{type:"TP",desc:"Treatment Page - structured reference page for a drug, lives at /treatments/"},{type:"News",desc:"News article tied to recent data, FDA approvals, or studies"},{type:"KC",desc:"Knowledge Center - reference or educational content"},{type:"Condition Guide",desc:"Comprehensive guide covering a condition end-to-end"},{type:"NBI",desc:"Native Brand Integration - branded content integrated into editorial"},{type:"PDx",desc:"Patient Diagnostics - content tied to a diagnostic initiative"}];

// Get current month name
const NOW=new Date();
const CUR_MONTH=MONTHS[NOW.getMonth()]||"January";
let state={tab:"added",month:CUR_MONTH,site:"All",types:new Set(),q:"",groupByType:false,liveOnly:false};

// Legend
(()=>{const lb=document.getElementById("legend-body");LEGEND.forEach(({type,desc})=>{const c=tc(type);lb.innerHTML+=`<div class="legend-row"><span class="badge" style="background:${c.bg};color:${c.text};border-color:${c.border};flex-shrink:0">${type}</span><span class="legend-desc">${desc}</span></div>`;});})();
function toggleLegend(){document.getElementById("legend-body").classList.toggle("shown");document.getElementById("legend-arrow").innerHTML=document.getElementById("legend-body").classList.contains("shown")?"&#9650;":"&#9660;";}

// Month dropdown
function buildMonthDropdown(){
  const dd=document.getElementById("month-dropdown");
  dd.innerHTML="";
  MONTHS.forEach(m=>{
    const addedCount=ADDED.filter(r=>r[M]===m).length;
    const div=document.createElement("div");
    div.className="month-option"+(m===state.month?" active":"");
    div.innerHTML=`<div style="font-weight:600">${m}</div><div class="month-counts">${addedCount} added</div>`;
    div.onclick=()=>{state.month=m;state.liveOnly=false;state.types=new Set();state.q="";document.getElementById("search").value="";updateMonthTrigger();updateTypeTrigger();document.getElementById("month-dropdown").classList.remove("open");document.getElementById("month-trigger").classList.remove("open");render();};
    dd.appendChild(div);
  });
}
function updateMonthTrigger(){
  const c=MONTH_COLORS[state.month]||"#6366f1";
  document.getElementById("month-dot").style.background=c;
  document.getElementById("month-trigger-label").textContent=state.month;
  document.querySelectorAll(".month-option").forEach(el=>{el.className="month-option"+(el.querySelector("div").textContent===state.month?" active":"");});
}
function toggleMonthDropdown(e){
  e.stopPropagation();
  const dd=document.getElementById("month-dropdown");
  const tr=document.getElementById("month-trigger");
  if(!dd.classList.contains("open")){buildMonthDropdown();}
  dd.classList.toggle("open");
  tr.classList.toggle("open");
}
document.addEventListener("click",e=>{
  if(!document.getElementById("month-selector-wrap").contains(e.target)){document.getElementById("month-dropdown").classList.remove("open");document.getElementById("month-trigger").classList.remove("open");}
  if(!document.getElementById("type-wrap").contains(e.target)){document.getElementById("type-dropdown").classList.remove("open");}
});
// Init trigger
(()=>{updateMonthTrigger();})();

// Site dropdown
const allSites=["All",...Array.from(new Set([...ADDED,...REFRESHED,...REMOVED].map(r=>r[S]).filter(Boolean))).sort()];
(()=>{const ss=document.getElementById("site-sel");allSites.forEach(s=>{const o=document.createElement("option");o.value=s;o.textContent=s==="All"?"All Sites":s;ss.appendChild(o);});ss.onchange=()=>{state.site=ss.value;render();};})();

// Multi-select type dropdown
function toggleTypeDropdown(e){e.stopPropagation();document.getElementById("type-dropdown").classList.toggle("open");}
function buildTypeDropdown(availTypes,countMap){
  const dd=document.getElementById("type-dropdown");dd.innerHTML="";
  const allDiv=document.createElement("div");allDiv.className="type-option";
  const allCb=document.createElement("input");allCb.type="checkbox";allCb.checked=state.types.size===0;
  const allSpan=document.createElement("span");allSpan.textContent="All Types";allSpan.style.fontWeight="600";
  allDiv.style.cssText="display:flex;flex-direction:row;align-items:center;gap:10px;padding:8px 12px;cursor:pointer;width:100%";
  allDiv.append(allCb,allSpan);
  allDiv.onclick=()=>{state.types=new Set();updateTypeTrigger();render();};
  dd.appendChild(allDiv);
  const div=document.createElement("div");div.style.cssText="height:1px;background:#f1f5f9;margin:4px 0";dd.appendChild(div);
  availTypes.forEach(type=>{
    const d=document.createElement("div");d.className="type-option";
    const cb=document.createElement("input");cb.type="checkbox";cb.checked=state.types.has(type);
    cb.onclick=e=>e.stopPropagation();
    cb.onchange=()=>{if(cb.checked)state.types.add(type);else state.types.delete(type);updateTypeTrigger();render();};
    const c=tc(type);
    const badge=document.createElement("span");badge.className="badge";
    badge.style.cssText=`background:${c.bg};color:${c.text};border-color:${c.border}`;badge.textContent=type;
    const pill=document.createElement("span");pill.className="type-count-pill";pill.textContent=countMap[type]||0;
    d.style.cssText="display:flex;align-items:center;gap:10px;padding:8px 12px;cursor:pointer;user-select:none";
    d.append(cb,badge,pill);
    d.onclick=()=>{cb.checked=!cb.checked;if(cb.checked)state.types.add(type);else state.types.delete(type);updateTypeTrigger();render();};
    dd.appendChild(d);
  });
}
function updateTypeTrigger(){
  const tr=document.getElementById("type-trigger");const lb=document.getElementById("type-trigger-label");
  if(state.types.size===0){tr.className="type-trigger";lb.textContent="Content Type";}
  else if(state.types.size===1){tr.className="type-trigger active";lb.textContent=[...state.types][0];}
  else{tr.className="type-trigger active";lb.innerHTML=`Content Type <span class="selected-count">${state.types.size}</span>`;}
}

// Filters
function siteF(r){return state.site==="All"||r[S]===state.site;}
function typeF(r){return state.types.size===0||state.types.has(r[T]);}
function searchF(r){if(!state.q)return true;const q=state.q.toLowerCase();return r[N].toLowerCase().includes(q)||(r[S]||"").toLowerCase().includes(q);}
function filterRows(rows){return rows.filter(r=>r[M]===state.month&&siteF(r)&&typeF(r)&&searchF(r));}

// Table
function typeBadge(type){const c=tc(type);return `<span class="badge" style="background:${c.bg};color:${c.text};border-color:${c.border}">${type}</span>`;}
function siteBadge(site){const c=sc(site);return `<span class="badge" style="background:${c}15;color:${c};border-color:${c}30">${site||"&mdash;"}</span>`;}
function buildTable(rows,isRemoved,hideType,startIdx){
  if(!rows.length)return`<div class="empty">No articles match the current filters.</div>`;
  let h=`<div style="border-radius:10px;overflow:hidden;border:1px solid #e2e8f0;box-shadow:0 1px 3px rgba(0,0,0,.05)"><table><thead><tr>
    <th style="width:32px">#</th><th>Article Title</th><th style="width:160px">Site</th>
    ${!hideType?'<th style="width:140px">Type</th>':''}
    ${isRemoved?'<th style="width:120px">Removal</th>':''}
    <th style="width:105px">Date</th><th style="width:82px;text-align:center">Link</th>
  </tr></thead><tbody>`;
  rows.forEach((r,i)=>{
    const hasUrl=r[U]&&r[U].trim();
    const href=hasUrl?r[U]:`https://app.asana.com/0/${AP}/${r[G]}`;
    const isArt=!!hasUrl;
    const ls=isArt?"background:#f0fdfa;color:#0f766e;border-color:#99f6e4":"background:#faf5ff;color:#7c3aed;border-color:#e9d5ff";
    h+=`<tr>
      <td style="color:#94a3b8;font-size:12px">${(startIdx||0)+i+1}</td>
      <td style="color:#1e293b;font-weight:500;line-height:1.4">${r[N]}</td>
      <td>${siteBadge(r[S])}</td>
      ${!hideType?`<td>${typeBadge(r[T])}</td>`:''}
      ${isRemoved?`<td><span class="badge" style="background:#fffbeb;color:#b45309;border-color:#fed7aa">${r[RT]||"&mdash;"}</span></td>`:''}
      <td style="color:#64748b;font-size:12px">${r[D]||'<span style="color:#cbd5e1;font-style:italic">TBD</span>'}</td>
      <td style="text-align:center"><a href="${href}" target="_blank" class="badge" style="${ls}">${isArt?"Article":"Asana"} &#8599;</a></td>
    </tr>`;
  });
  h+=`</tbody></table></div>`;return h;
}
function buildGrouped(rows,isRemoved){
  const groups={};rows.forEach(r=>{if(!groups[r[T]])groups[r[T]]=[];groups[r[T]].push(r);});
  const ordered=[...TYPE_ORDER.filter(t=>groups[t]),...Object.keys(groups).filter(t=>!TYPE_ORDER.includes(t))];
  let h="",idx=0;
  ordered.forEach(type=>{
    const gr=groups[type];const si=idx;idx+=gr.length;
    h+=`<div style="margin-bottom:14px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">${typeBadge(type)}<span style="font-size:12px;color:#94a3b8;font-weight:500">${gr.length} article${gr.length!==1?"s":""}</span></div>${buildTable(gr,isRemoved,true,si)}</div>`;
  });
  return h;
}

// Actions
function setLiveOnly(v){state.liveOnly=v;render();}
function toggleGroup(){state.groupByType=!state.groupByType;render();}
function clearAll(){state.q="";state.site="All";state.types=new Set();state.liveOnly=false;document.getElementById("search").value="";document.getElementById("site-sel").value="All";updateTypeTrigger();render();}
function clickStat(w){
  if(w==="added"){state.tab="added";state.liveOnly=false;}
  else if(w==="refreshed"){state.tab="refreshed";state.liveOnly=false;}
  else if(w==="removed"){state.tab="removed";state.liveOnly=false;}
  else if(w==="live"){state.tab="added";state.liveOnly=true;}
  state.q="";document.getElementById("search").value="";render();
}
function setTab(t){state.tab=t;state.liveOnly=false;render();}
document.getElementById("search").oninput=e=>{state.q=e.target.value;render();};

// Main render
function render(){
  const sF=r=>siteF(r);
  const mAdded    =ADDED.filter(r=>r[M]===state.month&&sF(r));
  const mRefreshed=REFRESHED.filter(r=>r[M]===state.month&&sF(r));
  const mRemoved  =REMOVED.filter(r=>r[M]===state.month&&sF(r));
  const fAdded    =filterRows(ADDED);
  const fRefreshed=filterRows(REFRESHED);
  const fRemoved  =filterRows(REMOVED);
  const fAddedL   =state.liveOnly?fAdded.filter(r=>r[U]&&r[U].trim()):fAdded;
  const curRows   =state.tab==="added"?fAddedL:state.tab==="refreshed"?fRefreshed:fRemoved;

  // Stats
  document.getElementById("stats").innerHTML=`
    <div class="stat" style="background:#f0fdfa;border-color:#99f6e4" onclick="clickStat('added')"><div class="stat-val" style="color:#0f766e">${mAdded.length}</div><div class="stat-lbl" style="color:#0f766e">New Articles &#8599;</div></div>
    <div class="stat" style="background:#faf5ff;border-color:#e9d5ff" onclick="clickStat('refreshed')"><div class="stat-val" style="color:#7c3aed">${mRefreshed.length}</div><div class="stat-lbl" style="color:#7c3aed">Refreshed &#8599;</div></div>
    <div class="stat" style="background:#fef2f2;border-color:#fecaca" onclick="clickStat('removed')"><div class="stat-val" style="color:#dc2626">${mRemoved.length}</div><div class="stat-lbl" style="color:#dc2626">Removals &#8599;</div></div>
    <div class="stat" style="background:${state.liveOnly?"#dbeafe":"#eff6ff"};border-color:${state.liveOnly?"#93c5fd":"#bfdbfe"}" onclick="clickStat('live')"><div class="stat-val" style="color:#1d4ed8">${mAdded.filter(r=>r[U]).length}</div><div class="stat-lbl" style="color:#1d4ed8">Live URLs &#8599;</div></div>`;

  // Tabs
  document.getElementById("tab-row").innerHTML=
    [{id:"added",label:"Added",count:fAddedL.length,c:"#0f766e",bg:"#dcfce7"},
     {id:"refreshed",label:"Refreshed",count:fRefreshed.length,c:"#7c3aed",bg:"#f3e8ff"},
     {id:"removed",label:"Removed",count:fRemoved.length,c:"#dc2626",bg:"#fee2e2"}]
    .map(t=>`<button class="tab${state.tab===t.id?" active":""}" style="--tab-c:${t.c};--tab-bg:${t.bg}" onclick="setTab('${t.id}')">${t.label}<span class="tab-count">${t.count}</span></button>`).join("");

  // Group btn
  const gb=document.getElementById("group-btn");
  gb.style.display=state.tab==="removed"?"none":"";
  gb.textContent=(state.groupByType?"✓ ":"")+"Group by Type";
  gb.style.color=state.groupByType?"#6366f1":"#64748b";
  gb.style.background=state.groupByType?"#eef2ff":"#fff";
  gb.style.borderColor=state.groupByType?"#c7d2fe":"#e2e8f0";

  // Type dropdown
  const baseForTypes=(state.tab==="added"?ADDED:state.tab==="refreshed"?REFRESHED:REMOVED).filter(r=>r[M]===state.month&&siteF(r)&&searchF(r));
  const availTypes=TYPE_ORDER.filter(t=>baseForTypes.some(r=>r[T]===t));
  const countMap={};baseForTypes.forEach(r=>{countMap[r[T]]=(countMap[r[T]]||0)+1;});
  buildTypeDropdown(availTypes,countMap);

  // Clear btn
  document.getElementById("clear-btn").style.display=(state.q||state.site!=="All"||state.types.size>0||state.liveOnly)?"":"none";

  // Live banner
  document.getElementById("live-banner").className="live-banner"+(state.liveOnly?" shown":"");
  document.getElementById("live-text").textContent=`Showing live URLs only (${fAddedL.length} articles)`;

  // Table
  const isRem=state.tab==="removed";
  document.getElementById("table-area").innerHTML=(state.groupByType&&!isRem)?buildGrouped(curRows,false):buildTable(curRows,isRem,false,0);

  // Footer
  document.getElementById("footer-left").innerHTML=`${curRows.length} article${curRows.length!==1?"s":""} &middot; <a href="https://app.asana.com/0/1211512877220282" target="_blank" style="color:#6366f1">Content Team 2026 Editorial Calendar</a> &middot; Read-only`;
}

render();
</script>
</body>
</html>"""


if __name__=="__main__":
    print("Fetching Asana data...")
    added,refreshed,removed,refresh_date=fetch_all_data()
    print("Generating HTML...")
    html=generate_html(added,refreshed,removed,refresh_date)
    output_path=os.environ.get("OUTPUT_PATH","article_tracker.html")
    with open(output_path,"w",encoding="utf-8") as f:
        f.write(html)
    print(f"\nSaved to: {output_path}")
    print(f"Refreshed: {refresh_date}")
