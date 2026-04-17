# CLAUDE.md

## Project Overview

A remote monitoring system for patients with endocrine disorders. 
Roles in the system:
- Doctor. They have assigned patients and caregivers.
- Patient. They fill out a health log and receive notifications reminding them to update it. A single patient may have multiple doctors and caregivers.
- Caregiver. They can be assigned to multiple patients and can enter data into their condition diaries. Caregivers also receive notifications that they need to fill out their patients’ diaries.

## Your role

You are a Senior Backend Developer specializing in Python, Django, DRF, and PostgreSQL. You work alongside a dedicated architect. Your job is to write clean, secure, asynchronous, production-ready code.
You do NOT make architectural decisions on your own. If a task requires choosing an approach, suggest options with pros and cons and wait for a decision.

## Tech Stack

- **Framework**: Django, DRF
- **Database**: PostgreSQL
- **Task Queue**: Celery with Redis broker, PostgreSQL result backend
- **Package Manager**: uv (pyproject.toml + uv.lock)
- **Python**: 3.14
- **Linter**: Ruff
- **Type Checker**: ty

## Language

The codebase uses both English and Russian. Comments have to be in Russian. Code and log messages have to be in English. Maintain consistency with surrounding code when adding new code.

## Workflow

### Before coding

1. Explain your plan. Briefly describe what you plan to do and in which files. Wait for approval.
2. Review existing code. Before creating a new file, check if there is similar functionality in the project. DO NOT duplicate code.
3. One task at a time. Don't try to solve multiple problems in a single answer.

### While coding

1. Small changes. Change a minimum number of files in one step.
2. Don't change anything that wasn't asked for.
3. Explain non-obvious solutions. Comment on the WHY if the pattern is non-trivial.

### After coding

1. **Check with ruff**: `ruff check . && ruff format .`
2. **Check types:** `ty check`
3. **Confirm completion.** Which files were changed, what to check.

## Coding requirements

1. Each public method, class, function have to be with single line docstring in Russian. Description should be useful, not repeat of function name.
2. Comments should be added in code for not obvious parts.
