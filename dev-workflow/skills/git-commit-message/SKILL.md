---
name: git-commit-message
description: "Use this when generating commit messages"
---

### Role & Objective
Your task is to analyze code changes (diffs) or developer task descriptions and **generate the final Git commit message**. 

### Audience
The primary readers of these commit messages are business stakeholders, product managers, and clients who have **zero technical background**. 

### Output Format
Your output must follow standard Git commit formatting: a concise summary line starting with a bracketed prefix, followed by a blank line, and then a brief paragraph providing a detailed functional description. Use the following categories for the prefix:

*   **`[New Feature]`** – For entirely new capabilities added to the application.
*   **`[Improvement]`** – For enhancements to existing features or user experiences.
*   **`[Bug Fix]`** – For correcting broken behavior or user-facing errors.
*   **`[Performance Update]`** – For under-the-hood speed optimizations.
*   **`[Security Update]`** – For data protection, dependency updates, and vulnerability patches.
*   **`[System Maintenance]`** – For internal stability, code cleanup, and preparing the system for future features.

If the changes span multiple categories, ALWAYS write the summaries first, then the summary + details for each category.
Commit messages must be written in **English**. 
---

### Strict Writing Rules

1.  **Focus on 'What' and 'Why':** Explain how the code change impacts the business, user experience, or system health. 
2.  **Zero Raw Jargon:** Do not include variable names, function names, specific library names, database tables, or infrastructure-specific jargon (e.g., avoid words like *AWS, refactor, React, array, API endpoint, regex*).
3.  **The "Under-the-Hood" Translation Rule:** If the code changes are purely technical (chores, infrastructure, refactoring), you must frame the commit message around one of these four business values:
    *   *Speed:* Making the application faster.
    *   *Stability:* Preventing future crashes or downtime.
    *   *Security:* Protecting user and company data.
    *   *Future Readiness:* Cleaning up internal workflows so future features can be built faster.
4. DO NOT add 'Co-Authored-By' reference.
---

### Issue tracker (ClickUp)
* If an issue tracker link is not provided by the user, you must ask for one before writing the message, with the ask questions tool.
* Include the link in the message, after the summary lines(s), if the user provides it in the answer. 
* Add a **romanian** equivalent of the git message as a comment to the provided issue, if you have available tools (ClickUp MCP server should be running). Include the commit id, do not include modified files or any technical data. This is a functional comment for the business users, not technical.

### Examples for Reference

*   **Input (Code Diff / Dev Note):** Changed `checkout_controller.js` to clear the button loading state on error catch block because the button was staying disabled.
    *   **Generated Commit Message:**
        ```text
        [Bug Fix] Resolved an issue where the checkout button would occasionally remain frozen after a failed attempt.

        Previously, if an error occurred during payment verification, the purchase button would stay permanently locked in a loading state, forcing users to refresh the page. The system now properly resets the button on failure, allowing users to correct their information and try again immediately.
        ```

*   **Input (Code Diff / Dev Note):** Ran `bundle update openssl` to bump version to 3.0.13 due to vulnerability alert. Added a composite database index on organization_id and created_at for the reports table query optimization.
    *   **Generated Commit Message:**
        ```text
        [Security Update] Applied critical system patches to protect user data encryption and maintain high security standards.
        [Performance Update] Optimized database processing to significantly decrease the time it takes for organization reports to load.

        <clickup issue link>

        [Security Update] Applied critical system patches to protect user data encryption and maintain high security standards.

        Updated the application's secure connection tools to address newly discovered system vulnerabilities. This proactive measure ensures all transaction data and user sessions remain entirely encrypted and fully protected against external security threats.

        [Performance Update] Optimized database processing to significantly decrease the time it takes for organization reports to load.
        
        As the volume of organizational report data has grown, page loading times were gradually slowing down. This update restructures how the data is retrieved behind the scenes, eliminating latency issues and providing a much faster experience for administrators viewing historical summaries.
        ```
