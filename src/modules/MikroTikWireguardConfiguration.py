"""
MikroTik WireGuard Configuration
Extends WireguardConfiguration to support MikroTik devices via REST API
"""
import os
import time
import ipaddress
import subprocess
from datetime import datetime, timedelta
import traceback
from typing import Optional, Dict, List, Tuple
from flask import current_app
import sqlalchemy

from .WireguardConfiguration import WireguardConfiguration
from .MikroTikClient import MikroTikClient
from .Peer import Peer
from .Utilities import GenerateWireguardPublicKey, StringToBoolean


class MikroTikWireguardConfiguration(WireguardConfiguration):
    """
    MikroTik WireGuard Configuration Handler
    Manages WireGuard configurations on MikroTik devices via REST API
    """
    
    def __init__(self, DashboardConfig, AllPeerJobs, AllPeerShareLinks, DashboardWebHooks,
                 name: str = None, data: dict = None, mikrotik_config: dict = None,
                 startup: bool = False):
        """
        Initialize MikroTik WireGuard Configuration
        
        Args:
            mikrotik_config: Dict containing MikroTik connection details:
                {
                    'host': 'router.example.com',
                    'username': 'admin',
                    'password': 'password',
                    'port': 443,
                    'use_ssl': True,
                    'verify_ssl': False
                }
        """
        self.isMikroTik = True
        self.mikrotik_config = mikrotik_config or {}
        self.mikrotik_client: Optional[MikroTikClient] = None
        self.mikrotik_interface_id: Optional[str] = None
        
        # Initialize MikroTik client
        if self.mikrotik_config:
            self.mikrotik_client = MikroTikClient(
                host=self.mikrotik_config.get('host'),
                username=self.mikrotik_config.get('username'),
                password=self.mikrotik_config.get('password'),
                port=self.mikrotik_config.get('port', 443),
                use_ssl=self.mikrotik_config.get('use_ssl', True),
                verify_ssl=self.mikrotik_config.get('verify_ssl', False)
            )
        
        # Initialize parent class (but override file operations)
        self.Protocol = "wg"  # MikroTik only supports standard WireGuard
        
        # Set properties before calling parent init
        self.DashboardConfig = DashboardConfig
        self.AllPeerJobs = AllPeerJobs
        self.AllPeerShareLinks = AllPeerShareLinks
        self.DashboardWebHooks = DashboardWebHooks
        
        # Don't call parent __init__ directly, initialize manually
        self._initializeConfiguration(name, data, startup)
    
    def _initializeConfiguration(self, name: str = None, data: dict = None, startup: bool = False):
        """Initialize configuration from MikroTik device or create new"""
        from .ConnectionString import ConnectionString
        from .WireguardConfigurationInfo import WireguardConfigurationInfo
        
        # Initialize basic properties
        self.Peers = []
        self.Status: bool = False
        self.Name: str = ""
        self.PrivateKey: str = ""
        self.PublicKey: str = ""
        self.ListenPort: str = ""
        self.Address: str = ""
        self.DNS: str = ""
        self.MTU: str = ""
        self.SaveConfig: bool = True
        
        # MikroTik doesn't use these, but keep for compatibility
        self.Table: str = ""
        self.PreUp: str = ""
        self.PostUp: str = ""
        self.PreDown: str = ""
        self.PostDown: str = ""
        
        # Database setup
        self.engine: sqlalchemy.Engine = sqlalchemy.create_engine(ConnectionString("wgdashboard"))
        self.metadata: sqlalchemy.MetaData = sqlalchemy.MetaData()
        self.dbType = self.DashboardConfig.GetConfig("Database", "type")[1]
        
        if name is not None:
            # Load existing configuration from MikroTik
            self.Name = name
            self.configPath = f"mikrotik://{self.mikrotik_config.get('host', 'unknown')}/{name}"
            self.createDatabase()
            self.__parseConfigurationFromMikroTik()
            self.__initPeersList()
        elif data is not None:
            # Create new configuration on MikroTik
            self.Name = data.get("ConfigurationName")
            self.configPath = f"mikrotik://{self.mikrotik_config.get('host', 'unknown')}/{self.Name}"
            
            # Set attributes from data
            for key in ["PrivateKey", "Address", "ListenPort", "DNS", "MTU"]:
                if key in data:
                    setattr(self, key, str(data[key]))
            
            self.PublicKey = GenerateWireguardPublicKey(self.PrivateKey)[1]
            
            # Create on MikroTik device
            self.createDatabase()
            self.__createConfigurationOnMikroTik()
            self.__initPeersList()
        
        # Create backup directory (virtual for MikroTik)
        backup_path = os.path.join(self.DashboardConfig.GetConfig("Server", "wg_conf_path")[1], 'WGDashboard_Backup_MikroTik')
        if not os.path.exists(backup_path):
            os.makedirs(backup_path, exist_ok=True)
        
        current_app.logger.info(f"Initialized MikroTik Configuration: {self.Name} on {self.mikrotik_config.get('host')}")
        
        # Configuration info
        self.configurationInfo: WireguardConfigurationInfo | None = None
        configurationInfoJson = self.readConfigurationInfo()
        if not configurationInfoJson:
            self.configurationInfo = WireguardConfigurationInfo(**{})
            self.initConfigurationInfo()
        else:
            from .WireguardConfigurationInfo import WireguardConfigurationInfo
            self.configurationInfo = WireguardConfigurationInfo.model_validate_json(configurationInfoJson.get("Info"))
        
        if self.Status and startup:
            current_app.logger.info(f"MikroTik Configuration {self.Name} is already running")
    
    def __parseConfigurationFromMikroTik(self):
        """Parse configuration from MikroTik device via API"""
        if not self.mikrotik_client:
            raise Exception("MikroTik client not initialized")
        
        # Get interface details
        success, interface_data = self.mikrotik_client.get_wireguard_interface_by_name(self.Name)
        if not success or interface_data is None:
            raise self.InvalidConfigurationFileException(
                f"WireGuard interface '{self.Name}' not found on MikroTik device"
            )
        
        # Store interface ID for future operations
        self.mikrotik_interface_id = interface_data.get('.id')
        
        # Map MikroTik fields to WGDashboard fields
        self.PrivateKey = interface_data.get('private-key', '')
        self.PublicKey = interface_data.get('public-key', '')
        self.ListenPort = str(interface_data.get('listen-port', ''))
        self.MTU = str(interface_data.get('mtu', ''))
        
        # Get interface IP addresses
        success, ip_addresses = self.mikrotik_client.get_ip_addresses(self.Name)
        if success and ip_addresses:
            # Combine all addresses
            addresses = [addr.get('address', '') for addr in ip_addresses]
            self.Address = ', '.join(addresses)
        
        # Check if interface is running
        self.Status = not interface_data.get('disabled', False)
        
        current_app.logger.info(f"Parsed MikroTik configuration: {self.Name}")
    
    def __createConfigurationOnMikroTik(self):
        """Create new WireGuard configuration on MikroTik device"""
        if not self.mikrotik_client:
            raise Exception("MikroTik client not initialized")
        
        # Create WireGuard interface
        success, result = self.mikrotik_client.create_wireguard_interface(
            name=self.Name,
            listen_port=int(self.ListenPort) if self.ListenPort else 13231,
            private_key=self.PrivateKey,
            mtu=int(self.MTU) if self.MTU and int(self.MTU) > 0 else 1420,
            comment=f"Managed by WGDashboard"
        )
        
        if not success:
            raise Exception(f"Failed to create WireGuard interface on MikroTik: {result}")
        
        self.mikrotik_interface_id = result.get('.id')
        
        # Add IP address if specified
        if self.Address:
            for addr in self.Address.split(','):
                addr = addr.strip()
                if addr:
                    success, result = self.mikrotik_client.add_ip_address(
                        address=addr,
                        interface=self.Name
                    )
                    if not success:
                        current_app.logger.warning(f"Failed to add IP {addr}: {result}")
        
        current_app.logger.info(f"Created MikroTik WireGuard interface: {self.Name}")
    
    def getStatus(self) -> bool:
        """Get interface status from MikroTik"""
        if not self.mikrotik_client:
            return False
        
        success, interface_data = self.mikrotik_client.get_wireguard_interface_by_name(self.Name)
        if success and interface_data:
            self.Status = not interface_data.get('disabled', False)
            return self.Status
        return False
    
    def toggleConfiguration(self) -> Tuple[bool, str]:
        """Enable/disable WireGuard interface on MikroTik"""
        if not self.mikrotik_client or not self.mikrotik_interface_id:
            return False, "MikroTik client not properly initialized"
        
        current_status = self.getStatus()
        
        if current_status:
            # Disable interface
            success, result = self.mikrotik_client.disable_interface("wireguard", self.mikrotik_interface_id)
            if success:
                self.Status = False
                return True, "Configuration stopped successfully"
            return False, f"Failed to stop configuration: {result}"
        else:
            # Enable interface
            success, result = self.mikrotik_client.enable_interface("wireguard", self.mikrotik_interface_id)
            if success:
                self.Status = True
                return True, "Configuration started successfully"
            return False, f"Failed to start configuration: {result}"
    
    def getPeers(self):
        """Get peers from MikroTik device"""
        tmpList = []
        
        if not self.mikrotik_client:
            current_app.logger.error("MikroTik client not initialized")
            return
        
        # Get peers from MikroTik
        success, peers_data = self.mikrotik_client.get_wireguard_peers(self.Name)
        if not success:
            current_app.logger.error(f"Failed to get peers from MikroTik: {peers_data}")
            return
        
        # Process each peer
        for peer_data in peers_data:
            public_key = peer_data.get('public-key', '')
            if not public_key:
                continue
            
            # Check if peer exists in database
            with self.engine.connect() as conn:
                tempPeer = conn.execute(
                    self.peersTable.select().where(
                        self.peersTable.columns.id == public_key
                    )
                ).mappings().fetchone()
            
            if tempPeer is None:
                # Create new peer record
                tempPeer = {
                    "id": public_key,
                    "private_key": "",
                    "DNS": self.DashboardConfig.GetConfig("Peers", "peer_global_DNS")[1],
                    "endpoint_allowed_ip": self.DashboardConfig.GetConfig("Peers", "peer_endpoint_allowed_ip")[1],
                    "name": peer_data.get('comment', ''),
                    "total_receive": 0,
                    "total_sent": 0,
                    "total_data": 0,
                    "endpoint": peer_data.get('endpoint-address', 'N/A'),
                    "status": "stopped",
                    "latest_handshake": "N/A",
                    "allowed_ip": peer_data.get('allowed-address', 'N/A'),
                    "cumu_receive": 0,
                    "cumu_sent": 0,
                    "cumu_data": 0,
                    "mtu": self.DashboardConfig.GetConfig("Peers", "peer_mtu")[1] if len(self.DashboardConfig.GetConfig("Peers", "peer_mtu")[1]) > 0 else None,
                    "keepalive": int(peer_data.get('persistent-keepalive', 0)) if peer_data.get('persistent-keepalive') else None,
                    "remote_endpoint": self.DashboardConfig.GetConfig("Peers", "remote_endpoint")[1],
                    "preshared_key": peer_data.get('preshared-key', '')
                }
                with self.engine.begin() as conn:
                    conn.execute(
                        self.peersTable.insert().values(tempPeer)
                    )
            else:
                # Update existing peer with latest data from MikroTik
                with self.engine.begin() as conn:
                    conn.execute(
                        self.peersTable.update().values({
                            "allowed_ip": peer_data.get('allowed-address', 'N/A'),
                            "endpoint": peer_data.get('endpoint-address', 'N/A'),
                            "keepalive": int(peer_data.get('persistent-keepalive', 0)) if peer_data.get('persistent-keepalive') else None,
                        }).where(
                            self.peersTable.columns.id == public_key
                        )
                    )
            
            tmpList.append(Peer(tempPeer, self))
        
        self.Peers = tmpList
    
    def addPeers(self, peers: list) -> tuple[bool, list, str]:
        """Add peers to MikroTik device"""
        result = {
            "message": None,
            "peers": []
        }
        
        if not self.mikrotik_client:
            return False, [], "MikroTik client not initialized"
        
        try:
            # Insert peers into database
            with self.engine.begin() as conn:
                for peer in peers:
                    newPeer = {
                        "id": peer['id'],
                        "private_key": peer['private_key'],
                        "DNS": peer['DNS'],
                        "endpoint_allowed_ip": peer['endpoint_allowed_ip'],
                        "name": peer['name'],
                        "total_receive": 0,
                        "total_sent": 0,
                        "total_data": 0,
                        "endpoint": "N/A",
                        "status": "stopped",
                        "latest_handshake": "N/A",
                        "allowed_ip": peer.get("allowed_ip", "N/A"),
                        "cumu_receive": 0,
                        "cumu_sent": 0,
                        "cumu_data": 0,
                        "mtu": peer['mtu'],
                        "keepalive": peer['keepalive'],
                        "remote_endpoint": self.DashboardConfig.GetConfig("Peers", "remote_endpoint")[1],
                        "preshared_key": peer["preshared_key"]
                    }
                    conn.execute(
                        self.peersTable.insert().values(newPeer)
                    )
            
            # Add peers to MikroTik
            for peer in peers:
                peer_params = {
                    "interface": self.Name,
                    "public-key": peer['id'],
                    "allowed-address": peer['allowed_ip'].replace(' ', ''),
                    "comment": peer['name']
                }
                
                if peer.get('keepalive') and peer['keepalive'] > 0:
                    peer_params['persistent-keepalive'] = f"{peer['keepalive']}s"
                
                if peer.get('preshared_key') and len(peer['preshared_key']) > 0:
                    peer_params['preshared-key'] = peer['preshared_key']
                
                success, api_result = self.mikrotik_client.create_wireguard_peer(**peer_params)
                
                if not success:
                    current_app.logger.error(f"Failed to add peer {peer['id']} to MikroTik: {api_result}")
                    return False, [], f"Failed to add peer: {api_result}"
            
            # Reload peers
            self.getPeers()
            
            for peer in peers:
                p = self.searchPeer(peer['id'])
                if p[0]:
                    result['peers'].append(p[1])
            
            self.DashboardWebHooks.RunWebHook("peer_created", {
                "configuration": self.Name,
                "peers": list(map(lambda k: k['id'], peers))
            })
            
        except Exception as e:
            current_app.logger.error(f"Add peers error: {e}")
            traceback.print_exc()
            return False, [], str(e)
        
        return True, result['peers'], ""
    
    def deletePeers(self, listOfPublicKeys, AllPeerJobs, AllPeerShareLinks) -> tuple[bool, str]:
        """Delete peers from MikroTik device"""
        if not self.mikrotik_client:
            return False, "MikroTik client not initialized"
        
        numOfDeletedPeers = 0
        numOfFailedToDeletePeers = 0
        deleted = []
        
        # Get all peers from MikroTik
        success, mt_peers = self.mikrotik_client.get_wireguard_peers(self.Name)
        if not success:
            return False, f"Failed to get peers from MikroTik: {mt_peers}"
        
        with self.engine.begin() as conn:
            for public_key in listOfPublicKeys:
                found, pf = self.searchPeer(public_key)
                
                # Delete associated jobs and share links
                if found:
                    for job in pf.jobs:
                        AllPeerJobs.deleteJob(job)
                    for shareLink in pf.ShareLink:
                        AllPeerShareLinks.updateLinkExpireDate(shareLink.ShareID, datetime.now())
                
                # Find peer on MikroTik
                mt_peer = None
                for peer in mt_peers:
                    if peer.get('public-key') == public_key:
                        mt_peer = peer
                        break
                
                if mt_peer:
                    # Delete from MikroTik
                    peer_id = mt_peer.get('.id')
                    success, result = self.mikrotik_client.delete_wireguard_peer(peer_id)
                    
                    if success:
                        # Delete from database
                        conn.execute(
                            self.peersTable.delete().where(
                                self.peersTable.columns.id == public_key
                            )
                        )
                        deleted.append(public_key)
                        numOfDeletedPeers += 1
                    else:
                        current_app.logger.error(f"Failed to delete peer {public_key}: {result}")
                        numOfFailedToDeletePeers += 1
                else:
                    numOfFailedToDeletePeers += 1
        
        self.getPeers()
        
        if numOfDeletedPeers == 0 and numOfFailedToDeletePeers == 0:
            return False, "No peer(s) to delete found"
        
        if numOfDeletedPeers == len(listOfPublicKeys):
            self.DashboardWebHooks.RunWebHook("peer_deleted", {
                "configuration": self.Name,
                "peers": deleted
            })
            return True, f"Deleted {numOfDeletedPeers} peer(s)"
        
        return False, f"Deleted {numOfDeletedPeers} peer(s) successfully. Failed to delete {numOfFailedToDeletePeers} peer(s)"
    
    def getPeersLatestHandshake(self):
        """Get peer handshake times from MikroTik"""
        if not self.mikrotik_client:
            return
        
        success, peers_data = self.mikrotik_client.get_wireguard_peers(self.Name)
        if not success:
            return
        
        now = datetime.now()
        time_delta = timedelta(minutes=3)
        
        with self.engine.begin() as conn:
            for peer in peers_data:
                public_key = peer.get('public-key', '')
                last_handshake = peer.get('last-handshake', '')
                
                if last_handshake and last_handshake != 'never':
                    try:
                        # MikroTik format: "1w2d3h4m5s" or similar
                        # Parse and convert to datetime
                        # For simplicity, check current-endpoint-address to determine status
                        has_endpoint = peer.get('current-endpoint-address', '') != ''
                        status = "running" if has_endpoint else "stopped"
                        
                        conn.execute(
                            self.peersTable.update().values({
                                "latest_handshake": last_handshake,
                                "status": status
                            }).where(
                                self.peersTable.columns.id == public_key
                            )
                        )
                    except Exception as e:
                        current_app.logger.error(f"Error parsing handshake for {public_key}: {e}")
                else:
                    conn.execute(
                        self.peersTable.update().values({
                            "latest_handshake": "No Handshake",
                            "status": "stopped"
                        }).where(
                            self.peersTable.columns.id == public_key
                        )
                    )
    
    def getPeersTransfer(self):
        """Get peer transfer statistics from MikroTik"""
        if not self.mikrotik_client:
            return
        
        success, peers_data = self.mikrotik_client.get_wireguard_peers(self.Name)
        if not success:
            return
        
        with self.engine.begin() as conn:
            for peer in peers_data:
                public_key = peer.get('public-key', '')
                
                # Get current peer from database
                cur_peer = conn.execute(
                    self.peersTable.select().where(
                        self.peersTable.c.id == public_key
                    )
                ).mappings().fetchone()
                
                if cur_peer is not None:
                    # MikroTik reports in bytes
                    rx_bytes = int(peer.get('rx', 0))
                    tx_bytes = int(peer.get('tx', 0))
                    
                    # Convert to GB
                    cur_total_receive = rx_bytes / (1024 ** 3)
                    cur_total_sent = tx_bytes / (1024 ** 3)
                    
                    total_receive = cur_peer['total_receive']
                    total_sent = cur_peer['total_sent']
                    
                    cumulative_receive = cur_peer['cumu_receive'] + total_receive
                    cumulative_sent = cur_peer['cumu_sent'] + total_sent
                    
                    if total_sent <= cur_total_sent and total_receive <= cur_total_receive:
                        total_sent = cur_total_sent
                        total_receive = cur_total_receive
                    else:
                        # Interface was reset, update cumulative
                        conn.execute(
                            self.peersTable.update().values({
                                "cumu_receive": cumulative_receive,
                                "cumu_sent": cumulative_sent,
                                "cumu_data": cumulative_receive + cumulative_sent,
                                "total_receive": cur_total_receive,
                                "total_sent": cur_total_sent,
                                "total_data": cur_total_receive + cur_total_sent
                            }).where(
                                self.peersTable.columns.id == public_key
                            )
                        )
                        continue
                    
                    conn.execute(
                        self.peersTable.update().values({
                            "total_receive": total_receive,
                            "total_sent": total_sent,
                            "total_data": total_receive + total_sent
                        }).where(
                            self.peersTable.columns.id == public_key
                        )
                    )
    
    def getRawConfigurationFile(self):
        """Generate a WireGuard config file representation from MikroTik data"""
        if not self.mikrotik_client:
            return "# MikroTik client not initialized"
        
        # Build config file representation
        config_lines = ["[Interface]"]
        config_lines.append(f"# MikroTik Device: {self.mikrotik_config.get('host')}")
        config_lines.append(f"# Interface: {self.Name}")
        config_lines.append(f"PrivateKey = {self.PrivateKey}")
        if self.Address:
            config_lines.append(f"Address = {self.Address}")
        if self.ListenPort:
            config_lines.append(f"ListenPort = {self.ListenPort}")
        if self.MTU:
            config_lines.append(f"MTU = {self.MTU}")
        config_lines.append("")
        
        # Add peers
        success, peers_data = self.mikrotik_client.get_wireguard_peers(self.Name)
        if success:
            for peer in peers_data:
                config_lines.append("[Peer]")
                if peer.get('comment'):
                    config_lines.append(f"#Name# = {peer['comment']}")
                config_lines.append(f"PublicKey = {peer.get('public-key', '')}")
                if peer.get('preshared-key'):
                    config_lines.append(f"PresharedKey = {peer['preshared-key']}")
                if peer.get('allowed-address'):
                    config_lines.append(f"AllowedIPs = {peer['allowed-address']}")
                if peer.get('endpoint-address'):
                    endpoint_port = peer.get('endpoint-port', '')
                    config_lines.append(f"Endpoint = {peer['endpoint-address']}:{endpoint_port}")
                if peer.get('persistent-keepalive'):
                    config_lines.append(f"PersistentKeepalive = {peer['persistent-keepalive']}")
                config_lines.append("")
        
        return "\n".join(config_lines)
