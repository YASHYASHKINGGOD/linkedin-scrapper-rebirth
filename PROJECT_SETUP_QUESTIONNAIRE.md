# Project Setup Questionnaire

This document contains all the questions you need to answer to properly fill out each of the 12 core markdown template files for your project setup.

## 1. ROOT LEVEL FILES (8 files)

### WARP.md Questions

**Purpose & Context:**
1. What is the project name?
2. What is the primary purpose of this project?
3. How does this project fit into your larger ecosystem?
4. What are the key business objectives?

**Project Structure:**
5. What are the main directories in your project?
6. What is the purpose of each directory?
7. How are files organized (by feature, by type, etc.)?
8. What naming conventions do you follow?

**Development Workflow:**
9. What are the setup requirements (languages, tools, databases)?
10. What make targets do you need (dev, test, lint, etc.)?
11. What is your testing approach (unit, integration, e2e)?
12. How do you deploy (manual, CI/CD, staging process)?

**Safety & Compliance:**
13. What security requirements must be followed?
14. How do you handle sensitive data?
15. What environment variables are needed?
16. How are secrets managed (env vars, secret managers)?
17. Are there compliance requirements (GDPR, SOC2, etc.)?

**Verification:**
18. What steps verify a successful setup?
19. How do you verify tests are working?
20. What deployment verification is needed?

### DESIGN.md Questions

**Vision & Goals:**
1. What problem does this project solve?
2. Who are the end users?
3. What does success look like?
4. How will you measure success?
5. What are the primary objectives?
6. What are secondary/nice-to-have objectives?

**Non-Goals & Scope:**
7. What will this project explicitly NOT do?
8. What features are out of scope?
9. What future considerations are deferred?
10. What are the project boundaries?

**Architecture:**
11. What is the high-level system architecture?
12. How do components interact with each other?
13. What is the data flow through the system?
14. Why did you choose this technology stack?
15. What external services does it integrate with?

**Components:**
16. What are the main components/modules?
17. What is each component responsible for?
18. What are the interfaces between components?
19. How do components communicate?

**Data Model:**
20. What entities does your system manage?
21. How are entities related to each other?
22. What is your database schema?
23. How does data flow through the system?

**Performance & Security:**
24. What are your expected load/volume requirements?
25. What response time requirements do you have?
26. How will the system scale?
27. What authentication/authorization approach do you use?
28. How is sensitive data protected?

**Dependencies:**
29. What external services do you depend on?
30. What third-party libraries are critical?
31. What infrastructure is required?

### planning.md Questions

**Milestone Planning:**
1. What are the major phases of development?
2. What is the estimated timeline for each phase?
3. What dependencies exist between milestones?
4. What are the deliverables for each milestone?

**For Each Milestone:**
5. What are the primary objectives?
6. What defines success for this milestone?
7. What components need to be built?
8. What are the acceptance criteria for each component?

**Testing Strategy:**
9. What unit testing approach will you use?
10. What integration testing is needed?
11. What manual testing must be done?
12. What performance testing is required?

**Risk Assessment:**
13. What technical risks could derail the project?
14. What timeline risks exist?
15. What dependency risks are there?
16. How will each risk be mitigated?

**Resources:**
17. What development resources are needed?
18. What infrastructure resources are required?
19. What external dependencies must be coordinated?

### tasks.md Questions

**Current Work:**
1. What tasks are currently in progress?
2. What are you blocked on?
3. What tasks are ready to start immediately?
4. What prerequisites must be completed first?

**Backlog Prioritization:**
5. What are the high-priority tasks?
6. What business value does each task provide?
7. What is the estimated effort for each task?
8. How do tasks depend on each other?

**Task Definition:**
9. For each task, what are the specific acceptance criteria?
10. What constitutes "done" for each task?
11. What edge cases need to be considered?
12. What testing is required for each task?

### SESSION_TEMPLATE.md Questions

**Session Planning:**
1. What are the primary goals for this session?
2. What specific tasks will you complete?
3. What is the current state of the project?
4. What blockers or issues exist?

**Work Tracking:**
5. What code files were modified/created?
6. What key functions/features were implemented?
7. What test coverage was added?
8. What documentation was updated?

**Issues & Decisions:**
9. What problems were encountered?
10. How were blockers resolved?
11. What technical debt was created?
12. What important decisions were made?
13. What architecture insights were gained?

**Next Steps:**
14. What are the immediate next tasks?
15. What preparation is needed for the next session?
16. What dependencies need to be resolved?

### CONTRIBUTING.md Questions

**Code Standards:**
1. What language-specific style guides do you follow?
2. What formatting tools do you use?
3. What naming conventions are required?
4. What code organization principles do you follow?

**Git Workflow:**
5. What branch naming convention do you use?
6. What commit message format is required?
7. What is your PR/review process?
8. How do you handle releases?

**Quality Gates:**
9. What must be done before code is considered complete?
10. What testing coverage is required?
11. What documentation must be updated?
12. What security reviews are needed?
13. What performance criteria must be met?

**Process:**
14. Who reviews code?
15. How many approvals are needed?
16. What is the deployment process?
17. How do you handle hotfixes?

### README.md Questions

**Project Overview:**
1. What is the project name?
2. What does this project do in one sentence?
3. Who would use this project?
4. What problem does it solve?

**Quick Start:**
5. What system requirements exist?
6. What dependencies must be installed?
7. What environment setup is needed?
8. What are the minimal steps to get running?

