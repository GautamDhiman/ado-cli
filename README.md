# ADO CLI

A command-line tool for Azure DevOps work item management.

## Installation

```bash
cd ado-cli
python -m venv venv
source venv/bin/activate
pip install -e .
```

## Configuration

Run the interactive setup:

```bash
ado config
```

This prompts for:
- **Organization**: Your Azure DevOps org (e.g., `delhivery`)
- **Project**: Project name (e.g., `Fleet Management System`)
- **PAT**: Personal Access Token

Config is saved to `~/.ado-cli/config.yaml`

### View Current Config

```bash
ado config --show
```

### Test Connection

```bash
ado test
```

## Commands

### List My Work Items

```bash
ado item list
```

Filter by state:

```bash
ado item list --state "In Progress"
```

### Sprint Board

View your current sprint work items grouped by state:

```bash
ado board
```

View another user's sprint board:

```bash
ado board --user "user@example.com"
```

### Sprint Summary

View sprint effort totals (story points, estimates, progress):

```bash
ado sprint summary
```

Output:
```
Sprint: Fleet 2026 06 Jan - 19 Jan

        Sprint Effort Summary        
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Metric               ┃      Value ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Total Items          │          7 │
│ Story Points         │       13.0 │
│ Original Estimate    │      54.0h │
│ Completed Work       │      37.0h │
│ Remaining Work       │      18.0h │
│ Progress             │        69% │
└──────────────────────┴────────────┘
```

### Get Work Item Details

```bash
ado item get 332561
```

Shows: ID, Type, Title, State, Assigned To, Iteration, Area, Story Points, Original Estimate, Remaining Work, Completed Work, Tags, URL, and Description.

### Update Work Item

Update completed work hours:

```bash
ado item update 332561 --completed 8
```

Update remaining work:

```bash
ado item update 332561 --remaining 6
```

Update multiple fields:

```bash
ado item update 332561 --state "In Progress" --remaining 4 --completed 2
```

Available update options:
- `--state`, `-s` - Work item state
- `--title`, `-t` - Title
- `--desc`, `-d` - Description
- `--remaining`, `-r` - Remaining work (hours)
- `--completed`, `-c` - Completed work (hours)
- `--points`, `-p` - Story points
- `--estimate`, `-e` - Original estimate (hours)
- `--interactive`, `-i` - Interactive mode (shows current values)

### Interactive Update Mode

```bash
ado item update 332561 -i
```

Prompts for each field showing current values - press Enter to keep existing value.

### Add Comment

```bash
ado comment add 332561 "Your comment here"
```

Or interactively:

```bash
ado comment add 332561
# Prompts for comment text
```

### List Comments

```bash
ado comment list 332561
```

## File Locations

| File | Purpose |
|------|---------|
| `~/.ado-cli/config.yaml` | Stores org, project, and PAT |

## Requirements

- Python 3.10+
- Azure DevOps Personal Access Token with Work Items read/write scope

## Future prospects
- Agent integration.

---

**Author:** Gautam Dhiman  
**Created:** January 2026

