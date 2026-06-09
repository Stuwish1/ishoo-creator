<response>
<summary>Implementerar 3-fas pipeline med tabbar (Design → Bygg → QA) med godkännande mellan faser, fas-state i pipeline_state.json, nya WebSocket-endpoints, och tab-UI i index.html</summary>
<file>
  <path>app.py</path>
  <action>modify</action>
  <description>Lägger till tre nya endpoints för pipeline-faser samt pipeline_state.json-persistering efter System Health Check-sektionen</description>
  <content>
#!/usr/bin/env python3
"""
Ishoo Creator — Lokal Agent Backend v4 (Settings Edition)
==========================================================
Allt konfigurerbart inifrån UI:
- Settings (API-nycklar, git-info, modeller, max iterationer)
- Agent CRUD (lägg till / redigera / ta bort agenter)
- Dev/Prod branch-separation
- Per-projekt Supabase-konfiguration
"""

import os, json, asyncio, re, difflib, subprocess, threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ─── Dev Server State ────────────────────────────────────────────────────────
_dev_server_proc = None
_dev_server_pid_lock = threading.Lock()

import anthropic
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Ishoo Creator")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PROJECTS_FILE = Path("projects.json")
PROJECTS_DIR  = Path("projects")
SETTINGS_FILE = Path("settings.json")

SONNET_DEFAULT = "claude-sonnet-4-6"
HAIKU_DEFAULT  = "claude-haiku-4-5-20251001"

# ─── Settings ─────────────────────────────────────────────────────────────────

