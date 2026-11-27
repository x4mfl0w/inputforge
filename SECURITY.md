# Security Policy

## Supported versions

Only the latest release receives security fixes.

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead, report them privately via
GitHub's [private vulnerability reporting](https://github.com/x4mfl0w/inputforge/security/advisories/new)
("Security" tab → "Report a vulnerability").

Please include a description of the issue, the affected version and platform, and steps to
reproduce. You can expect an initial response within a few days.

## Scope

InputForge installs global keyboard/mouse hooks and sends synthetic input. Relevant issues
include, for example:

- loading a crafted profile (JSON) or template image leading to code execution or file access
  outside the profile directory
- the application escalating privileges or exposing input to other processes/users

Using macros in games against their terms of service is not a security issue.
