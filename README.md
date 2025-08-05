# Briefly

A tool to briefly aggregate and display information from multiple sources (GitHub, Matrix) in a unified format.

## Features

- Fetch GitHub repository issues and pull requests
- Read Matrix room messages
- Configurable via TOML file
- Support for multiple clients simultaneously

## Installation

```bash
# Install dependencies
uv sync

# Run the program
uv run main.py
```

## Configuration

Create a `clients.toml` file to configure your data sources. Each section represents a different client configuration.

### Basic Structure

```toml
[section_name]
name = "Display Name"
api = "github" | "matrix"
# ... specific configuration options
```

### GitHub Configuration

```toml
[github_example]
name = "Podman Issues"
api = "github"
access_token = "github_pat_xxxxx"  # or "ghp_xxxxx"
owner = "containers"
repo = "podman"
```

#### GitHub Token Requirements
- Use GitHub Personal Access Token (classic) with format `github_pat_*` 
- Or GitHub App token with format `ghp_*`
- Token must have read access to the repository

### Matrix Configuration

```toml
[matrix_example]
name = "My Matrix Room"
api = "matrix"
config = "credentials.json"  # Path to JSON file with Matrix credentials
room_id = "!roomid:example.org"
```

The `credentials.json` file should contain:
```json
{
    "homeserver": "https://matrix.example.org",
    "access_token": "syt_xxxxx",
    "user_id": "@user:example.org",
    "device_id": "DEVICEID123"
}
```

### Generte `credentials.json`

Use the included `login_with_access_token.py` script to generate Matrix credentials:

```bash
uv run login_with_access_token.py
```

This will create a `credentials.json` file that you can reference in your TOML configuration.


## Output Format

The program outputs information in a pseudo-markdown format. The display now includes initialization info and a timestamp:

```
# Initialized 2 clients
## Now is: 2025-08-05T13:31:27.498599
## Clients:
- podman_issues
- podman_prs
- matrix_testing_room

## Display Name

Issue: Issue title here
Author: github_username
URL: https://api.github.com/repos/owner/repo/issues/...
Created: 0 days ago: 2025-08-05
Updated: 0 days ago: 2025-08-05

Body: Full issue body text...

---

...

---

PR: A PR title here
Author: another_user
URL: https://api.github.com/repos/owner/repo/pull/...
Created: 1 days ago: 2025-08-04
Updated: 0 days ago: 2025-08-05

Body: Another issue body...

---

...

---

## Testing Room

[10:26:24] (PTjHTIkO) <@user1:matrix.org>: this is a public room
[10:26:33] (UTsdvvdd) <@user2:matrix.org>: all messages are unencrypted
[10:26:44] (rYc3B3qa) <@user1:matrix.org> (Re: UTsdvvdd): we can interact and reply
[10:26:51] (sgwNCe5k) <@user1:matrix.org> (Th: rYc3B3qa) and create a thread
[11:05:35] (FrnbwA-f) <@user1:matrix.org>: isolated message
[11:05:50] (HPnT15Sq) <@user2:matrix.org> (Th: rYc3B3qa) this is part of the thread btw
[11:06:05] (odyi3pjB) <@user2:matrix.org> (Th: rYc3B3qa) and there is a reply within the thread

---
```

## Development

- `main.py` - Main application entry point
- `login_with_access_token.py` - Matrix credential generator
- `clients.toml` - Configuration file (create this)

## Security Notes

- Never commit tokens or credentials to version control
- Use environment variables or secure credential storage for production deployments
- GitHub tokens should have minimal required permissions
- Matrix access tokens provide full account access - handle with care
