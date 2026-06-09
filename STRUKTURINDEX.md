# STRUKTURINDEX
Uppdaterad: 2026-06-09 13:42

## Filstruktur
```
STRUKTURINDEX.md  (1kb)
app.py  (163kb)
fix_duplicate.py  (3kb)
git_setup.py  (3kb)
index.html  (162kb)
patch_apply_and_push.py  (9kb)
projects.json  (301b)
projects/
  innob-bygg/
    project_settings.json  (157b)
  ishoo-creator/
    STRUKTURINDEX.md  (1kb)
    features.json  (23kb)
    memory/
      ARCHITECTURE.md  (3kb)
      CLAUDE.md  (2kb)
      DECISIONS.md  (1014b)
      FEATURES.md  (457b)
      PATTERNS.md  (2kb)
      SCHEMA.md  (1kb)
    project_settings.json  (152b)
    queue.json  (1kb)
settings.json  (388b)
startup_patch.py  (970b)
syntax_guard.py  (2kb)
```

## Strukturindex per fil

### app.py
```
  [3346 rader]
  r17: # ─── Dev Server State ───────────────────────────────────────────────
  r37: # ─── Settings ───────────────────────────────────────────────────────
  r84: REGLER Python/FastAPI: endpoints i app.py under rätt # ─── sektion, ag
  r216: def load_settings
  r232: def save_settings
  r236: def get_client
  r241: def model_for
  r248: # ─── Projekthantering ───────────────────────────────────────────────
  r250: def load_projects
  r260: def save_projects
  r263: def get_active_project
  r267: def project_dir
  r271: def load_memory
    r276: def sort_key
  r290: def load_features
  r294: def save_features
  r298: def add_feature
  r305: def add_subtasks
  r346: def load_project_settings
  r350: def save_project_settings
  r354: def slug
  r359: # ─── Git / Repo ─────────────────────────────────────────────────────
  r361: def repo_dir
  r364: def effective_repo_dir
  r370: def is_self_project
  r373: def git
  r377: def clone_or_pull
  r440: def _should_skip
  r443: def build_file_index
  r453: if "# ───" in s or "# ---" in s:
  r470: def get_file_section
  r499: def generate_strukturindex
  r558: "- Endpoints: `app.py` under rätt `# ───` sektion",
  r577: def read_codebase_context
  r669: def generate_diff_text
  r708: async def build_code
    r784: def _tag
  r819: def compute_diffs
  r835: def store_pending
  r839: def load_pending
  r843: def apply_and_push
  r951: # ─── Agenter ────────────────────────────────────────────────────────
  r953: def get_agents_from_settings
  r962: def _gather_live_context
  r1215: # ─── Domare — aktiveras efter max_iter misslyckanden ────────────────
  r1231: # ─── Post-build agenter (kör automatiskt efter varje bygge) ─────────
  r1286: def parse_fraga
  r1307: def parse_feature_klar
  r1316: def parse_system_klar
  r1326: def phases_summary
  r1334: def _ollama_available
  r1341: def run_agent_ollama
  r1372: def _parse_json_robust
  r1403: def run_agent
  r1435: @app.post
  r1436: async def apply_system_config
  r1466: # ─── WebSocket ──────────────────────────────────────────────────────

  r1468: class ConnectionManager
    r1469: def __init__
    r1470: async def connect
    r1471: def disconnect
    r1472: async def broadcast
  r1481: # ─── API ────────────────────────────────────────────────────────────
  r1483: @app.get
  r1484: async def root
  r1487: @app.get
  r1488: async def get_settings_api
  r1496: @app.post
  r1497: async def save_settings_api
  r1509: @app.get
  r1510: async def get_agents
  r1513: @app.post
  r1514: async def create_agent
  r1523: @app.put
  r1524: async def update_agent
  r1533: @app.delete
  r1534: async def delete_agent
  r1540: @app.get
  r1541: async def get_projects
  r1543: @app.post
  r1544: async def create_project
  r1579: @app.put
  r1580: async def set_active
  r1585: @app.delete
  r1586: async def delete_project
  r1593: @app.get
  r1594: async def get_project_settings
  r1597: @app.post
  r1598: async def update_project_settings
  r1612: @app.get
  r1613: async def get_features
  r1616: @app.post
  r1617: async def explain_backlog
  r1656: @app.delete
  r1657: async def delete_feature
  r1688: @app.post
  r1689: async def chat
  r1726: @app.post
  r1727: async def review_feature
    r1770: def ctx_for
    r1891: def is_fp
    r1894: def fp_overlap_with_spec
  r2021: @app.post
  r2022: async def build_feature
  r2043: async def _run_inspector_post_build
  r2100: def build_code_sync
  r2105: @app.post
  r2106: async def push_feature
    r2122: async def _regen_arch
    r2149: async def _regen_index
  r2165: @app.post
  r2166: async def rebuild_strukturindex
  r2181: # ─── Vercel Preview ─────────────────────────────────────────────────
  r2183: @app.get
  r2184: async def get_preview
    r2202: def fetch_latest_deployment
    r2221: def fetch_prod_deployment
  r2244: @app.websocket
  r2245: async def ws_endpoint
  r2251: # ─── Feature Queue ──────────────────────────────────────────────────
  r2253: def load_queue
  r2257: def save_queue
  r2261: @app.get
  r2262: async def get_queue
  r2266: @app.post
  r2267: async def add_to_queue
  r2279: @app.delete
  r2280: async def remove_from_queue
  r2287: @app.put
  r2288: async def reorder_queue
  r2294: # ─── Feature Suggestions ────────────────────────────────────────────
  r2308: @app.post
  r2309: async def get_suggestions
  r2329: # ─── Architecture Map ───────────────────────────────────────────────
  r2331: def load_architecture
  r2335: def save_architecture
  r2338: def update_features_md
  r2390: @app.post
  r2391: async def onboard_project
  r2441: @app.get
  r2442: async def get_architecture
  r2447: @app.post
  r2448: async def update_architecture
  r2454: @app.post
  r2455: async def generate_architecture
  r2487: # ─── Lokal Dev Server ───────────────────────────────────────────────
  r2489: @app.post
  r2490: async def start_dev_server
  r2512: @app.post
  r2513: async def stop_dev_server
  r2530: @app.get
  r2531: async def dev_server_status
  r2537: # ─── Felklistraren — auto-fix error ─────────────────────────────────
  r2550: @app.post
  r2551: async def fix_error
  r2582: # ─── Versionshistorik & Revert ──────────────────────────────────────
  r2584: @app.get
  r2585: async def git_log
  r2600: @app.get
  r2601: async def git_status
  r2619: @app.post
  r2620: async def git_revert
  r2639: @app.get
  r2640: async def ollama_status
  r2653: # ─── Konsultation — agenter som rena konsulter (aldrig blockerande) ─
  r2671: @app.post
  r2672: async def consult_feature
  r2787: # ─── Spec-granskare ─────────────────────────────────────────────────
  r2804: @app.post
  r2805: async def spec_review
  r2829: # ─── Build Verification Loop ────────────────────────────────────────
  r2831: def run_npm_build
  r2869: @app.post
  r2870: async def build_verify
  r2989: # ─── System Health Check ────────────────────────────────────────────
  r2991: @app.get
  r2992: async def system_health
  r3038: @app.post
  r3039: async def git_push_simple
  r3073: @app.post
  r3074: async def git_push_direct
  r3109: def _read_project_files
  r3144: @app.post
  r3145: async def code_iterator
  r3160: async def _run_code_iterator_bg
  r3294: @app.get
  r3295: async def get_arch_by_pid
  r3299: @app.put
  r3300: async def save_arch_by_pid
  r3305: @app.post
  r3306: async def generate_arch_by_pid
  r3326: @app.on_event
  r3327: async def start_file_watcher
    r3328: async def _watch
```

### patch_apply_and_push.py
```
  [210 rader]
  r16: def create_patched_apply_and_push
    r29: async def apply_and_push_async
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

### syntax_guard.py
```
  [93 rader]
  r12: def validate_python_syntax
  r73: def validate_file_changes
```

### startup_patch.py
```
  [30 rader]
  r7: def apply_syntax_guard_patch
```

## Konventioner

- Endpoints: `app.py` under rätt `# ───` sektion
- Agenter: DEFAULT_AGENTS eller POST_BUILD_AGENTS
- Helpers: nära relaterade funktioner
