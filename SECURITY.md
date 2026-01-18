# Security Policy

## Overview

The Zwift Control API is explicitly designed for **LOCAL NETWORK USE ONLY** in a trusted home environment. This document outlines the security model, known limitations, and best practices for secure deployment.

## Threat Model

### Intended Use Case

- **Environment**: Home LAN (Local Area Network)
- **Threat Level**: Low-to-medium threat environment
- **Assumptions**:
  - Network is protected by router firewall (NAT)
  - Wireless network uses WPA3 or WPA2 encryption
  - Only trusted devices on the network
  - Physical security of network (no public access)

### Out of Scope

This API is **NOT designed for**:

- Public internet exposure (DO NOT port forward)
- Multi-tenant environments
- Untrusted networks (coffee shops, hotels, etc.)
- Enterprise deployments without additional security layers

## Current Security Posture

### ✅ Security Features Implemented

1. **No Hardcoded Secrets**: All sensitive configuration (IP, MAC, credentials) loaded from environment variables
2. **SSH Public Key Authentication**: No passwords transmitted over network
3. **Sanitized Logging**: IP addresses, MAC addresses, and hostnames are masked in logs
4. **Docker Security**: Non-root user, minimal attack surface
5. **Explicit CORS Methods**: Only GET and POST allowed (no wildcards)
6. **Pre-commit Hooks**: Automated secret detection prevents credential commits
7. **Network Isolation**: Designed for host network mode (local only)

### ⚠️ Known Limitations

1. **No Authentication**: Anyone on the local network can access the API
   - **Rationale**: Home LAN environment, would break iOS Shortcuts integration
   - **Mitigation**: Network-level security (router firewall, WiFi encryption)

2. **SSH Host Key Verification Disabled**: Vulnerable to Man-in-the-Middle attacks
   - **Rationale**: Local network with static IP reduces risk
   - **Mitigation**: Use static IP, monitor network for rogue devices
   - **Code Location**: api/utils/ssh_client.py:64, 132

3. **CORS Wildcard Origins**: Any origin can make requests
   - **Rationale**: iOS Shortcuts use dynamic local IPs
   - **Mitigation**: `allow_credentials=False`, explicit methods/headers
   - **Code Location**: api/main.py:34

4. **No Rate Limiting**: Susceptible to abuse if malicious device on network
   - **Rationale**: Low-risk home environment
   - **Mitigation**: Network access control, monitor logs

5. **No TLS/HTTPS**: All traffic unencrypted on local network
   - **Rationale**: Local network, minimal eavesdropping risk
   - **Mitigation**: Use WPA3 WiFi encryption, consider VPN for remote access

## Network Security Recommendations

### Router Configuration

1. **Enable Firewall**: Ensure router firewall is active (blocks inbound from internet)
2. **Disable Port Forwarding**: NEVER port forward to API (ports 8000, 8001)
3. **Disable UPnP**: Prevent automatic port forwarding
4. **Enable WiFi Encryption**: Use WPA3 (or WPA2 minimum)
5. **Change Default Credentials**: Router admin password should be strong and unique

### Network Segmentation (Advanced)

For enhanced security, consider VLAN segmentation:

- **IoT VLAN**: Place Zwift PC and API on isolated network
- **Firewall Rules**: Only allow specific devices (your Mac, iPhone) to access API
- **Network Monitoring**: Use Pi-hole or similar to detect anomalies

### Access Control

1. **Strong WiFi Password**: Use 20+ character passphrase
2. **MAC Address Filtering**: (Optional) Whitelist known devices
3. **Guest Network**: Do NOT allow guest devices access to main network
4. **Regular Audits**: Periodically review connected devices

## Secure Deployment Checklist

Before deploying the Zwift Control API, ensure:

- [ ] `.env` file contains your actual PC configuration (not defaults)
- [ ] `.env` file has restrictive permissions (`chmod 600 .env`)
- [ ] SSH public key authentication is configured (not password)
- [ ] Router firewall is enabled and configured
- [ ] WiFi uses WPA3 or WPA2 encryption
- [ ] No port forwarding to API ports (8000, 8001)
- [ ] API runs in Docker with host network mode (--network host)
- [ ] Logs are monitored for suspicious activity
- [ ] Pre-commit hooks are installed (`pre-commit install`)

## Future Roadmap (v2.0)

The following security enhancements are planned for future releases:

### Authentication & Authorization

- **API Key Authentication**: Simple token-based auth for API access
- **JWT Tokens**: Short-lived tokens for iOS Shortcuts
- **HMAC Request Signing**: Verify request integrity
- **IP Allowlist**: Restrict access to specific devices

### SSH Improvements

