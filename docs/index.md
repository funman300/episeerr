# Episeerr Documentation

Welcome to the Episeerr documentation. Episeerr provides three independent automation solutions for managing TV episodes in Sonarr, plus intelligent storage management.

## Getting Started

### New to Episeerr?
1. [Installation & Setup](installation.md) - Get Episeerr running
2. [Global Storage Gate Guide](global_storage_gate_guide.md) - Set up smart storage management
3. Choose your automation approach below

### Which Features Do You Want?

#### 🎬 Episode Selection Only
**Use case:** Choose specific episodes manually, try new shows with just pilots
**Setup:** Sonarr webhook + episode selection interface
→ **[Episode Selection Guide](episode-selection.md)**

#### ⚡ Viewing Automation Only  
**Use case:** Episodes ready as you watch, automatic next episode preparation
**Setup:** Sonarr webhook + Tautulli/Jellyfin webhook + rules
→ **[Rules System Guide](rules-guide.md)** → **[Webhook Setup](webhooks.md)**

#### 💾 Storage Management Only
**Use case:** Automatic cleanup based on time and viewing activity
**Setup:** Rules with grace/dormant timers + global storage gate
→ **[Global Storage Gate Guide](global_storage_gate_guide.md)** → **[Rules System Guide](rules-guide.md)**

#### 🚀 Complete Automation
**Use case:** All features working together
**Setup:** All webhooks + rules with timers + episode selection + storage gate
→ **[Installation](installation.md)** → Configure all features

---

## Core Features

### 🎬 Episode Selection System
- [Episode Selection Guide](episode-selection.md) - Choose specific episodes across seasons
- [Sonarr Integration](sonarr_integration.md) - Tags and delayed profiles for episode selection

### ⚡ Viewing-Based Automation  
- [Rules System Guide](rules-guide.md) - Automate based on viewing activity
- [Rule Examples](rule-examples.md) - Common configurations for different use cases

### 💾 Storage Management (NEW!)
- [Global Storage Gate Guide](global_storage_gate_guide.md) - One threshold controls all cleanup
- [Understanding Grace vs Dormant Timers](global_storage_gate_guide.md#the-chips-philosophy) - "Chips" philosophy explained

### 🔧 Integration
- [Sonarr Integration](sonarr_integration.md) - Tags, profiles, and webhook setup
- [Webhook Setup](webhooks.md) - Tautulli, Jellyfin, Sonarr, and request system webhooks

---

## Advanced Topics

- [API Reference](api-reference.md) - Endpoints and usage
- [Custom Configurations](advanced-config.md) - Environment variables and tuning
- [Migration from OCDarr](migration.md) - Switching from full OCDarr setup
- [Multiple Rule Strategies](advanced-rules.md) - Complex automation setups

---

## Troubleshooting

- [Common Issues](troubleshooting.md) - Solutions to frequent problems
- [Debugging Guide](debugging.md) - Logs and diagnostics
- [FAQ](faq.md) - Frequently asked questions

---

## Understanding the System

### How Features Work Together

**Episode Selection Workflow:**
```
Request with episeerr_select tag → Sonarr webhook → Episode selection interface → Manual choice
```

**Viewing Automation Workflow:**
```
Watch episode → Tautulli/Jellyfin webhook → Apply rule → Update episodes in Sonarr
```

**Storage Management Workflow:**
```
Storage check → Below threshold → Cleanup based on grace/dormant timers → Stop when above threshold
```

### Rule Protection System
- **Rules with grace/dormant timers:** Participate in storage cleanup
- **Rules with null timers:** Protected, never cleaned up
- **Global storage gate:** Only runs cleanup when needed, stops when threshold met

---

**Need help?** 
- Start with [Installation](installation.md) if you're new
- Check [Troubleshooting](troubleshooting.md) for common issues
- Review [FAQ](faq.md) for quick answers