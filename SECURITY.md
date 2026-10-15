# Security policy

## Supported code

Security fixes target the latest code on `main`. Older commits and forks do not have a separate security-maintenance guarantee. Update dependencies and review upstream security advisories when running Crunch3D.

## Report a vulnerability privately

Use GitHub's **Report a vulnerability** option in the repository's [Security advisories](https://github.com/Lesgo-HQ/Crunch3D/security/advisories) page when it is available. Private vulnerability reporting must be enabled by a repository administrator; this document does not enable it.

If the option is unavailable, contact a [maintainer](MAINTAINERS.md) using a private contact method listed on their GitHub profile. If no private route is listed, open an issue that only requests a secure contact channel. Do not include the vulnerability, exploit, sensitive file, or affected user's details in a public issue.

Include the affected commit, operating system, dependency versions, impact, and minimal reproduction once a private channel is established. Use synthetic data and redact secrets. Please allow the maintainers time to investigate and coordinate disclosure. There is no guaranteed response time or paid bounty program.

## Local deployment boundary

Crunch3D is intended to run on your computer with the backend bound to `127.0.0.1`. It has no multi-user authentication or tenant isolation. CORS is not authentication. Do not expose the API directly to the internet.

Mesh parsing uses native dependencies. Treat untrusted files cautiously and avoid running the application with elevated privileges. Uploads and outputs persist locally until deleted. There is no application upload cap by default; `MAX_FILE_SIZE_MB` can limit individual uploads, but is not a complete memory, CPU, or disk quota.
