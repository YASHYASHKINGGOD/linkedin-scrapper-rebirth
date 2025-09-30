# Project Template Files - Complete Superset

This document contains outlines for ALL markdown files needed for a complete project setup, based on the AI Interns workflow and project-specific requirements.

## 1. ROOT LEVEL FILES

### WARP.md (Project Memory & Rules)
```markdown
# WARP.md — [Project Name]

## Purpose
- Brief description of the project
- What this file contains (project memory & rules)

## Rule Precedence
- How this file relates to other WARP.md files
- Inheritance hierarchy (root → app-specific)

## Daily Loop
1. Start: Read WARP.md, DESIGN.md, planning.md, tasks.md, README.md
2. Implement: Small commits, tests updated, make check green
3. Handover: Update tasks.md, append to WARP.md, save session notes

## Project Structure
- Key directories and their purposes
- File organization principles

## Development Workflow
- Setup requirements
- Development commands (make targets)
- Testing approach
- Deployment process

## Safety & Compliance
- Security requirements
- Data handling rules
- Environment variable management
- Secrets handling

## Verification Checklist
- Setup verification steps
- Testing verification
- Deployment verification
```

### DESIGN.md (Architecture & Goals)
```markdown
# DESIGN.md — [Project Name]

## Vision
- Project purpose and objectives
- Success metrics

## Goals
- Primary objectives
- Secondary objectives
- Success criteria

## Non-Goals
- Explicit list of what this project will NOT do
- Scope limitations
- Future considerations

## Architecture Overview
- High-level system design
- Component relationships
- Data flow diagrams
- Technology stack choices

## Key Components
- Component 1: Purpose, responsibilities, interfaces
- Component 2: Purpose, responsibilities, interfaces
- [Continue for each major component]

## Data Model
- Database schema overview
- Key entities and relationships
- Data flow patterns

## Security Considerations
- Authentication/authorization approach
- Data protection measures
- Compliance requirements

## Performance Requirements
- Expected load/volume
- Response time requirements
- Scalability considerations

## Dependencies
- External services
- Third-party libraries
- Infrastructure requirements
```

### planning.md (Milestone Planning)
```markdown
# planning.md — [Project Name]

## Milestone Overview
- Project phases
- Timeline estimates
- Dependencies between milestones

## Milestone 1: [Name]
### Objectives
- Primary deliverables
- Success criteria

### Components
- Component A: Description, acceptance criteria
- Component B: Description, acceptance criteria

### Test Plan
- Unit testing approach
- Integration testing requirements
- Manual testing checklist

### Definition of Done
- Code complete criteria
- Documentation requirements
- Testing requirements

## Milestone 2: [Name]
[Same structure as Milestone 1]

## Risk Assessment
- Technical risks and mitigation
- Timeline risks
- Dependency risks

## Resource Requirements
- Development resources
- Infrastructure needs
- External dependencies
```

### tasks.md (Living Backlog)
```markdown
# tasks.md — [Project Name]

## Current Sprint/Active Tasks

### In Progress
- [ ] Task 1: Description
  - Acceptance criteria
  - Notes/blockers

### Ready for Development
- [ ] Task 2: Description
  - Acceptance criteria
  - Prerequisites completed

## Backlog

### High Priority
- [ ] Task 3: Description
  - Business justification
  - Acceptance criteria
  - Estimated effort

### Medium Priority
- [ ] Task 4: Description

### Low Priority / Future
- [ ] Task 5: Description

## Completed
- [x] Task 0: Initial setup (2024-01-01)
  - Notes on completion

## Task Template
```
- [ ] Task Title: Brief description
  - **Acceptance Criteria:**
    - Criterion 1
    - Criterion 2
  - **Notes:** Additional context
  - **Estimate:** Time/complexity estimate
```

## Notes
- Task prioritization rationale
- Dependencies between tasks
```

