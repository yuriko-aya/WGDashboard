#!/usr/bin/env python3
"""
Example script demonstrating MikroTik WireGuard integration with WGDashboard

This script shows how to:
1. Test connection to a MikroTik device
2. Import existing WireGuard configuration
3. Create new configuration
4. Add peers
5. Monitor statistics
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from modules.MikroTikClient import MikroTikClient
from modules.Utilities import GenerateWireguardPrivateKey, GenerateWireguardPublicKey


def example_test_connection():
    """Example: Test connection to MikroTik device"""
    print("=" * 60)
    print("Example 1: Test Connection")
    print("=" * 60)
    
    # Initialize client
    client = MikroTikClient(
        host="192.168.88.1",
        username="admin",
        password="your_password",
        port=443,
        use_ssl=True,
        verify_ssl=False  # For self-signed certificates
    )
    
    # Test connection
    success, message = client.test_connection()
    if success:
        print(f"✅ {message}")
        
        # Get WireGuard interfaces
        success, interfaces = client.get_wireguard_interfaces()
        if success:
            print(f"\n📡 Found {len(interfaces)} WireGuard interface(s):")
            for iface in interfaces:
                print(f"   - {iface.get('name')} (Port: {iface.get('listen-port')})")
    else:
        print(f"❌ Connection failed: {message}")
    
    print()


def example_create_interface():
    """Example: Create WireGuard interface on MikroTik"""
    print("=" * 60)
    print("Example 2: Create WireGuard Interface")
    print("=" * 60)
    
    client = MikroTikClient(
        host="192.168.88.1",
        username="admin",
        password="your_password",
        port=443,
        use_ssl=True,
        verify_ssl=False
    )
    
    # Generate keys
    private_key = GenerateWireguardPrivateKey()[1]
    public_key = GenerateWireguardPublicKey(private_key)[1]
    
    print(f"🔑 Generated keys:")
    print(f"   Private: {private_key[:20]}...")
    print(f"   Public:  {public_key[:20]}...")
    
    # Create interface
    success, result = client.create_wireguard_interface(
        name="wg-dashboard",
        listen_port=13231,
        private_key=private_key,
        mtu=1420,
        comment="Created by WGDashboard"
    )
    
    if success:
        print(f"\n✅ Interface created successfully!")
        print(f"   ID: {result.get('.id')}")
        
        # Add IP address
        success, ip_result = client.add_ip_address(
            address="10.0.50.1/24",
            interface="wg-dashboard"
        )
        if success:
            print(f"✅ IP address added: 10.0.50.1/24")
    else:
        print(f"❌ Failed to create interface: {result}")
    
    print()


def example_add_peer():
    """Example: Add peer to existing interface"""
    print("=" * 60)
    print("Example 3: Add WireGuard Peer")
    print("=" * 60)
    
    client = MikroTikClient(
        host="192.168.88.1",
        username="admin",
        password="your_password",
        port=443,
        use_ssl=True,
        verify_ssl=False
    )
    
    # Generate peer keys
    peer_private_key = GenerateWireguardPrivateKey()[1]
    peer_public_key = GenerateWireguardPublicKey(peer_private_key)[1]
    
    print(f"🔑 Peer keys:")
    print(f"   Private: {peer_private_key[:20]}...")
    print(f"   Public:  {peer_public_key[:20]}...")
    
    # Add peer
    success, result = client.create_wireguard_peer(
        interface="wg-dashboard",
        public_key=peer_public_key,
        allowed_address="10.0.50.2/32",
        comment="Example Client",
        **{"persistent-keepalive": "25s"}
    )
    
    if success:
        print(f"\n✅ Peer added successfully!")
        print(f"   ID: {result.get('.id')}")
        print(f"   Allowed IPs: 10.0.50.2/32")
        
        # Generate client config
        print(f"\n📱 Client configuration:")
        print(f"""
[Interface]
PrivateKey = {peer_private_key}
Address = 10.0.50.2/32
DNS = 1.1.1.1

