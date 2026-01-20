# ComfyUI-DiscordSend Refactoring PRD

**Document Type:** Product Requirements Document
**Project:** ComfyUI-DiscordSend Separation of Concerns Refactor
**Version:** 1.0
**Date:** 2026-01-19
**Author:** Claude Opus 4.5 + Human Review
**Status:** In Progress (Phases 0-5 Complete)

---

## 1. Overview

### 1.1 Purpose
This PRD defines the requirements and scope for a comprehensive refactoring of the ComfyUI-DiscordSend project to improve code organization, reduce duplication, and complete missing features.

### 1.2 Background
The project currently consists of two main components:
- **ComfyUI Nodes**: Production-ready custom nodes for sending images/videos to Discord
- **Discord Bot**: A companion bot for triggering generations from Discord (functional but incomplete)

### 1.3 Problem Statement
| Issue | Impact | Severity |
|-------|--------|----------|
| 4 critical bugs preventing bot startup | Bot unusable | Critical |
| 1562-line monolithic video node | Hard to maintain/debug | High |
| ~400 lines of duplicated code | Bug fixes needed in multiple places | High |
| Wrong coupling (video imports from image node) | Fragile dependencies | Medium |
| No directory structure for separation | Confusing organization | Medium |
| Incomplete bot features | Missing user functionality | Medium |

---

## 2. Goals & Non-Goals

### 2.1 Goals
1. **Fix all critical bugs** that prevent the bot from running
2. **Restructure directory layout** with clear separation: `nodes/`, `shared/`, `bot/`
3. **Eliminate code duplication** between image and video nodes
4. **Extract video encoding logic** to reduce video node from 1562 to ~400 lines
5. **Create base node class** for shared functionality
6. **Complete missing bot features**: templates, history, error delivery, WebSocket reconnection
7. **Improve maintainability** through modular design

### 2.2 Non-Goals
- Adding new node features (beyond bug fixes)
- Changing the Discord webhook API integration
- Modifying ComfyUI compatibility requirements
- Database schema changes (bot uses existing models)
- UI/UX changes to ComfyUI node interface

---

## 3. Requirements

### 3.1 Functional Requirements

#### FR-1: Bug Fixes (Phase 0)
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1.1 | Fix `BotConfig` class name mismatch in `bot/__main__.py` | P0 |
| FR-1.2 | Add missing `json` import to `bot/services/delivery.py` | P0 |
| FR-1.3 | Fix `PermissionLevel` import in `bot/cogs/admin.py` | P0 |
| FR-1.4 | Fix `config.comfyui.url` attribute path in admin cog | P0 |

#### FR-2: Directory Structure (Phase 1)
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-2.1 | Create `nodes/` directory for node implementations | P1 |
| FR-2.2 | Create `shared/` directory for utilities | P1 |
| FR-2.3 | Create `shared/discord/`, `shared/media/`, `shared/workflow/` subdirectories | P1 |
| FR-2.4 | Move utility files to appropriate locations | P1 |
| FR-2.5 | Update all imports throughout codebase | P1 |
| FR-2.6 | Maintain backward compatibility for ComfyUI node loading | P1 |

#### FR-3: Shared Utilities (Phase 2)
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-3.1 | Extract filename/timestamp utilities to `shared/filename_utils.py` | P1 |
| FR-3.2 | Extract output directory logic to `shared/path_utils.py` | P1 |
| FR-3.3 | Extract Discord message building to `shared/discord/message_builder.py` | P1 |
| FR-3.4 | Extract CDN URL handling to `shared/discord/cdn_extractor.py` | P1 |

#### FR-4: Video Encoder Extraction (Phase 3)
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-4.1 | Create `FFmpegEncoder` class in `shared/media/video_encoder.py` | P1 |
| FR-4.2 | Create `PILGifEncoder` fallback class | P1 |
| FR-4.3 | Extract format detection to `shared/media/format_utils.py` | P1 |
| FR-4.4 | Reduce video node to orchestration layer (~400 lines) | P1 |

#### FR-5: Base Node Class (Phase 4)
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.1 | Create `BaseDiscordNode` class in `nodes/base_node.py` | P2 |
| FR-5.2 | Extract common `INPUT_TYPES` definitions | P2 |
| FR-5.3 | Extract shared methods (sanitize, send, etc.) | P2 |
| FR-5.4 | Refactor image and video nodes to inherit from base | P2 |