### SESSION_TEMPLATE.md (Session Log Template)
```markdown
# Session Template

Copy this file to `sessions/SESSION-YYYY-MM-DD.md` for each work session.

## Session: YYYY-MM-DD

### Objectives
- Primary goals for this session
- Specific tasks to complete

### Context
- Current state of the project
- Previous session outcomes
- Any blockers or issues

### Work Completed
- [ ] Task 1: Description and outcome
- [ ] Task 2: Description and outcome
- [ ] Bug fixes or improvements

### Code Changes
- Files modified/created
- Key functions/features implemented
- Test coverage added

### Issues Encountered
- Problems faced and solutions
- Blockers and their resolution
- Technical debt created

### Next Steps
- Immediate next tasks
- Preparation needed for next session
- Dependencies to resolve

### Notes
- Important decisions made
- Architecture insights
- Performance observations
- Security considerations

### Verification
- [ ] `make check` passes
- [ ] Tests updated and passing
- [ ] Documentation updated
- [ ] Ready for handover
```

### CONTRIBUTING.md (Development Standards)
```markdown
# CONTRIBUTING.md — [Project Name]

## Development Standards

### Code Style
- Language-specific style guides
- Formatting requirements
- Naming conventions

### Git Workflow
- Branch naming conventions
- Commit message format
- PR requirements

### Definition of Done
- [ ] Code complete and reviewed
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] `make check` passes
- [ ] Security review completed
- [ ] Performance acceptable

### PR Checklist
- [ ] Description explains the change
- [ ] Tests cover new functionality
- [ ] Documentation updated
- [ ] Breaking changes noted
- [ ] Security implications considered

### Testing Requirements
- Unit test coverage expectations
- Integration test requirements
- Manual testing checklist

### Code Review Process
- Review assignment
- Review criteria
- Approval requirements

### Release Process
- Version numbering
- Release notes requirements
- Deployment checklist
```

### README.md (Project Overview)
```markdown
# [Project Name]

Brief description of the project and its purpose.

## Quick Start

### Prerequisites
- System requirements
- Dependencies to install
- Environment setup

### Installation
```bash
# Step-by-step installation commands
make setup
```

### Basic Usage
```bash
# Common commands
make start
make test
```

## Project Structure
```
project/
├── apps/           # Application modules
├── docs/           # Documentation
├── sessions/       # Session logs
├── tests/          # Test files
└── README.md
```

## Development

### Setup
```bash
make setup
```

### Common Commands
- `make dev` - Start development server
- `make test` - Run tests
- `make check` - Run all quality checks
- `make fmt` - Format code

### Daily Workflow
1. Read project documentation
2. Pick task from tasks.md
3. Implement with tests
4. Run `make check`
5. Update documentation

## Documentation
- [Design Document](DESIGN.md)
- [Development Planning](planning.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [Task Backlog](tasks.md)

## Support
- How to get help
- Contact information
- Issue reporting
```

### CLAUDE.md (AI Session Notes)
```markdown
# CLAUDE.md — [Project Name]

## Project Context
- Current understanding of the project
- Key decisions and rationale
- Architecture insights

## Recent Sessions
### Session YYYY-MM-DD
- Summary of work completed
- Key insights gained
- Issues encountered

### Session YYYY-MM-DD
- [Previous session notes]

## Current State
- What's working
- Known issues
- Next priorities

## AI Handover Notes
- Context for next AI session
- Important considerations
- Files to review first

## Decisions Log
- Important architectural decisions
- Technology choices and rationale
- Trade-offs made
```

## 2. APP-SPECIFIC FILES (in apps/[app-name]/)

### WARP.md (App-Specific Rules)
```markdown
# WARP.md — [App Name]

## Purpose
- App-specific functionality
- How it fits into the larger project

## Rule Precedence
- Inherits root WARP.md rules
- App-specific overrides or additions

## Daily Loop (This App)
1. Read root and app-specific docs
2. Pick tasks from app Tasks.md
3. Implement and test
4. Update app documentation

## App-Specific Commands
- `make [app].dev` - Development mode
- `make [app].test` - Run app tests
- `make [app].worker` - Background processing

## Scope
- What this app handles
- Boundaries and limitations

## Dependencies
- External services
- Other project components
- Required infrastructure

## Verification Checklist
- App-specific setup verification
- Functionality tests
- Integration verification
```

