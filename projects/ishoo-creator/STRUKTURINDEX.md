# STRUKTURINDEX
Uppdaterad: 2026-06-09 12:50

## Filstruktur
```
app.py  (151kb)
fix_duplicate.py  (3kb)
git_setup.py  (3kb)
index.html  (152kb)
projects.json  (301b)
projects/
  innob-bygg/
    project_settings.json  (157b)
  ishoo-creator/
    features.json  (30kb)
    memory/
      ARCHITECTURE.md  (3kb)
      CLAUDE.md  (2kb)
      DECISIONS.md  (1014b)
      FEATURES.md  (1kb)
      PATTERNS.md  (2kb)
      SCHEMA.md  (1kb)
    project_settings.json  (152b)
    queue.json  (1kb)
settings.json  (388b)
```

## Strukturindex per fil

### app.py
```
  [3128 rader]
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
  r1001: # ─── Domare — aktiveras efter max_iter misslyckanden ────────────────
  r1017: # ─── Post-build agenter (kör automatiskt efter varje bygge) ─────────
  r1072: def parse_fraga
  r1093: def parse_feature_klar
  r1102: def parse_system_klar
  r1112: def phases_summary
  r1120: def _ollama_available
  r1127: def run_agent_ollama
  r1158: def _parse_json_robust
  r1189: def run_agent
  r1221: @app.post
  r1222: async def apply_system_config
  r1252: # ─── WebSocket ──────────────────────────────────────────────────────

  r1254: class ConnectionManager
    r1255: def __init__
    r1256: async def connect
    r1257: def disconnect
    r1258: async def broadcast
  r1267: # ─── API ────────────────────────────────────────────────────────────
  r1269: @app.get
  r1270: async def root
  r1273: @app.get
  r1274: async def get_settings_api
  r1282: @app.post
  r1283: async def save_settings_api
  r1295: @app.get
  r1296: async def get_agents
  r1299: @app.post
  r1300: async def create_agent
  r1309: @app.put
  r1310: async def update_agent
  r1319: @app.delete
  r1320: async def delete_agent
  r1326: @app.get
  r1327: async def get_projects
  r1329: @app.post
  r1330: async def create_project
  r1365: @app.put
  r1366: async def set_active
  r1371: @app.delete
  r1372: async def delete_project
  r1379: @app.get
  r1380: async def get_project_settings
  r1383: @app.post
  r1384: async def update_project_settings
  r1398: @app.get
  r1399: async def get_features
  r1402: @app.post
  r1403: async def explain_backlog
  r1442: @app.delete
  r1443: async def delete_feature
  r1474: @app.post
  r1475: async def chat
  r1508: @app.post
  r1509: async def review_feature
    r1552: def ctx_for
    r1673: def is_fp
    r1676: def fp_overlap_with_spec
  r1803: @app.post
  r1804: async def build_feature
  r1825: async def _run_inspector_post_build
  r1882: def build_code_sync
  r1887: @app.post
  r1888: async def push_feature
    r1904: async def _regen_arch
    r1931: async def _regen_index
  r1947: @app.post
  r1948: async def rebuild_strukturindex
  r1963: # ─── Vercel Preview ─────────────────────────────────────────────────
  r1965: @app.get
  r1966: async def get_preview
    r1984: def fetch_latest_deployment
    r2003: def fetch_prod_deployment
  r2026: @app.websocket
  r2027: async def ws_endpoint
  r2033: # ─── Feature Queue ──────────────────────────────────────────────────
  r2035: def load_queue
  r2039: def save_queue
  r2043: @app.get
  r2044: async def get_queue
  r2048: @app.post
  r2049: async def add_to_queue
  r2061: @app.delete
  r2062: async def remove_from_queue
  r2069: @app.put
  r2070: async def reorder_queue
  r2076: # ─── Feature Suggestions ────────────────────────────────────────────
  r2090: @app.post
  r2091: async def get_suggestions
  r2111: # ─── Architecture Map ───────────────────────────────────────────────
  r2113: def load_architecture
  r2117: def save_architecture
  r2120: def update_features_md
  r2172: @app.post
  r2173: async def onboard_project
  r2223: @app.get
  r2224: async def get_architecture
  r2229: @app.post
  r2230: async def update_architecture
  r2236: @app.post
  r2237: async def generate_architecture
  r2269: # ─── Lokal Dev Server ───────────────────────────────────────────────
  r2271: @app.post
  r2272: async def start_dev_server
  r2294: @app.post
  r2295: async def stop_dev_server
  r2312: @app.get
  r2313: async def dev_server_status
  r2319: # ─── Felklistraren — auto-fix error ─────────────────────────────────
  r2332: @app.post
  r2333: async def fix_error
  r2364: # ─── Versionshistorik & Revert ──────────────────────────────────────
  r2366: @app.get
  r2367: async def git_log
  r2382: @app.get
  r2383: async def git_status
  r2401: @app.post
  r2402: async def git_revert
  r2421: @app.get
  r2422: async def ollama_status
  r2435: # ─── Konsultation — agenter som rena konsulter (aldrig blockerande) ─
  r2453: @app.post
  r2454: async def consult_feature
  r2569: # ─── Spec-granskare ─────────────────────────────────────────────────
  r2586: @app.post
  r2587: async def spec_review
  r2611: # ─── Build Verification Loop ────────────────────────────────────────
  r2613: def run_npm_build
  r2651: @app.post
  r2652: async def build_verify
  r2771: # ─── System Health Check ────────────────────────────────────────────
  r2773: @app.get
  r2774: async def system_health
  r2820: @app.post
  r2821: async def git_push_simple
  r2855: @app.post
  r2856: async def git_push_direct
  r2891: def _read_project_files
  r2926: @app.post
  r2927: async def code_iterator
  r2942: async def _run_code_iterator_bg
  r3076: @app.get
  r3077: async def get_arch_by_pid
  r3081: @app.put
  r3082: async def save_arch_by_pid
  r3087: @app.post
  r3088: async def generate_arch_by_pid
  r3108: @app.on_event
  r3109: async def start_file_watcher
    r3110: async def _watch
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
