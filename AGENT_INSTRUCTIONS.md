# 🤖 Autonomous Agent Instructions & Configurations

This file contains the core operational directives for any AI Agent (like Antigravity) interacting with the EduBoost SA repository. **All AI models reading this workspace MUST prioritize these instructions.**

## 1. Interaction Paradigm: Elevated Autonomy
Do not wait for micro-managed, line-by-line instructions. Expect high-level "Epics" and execute them autonomously using your available tools. 
- **Prompt Coaching:** Whenever the USER provides a micromanaged prompt (e.g., "Change line 45 in X file"), the Agent **MUST** gently suggest an elevated, goal-oriented version of the prompt for future use.

## 2. Test-Driven Autonomy (TDD Loop)
When tasked with a backend feature or fix, the Agent must autonomously execute the following loop:
1. **Understand:** Read the relevant roadmap/epic.
2. **Test First:** Write integration/unit tests for the expected behavior *before* changing core logic.
3. **Execute:** Run the tests in the terminal (`pytest`). They should fail.
4. **Implement:** Write the core logic.
5. **Verify:** Re-run the tests autonomously. If they fail, read the errors and fix the code. Repeat until green.
6. **Commit:** Once verified, stage and commit the changes.

## 3. Out-Of-The-Box (OOTB) Execution Strategies
Agents must leverage their advanced tooling whenever applicable:
- **Browser Subagents:** When working on the Next.js frontend, do not just assume the React code works. Spawn a browser subagent (`browser_subagent` tool), navigate to the local dev server, visually verify the UI/gamification components, and fix hydration/styling errors autonomously.
- **Chaos Sweeps:** When tasked with security or refactoring, proactively run grep searches across the codebase to ensure system-wide compliance (e.g., POPIA scrubbing, type hinting, linting).
- **Terminal Heavy:** Use background terminal commands to spin up Redis, Postgres, or Celery workers locally to guarantee end-to-end integration before reporting back to the user.

## 4. Roadmap Tracking
All autonomous work is tracked in the following files:
- `audits/roadmaps/Agentic_Execution_Roadmap.md`
- `audits/reports/Agentic_Execution_Report.md`

When executing an Epic, the Agent must update both the Roadmap and the Report upon completion.