DEFAULT_AGENTS = [

    # ══ STEG 0: SPEC-GRANSKNING (kör alltid, kan stoppa pipelinen direkt) ══════

    # ── Kravanalytikorn ──────────────────────────────────────────────────────────
    {"id":"kravanalytiker","name":"Kravanalytikorn","emoji":"🔍","model":"haiku","enabled":True,
     "prompt":'''Du granskar om spec är byggbar. Var EXTREMT generös.

Kod-fixar, bugg-fixar, tekniska förbättringar och iterativa ändringar GODKÄNNS alltid.
AVVISAD HIGH ENBART om: spec är helt tom (0-3 ord utan mening).
I alla andra fall returnerar du GODKÄND.

Returnera ENBART JSON: {"status":"GODKÄND","findings":[],"severity":"LOW","suggestions":[]}'''},

    # ── Beroendeanalytikorn ──────────────────────────────────────────────────────
    {"id":"beroendeanalytiker","name":"Beroendeanalytikorn","emoji":"🔗","model":"sonnet","enabled":True,
     "prompt":'''Du ansvarar ENBART för att identifiera beroenden som måste finnas INNAN denna feature kan byggas.

Kontrollera ALLA dessa kategorier:
1. FEATURES: Kräver denna feature att en annan feature är byggd och klar?
2. DATABAS: Krävs specifika tabeller, kolumner, relationer eller RLS-policies?
3. PACKAGES: Krävs npm-paket eller Python-bibliotek som inte är installerade?
4. ENV-VARIABLER: Krävs miljövariabler som kanske saknas (.env)?
5. API-ENDPOINTS: Kräver denna feature endpoints som inte finns än?
6. TYPER/INTERFACES: Krävs TypeScript-typer eller interfaces som saknas?

GODKÄND om: alla beroenden finns på plats.
AVVISAD om: minst ett beroende saknas — lista EXAKT vad som saknas och måste skapas först.

Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."],"saknade_beroenden":[{"typ":"feature"/"db"/"package"/"env"/"api"/"typ","namn":"...","beskrivning":"..."}]}'''},

    # ══ STEG 1: TEKNISK GRANSKNING (parallell) ═══════════════════════════════════

    # ── Strukturnavigatorn ───────────────────────────────────────────────────────
    {"id":"strukturnavigator","name":"Strukturnavigatorn","emoji":"🗺️","model":"sonnet","enabled":True,
     "prompt":'''Du ansvarar ENBART för kodbas-struktur och filnavigation.

JOBB (i ordning):
1. Kontrollera om STRUKTURINDEX.md finns. Saknas den → AVVISAD HIGH.
2. Bestäm exakt var varje ny fil placeras (mapp + filnamn).
3. Identifiera befintliga filer som påverkas.
4. Verifiera att namnkonventioner följs (PascalCase komponenter, camelCase hooks etc).
5. Om nödvändig mappstruktur saknas → AVVISAD med exakt vad som skapas först.

REGLER React/TypeScript: src/components/[domän]/[Komponent].tsx, src/pages/, src/hooks/use[Namn].ts, src/lib/, src/types/, src/utils/
REGLER Python/FastAPI: endpoints i app.py under rätt # ─── sektion, agenter i DEFAULT_AGENTS

Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."],"filplacering":[{"fil":"src/...","typ":"create"/"modify","anledning":"..."}]}'''},

    # ── Säkerhet ─────────────────────────────────────────────────────────────────
    {"id":"security","name":"Säkerhetsansvarig","emoji":"🔒","model":"sonnet","enabled":True,
     "prompt":'Du ansvarar ENBART för säkerhet. Granska: SQL-injection, XSS, exponerade API-nycklar, saknad RLS i Supabase, felaktig autentisering/auktorisering, CSRF, osäker direktlänkning till resurser. Kommentera inget annat. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},

    # ── Databas ──────────────────────────────────────────────────────────────────
    {"id":"dba","name":"DBA","emoji":"🗄️","model":"ollama:qwen2.5-coder:7b","enabled":True,
     "prompt":'''Du ansvarar ENBART för databasfrågor.
STEG 1: Kräver denna feature persistent datalagring?
STEG 2a — JA + ingen DB: AVVISAD HIGH, beskriv exakt vilka tabeller/kolumner som behövs.
STEG 2b — JA + DB finns: granska migreringar, saknade index, N+1, saknad RLS.
STEG 2c — NEJ: GODKÄND "Ingen databas krävs."
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'''},

    # ── Arkitektur ───────────────────────────────────────────────────────────────
    {"id":"architect","name":"Arkitekt","emoji":"🏗️","model":"sonnet","enabled":True,
     "prompt":'Du ansvarar ENBART för systemarkitektur. Granska: separation of concerns, onödig prop drilling, felaktiga modulberoenden, duplicerad affärslogik, felplacerad kod. Kommentera inte säkerhet, prestanda eller UX. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},

    # ── Ansvarsfördelning ────────────────────────────────────────────────────────
    {"id":"ansvarsfordelning","name":"Ansvarsfördelning","emoji":"⚖️","model":"sonnet","enabled":True,
     "prompt":'Du ansvarar ENBART för Single Responsibility. Granska: har varje funktion/komponent ett enda ansvar? God Objects? Otydliga gränssnitt mellan lager? Saknade abstraktioner? Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},

    # ── TypeScript-typer ─────────────────────────────────────────────────────────
    {"id":"typgranskare","name":"Typgranskaren","emoji":"🔷","model":"ollama:qwen2.5-coder:7b","enabled":True,
     "prompt":'''Du ansvarar ENBART för TypeScript-typsäkerhet.
Granska: användning av `any` (förbjudet utom med explicit motivering), saknade interface/type-definitioner, inkonsekventa typer mot befintlig src/types/, icke-exporterade typer som borde vara delade, implicit `any` från bibliotek utan types, union types som borde vara enums.
GODKÄND om: inga `any`, alla nya typer definierade och exporterade korrekt.
AVVISAD om: `any` används, typer saknas, eller typer är inkompatibla med befintlig kod.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'''},

    # ── Felhantering ─────────────────────────────────────────────────────────────
    {"id":"felhantering","name":"Felhanteringsgranskaren","emoji":"🚨","model":"ollama:qwen2.5-coder:7b","enabled":True,
     "prompt":'''Du ansvarar ENBART för felhantering och robusthet.
Granska:
- Saknar API-anrop try/catch?
- Visas fel för användaren (toast, error state, fallback UI)?
- Finns loading-state under async-operationer?
- Hanteras null/undefined-värden defensivt?
- Finns tomma-listan-state (empty state) när data saknas?
- Kraschar UI om ett enskilt fält saknas i API-svaret?
GODKÄND om: alla async-operationer har felhantering och UI har error/loading/empty states.
AVVISAD om: saknat try/catch, ingen error state, eller UI kan krascha på null-data.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'''},

    # ── Tillgänglighet ───────────────────────────────────────────────────────────
    {"id":"tillganglighet","name":"Tillgänglighetsgranskaren","emoji":"♿","model":"haiku","enabled":True,
     "prompt":'''Du ansvarar ENBART för tillgänglighet (a11y/WCAG).
Granska: saknade aria-label/aria-describedby på knappar och ikoner, bilder utan alt-text, formulärfält utan kopplad label, otillräcklig färgkontrast (under 4.5:1), element som inte är nåbara med tangentbord (Tab/Enter/Escape), modaler utan fokushantering (focus trap), dynamisk text som skärmläsare missar.
GODKÄND om: alla interaktiva element är tillgängliga och ARIA används korrekt.
AVVISAD om: kritiska a11y-problem som utestänger användare med hjälpmedel.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'''},

    # ── Konfiguration ────────────────────────────────────────────────────────────
    {"id":"konfiguration","name":"Konfigurationsgranskaren","emoji":"⚙️","model":"ollama:qwen2.5-coder:7b","enabled":True,
     "prompt":'''Du ansvarar ENBART för konfiguration och hårdkodade värden.
Granska: hårdkodade URL:er (ska vara env-variabler), hårdkodade API-nycklar (KRITISKT), magiska strängar/siffror som borde vara konstanter, timeout-värden som borde vara konfigurerbara, feature flags som saknas, .env.example som inte uppdaterats med nya variabler.
GODKÄND om: inga hårdkodade secrets, alla env-variabler dokumenterade i .env.example.
AVVISAD HIGH om: API-nyckel eller URL hårdkodad. AVVISAD MEDIUM om: magiska värden saknar konstanter.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'''},

    # ── Prestanda ────────────────────────────────────────────────────────────────
    {"id":"performance","name":"Prestanda","emoji":"⚡","model":"ollama:qwen2.5-coder:7b","enabled":True,
     "prompt":'Du ansvarar ENBART för prestanda. Granska: onödiga re-renders, saknad useMemo/useCallback, tunga beräkningar i render-loop, stora bundle-imports, saknad lazy loading, långsamma queries, saknad paginering. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},

    # ── UX ───────────────────────────────────────────────────────────────────────
    {"id":"ux","name":"UX Designern","emoji":"🎨","model":"sonnet","enabled":True,
     "prompt":'''Du är UX Designer. Analysera feature-spec ur användarens perspektiv.

Ditt jobb:
1. Användarflöde: beskriv EXAKT steg-för-steg hur användaren interagerar
2. Friktionspunkter: var kan användaren fastna, bli förvirrad eller göra fel?
3. Feedback-design: hur vet användaren att något hände? (loading, success, error)
4. Accessibility: tangentbordsnavigering, aria-labels, kontrast
5. Microcopy: exakta knapp-texter, felmeddelanden, tooltips på svenska

Ge SPECIFIKA förbättringsförslag med exakta UI-texter och interaktionsmönster.

Returnera ENBART JSON: {"status":"GODKÄND","findings":["Konkret UX-observation"],"severity":"LOW","suggestions":["Exakt förbättring med UI-text och flöde"]}'''},

    # ── Mobil ────────────────────────────────────────────────────────────────────
    {"id":"mobile","name":"Mobil/Fält","emoji":"📱","model":"haiku","enabled":True,
     "prompt":'Du ansvarar ENBART för mobil/fält. Granska: touchmål under 44px, läsbarhet i solljus, för många steg, s