**Usage:**
9. What are the most common commands users will run?
10. What are typical use cases?
11. What configuration options exist?

**Project Structure:**
12. What are the key directories?
13. How is the code organized?
14. Where are important files located?

**Support:**
15. How do users get help?
16. Where do they report issues?
17. What contact information should be provided?

### CLAUDE.md Questions

**Project Context:**
1. What is the current understanding of the project?
2. What key architectural decisions have been made?
3. What is the reasoning behind major choices?
4. What patterns or principles guide development?

**Current State:**
5. What components are working well?
6. What known issues exist?
7. What are the current priorities?
8. What technical debt exists?

**AI Context:**
9. What should the next AI session focus on first?
10. What files are most important to review?
11. What context is crucial for understanding the codebase?
12. What gotchas or complexities should be highlighted?

## 2. APP-SPECIFIC FILES (4 files)

### WARP.md (App-Specific) Questions

**App Purpose:**
1. What specific functionality does this app provide?
2. How does it fit into the larger project?
3. What business problem does it solve?
4. Who are the users of this specific app?

**Integration:**
5. How does this app inherit from root project rules?
6. What app-specific rules override or extend root rules?
7. How does this app interact with other apps?

**Commands & Workflow:**
8. What make targets are specific to this app?
9. How do you run this app in development mode?
10. How do you test this app in isolation?
11. What background processes does it run?

**Scope & Boundaries:**
12. What does this app handle vs. other apps?
13. What are its specific responsibilities?
14. What are its limitations?
15. What is explicitly NOT this app's responsibility?

**Dependencies:**
16. What external services does this app use?
17. What other project components does it depend on?
18. What infrastructure does it require?

**Verification:**
19. How do you verify this app is set up correctly?
20. What functionality tests prove it's working?
21. How do you verify integration with other components?

### Orchestration.md Questions

**Message Flows:**
1. What input messages does this app receive?
2. What is the format of each input message type?
3. What output messages does this app produce?
4. How are messages routed between components?
5. What message transformation occurs?

**Queue Configuration:**
6. What queues does this app use?
7. What is the purpose of each queue?
8. What concurrency settings are appropriate?
9. How do you handle queue backups?

**Scheduling:**
10. What scheduled tasks does this app run?
11. What triggers cause tasks to execute?
12. What cron schedules are needed?
13. What dependencies exist between scheduled tasks?

**Error Handling:**
14. What retry logic is implemented?
15. How many retries are appropriate for each operation?
16. What conditions trigger dead letter queues?
17. What alerts should fire on errors?

**Monitoring:**
18. What metrics indicate healthy operation?
19. What health check endpoints exist?
20. What should be logged for debugging?
21. What dashboards or monitoring tools are used?

### OperatingManual.md Questions

**Local Development:**
1. What specific setup is required for this app?
2. What environment variables are needed?
3. What database setup is required?
4. What external services need to be configured?

**Running Locally:**
5. What commands start the app in development mode?
6. How do you run background workers?
7. What ports does the app use?
8. How do you simulate production conditions locally?

**Configuration:**
9. What environment variables control behavior?
10. What configuration files exist?
11. What feature flags are available?
12. How do you switch between environments?

**Troubleshooting:**
13. What are the most common issues?
14. How do you debug connection problems?
15. What log files should be checked?
16. How do you reset the app to a clean state?

**Monitoring & Operations:**
17. What health checks indicate the app is working?
18. What metrics endpoints are available?
19. How do you analyze logs for issues?
20. What regular maintenance is needed?

### Tasks.md (App-Specific) Questions

**Current Work:**
1. What app-specific tasks are in progress?
2. What app features are being developed?
3. What bugs need to be fixed in this app?
4. What integration work is needed?

**App Dependencies:**
5. What other apps does this depend on?
6. What shared components are needed?
7. What integration points need to be developed?
8. What testing requires multiple apps?

**Performance & Features:**
9. What performance targets exist for this app?
10. What scalability concerns need to be addressed?
11. What new features are planned?
12. What technical debt should be addressed?

## 3. IMPLEMENTATION CHECKLIST

### Before You Start:
- [ ] Answer all relevant questions above
- [ ] Gather all necessary information
- [ ] Identify any missing information that needs research
- [ ] Plan the order of file creation

### File Creation Order:
1. Start with DESIGN.md (defines the vision)
2. Create WARP.md (establishes rules and workflow)
3. Fill out planning.md (breaks down the work)
4. Create tasks.md (defines current work)
5. Set up README.md (provides entry point)
6. Create SESSION_TEMPLATE.md, CONTRIBUTING.md, CLAUDE.md as needed
7. For apps: Copy and customize the 4 app-specific templates to apps/[app-name]/

### Validation Questions:
- Can someone new to the project understand it from the README?
- Does the DESIGN document clearly explain architectural decisions?
- Are tasks in tasks.md actionable with clear acceptance criteria?
- Do the WARP.md rules provide clear guidance for development?
- Is there enough information to reproduce the development environment?

## 4. ONGOING MAINTENANCE QUESTIONS

### Daily/Weekly:
- What tasks were completed this session?
- What new tasks emerged?
- What blockers or issues arose?
- What decisions were made?

### Monthly:
- Are the project goals still accurate?
- Do the tasks reflect current priorities?
- Is the architecture documentation up to date?
- Are the operational procedures working?

### Project Milestones:
- Have the goals been achieved?
- What lessons were learned?
- What would you do differently?
- What should be documented for future projects?