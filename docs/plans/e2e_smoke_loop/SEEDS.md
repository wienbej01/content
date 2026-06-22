# Smoke Test Seed Topics (25 seeds)

Each seed produces a ~25-second teaser video with 2 hero shots, 1 b-roll, 1 graphic.

## AI Productivity & Time Management

1. "Use AI to batch process your morning email inbox in under 60 seconds"
2. "Let AI schedule your entire week from a single voice memo on Monday"
3. "Replace three tools with one AI assistant for project management"
4. "How AI meeting summaries save two hours of re-reading notes every day"
5. "AI calendar blocking: turn your to-do list into a complete daily schedule"
6. "Train an AI to write your weekly status reports from Slack messages"
7. "Use AI to triage your notifications and silence 90 percent of interruptions"
8. "How to delegate research tasks to AI and get summaries while you sleep"
9. "AI-powered Pomodoro: dynamically adjust work blocks based on energy levels"
10. "Build a personal AI dashboard that tracks your deep work hours automatically"

## AI Decision-Making & Workflow

11. "Let AI draft your difficult emails so you can send them without anxiety"
12. "Use AI to analyze your calendar and find three hidden hours every week"
13. "How AI can read your meeting transcripts and assign action items instantly"
14. "Replace your daily standup with an AI bot that tracks progress across tools"
15. "AI priority scoring: rank your 20 tasks by actual business impact in seconds"
16. "Train an AI to spot repetitive tasks in your workflow and automate them"
17. "Use AI to generate presentation slides from a single paragraph of notes"
18. "How to build an AI onboarding buddy that answers new hire questions 24-7"
19. "AI code review: catch bugs before your team sees them in pull requests"
20. "Let AI write your performance review from git commits and project logs"

## AI Creativity & Communication

21. "Use AI to brainstorm 50 content ideas from a single customer interview transcript"
22. "How AI can rewrite your technical documentation for five different audiences"
23. "Train an AI on your writing style to draft blog posts in your voice"
24. "AI video scripting: turn a bullet list into a complete storyboard in minutes"
25. "Use AI to generate custom diagrams and charts from spreadsheet data instantly"

## Seed Format

Each seed is used as: `python3 scripts/produce_db.py create --seed "<seed text>" --format teaser`

The pipeline auto-configures shots based on storyboard beats. Target output:
- 25 seconds total
- 2 hero lipsync shots (S000, S001) — AI avatar delivering key lines  
- 1 b-roll shot (B000) — supporting visual
- 1 graphic overlay (G000) — title card or lower third