### Orchestration.md (System Integration)
```markdown
# Orchestration.md — [App Name]

## Message Flows
- Input message formats
- Output message formats
- Message routing logic

## Queue Configuration
- Queue names and purposes
- Concurrency settings
- Retry policies

## Scheduling Details
- Cron schedules
- Event triggers
- Dependencies

## Error Handling
- Retry logic
- Dead letter queues
- Alert conditions

## Monitoring
- Key metrics to track
- Health check endpoints
- Logging requirements
```

### OperatingManual.md (Operations Guide)
```markdown
# Operating Manual — [App Name]

## Local Development
- Setup requirements
- Environment variables
- Database setup

## Running Locally
```bash
# Development commands
make [app].setup
make [app].dev
```

## Troubleshooting
- Common issues and solutions
- Debug commands
- Log locations

## Configuration
- Environment variables
- Configuration files
- Feature flags

## Monitoring
- Health checks
- Metrics endpoints
- Log analysis

## Common Operations
- Starting/stopping services
- Database migrations
- Data backups
```

### Tasks.md (App-Specific Tasks)
```markdown
# Tasks.md — [App Name]

## Current Tasks
- [ ] App-specific task 1
- [ ] App-specific task 2

## Backlog
- [ ] Future enhancement 1
- [ ] Bug fix 2

## Completed
- [x] Initial app setup

## App-Specific Considerations
- Dependencies on other apps
- Integration requirements
- Performance targets
```

## 3. SPECIALIZED FILES

### UI-INSTRUCTIONS.md (UI Guidelines)
```markdown
# UI Instructions

## Design System
- Color palette
- Typography
- Spacing guidelines

## Component Library
- Available components
- Usage guidelines
- Examples

## User Experience Guidelines
- Navigation patterns
- Form design
- Error handling

## Responsive Design
- Breakpoint definitions
- Mobile considerations
- Accessibility requirements

## Implementation Notes
- Framework-specific guidelines
- Performance considerations
- Browser compatibility
```

### [project-name]-handover.md (Project Handover)
```markdown
# [Project Name] Handover

## Project Overview
- Business context
- Technical summary
- Current state

## Key Stakeholders
- Project owner
- Technical lead
- End users

## Technical Architecture
- System overview
- Key components
- Data flows

## Development Environment
- Setup instructions
- Required tools
- Configuration details

## Deployment
- Deployment process
- Environment details
- Release procedures

## Known Issues
- Current bugs
- Technical debt
- Monitoring gaps

## Future Roadmap
- Planned features
- Architectural improvements
- Maintenance requirements

## Documentation Links
- Code repositories
- Design documents
- User guides

## Contact Information
- Who to contact for questions
- Escalation procedures
- Support channels
```

## 4. SUPPORTING FILES

### Makefile Commands Reference
Based on your rules, ensure these targets exist:
- `make setup` - Project initialization
- `make dev` - Development mode
- `make start` - Production start
- `make fmt` - Code formatting
- `make lint` - Code linting
- `make typecheck` - Type checking
- `make test` - Run tests
- `make check` - All quality checks

### Environment Files
- `.env.example` - Sample environment variables
- `.tool-versions` - Runtime version pinning
- `.nvmrc` - Node version specification
- `.pre-commit-config.yaml` - Auto-formatting/linting

## Usage Instructions

1. **Start a new project:**
   - Copy relevant templates
   - Customize for your specific project
   - Fill in project-specific details

2. **Daily workflow:**
   - Read key files (WARP.md, DESIGN.md, tasks.md)
   - Update session notes
   - Maintain tasks.md
   - Run `make check` before commits

3. **App-specific setup:**
   - Create `apps/[app-name]/` directory
   - Copy app-specific templates
   - Customize for the specific app

4. **Documentation maintenance:**
   - Update after each session
   - Keep tasks.md current
   - Maintain session logs in `sessions/`