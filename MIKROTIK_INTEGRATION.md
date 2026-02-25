# MikroTik Integration Guide

WGDashboard now supports managing WireGuard configurations on MikroTik RouterOS devices via their REST API. This allows you to manage remote MikroTik routers directly from the dashboard without needing SSH access or manual configuration file editing.

> **💡 Quick Start**: MikroTik routers use **self-signed SSL certificates by default**. This integration works out-of-the-box with these certificates by using encrypted HTTPS connections without certificate validation (`verify_ssl=False`). This is safe for private networks. See [FAQ](#-frequently-asked-questions) for details.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [MikroTik Router Setup](#mikrotik-router-setup)
- [Adding MikroTik Configuration](#adding-mikrotik-configuration)
- [API Endpoints](#api-endpoints)
- [Features](#features)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [FAQ](#-frequently-asked-questions)

---

## 🔧 Prerequisites

### Important: MikroTik API vs REST API

⚠️ **MikroTik has TWO different APIs - this integration uses REST API only:**

| Feature | Binary API | REST API (Used Here) |
|---------|-----------|---------------------|
| **Service** | `/ip/service/api` or `/ip/service/api-ssl` | `/ip/service/www` or `/ip/service/www-ssl` |
| **Default Ports** | 8728 (non-SSL), 8729 (SSL) | 80 (HTTP), 443 (HTTPS) |
| **Protocol** | Binary/proprietary | HTTP/HTTPS with JSON |
| **Authentication** | Custom | HTTP Basic Auth |
| **Endpoint Format** | Binary commands | `/rest/...` URLs |

**This integration requires the REST API (www/www-ssl service), NOT the binary API (api/api-ssl).**

### WGDashboard Requirements
- WGDashboard v4.3.1 or later
- Python packages: `requests`, `urllib3` (automatically installed)

### MikroTik Requirements
- RouterOS v7.0+ (for WireGuard support)
- REST API enabled (web service: www or www-ssl)
- User account with appropriate permissions

---

## 🛠️ MikroTik Router Setup

### 1. Enable REST API

Connect to your MikroTik router via terminal or Winbox and enable the REST API (web service):

```routeros
# Enable HTTPS web service (REST API)
/ip/service/enable www-ssl
/ip/service/set www-ssl port=443
```

Or for HTTP (not recommended for production):

```routeros
# Enable HTTP web service (REST API)
/ip/service/enable www
/ip/service/set www port=80
```

**Note:** The REST API is accessed via the web service (www/www-ssl), NOT the binary API service (api/api-ssl).

### 2. Create API User

Create a dedicated user for WGDashboard (recommended):

```routeros
/user add name=wgdashboard password=YourSecurePassword group=full comment="WGDashboard API Access"
```

**Security Best Practice**: Create a custom group with minimal required permissions:

```routeros
/user/group add name=wgdashboard-api policy=api,read,write,policy,test

/user add name=wgdashboard password=YourSecurePassword group=wgdashboard-api
```

### 3. Configure Firewall (Optional)

Allow access to REST API from WGDashboard server IP:

```routeros
/ip/firewall/filter
add chain=input action=accept protocol=tcp dst-port=443 src-address=YOUR_WGDASHBOARD_IP comment="WGDashboard REST API Access"
```

**Note:** Use port 443 for HTTPS (www-ssl) or port 80 for HTTP (www).

### 4. Understand SSL/TLS with Self-Signed Certificates

**Important**: MikroTik routers use **self-signed SSL certificates by default**. This is normal and expected.

#### What This Means:
- ✅ **Traffic is encrypted** - HTTPS connection is secure
- ⚠️ **Certificate cannot be validated** - No trusted CA signature
- ✅ **Safe for private networks** - When connecting to known devices on your LAN/VPN

#### How WGDashboard Handles This:
```python
# In MikroTikClient initialization:
verify_ssl=False  # Skip certificate validation (default)
use_ssl=True      # Still use HTTPS encryption
```

When `verify_ssl=False`:
- HTTPS connection is established
- Data is encrypted with TLS/SSL
- Certificate chain validation is skipped
- Prevents "certificate verification failed" errors

#### Connection Options:

| Option | Security | MikroTik Default Cert | Signed Cert | HTTP Only |
|--------|----------|----------------------|-------------|-----------|
| `use_ssl=True, verify_ssl=False` | ✅ Encrypted | ✅ Works | ✅ Works | ❌ N/A |
| `use_ssl=True, verify_ssl=True` | ✅ Encrypted + Verified | ❌ Fails | ✅ Works | ❌ N/A |
| `use_ssl=False` | ❌ Plain text | ❌ N/A | ❌ N/A | ✅ Works |

**Recommended**: Use `use_ssl=True, verify_ssl=False` for MikroTik with default certificates on private networks.

### 5. Test REST API Access

Test from your WGDashboard server:

```bash
# Test with self-signed certificate (default MikroTik setup)
curl -k -u wgdashboard:YourSecurePassword \
  https://your-mikrotik-ip:443/rest/system/resource

# The -k flag tells curl to skip certificate verification (same as verify_ssl=False)
```

You should receive a JSON response with system information.

---

## 📱 Adding MikroTik Configuration

### Via Web Interface

1. **Navigate to Configuration Management**
   - Click "Add Configuration" or "+"
   - Select "MikroTik Device" as configuration type

2. **Enter Connection Details**
   - **Configuration Name**: Name for this config in WGDashboard
   - **MikroTik Host**: IP address or hostname of your MikroTik router
   - **Username**: API username (e.g., `wgdashboard`)
   - **Password**: API user password
   - **Port**: REST API port (default: 443 for HTTPS/www-ssl, 80 for HTTP/www)
   - **Use SSL**: Enable for HTTPS (recommended - provides encryption)
   - **Verify SSL**: ⚠️ **Set to FALSE for self-signed certificates** (MikroTik default)
     - MikroTik routers use self-signed SSL certificates by default
     - Setting this to `false` allows connection while still using encrypted HTTPS
     - Only enable verification if you've installed a proper signed certificate on MikroTik

3. **Choose Mode**

   **Import Existing Configuration:**
   - Select existing WireGuard interface from MikroTik
   - Dashboard will import all settings and peers
   
   **Create New Configuration:**
   - Provide WireGuard settings (PrivateKey, ListenPort, Address)
   - Dashboard will create interface on MikroTik

4. **Test Connection**
   - Click "Test Connection" to verify settings
   - Dashboard will show available WireGuard interfaces

### Via API

#### Test Connection

```bash
curl -X POST http://localhost:10086/api/testMikroTikConnection \
  -H "Content-Type: application/json" \
  -d '{
    "MikroTikHost": "192.168.88.1",
    "MikroTikUsername": "wgdashboard",
    "MikroTikPassword": "YourPassword",
    "MikroTikPort": 443,
    "MikroTikUseSSL": true,
    "MikroTikVerifySSL": false
  }'
```

#### Import Existing Configuration

```bash
curl -X POST http://localhost:10086/api/addMikroTikConfiguration \
  -H "Content-Type: application/json" \
  -d '{
    "ConfigurationName": "wg0",
    "MikroTikHost": "192.168.88.1",
    "MikroTikUsername": "wgdashboard",
    "MikroTikPassword": "YourPassword",
    "MikroTikPort": 443,
    "MikroTikUseSSL": true,
    "MikroTikVerifySSL": false,
    "CreateNew": false
  }'
```

#### Create New Configuration

```bash
curl -X POST http://localhost:10086/api/addMikroTikConfiguration \
  -H "Content-Type: application/json" \
  -d '{
    "ConfigurationName": "wg-remote",
    "MikroTikHost": "192.168.88.1",
    "MikroTikUsername": "wgdashboard",
    "MikroTikPassword": "YourPassword",
    "MikroTikPort": 443,
    "MikroTikUseSSL": true,
    "MikroTikVerifySSL": false,
    "CreateNew": true,
    "PrivateKey": "YourWireGuardPrivateKey==",
    "ListenPort": 13231,
    "Address": "10.0.0.1/24",
    "MTU": 1420
  }'
```

---

## 🔌 API Endpoints

### MikroTik-Specific Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/testMikroTikConnection` | POST | Test connection to MikroTik device |
| `/api/addMikroTikConfiguration` | POST | Add/import MikroTik WireGuard config |

### Standard Endpoints (Work with MikroTik)

All standard WGDashboard endpoints work with MikroTik configurations:

- `/api/addPeers/<configName>` - Add peers to MikroTik
- `/api/deletePeers/<configName>` - Delete peers from MikroTik
- `/api/updatePeerSettings/<configName>` - Update peer settings
- `/api/toggleWireguardConfiguration` - Enable/disable interface
- `/api/getWireguardConfigurations` - List all configurations

---

## ✨ Features

### Supported Operations

✅ **Configuration Management**
- Import existing WireGuard interfaces from MikroTik
- Create new WireGuard interfaces on MikroTik
- Enable/disable interfaces
- View interface status and settings
- Read configuration as standard WireGuard format

✅ **Peer Management**
- Add peers to MikroTik interfaces
- Delete peers from MikroTik
- Update peer settings (AllowedIPs, PresharedKey, etc.)
- Bulk peer creation
- View peer status and handshakes

✅ **Monitoring**
- Real-time peer handshake tracking
- Transfer statistics (RX/TX bytes)
- Connection status monitoring
- Historical data tracking

✅ **Security**
- HTTPS/SSL support with encryption
- **Self-signed certificate support** (MikroTik default)
- Username/password authentication
- Preshared key support for peers

### What's Synchronized

The following data is synchronized between WGDashboard and MikroTik:

**Interface:**
- PrivateKey / PublicKey
- ListenPort
- MTU
- IP Addresses
- Enabled/Disabled status

**Peers:**
- PublicKey
- PresharedKey
- AllowedIPs
- PersistentKeepalive
- Endpoint (read-only from MikroTik)
- Transfer statistics
- Last handshake

---

## ⚠️ Limitations

### MikroTik-Specific Limitations

1. **No Pre/Post Up/Down Scripts**
   - MikroTik doesn't support these WireGuard features
   - Use MikroTik's native scripting system instead

2. **No SaveConfig Setting**
   - MikroTik automatically persists configuration
   - No need for `wg-quick save`

3. **Different MTU Defaults**
   - MikroTik default: 1420
   - Standard WireGuard: 1420
   - Adjust if needed for your network

4. **Peer Names as Comments**
   - Peer names are stored in the `comment` field
   - Limited to MikroTik's comment length restrictions

5. **Connection Dependency**
   - Requires network connectivity to MikroTik device
   - Operations will fail if device is unreachable

### API Rate Limiting

MikroTik's REST API may have rate limiting. If you experience issues:
- Reduce polling frequency in WGDashboard settings
- Avoid rapid successive API calls
- Check MikroTik logs for API connection issues

---

## 🔍 Troubleshooting

### Connection Issues

**Problem**: "Connection error" or "Request timeout"

**Solutions**:
1. Verify MikroTik is reachable: `ping your-mikrotik-ip`
2. Check firewall rules on MikroTik
3. Verify REST API (web service) is enabled: `/ip/service/print` (look for www or www-ssl)
4. Check port number (default: 443 for www-ssl, 80 for www)
5. Ensure the web service is enabled, not just the binary API service
6. Try increasing timeout in `MikroTikClient.__init__`

---

### Authentication Failures

**Problem**: "Authentication failed" or 401/403 errors

**Solutions**:
1. Verify username and password
2. Check user permissions: `/user/print`
3. Ensure user has appropriate group permissions
4. Try admin account to isolate permission issues

---

### SSL Certificate Errors

**Problem**: "SSL certificate verification failed"

**Solutions**:
1. ✅ **Recommended**: Set `MikroTikVerifySSL` to `false` for self-signed certificates (MikroTik default)
   - This is safe when connecting to known MikroTik devices on your network
   - SSL/TLS encryption is still used, only certificate validation is skipped
2. Or install MikroTik's certificate on WGDashboard server:
   ```bash
   # Export certificate from MikroTik
   /certificate export-certificate www-ssl
   # Copy to WGDashboard server and install in system trust store
   ```
3. Or use a proper signed certificate on MikroTik (Let's Encrypt, etc.)
4. Or use HTTP instead of HTTPS (not recommended for production)

**Note**: MikroTik routers use self-signed certificates by default. The integration is designed to work with these out-of-the-box by setting `verify_ssl=False`, which still provides encrypted communication but skips certificate validation.

---

### Interface Not Found

**Problem**: "WireGuard interface not found on MikroTik device"

**Solutions**:
1. Verify interface exists: `/interface/wireguard/print`
2. Check exact interface name (case-sensitive)
3. Try listing available interfaces via test connection
4. Create interface manually on MikroTik first

---

### Peer Operations Fail

**Problem**: "Failed to add/delete peer"

**Solutions**:
1. Check MikroTik logs: `/log/print where topics~"wireguard"`
2. Verify AllowedIPs format (comma-separated, CIDR notation)
3. Ensure PublicKey is valid base64
4. Check for duplicate AllowedIPs
5. Verify interface is enabled

---

### Statistics Not Updating

**Problem**: Transfer stats or handshakes not showing

**Solutions**:
1. Enable interface: `/interface/wireguard/enable [find name=wg0]`
2. Verify peers are active and connecting
3. Check background thread is running in WGDashboard
4. Increase polling interval if too aggressive
5. Check MikroTik system resources

---

## 📊 Architecture

### Components

```
┌─────────────────┐         ┌──────────────────┐
│  WGDashboard    │◄───────►│  MikroTik Router │
│                 │  HTTPS  │                  │
│  ┌───────────┐  │ REST API│  ┌────────────┐  │
│  │Dashboard  │  │         │  │ WireGuard  │  │
│  │   UI      │  │         │  │ Interface  │  │
│  └─────┬─────┘  │         │  └────────────┘  │
│        │        │         │                  │
│  ┌─────▼─────┐  │         │                  │
│  │ MikroTik  │  │         │                  │
│  │ WG Config │  │         │                  │
│  └─────┬─────┘  │         │                  │
│        │        │         │                  │
│  ┌─────▼─────┐  │         │                  │
│  │ MikroTik  │  │         │                  │
│  │  Client   │──┼────────►│                  │
│  └───────────┘  │         │                  │
│                 │         │                  │
│  ┌───────────┐  │         │                  │
│  │ Database  │  │         │                  │
│  │(SQLAlchemy│  │         │                  │
│  └───────────┘  │         │                  │
└─────────────────┘         └──────────────────┘
```

### Data Flow

1. **Dashboard → MikroTikClient**: API requests
2. **MikroTikClient → MikroTik**: HTTPS REST API calls
3. **MikroTik → MikroTikClient**: JSON responses
4. **MikroTikWireguardConfiguration**: Parses and stores in database
5. **Database**: Stores peer info, statistics, history

---

## 🔐 Security Best Practices

1. **Use HTTPS**: Always use SSL/TLS for API communication
2. **Dedicated User**: Create separate user for WGDashboard
3. **Minimal Permissions**: Grant only necessary permissions
4. **Strong Passwords**: Use complex passwords for API users
5. **Firewall Rules**: Restrict API access to WGDashboard IP
6. **Regular Updates**: Keep RouterOS and WGDashboard updated
7. **Monitor Logs**: Check MikroTik logs regularly for suspicious activity
8. **VPN Access**: Consider accessing MikroTik API over VPN

---

## 🚀 Example Workflow

### Complete Setup Example

```bash
# 1. Enable REST API on MikroTik (web service)
/ip/service/enable www-ssl
/ip/service/set www-ssl port=443

# 2. Create WGDashboard user
/user/group add name=wgdashboard-api policy=api,read,write,policy,test
/user add name=wgdashboard password=SecurePass123! group=wgdashboard-api

# 3. Create WireGuard interface on MikroTik (if not exists)
/interface/wireguard add name=wg0 listen-port=13231 private-key="YourPrivateKey=="

# 4. Add IP address
/ip/address add address=10.0.0.1/24 interface=wg0

# 5. Enable interface
/interface/wireguard enable wg0

# 6. In WGDashboard, import the configuration
curl -X POST http://localhost:10086/api/addMikroTikConfiguration \
  -H "Content-Type: application/json" \
  -d '{
    "ConfigurationName": "wg0",
    "MikroTikHost": "192.168.88.1",
    "MikroTikUsername": "wgdashboard",
    "MikroTikPassword": "SecurePass123!",
    "MikroTikPort": 443,
    "MikroTikUseSSL": true,
    "MikroTikVerifySSL": false
  }'

# 7. Add a peer via WGDashboard
curl -X POST http://localhost:10086/api/addPeers/wg0 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Client1",
    "allowed_ips": ["10.0.0.2/32"],
    "DNS": "1.1.1.1",
    "keepalive": 25
  }'
```

---

## 📝 Notes

- MikroTik configurations are stored in the same database as local configurations
- The `configPath` for MikroTik configs uses the format: `mikrotik://host/interface_name`
- Statistics are updated via background threads, same as local configs
- All standard WGDashboard features (jobs, share links, webhooks) work with MikroTik configs

---

## ❓ Frequently Asked Questions

### Is it safe to use `verify_ssl=False` with self-signed certificates?

**Short answer**: Yes, for private networks with known MikroTik devices.

**Detailed explanation**:
- ✅ **Traffic is still encrypted** - HTTPS/TLS encryption is active
- ✅ **Safe on private networks** - When connecting to MikroTik on your LAN/VPN
- ✅ **MikroTik default** - Self-signed certificates are standard on MikroTik
- ⚠️ **What you're bypassing** - Only the certificate chain-of-trust validation
- ❌ **Not for public internet** - Don't use for untrusted/unknown hosts

**What `verify_ssl=False` does**:
```
With verify_ssl=True:
1. Establish TLS connection ✅
2. Encrypt traffic ✅
3. Verify certificate signed by trusted CA ❌ (fails with self-signed)

With verify_ssl=False:
1. Establish TLS connection ✅
2. Encrypt traffic ✅
3. Skip certificate validation ⚠️ (allows self-signed)
```

**When to use each setting**:

| Scenario | verify_ssl | Reason |
|----------|-----------|---------|
| MikroTik on private network (default cert) | `False` | Safe, avoids certificate errors |
| MikroTik with Let's Encrypt certificate | `True` | Proper validation possible |
| MikroTik over public internet (default cert) | `False`* | *Still encrypted, but consider proper cert |
| Development/testing | `False` | Convenience |

### Can I use a proper signed certificate instead?

Yes! If you want full certificate validation:

1. **Option 1: Let's Encrypt on MikroTik**
   ```routeros
   # Install certbot package and configure
   # See MikroTik wiki for detailed steps
   ```

2. **Option 2: Import your own certificate**
   ```routeros
   /certificate import file-name=your-cert.crt
   /certificate import file-name=your-key.key
   /ip service set www-ssl certificate=your-cert.crt_0
   ```

3. **Then in WGDashboard**: Set `MikroTikVerifySSL: true`

### Does this support certificate pinning?

Not currently, but this could be added as an enhancement. The `MikroTikClient` could be extended to support certificate fingerprint pinning for additional security even with self-signed certificates.

---

## 🆘 Support

If you encounter issues:

1. Check WGDashboard logs: `./log/error_*.log`
2. Check MikroTik logs: `/log/print where topics~"api,wireguard"`
3. Test connection manually with curl
4. Verify RouterOS version supports WireGuard
5. Open an issue on GitHub with logs and configuration details

---

## 🎯 Future Enhancements

Planned features for MikroTik integration:

- [ ] Batch configuration import
- [ ] MikroTik cluster support
- [ ] Certificate-based authentication
- [ ] IP pool management from MikroTik
- [ ] Firewall rule generation
- [ ] Routing table integration
- [ ] Multi-MikroTik dashboard view

---

**Happy Tunneling! 🚀**
