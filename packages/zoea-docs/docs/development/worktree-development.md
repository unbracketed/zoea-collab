# Git Worktree Development

This guide explains how to use git worktrees for parallel development on multiple branches with isolated Docker environments.

## Overview

Each worktree gets:

- Its own git checkout (separate branch)
- Isolated Docker containers with unique names
- Unique ports for all services (frontend, backend, docs, postgres)
- Independent data volumes

This allows you to run multiple instances of Zoea Studio simultaneously, each on a different branch.

## Quick Start

```bash
# Create a new worktree for a feature branch
mise run worktree-create feature/my-feature

# List all worktrees
mise run worktree-list

# Remove a worktree when done
mise run worktree-remove my-feature
```

## Port Allocation

Each worktree is allocated a base port, and services are offset from that base:

| Service    | Offset | Main (20000) | Worktree (20100) |
|------------|--------|--------------|------------------|
| Frontend   | +0     | 20000        | 20100            |
| Backend    | +25    | 20025        | 20125            |
| Postgres   | +32    | 20032        | 20132            |
| Docs       | +50    | 20050        | 20150            |

Worktrees are allocated with a 100-port gap between them to allow for future service additions.

## Commands

### Create a Worktree

```bash
mise run worktree-create <branch-name> [worktree-name]
```

**Arguments:**

- `branch-name`: Git branch to checkout (created if it doesn't exist)
- `worktree-name`: Optional custom name (defaults to sanitized branch name)

**Example:**

```bash
# Create worktree for existing branch
mise run worktree-create feature/new-ui

# Create worktree with custom name
mise run worktree-create feature/authentication auth-feature
```

This will:

1. Allocate the next available port range
2. Create the git worktree at `../worktrees/ZoeaStudio-<name>/`
3. Generate a `.env` file with the correct ports
4. Update the worktree registry

### List Worktrees

```bash
mise run worktree-list
```

Shows all registered worktrees with their paths, branches, and port ranges.

### Remove a Worktree

```bash
mise run worktree-remove <worktree-name> [--force]
```

**Arguments:**

- `worktree-name`: Name of the worktree to remove
- `--force`: Skip confirmation prompt

This will:

1. Stop and remove Docker containers for the worktree
2. Remove Docker volumes for the worktree
3. Remove the git worktree directory
4. Update the worktree registry

## Working with a Worktree

After creating a worktree:

```bash
# Navigate to the worktree
cd ../worktrees/ZoeaStudio-my-feature

# Install dependencies
mise install

# Start Docker services
docker-compose up -d

# Or run without Docker
mise run dev-backend  # Uses port from .env
mise run dev-frontend # Uses port from .env
```

## Registry File

Worktrees are tracked in `.worktrees.json` at the project root:

```json
{
  "worktrees": {
    "main": {
      "base_port": 20000,
      "path": ".",
      "branch": "main",
      "created_at": "2025-12-04T00:00:00Z"
    },
    "my-feature": {
      "base_port": 20100,
      "path": "../worktrees/ZoeaStudio-my-feature",
      "branch": "feature/my-feature",
      "created_at": "2025-12-04T12:00:00Z"
    }
  },
  "next_base_port": 20200,
  "port_gap": 100
}
```

## Docker Container Naming

Containers are named using the `ZOEA_INSTANCE` environment variable:

- `zoeastudio-main-backend`
- `zoeastudio-main-frontend`
- `zoeastudio-my-feature-backend`
- `zoeastudio-my-feature-frontend`

This allows you to see which instance each container belongs to with `docker ps`.

## Troubleshooting

### Port Already in Use

If you see "port in use" errors, check what's running:

```bash
lsof -i :20100
```

The worktree-create script will automatically try the next available port range if conflicts are detected.

### Docker Volume Conflicts

If volumes from a previous worktree remain, remove them manually:

```bash
docker volume ls | grep zoeastudio-my-feature
docker volume rm zoeastudio-my-feature-backend-venv
```

### Orphaned Worktrees

If a worktree was removed outside of the script, clean up the registry:

```bash
# Prune git worktrees
git worktree prune

# Manually edit .worktrees.json to remove stale entries
```

### Main Worktree Protection

The main worktree cannot be removed via the script to prevent accidental deletion of your primary development environment.
