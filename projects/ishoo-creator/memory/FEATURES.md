# Features — Ishoo Creator v6

*Dessa features finns i den nuvarande versionen.*

## Klara (main)
- ✅ **Multi-agent review pipeline** — 10 parallella agenter (Security, DBA, UX, Arkitekt, Affärslogik, Testgranskare, Prestandagranskare, Mobil/Fält, Konfliktgranskare, Besiktningsman)
- ✅ **Spec-granskare** — kontrollerar spec-tydlighet och acceptanskriterier INNAN byggstart
- ✅ **Snickaren** — kodgenerering via Claude + diff-visning
- ✅ **Build-verify loop** — npm build + auto-fix tills grönt
- ✅ **6-fils minnessystem** — CLAUDE.md, SCHEMA.md, PATTERNS.md, ARCHITECTURE.md, DECISIONS.md, FEATURES.md
- ✅ **Projekt-onboarding wizard** — Projektledaren ställer 5 frågor, genererar all dokumentation
- ✅ **Feature-kö** — prioritetsordnad kö med drag-to-reorder
- ✅ **Lokal dev server** — start/stop npm run dev, live preview i modal
- ✅ **Felklistraren** — klistra konsolfel → Snickaren fixar automatiskt
- ✅ **Versionshistorik** — git log + force-revert till valfri commit
- ✅ **Auto-uppdatera ARCHITECTURE.md** — efter varje push
- ✅ **Dev/Prod branch-separation** — dev-branch + merge till main

## Möjliga förbättringar (v1)
- [ ] **TypeScript-typkontroll** — kör tsc --noEmit och visa fel i UI
- [ ] **Supabase-tabell-wizard** — skapa tabeller via chat
- [ ] **Screenshot → feature-spec** — ladda upp bild, AI genererar spec
- [ ] **Multi-fil diff** — sida vid sida-jämförelse
- [ ] **Agent-prestanda-statistik** — visa vilka agenter avvisar mest
- [ ] **Offline-läge** — jobba utan internet, synka senare

## Framtida (v2)
- [ ] **Självuppdatering via CI** — Ishoo Creator pushar till sig själv, GitHub Actions kör tester
- [ ] **Plugin-system** — installerbara agenter
- [ ] **Team-läge** — flera användare på samma projekt