[Peer]
PublicKey = <server_public_key>
Endpoint = <server_ip>:13231
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
""")
    else:
        print(f"❌ Failed to add peer: {result}")
    
    print()


def example_get_statistics():
    """Example: Get interface and peer statistics"""
    print("=" * 60)
    print("Example 4: Get Statistics")
    print("=" * 60)
    
    client = MikroTikClient(
        host="192.168.88.1",
        username="admin",
        password="your_password",
        port=443,
        use_ssl=True,
        verify_ssl=False
    )
    
    # Get interface stats
    success, stats = client.get_interface_stats("wg-dashboard")
    if success:
        print(f"📊 Interface Statistics:")
        print(f"   RX: {stats.get('rx-byte', 0):,} bytes")
        print(f"   TX: {stats.get('tx-byte', 0):,} bytes")
        print(f"   Running: {stats.get('running', False)}")
    
    # Get peers
    success, peers = client.get_wireguard_peers("wg-dashboard")
    if success:
        print(f"\n👥 Peers ({len(peers)}):")
        for peer in peers:
            print(f"\n   Peer: {peer.get('comment', 'Unnamed')}")
            print(f"      Public Key: {peer.get('public-key', '')[:20]}...")
            print(f"      Allowed IPs: {peer.get('allowed-address', 'N/A')}")
            print(f"      Last Handshake: {peer.get('last-handshake', 'never')}")
            print(f"      RX: {int(peer.get('rx', 0)):,} bytes")
            print(f"      TX: {int(peer.get('tx', 0)):,} bytes")
    
    print()


def example_enable_disable_interface():
    """Example: Enable/disable interface"""
    print("=" * 60)
    print("Example 5: Enable/Disable Interface")
    print("=" * 60)
    
    client = MikroTikClient(
        host="192.168.88.1",
        username="admin",
        password="your_password",
        port=443,
        use_ssl=True,
        verify_ssl=False
    )
    
    # Get interface ID
    success, interface_data = client.get_wireguard_interface_by_name("wg-dashboard")
    if not success or not interface_data:
        print("❌ Interface not found")
        return
    
    interface_id = interface_data.get('.id')
    is_disabled = interface_data.get('disabled', False)
    
    print(f"Interface 'wg-dashboard' is currently: {'DISABLED' if is_disabled else 'ENABLED'}")
    
    if is_disabled:
        # Enable it
        success, result = client.enable_interface("wireguard", interface_id)
        if success:
            print("✅ Interface enabled")
        else:
            print(f"❌ Failed to enable: {result}")
    else:
        # Disable it
        success, result = client.disable_interface("wireguard", interface_id)
        if success:
            print("✅ Interface disabled")
        else:
            print(f"❌ Failed to disable: {result}")
    
    print()


def example_cleanup():
    """Example: Remove peer and interface"""
    print("=" * 60)
    print("Example 6: Cleanup")
    print("=" * 60)
    
    client = MikroTikClient(
        host="192.168.88.1",
        username="admin",
        password="your_password",
        port=443,
        use_ssl=True,
        verify_ssl=False
    )
    
    # Get and delete all peers
    success, peers = client.get_wireguard_peers("wg-dashboard")
    if success and peers:
        print(f"🗑️  Deleting {len(peers)} peer(s)...")
        for peer in peers:
            peer_id = peer.get('.id')
            success, result = client.delete_wireguard_peer(peer_id)
            if success:
                print(f"   ✅ Deleted peer: {peer.get('comment', 'Unknown')}")
            else:
                print(f"   ❌ Failed to delete peer: {result}")
    
    # Delete IP addresses
    success, addresses = client.get_ip_addresses("wg-dashboard")
    if success and addresses:
        print(f"\n🗑️  Deleting {len(addresses)} IP address(es)...")
        for addr in addresses:
            addr_id = addr.get('.id')
            success, result = client.delete_ip_address(addr_id)
            if success:
                print(f"   ✅ Deleted address: {addr.get('address')}")
    
    # Delete interface
    success, interface_data = client.get_wireguard_interface_by_name("wg-dashboard")
    if success and interface_data:
        interface_id = interface_data.get('.id')
        success, result = client.delete_wireguard_interface(interface_id)
        if success:
            print(f"\n✅ Interface 'wg-dashboard' deleted")
        else:
            print(f"\n❌ Failed to delete interface: {result}")
    
    print()


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("MikroTik WireGuard Integration Examples")
    print("=" * 60 + "\n")
    
    print("⚠️  WARNING: These examples will make changes to your MikroTik device!")
    print("⚠️  Please update the connection details before running.\n")
    
    response = input("Do you want to continue? (y/N): ")
    if response.lower() != 'y':
        print("Aborted.")
        return
    
    try:
        # Run examples
        example_test_connection()
        
        # Uncomment to run other examples
        # example_create_interface()
        # example_add_peer()
        # example_get_statistics()
        # example_enable_disable_interface()
        # example_cleanup()
        
        print("=" * 60)
        print("Examples completed!")
        print("=" * 60)
        print("\nTo run other examples, uncomment them in the main() function.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