- **Host Key Verification**: Enable known_hosts checking with first-time setup flow
- **Certificate-Based Auth**: Stronger than public key authentication
- **Connection Pooling**: Reduce SSH handshake overhead

### TLS/HTTPS

- **Self-Signed Certificates**: HTTPS for local network
- **Automatic Certificate Rotation**: Using certbot or similar
- **Certificate Pinning**: For iOS Shortcuts (prevent MITM)

### Rate Limiting & Monitoring

- **Rate Limiting**: Prevent abuse (e.g., 100 requests/minute per IP)
- **Audit Logging**: Detailed logs of all API access
- **Prometheus Metrics**: Security events exported for alerting

### Compliance

- **Security Headers**: HSTS, X-Frame-Options, CSP
- **Input Validation**: Enhanced sanitization of all inputs
- **Secrets Management**: Integration with Vault or similar

## Vulnerability Reporting

If you discover a security vulnerability, please report it responsibly:

- **Email**: <eamon.mason@thomsonreuters.com>
- **Subject**: "Zwift Control API Security Issue"
- **Include**:
  - Description of the vulnerability
  - Steps to reproduce
  - Potential impact
  - Suggested fix (if any)

**Please do NOT**:

- Open a public GitHub issue for security vulnerabilities
- Exploit the vulnerability maliciously
- Share vulnerability details publicly before fix is available

We aim to respond to security reports within 72 hours and provide a fix within 30 days.

## Security Best Practices for Users

### Environment Variables (.env)

```bash
# GOOD - Using .env file (ignored by git)
PC_NAME=desktop-fpu771
PC_IP=192.168.1.194
PC_MAC=B0:83:FE:68:5B:E6
PC_USER=eamon

# BAD - Hardcoding in code (security risk)
settings = Settings(pc_ip="192.168.1.194")  # DON'T DO THIS
```

### SSH Key Permissions

```bash
# Correct permissions for SSH keys
chmod 600 ~/.ssh/id_rsa        # Private key (read/write for owner only)
chmod 644 ~/.ssh/id_rsa.pub    # Public key (readable by all)
```

### Container Security

```bash
# GOOD - Host network mode (local only)
docker run --network host -v ~/.ssh/id_rsa:/home/apiuser/.ssh/id_rsa:ro zwift-control

# BAD - Port mapping exposes to all interfaces
docker run -p 0.0.0.0:8000:8000 zwift-control  # DON'T DO THIS
```

### Log Monitoring

Regularly check logs for suspicious activity:

```bash
# View recent API access
docker logs zwift-control | grep -E "POST|GET" | tail -n 50

# Check for failed authentication attempts (future feature)
docker logs zwift-control | grep -i "unauthorized\|forbidden"
```

## Acceptable Use Cases

### ✅ Acceptable

- Using API from your Mac on home network
- iOS Shortcuts on your iPhone connected to home WiFi
- Docker deployment on local network
- Monitoring with Prometheus/Grafana on same network
- VPN access to home network (with proper VPN security)

### ❌ NOT Acceptable

- Exposing API to public internet via port forwarding
- Running API on untrusted networks (coffee shop WiFi)
- Sharing API access with untrusted users
- Using API for critical infrastructure (medical, safety systems)
- Deploying without proper network security (open WiFi, no firewall)

## Security Considerations by Component

### Wake-on-LAN (WoL)

- **Risk**: WoL packets are broadcast on local network (unencrypted)
- **Mitigation**: Local network only, requires network access to send packets
- **Impact**: Low (can only wake PC, not execute commands)

### SSH Remote Execution

- **Risk**: Arbitrary command execution on target PC
- **Mitigation**: Public key authentication, command logging, non-root user
- **Impact**: High if compromised (full PC access)

### FastAPI Application

- **Risk**: Arbitrary API calls from any device on network
- **Mitigation**: Network segmentation, input validation, sanitized logging
- **Impact**: Medium (can control PC but no data exfiltration)

### Docker Container

- **Risk**: Container escape to host system
- **Mitigation**: Non-root user, minimal base image, read-only SSH key mount
- **Impact**: Low (Docker provides strong isolation)

## Compliance & Standards

This project does NOT comply with:

- **PCI DSS**: Payment card industry standards (not applicable)
- **HIPAA**: Healthcare data protection (not applicable)
- **SOC 2**: Security, availability, and confidentiality controls (home use)
- **ISO 27001**: Information security management (not certified)

This project IS suitable for:

- **Home automation and personal use**
- **Non-critical monitoring and control**
- **Educational and learning purposes**

## License

This security policy is provided "as-is" without warranty. By using this software, you acknowledge the security limitations and accept responsibility for secure deployment in your environment.

---

**Last Updated**: 2026-01-18
**Version**: 1.0.0
**Contact**: <eamon.mason@thomsonreuters.com>
