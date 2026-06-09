# STRUKTURINDEX
Uppdaterad: 2026-06-09 12:59

## Filstruktur
```
STRUKTURINDEX.md  (9kb)
app.py  (154kb)
fix_duplicate.py  (3kb)
git_setup.py  (3kb)
index.html  (152kb)
projects.json  (301b)
projects/
  innob-bygg/
    project_settings.json  (157b)
  ishoo-creator/
    STRUKTURINDEX.md  (9kb)
    features.json  (1kb)
    memory/
      ARCHITECTURE.md  (3kb)
      CLAUDE.md  (2kb)
      DECISIONS.md  (1014b)
      FEATURES.md  (228b)
      PATTERNS.md  (2kb)
      SCHEMA.md  (1kb)
    project_settings.json  (152b)
    queue.json  (1kb)
settings.json  (388b)
```

## Strukturindex per fil

### app.py
```
  [3197 rader]
  r17: # ─── Dev Server State ───────────────────────────────────────────────
  r36: # ─── Settings ───────────────────────────────────────────────────────
  r83: REGLER Python/FastAPI: endpoints i app.py under rätt # ─── sektion, ag
  r197: def load_settings
  r213: def save_settings
  r217: def get_client
  r222: def model_for
  r229: # ─── Projekthantering ───────────────────────────────────────────────
  r231: def load_projects
  r241: def save_projects
  r244: def get_active_project
  r248: def project_dir
  r252: def load_memory
    r257: def sort_key
  r271: def load_features
  r275: def save_features
  r279: def add_feature
  r286: def add_subtasks
  r327: def load_project_settings
  r331: def save_project_settings
  r335: def slug
  r340: # ─── Git / Repo ─────────────────────────────────────────────────────
  r342: def repo_dir
  r345: def effective_repo_dir
  r351: def is_self_project
  r354: def git
  r358: def clone_or_pull
  r421: def _should_skip
  r424: def build_file_index
  r434: if "# ───" in s or "# ---" in s:
  r451: def get_file_section
  r480: def generate_strukturindex
  r539: "- Endpoints: `app.py` under rätt `# ───` sektion",
  r558: def read_codebase_context
  r650: def generate_diff_text
  r681: async def build_code
    r719: def _tag
  r752: def compute_diffs
  r768: def store_pending
  r772: def load_pending
  r776: def apply_and_push
  r832: # ─── Agenter ────────────────────────────────────────────────────────
  r834: def get_agents_from_settings
  r843: def _gather_live_context
  r1070: # ─── Domare — aktiveras efter max_iter misslyckanden ────────────────
  r1086: # ─── Post-build agenter (kör automatiskt efter varje bygge) ─────────
  r1141: def parse_fraga
  r1162: def parse_feature_klar
  r1171: def parse_system_klar
  r1181: def phases_summary
  r1189: def _ollama_available
  r1196: def run_agent_ollama
  r1227: def _parse_json_robust
  r1258: def run_agent
  r1290: @app.post
  r1291: async def apply_system_config
  r1321: # ─── WebSocket ──────────────────────────────────────────────────────

  r1323: class ConnectionManager
    r1324: def __init__
    r1325: async def connect
    r1326: def disconnect
    r1327: async def broadcast
  r1336: # ─── API ────────────────────────────────────────────────────────────
  r1338: @app.get
  r1339: async def root
  r1342: @app.get
  r1343: async def get_settings_api
  r1351: @app.post
  r1352: async def save_settings_api
  r1364: @app.get
  r1365: async def get_agents
  r1368: @app.post
  r1369: async def create_agent
  r1378: @app.put
  r1379: async def update_agent
  r1388: @app.delete
  r1389: async def delete_agent
  r1395: @app.get
  r1396: async def get_projects
  r1398: @app.post
  r1399: async def create_project
  r1434: @app.put
  r1435: async def set_active
  r1440: @app.delete
  r1441: async def delete_project
  r1448: @app.get
  r1449: async def get_project_settings
  r1452: @app.post
  r1453: async def update_project_settings
  r1467: @app.get
  r1468: async def get_features
  r1471: @app.post
  r1472: async def explain_backlog
  r1511: @app.delete
  r1512: async def delete_feature
  r1543: @app.post
  r1544: async def chat
  r1577: @app.post
  r1578: async def review_feature
    r1621: def ctx_for
    r1742: def is_fp
    r1745: def fp_overlap_with_spec
  r1872: @app.post
  r1873: async def build_feature
  r1894: async def _run_inspector_post_build
  r1951: def build_code_sync
  r1956: @app.post
  r1957: async def push_feature
    r1973: async def _regen_arch
    r2000: async def _regen_index
  r2016: @app.post
  r2017: async def rebuild_strukturindex
  r2032: # ─── Vercel Preview ─────────────────────────────────────────────────
  r2034: @app.get
  r2035: async def get_preview
    r2053: def fetch_latest_deployment
    r2072: def fetch_prod_deployment
  r2095: @app.websocket
  r2096: async def ws_endpoint
  r2102: # ─── Feature Queue ──────────────────────────────────────────────────
  r2104: def load_queue
  r2108: def save_queue
  r2112: @app.get
  r2113: async def get_queue
  r2117: @app.post
  r2118: async def add_to_queue
  r2130: @app.delete
  r2131: async def remove_from_queue
  r2138: @app.put
  r2139: async def reorder_queue
  r2145: # ─── Feature Suggestions ────────────────────────────────────────────
  r2159: @app.post
  r2160: async def get_suggestions
  r2180: # ─── Architecture Map ───────────────────────────────────────────────
  r2182: def load_architecture
  r2186: def save_architecture
  r2189: def update_features_md
  r2241: @app.post
  r2242: async def onboard_project
  r2292: @app.get
  r2293: async def get_architecture
  r2298: @app.post
  r2299: async def update_architecture
  r2305: @app.post
  r2306: async def generate_architecture
  r2338: # ─── Lokal Dev Server ───────────────────────────────────────────────
  r2340: @app.post
  r2341: async def start_dev_server
  r2363: @app.post
  r2364: async def stop_dev_server
  r2381: @app.get
  r2382: async def dev_server_status
  r2388: # ─── Felklistraren — auto-fix error ─────────────────────────────────
  r2401: @app.post
  r2402: async def fix_error
  r2433: # ─── Versionshistorik & Revert ──────────────────────────────────────
  r2435: @app.get
  r2436: async def git_log
  r2451: @app.get
  r2452: async def git_status
  r2470: @app.post
  r2471: async def git_revert
  r2490: @app.get
  r2491: async def ollama_status
  r2504: # ─── Konsultation — agenter som rena konsulter (aldrig blockerande) ─
  r2522: @app.post
  r2523: async def consult_feature
  r2638: # ─── Spec-granskare ─────────────────────────────────────────────────
  r2655: @app.post
  r2656: async def spec_review
  r2680: # ─── Build Verification Loop ────────────────────────────────────────
  r2682: def run_npm_build
  r2720: @app.post
  r2721: async def build_verify
  r2840: # ─── System Health Check ────────────────────────────────────────────
  r2842: @app.get
  r2843: async def system_health
  r2889: @app.post
  r2890: async def git_push_simple
  r2924: @app.post
  r2925: async def git_push_direct
  r2960: def _read_project_files
  r2995: @app.post
  r2996: async def code_iterator
  r3011: async def _run_code_iterator_bg
  r3145: @app.get
  r3146: async def get_arch_by_pid
  r3150: @app.put
  r3151: async def save_arch_by_pid
  r3156: @app.post
  r3157: async def generate_arch_by_pid
  r3177: @app.on_event
  r3178: async def start_file_watcher
    r3179: async def _watch
```

### fix_duplicate.py
```
  [118 rader]
```

### git_setup.py
```
  [110 rader]
  r55: def git
```

## Konventioner

- Endpoints: `app.py` under rätt `# ───` sektion
- Agenter: DEFAULT_AGENTS eller POST_BUILD_AGENTS
- Helpers: nära relaterade funktioner