#### FR-6: Bot Features (Phase 5)
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-6.1 | Implement WebSocket reconnection with exponential backoff | P1 |
| FR-6.2 | Implement error delivery to Discord users | P1 |
| FR-6.3 | Implement `/template` commands (save, load, list, delete) | P2 |
| FR-6.4 | Implement `/history` and `/rerun` commands | P2 |
| FR-6.5 | Create `config.yaml.example` template | P1 |
| FR-6.6 | Create `.env.example` template | P1 |

### 3.2 Non-Functional Requirements

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR-1 | Reduce total node code by >50% | 2548 → <1200 lines |
| NFR-2 | Eliminate code duplication | ~400 lines → 0 |
| NFR-3 | Maintain test pass rate | All existing tests pass |
| NFR-4 | No breaking changes to ComfyUI | Nodes load and function identically |
| NFR-5 | Improve modularity | 12+ separate utility modules |

---

## 4. Architecture

### 4.1 Current State
```
comfyui-discordsend/
├── discord_image_node.py (986 lines)
├── discord_video_node.py (1562 lines)
├── discordsend_utils/ (6 files, tightly coupled)
└── bot/ (incomplete, 4 bugs)
```

### 4.2 Target State
```
comfyui-discordsend/
├── __init__.py                    # ComfyUI entry point
├── nodes/                         # Node implementations (~950 lines total)
│   ├── __init__.py
│   ├── base_node.py              # Shared base class
│   ├── image_node.py             # Image-specific logic
│   └── video_node.py             # Video-specific logic
├── shared/                        # Shared utilities (12 modules)
│   ├── discord/                   # Discord integration
│   │   ├── webhook_client.py
│   │   ├── message_builder.py
│   │   └── cdn_extractor.py
│   ├── media/                     # Media processing
│   │   ├── image_processing.py
│   │   ├── video_encoder.py
│   │   └── format_utils.py
│   ├── workflow/                  # Workflow utilities
│   │   ├── sanitizer.py
│   │   ├── prompt_extractor.py
│   │   └── workflow_builder.py
│   ├── github_integration.py
│   ├── filename_utils.py
│   ├── path_utils.py
│   └── logging_config.py
└── bot/                           # Fully functional bot
    ├── cogs/
    │   ├── generate.py
    │   ├── queue.py
    │   ├── admin.py
    │   ├── templates.py          # NEW
    │   └── history.py            # NEW
    └── ...
```

### 4.3 Component Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                      ComfyUI Runtime                             │
│  ┌──────────────┐     ┌──────────────┐                          │
│  │  ImageNode   │     │  VideoNode   │                          │
│  └──────┬───────┘     └──────┬───────┘                          │
│         │                    │                                   │
│         └────────┬───────────┘                                   │
│                  ▼                                               │
│         ┌──────────────┐                                         │
│         │  BaseNode    │                                         │
│         └──────┬───────┘                                         │
└────────────────┼────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      shared/                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ discord │  │  media  │  │workflow │  │  utils  │            │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
└─────────────────────────────────────────────────────────────────┘
                 │
                 ▼ (logging_config only)
┌─────────────────────────────────────────────────────────────────┐
│                        bot/                                      │
│  (Minimal shared dependency - mostly independent)                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Phased Implementation

### Phase 0: Critical Bug Fixes ✅ COMPLETE
- Fix 4 bugs preventing bot startup
- Verify all existing tests pass
- **Status:** Complete (2026-01-19)

### Phase 1: Directory Restructure ✅ COMPLETE
- Create new directory structure (`nodes/`, `shared/`)
- Move files to new locations
- Update all imports
- Remove deprecated `discordsend_utils/`
- **Status:** Complete (2026-01-20)
- **Commit:** 852840d

### Phase 2: Extract Shared Utilities ✅ COMPLETE
- Create `filename_utils.py` - filename with date/time/dimensions
- Create `path_utils.py` - output directory handling
- Create `message_builder.py` - Discord message construction
- Create `cdn_extractor.py` - CDN URL extraction and file sending
- **Status:** Complete (2026-01-20)
- **Commit:** a208cd4
- **Result:** 522 lines removed from nodes (image: -161, video: -361)

