"""
MikroTik REST API Client
Handles communication with MikroTik RouterOS devices via REST API
"""
import requests
import base64
import json
from typing import Optional, Dict, List, Tuple, Any
from flask import current_app
from requests.auth import HTTPBasicAuth
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MikroTikClient:
    """Client for MikroTik RouterOS REST API"""
    
    def __init__(self, host: str, username: str, password: str, port: int = 443, use_ssl: bool = True, verify_ssl: bool = False):
        """
        Initialize MikroTik client
        
        Args:
            host: MikroTik device IP or hostname
            username: API username
            password: API password
            port: API port (default: 443 for HTTPS, 80 for HTTP)
            use_ssl: Use HTTPS (default: True)
            verify_ssl: Verify SSL certificates (default: False for self-signed)
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl
        self.base_url = f"{'https' if use_ssl else 'http'}://{host}:{port}/rest"
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        self.session.verify = verify_ssl
        
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Tuple[bool, Any]:
        """
        Make REST API request to MikroTik
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint path
            data: Request payload
            
        Returns:
            Tuple of (success: bool, response_data or error_message)
        """
        url = f"{self.base_url}{endpoint}"
        try:
            if method == "GET":
                response = self.session.get(url, timeout=10)
            elif method == "POST":
                response = self.session.post(url, json=data, timeout=10)
            elif method == "PUT":
                response = self.session.put(url, json=data, timeout=10)
            elif method == "PATCH":
                response = self.session.patch(url, json=data, timeout=10)
            elif method == "DELETE":
                response = self.session.delete(url, timeout=10)
            else:
                return False, f"Unsupported HTTP method: {method}"
            
            if response.status_code in [200, 201, 204]:
                if response.content:
                    return True, response.json()
                return True, {}
            else:
                error_msg = f"API request failed: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        error_msg += f" - {error_data['detail']}"
                    elif 'message' in error_data:
                        error_msg += f" - {error_data['message']}"
                except:
                    error_msg += f" - {response.text}"
                return False, error_msg
                
        except requests.exceptions.ConnectionError as e:
            return False, f"Connection error: {str(e)}"
        except requests.exceptions.Timeout:
            return False, "Request timeout"
        except Exception as e:
            return False, f"Request failed: {str(e)}"
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to MikroTik device"""
        success, result = self._request("GET", "/system/resource")
        if success:
            return True, "Connection successful"
        return False, result
    
    # WireGuard Interface methods
    def get_wireguard_interfaces(self) -> Tuple[bool, List[Dict] | str]:
        """Get all WireGuard interfaces"""
        return self._request("GET", "/interface/wireguard")
    
    def get_wireguard_interface(self, interface_id: str) -> Tuple[bool, Dict | str]:
        """Get specific WireGuard interface by ID"""
        return self._request("GET", f"/interface/wireguard/{interface_id}")
    
    def get_wireguard_interface_by_name(self, name: str) -> Tuple[bool, Optional[Dict] | str]:
        """Get WireGuard interface by name"""
        success, interfaces = self.get_wireguard_interfaces()
        if not success:
            return False, interfaces
        
        for iface in interfaces:
            if iface.get('name') == name:
                return True, iface
        return False, None
    
    def create_wireguard_interface(self, name: str, listen_port: int, private_key: str, **kwargs) -> Tuple[bool, Dict | str]:
        """
        Create WireGuard interface
        
        Args:
            name: Interface name
            listen_port: UDP listen port
            private_key: WireGuard private key
            **kwargs: Additional parameters (mtu, disabled, comment, etc.)
        """
        data = {
            "name": name,
            "listen-port": listen_port,
            "private-key": private_key,
            **kwargs
        }
        return self._request("POST", "/interface/wireguard", data)
    
    def update_wireguard_interface(self, interface_id: str, **kwargs) -> Tuple[bool, Dict | str]:
        """Update WireGuard interface"""
        return self._request("PATCH", f"/interface/wireguard/{interface_id}", kwargs)
    
    def delete_wireguard_interface(self, interface_id: str) -> Tuple[bool, Any]:
        """Delete WireGuard interface"""
        return self._request("DELETE", f"/interface/wireguard/{interface_id}")
    
    # WireGuard Peers methods
    def get_wireguard_peers(self, interface_name: Optional[str] = None) -> Tuple[bool, List[Dict] | str]:
        """Get all WireGuard peers, optionally filtered by interface"""
        success, peers = self._request("GET", "/interface/wireguard/peers")
        if not success:
            return False, peers
        
        if interface_name:
            filtered_peers = [p for p in peers if p.get('interface') == interface_name]
            return True, filtered_peers
        return True, peers
    
    def get_wireguard_peer(self, peer_id: str) -> Tuple[bool, Dict | str]:
        """Get specific WireGuard peer by ID"""
        return self._request("GET", f"/interface/wireguard/peers/{peer_id}")
    
    def create_wireguard_peer(self, interface: str, public_key: str, allowed_address: str, **kwargs) -> Tuple[bool, Dict | str]:
        """
        Create WireGuard peer
        
        Args:
            interface: Interface name
            public_key: Peer's public key
            allowed_address: Allowed IP addresses (comma-separated)
            **kwargs: Additional parameters (endpoint-address, endpoint-port, preshared-key, etc.)
        """
        data = {
            "interface": interface,
            "public-key": public_key,
            "allowed-address": allowed_address,
            **kwargs
        }
        return self._request("POST", "/interface/wireguard/peers", data)
    
    def update_wireguard_peer(self, peer_id: str, **kwargs) -> Tuple[bool, Dict | str]:
        """Update WireGuard peer"""
        return self._request("PATCH", f"/interface/wireguard/peers/{peer_id}", kwargs)
    
    def delete_wireguard_peer(self, peer_id: str) -> Tuple[bool, Any]:
        """Delete WireGuard peer"""
        return self._request("DELETE", f"/interface/wireguard/peers/{peer_id}")
    
    # IP Address methods
    def get_ip_addresses(self, interface: Optional[str] = None) -> Tuple[bool, List[Dict] | str]:
        """Get IP addresses, optionally filtered by interface"""
        success, addresses = self._request("GET", "/ip/address")
        if not success:
            return False, addresses
        
        if interface:
            filtered = [a for a in addresses if a.get('interface') == interface]
            return True, filtered
        return True, addresses
    
    def add_ip_address(self, address: str, interface: str, **kwargs) -> Tuple[bool, Dict | str]:
        """Add IP address to interface"""
        data = {
            "address": address,
            "interface": interface,
            **kwargs
        }
        return self._request("POST", "/ip/address", data)
    
    def delete_ip_address(self, address_id: str) -> Tuple[bool, Any]:
        """Delete IP address"""
        return self._request("DELETE", f"/ip/address/{address_id}")
    
    # Interface enable/disable
    def enable_interface(self, interface_type: str, interface_id: str) -> Tuple[bool, Any]:
        """Enable interface"""
        return self._request("PATCH", f"/interface/{interface_type}/{interface_id}", {"disabled": "false"})
    
    def disable_interface(self, interface_type: str, interface_id: str) -> Tuple[bool, Any]:
        """Disable interface"""
        return self._request("PATCH", f"/interface/{interface_type}/{interface_id}", {"disabled": "true"})
    
    # Statistics
    def get_interface_stats(self, interface_name: str) -> Tuple[bool, Dict | str]:
        """Get interface statistics"""
        # Get from interface list with stats
        success, result = self._request("GET", "/interface")
        if not success:
            return False, result
        
        for iface in result:
            if iface.get('name') == interface_name:
                return True, {
                    'rx-byte': iface.get('rx-byte', 0),
                    'tx-byte': iface.get('tx-byte', 0),
                    'rx-packet': iface.get('rx-packet', 0),
                    'tx-packet': iface.get('tx-packet', 0),
                    'running': iface.get('running', False)
                }
        return False, f"Interface {interface_name} not found"
