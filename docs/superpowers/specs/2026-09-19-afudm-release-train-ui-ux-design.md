# AfuDM Release Train UI/UX Design

## Status

Approved design direction. This document defines the user-facing contract for features introduced from v1.0.0 through v2.3.0.

## Goal

Every shipped capability must be visible and operable in the AfuDM interface. A feature is not considered user-complete until the UI can display its state, invoke its primary action, expose relevant settings, and show errors or unavailable states.

## Design principles

- English-first labels with complete Turkish translations through the existing i18n layer.
- Preserve the current dark, compact download-manager layout and blue primary-action color.
- Keep the main download list fast; advanced controls belong in the selected-download details panel.
- Use progressive disclosure: overview first, advanced controls in tabs or expandable sections.
- Every remote, engine, plugin, automation, and rule action has loading, success, unavailable, and error states.
- Desktop and mobile expose the same capabilities through adapted navigation, not separate behavior.

## Information architecture

### Primary navigation

- Dashboard — global throughput, active jobs, health summary.
- Downloads — all, downloading, paused, video, torrent, completed, failed.
- Automation — scheduled and event-driven jobs.
- Rules — rule list, editor, simulation and execution history.
- Plugins — installed, available, permissions and updates.
- System — Headless Server, Windows Integration, Reliability & Security.
- Settings — language, appearance, engine, network, storage and account/API settings.

### Selected-download details

The selected item opens a details surface with these capability tabs:

- Overview
- Files
- Trackers
- Rules
- Automation
- Logs

The surface is a right-side panel on desktop and a bottom sheet or full-screen route on mobile/PWA.

## Release-to-UI mapping

| Release | User-facing area | Required controls |
|---|---|---|
| v1.0.0 Portable Core | Dashboard, Downloads, Settings | Start, pause, resume, remove, storage and portable-mode state |
| v1.1.0 Browser Integration | Browser Integration settings | Extension status, browser install, permissions, test connection |
| v1.2.0 Download Engine | Engine settings, download details | Engine status, concurrency, speed limits, retry controls |
| v1.3.0 Remote & Mobile | Remote settings, Mobile/PWA navigation | Pairing, endpoint, connection state, mobile actions |
| v1.3.1 Performance & Stability | System health | Performance counters, warnings, recovery state |
| v1.4.0 Foundation & Network Core | Network settings | Connectivity, proxy, IPv4/IPv6, diagnostics |
| v1.5.0 LinkGrabber | LinkGrabber panel | Paste/import links, queue preview, duplicate handling, validation errors |
| v1.6.0 Video Pro | Video details and settings | Format, quality, audio, subtitles, cookies and extractor status |
| v1.7.0 Torrent Pro | Torrent details | File tree, file selection, seed, ratio, peers, trackers and metadata readiness |
| v1.7.5 Mobile & PWA | Mobile/PWA shell | Responsive navigation, install state, offline state and touch-safe controls |
| v1.8.0 Automation | Automation | Create, enable/disable, schedule, event trigger, run history and logs |
| v1.9.0 Rules Engine | Rules | Conditions, actions, ordering, enable/disable, dry-run and execution history |
| v2.0.0 Plugin Platform | Plugins | Install, enable/disable, permissions, update, uninstall and compatibility state |
| v2.1.0 Headless Server | System / Headless | Service state, bind address, API key, clients, logs and safe restart |
| v2.2.0 Windows Integration | System / Windows | Startup, notifications, file associations, shell integration and tray state |
| v2.3.0 Reliability & Security | System / Health | Health checks, error history, security events, diagnostics and recovery actions |

## Feature control contract

Each feature must expose four UI concerns:

1. **Display** — current state and relevant metrics.
2. **Operate** — the primary user action.
3. **Configure** — settings and scope of effect.
4. **Diagnose** — loading, unavailable, error, warning and recovery states.

The API/UI bridge should return explicit readiness and error information rather than forcing the UI to infer state from missing fields. The standard unavailable state is represented by `hazir_degil` where applicable, with a localized explanation and a retry or refresh action when safe.

## Responsive behavior

Desktop keeps the current left navigation and adds a resizable details panel. Mobile/PWA collapses primary navigation into a bottom navigation bar and presents details as a bottom sheet or full-screen page. No capability is desktop-only unless the underlying Windows integration explicitly requires Windows.

## Accessibility and safety

- Every icon-only control has a localized accessible name.
- Keyboard focus remains visible and follows modal/panel open-close behavior.
- Destructive actions require confirmation and identify the exact target.
- Long lists use bounded rendering, filtering and explicit “show all” behavior.
- Secrets and sensitive request headers never appear in UI logs or plugin output.

## Testing contract

Each release feature must have:

- i18n key parity tests for English and Turkish;
- UI/API bridge contract tests;
- ready, unavailable and error-state tests;
- bounded rendering tests for large lists;
- responsive smoke coverage where layout changes;
- end-to-end smoke coverage for the primary user action.

## Delivery order

Implement the shared shell and selected-download details contract first, then deliver release slices in roadmap order. v1.7 Torrent Pro is the first consumer of the details tabs; later releases add tabs or System/Automation/Rules/Plugins surfaces without changing the navigation contract.