### Phase 3: Extract Video Encoder ✅ COMPLETE
- Create `FFmpegEncoder` class with format-specific encoding
- Create `PILEncoder` class for GIF/WebP fallback
- Create `format_utils.py` - format detection, validation, Discord compatibility
- Refactor video node to use shared encoders
- **Status:** Complete (2026-01-20)
- **Commit:** 76da850
- **Result:** Video node reduced from 1562 to 1092 lines (-470 lines, 30% reduction)

### Phase 4: Create Base Node Class ✅ COMPLETE
- Create `BaseDiscordNode` (343 lines) in `nodes/base_node.py`
- Extract common `INPUT_TYPES` generators (Discord, CDN, filename metadata)
- Extract shared methods (sanitize, send, GitHub update, etc.)
- **Status:** Complete (2026-01-20)
- **Commit:** 87c97e0
- **Note:** Nodes not yet refactored to inherit from base (deferred to reduce risk)

### Phase 4.1: PR Review Bug Fixes ✅ COMPLETE
- Fix else block indentation in batch Discord send (1e94a69)
- Add section header when only dimensions displayed (b8aadd7)
- Restore SDXL workflow prompt extraction support (36c5d06)
- Prevent redundant CDN URL sends on 204 responses (cc07d20)
- Add trailing newline to metadata section formatting (0d6ed9d)
- **Status:** Complete (2026-01-20)

### Phase 5: Complete Bot Features ✅ COMPLETE
- WebSocket reconnection with exponential backoff
- Error delivery to Discord users
- Templates cog (`/template save/load/list/delete`)
- History cog (`/history`, `/rerun`)
- Config templates (already existed)
- Fixed BotConfig import bug
- **Status:** Complete (2026-01-20)
- **Commit:** b083702

### Phase 6: Final Cleanup
- Update documentation
- Add new tests
- Remove dead code
- **Deliverable:** Production-ready codebase

---

## 6. Success Metrics

| Metric | Original | Current | Target | Status |
|--------|----------|---------|--------|--------|
| Image node lines | 986 | 836 | ~350 | 🟡 -150 lines (15%) |
| Video node lines | 1562 | 1092 | ~400 | 🟡 -470 lines (30%) |
| Total node lines | 2548 | 1928 | ~750 | 🟡 -620 lines (24%) |
| Base node class | 0 | 343 | ~200 | ✅ Created |
| Utility modules | 6 | 17 | 12+ | ✅ Exceeded |
| Code duplication | ~400 lines | ~200 | 0 | 🟡 In progress |
| Test pass rate | 46/52 | 46/52 | 52/52 | 🟡 Maintained |
| Bot features | 60% | 100% | 100% | ✅ Phase 5 Complete |

**Notes:**
- Node line counts don't include base_node.py (343 lines of reusable code)
- 6 test failures are pre-existing numpy mocking issues, not refactoring-related
- Nodes have not yet been refactored to inherit from BaseDiscordNode

---

## 7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking ComfyUI node loading | Medium | High | Test after each phase; maintain `__init__.py` |
| Breaking existing workflows | Low | High | Preserve node class names exactly |
| Introducing new bugs | Medium | Medium | Comprehensive tests; review after each phase |
| Merge conflicts | Low | Low | Work on feature branch; small commits |
| Scope creep | Medium | Medium | Strict adherence to PRD; defer new features |

---

## 8. Out of Scope (Future Work)

- New node types (audio, 3D, etc.)
- Multi-webhook support per node
- Cloud storage integration (S3, GCS)
- Web dashboard for bot
- Rate limiting per user in nodes
- Encrypted webhook storage

---

## 9. Approval & Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Claude Opus 4.5 | 2026-01-19 | Approved |
| Reviewer | Human | 2026-01-19 | Approved |

---

## 10. Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-19 | Claude | Initial PRD created |
| 1.0.1 | 2026-01-19 | Claude | Phase 0 marked complete |
| 1.1 | 2026-01-20 | Claude | Phase 1 complete - directory restructure |
| 1.2 | 2026-01-20 | Claude | Phase 2 complete - shared utilities extracted |
| 1.3 | 2026-01-20 | Claude | Phase 3 complete - video encoder extraction |
| 1.4 | 2026-01-20 | Claude | Phase 4 complete - BaseDiscordNode created |
| 1.4.1 | 2026-01-20 | Claude | Phase 4.1 - PR review bug fixes (5 issues resolved) |
