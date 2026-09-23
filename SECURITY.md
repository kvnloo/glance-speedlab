# Security and privacy

## Supported version

Security fixes target the current `main` branch until tagged releases establish a broader support policy.

## Reporting a vulnerability

Do not open a public issue for a vulnerability that could expose camera frames, local files, credentials, or remote code execution. Use GitHub’s private security-advisory feature on the repository. If that feature is unavailable, contact the repository owner privately through the contact method on their GitHub profile.

Include a minimal reproduction, impact, affected commit, and suggested mitigation when known. Do not include real camera frames, credentials, or personally identifying data.

## Threat model

Speedlab is designed for trusted local use:

- The gateway, Glance, and optional MLX scorer bind to loopback by default.
- Camera frames are held in memory and sent only to the selected local backend.
- Metric recording is opt-in and excludes frame bytes.
- The static server is not hardened for exposure to untrusted networks.
- The application does not authenticate local users.

Do not bind Speedlab to a public interface without adding authentication, transport security, request limits, origin controls, and a production-grade server.
