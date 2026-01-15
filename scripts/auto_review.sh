#!/bin/bash

# auto_review.sh - Automatically review the latest changes using Gemini CLI

# 1. Get the latest changes (staged or last commit)
# If there are staged changes, review them. Otherwise review last commit.
if git diff --quiet --cached; then
    # No staged changes, check last commit
    DIFF_CONTENT=$(git show HEAD)
    CONTEXT="Review the following changes from the last commit:"
else
    # Staged changes exist
    DIFF_CONTENT=$(git diff --cached)
    CONTEXT="Review the following staged changes:"
fi

if [ -z "$DIFF_CONTENT" ]; then
    echo "No changes found to review."
    exit 0
fi

# 2. Construct Prompt
PROMPT="You are a Senior Software Engineer acting as a code reviewer. 
Review the following code changes for:
1. Potential bugs or race conditions
2. Security vulnerabilities
3. Code style and best practices
4. Logical errors

Be concise and constructive.

$CONTEXT
\`\`\`diff
$DIFF_CONTENT
\`\`\`
"

# 3. Call Gemini CLI
echo "🤖 Asking Gemini to review changes..."
echo "----------------------------------------"
gemini "$PROMPT"
echo "----------------------------------------"
