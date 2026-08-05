# Goal Writing Guide — Web Flow Mapper

A well-written goal determines the quality of the navigation map. This guide
covers how to write precise goals for each website type and use case.

---

## Goal Anatomy

A high-quality goal has four components:

```
[WHAT TO NAVIGATE] + [OVERLAY HANDLING] + [STOP CONDITION] + [OUTPUT INTENT]
```

**Example:**
```
Map all top navigation sections [WHAT] — dismiss all popups, banners, and chat
widgets automatically [OVERLAY] — stop if a login or payment wall is reached
[STOP] — output dual-viewport full-page screenshots for each section [OUTPUT].
```

---

## Goal Templates by Website Type

### 1. Any Website (Universal Default)

```
Map the complete website structure by clicking every top navigation link and
tab visible without login. On each page, automatically dismiss all popups,
cookie consent banners, chat widgets (Intercom, Drift, Zendesk), newsletter
modals, and geo selection dialogs. Stop if a login wall, payment gate, or
CAPTCHA challenge is encountered. Capture full-page dual-viewport screenshots
of every unique section reached.
```

### 2. SaaS / Product

```
Map the complete SaaS product marketing site. Navigate: homepage hero,
product/features pages (all sub-tabs if visible), pricing page (all tiers),
integrations or ecosystem page, documentation entry point, about/team,
blog or resources, and contact. Dismiss all chat widgets, trial prompt
modals, and cookie banners automatically. Capture full-page screenshots
at both desktop 1440px and mobile 390px. Note any pricing or feature
sections with significant mobile layout differences.
```

### 3. E-Commerce (Discovery Flow)

```
Map the e-commerce website discovery and product funnel. Navigate: homepage,
all major category navigation links in the top nav, one product listing page,
one product detail page, and the cart or bag entry point. Bypass all
promotional popups, loyalty/rewards sign-up modals, live chat prompts,
cookie consent banners, and location/city selectors automatically. Stop
at any login or payment checkpoint and flag it. Full-page dual-viewport
screenshots at each step.
```

### 4. Competitive UX Audit

```
Conduct a comprehensive competitive UX audit of this website. Systematically
navigate every top-level section and sub-section visible without authentication.
Prioritize: homepage (full hero and above-fold), features or product section
(all major feature categories), pricing page, customer stories or case studies,
about and team page, blog or resources, and contact or demo request page.
Dismiss all popups and overlays. Capture full-page screenshots at desktop
1440px and mobile 390px for every section. Flag any pages where the mobile
layout differs significantly from desktop.
```

### 5. Documentation / Developer Portal

```
Map the documentation and developer portal structure. Navigate all top-level
documentation categories and sections visible in the primary navigation or
sidebar. Capture the landing page of each major section (not individual
articles or API references). Dismiss any cookie banners or sign-in prompts.
Desktop viewport only at 1440px. Maximum 14 sections.
```

### 6. Landing Page / Single-Page Site

```
Perform a full landing page visual audit. Load the page and wait for all
lazy-loaded content, animations, and hero media to fully render. Dismiss
any exit-intent popups, cookie consent, or chat widget prompts. Capture a
full-page desktop screenshot and a full-page mobile screenshot of the entire
scrollable page. Identify the key sections: hero, value proposition, features,
social proof, pricing or CTA, and footer.
```

### 7. Mobile-First App / PWA

```
Conduct a mobile-first UX mapping at 390px iPhone 14 viewport. Navigate the
complete site using the mobile hamburger menu or bottom navigation if present.
Dismiss any mobile app download smart banners, push notification permission
prompts, location access requests, and cookie consent dialogs. Capture
full-page mobile screenshots of every major section. Document which sections
use bottom sheets, drawers, or mobile-specific navigation patterns.
```

### 8. Portfolio / Creative Agency

```
Map this creative portfolio or agency website with attention to visual fidelity.
Navigate all sections: homepage, work or projects gallery, individual case
study or project pages (up to 3), about, services or expertise, and contact.
Allow extra time for WebGL shaders, canvas animations, and scroll-triggered
effects to fully render before each screenshot. Dismiss cookie or GDPR dialogs.
Full-page desktop screenshots at 1440px for maximum visual quality.
```

---

## Goal Quality Checklist

Before running, verify your goal includes:

- [ ] **Navigation scope** — which sections to visit (all nav / specific pages)
- [ ] **Overlay handling** — explicit instruction to dismiss popups/banners
- [ ] **Stop condition** — when to halt (login wall, payment, N pages)
- [ ] **Viewport intent** — desktop + mobile / desktop only / mobile only
- [ ] **Screenshot type** — full-page or viewport-only
- [ ] **Priority pages** — call out must-visit pages (pricing, features, etc.)

---

## Common Goal Mistakes

| Mistake | Problem | Fix |
|---|---|---|
| Too vague: "map the site" | Crawler may pick random elements | Add: "by clicking every top navigation link" |
| No overlay instruction | Popups may block navigation | Add: "dismiss all popups and banners automatically" |
| No stop condition | May hit login and loop | Add: "stop at any login or payment wall" |
| Asking for login-gated content | Impossible without credentials | Scope to "sections visible without login" |
| Asking for "all pages" on large site | Takes too long / hits step limit | Add `--max-steps 12` and scope to top-nav only |
