#!/usr/bin/env python3
"""
FireDog Dog Agent - Main Script
Agent per comunicazione con server FireDog
"""
import asyncio
import logging
import sys
import signal
from datetime import datetime

from config_manager import ConfigManager
from websocket_client import WebSocketClient
from system_monitor import SystemMonitor
from firewall_manager import FirewallManager
from threat_detector import ThreatDetector
from integrity_monitor import IntegrityMonitor


class DogAgent:
    """Dog Agent principale"""

    def __init__(self, config_path='/etc/dog-agent/agent.conf'):
        """Inizializza agent"""
        self.config = ConfigManager(config_path)

        # Setup logging
        log_level = self.config.get('agent.log_level', 'INFO')
        log_path = self.config.get('agent.log_path', '/var/log/dog-agent.log')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

        # Componenti
        self.ws_client = None
        self.system_monitor = SystemMonitor()
        self.firewall_manager = FirewallManager()
        self.threat_detector = None
        self.integrity_monitor = None

        # Stato
        self.running = False
        self.paired = False
        self.target_id = None

        # Tasks
        self.heartbeat_task = None
        self.threat_analysis_task = None
        self.integrity_check_task = None

    async def start(self):
        """Avvia agent"""
        self.logger.info("Starting Dog Agent...")

        # Inizializza componenti
        server_url = self.config.get('server.url')
        api_key = self.config.get('server.api_key')
        verify_ssl = self.config.get('server.verify_ssl', True)

        if not server_url or not api_key:
            self.logger.error("Missing server URL or API key in configuration")
            return False

        # WebSocket client
        self.ws_client = WebSocketClient(server_url, api_key, verify_ssl)

        # Registra message handlers
        self.ws_client.on_message('pairing_status', self.handle_pairing_status)
        self.ws_client.on_message('command', self.handle_command)
        self.ws_client.on_message('config', self.handle_config_update)
        self.ws_client.on_message('heartbeat_ack', self.handle_heartbeat_ack)
        self.ws_client.on_message('error', self.handle_error)

        # Connetti al server
        if not await self.ws_client.connect():
            self.logger.error("Failed to connect to server")
            return False

        # Invia pairing request
        await self.send_pairing_request()

        self.running = True

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        self.logger.info("Dog Agent started successfully")
        return True

    async def stop(self):
        """Ferma agent"""
        self.logger.info("Stopping Dog Agent...")
        self.running = False

        # Cancella tasks
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.threat_analysis_task:
            self.threat_analysis_task.cancel()
        if self.integrity_check_task:
            self.integrity_check_task.cancel()

        # Disconnetti WebSocket
        if self.ws_client:
            await self.ws_client.disconnect()

        self.logger.info("Dog Agent stopped")

    async def send_pairing_request(self):
        """Invia richiesta di pairing al server"""
        network_info = self.system_monitor.get_network_info()

        await self.ws_client.send({
            'type': 'pair_request',
            'api_key': self.config.get('server.api_key'),
            'ip': network_info['ip_address'],
            'hostname': network_info['hostname'],
            'mac': network_info['mac_address']
        })

        self.logger.info("Pairing request sent")

    async def handle_pairing_status(self, data):
        """Gestisce risposta pairing"""
        status = data.get('status')
        self.logger.info(f"Pairing status: {status}")

        if status == 'success':
            self.paired = True
            self.target_id = data.get('target_id')
            self.logger.info(f"Pairing successful! Target ID: {self.target_id}")

            # Avvia tasks periodici
            await self.start_periodic_tasks()

        elif status == 'failed':
            error = data.get('error', 'Unknown error')
            self.logger.error(f"Pairing failed: {error}")

    async def start_periodic_tasks(self):
        """Avvia tasks periodici dopo pairing"""
        # Heartbeat
        heartbeat_interval = self.config.get('agent.notification_interval', 30)
        self.heartbeat_task = asyncio.create_task(self.heartbeat_loop(heartbeat_interval))

        # Threat analysis
        self.threat_detector = ThreatDetector(
            self.config.get('monitoring.pcap_path_input'),
            self.config.get('monitoring.pcap_path_output'),
            self.config.get('intervention.threat_threshold', 75)
        )
        self.threat_analysis_task = asyncio.create_task(self.threat_analysis_loop())

        # Integrity check
        if self.config.get('monitoring.check_integrity'):
            integrity_files = self.config.get('monitoring.integrity_files', [])
            self.integrity_monitor = IntegrityMonitor(integrity_files)
            self.integrity_check_task = asyncio.create_task(self.integrity_check_loop())

        self.logger.info("Periodic tasks started")

    async def heartbeat_loop(self, interval: int):
        """Loop heartbeat"""
        while self.running and self.paired:
            try:
                # Raccogli statistiche
                system_stats = self.system_monitor.get_system_stats()
                firewall_stats = self.firewall_manager.get_stats()

                # Unisci stats
                stats = {**system_stats, **firewall_stats}

                # Invia heartbeat
                await self.ws_client.send({
                    'type': 'heartbeat',
                    'timestamp': datetime.now().isoformat(),
                    'system_stats': stats
                })

                self.logger.debug("Heartbeat sent")

            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")

            await asyncio.sleep(interval)

    async def threat_analysis_loop(self):
        """Loop analisi minacce"""
        while self.running and self.paired:
            try:
                # Analizza traffico
                threats = self.threat_detector.analyze_traffic()

                if threats:
                    self.logger.info(f"Found {len(threats)} threats")

                    # Auto-block se configurato
                    if self.config.get('intervention.mode') == 'automatic':
                        for threat in threats:
                            if self.threat_detector.should_auto_block(threat['threat_score']):
                                self.logger.warning(f"Auto-blocking IP: {threat['source_ip']}")
                                self.firewall_manager.block_ip(threat['source_ip'])

                    # Invia threat log al server
                    await self.ws_client.send({
                        'type': 'threat_log',
                        'threats': threats
                    })

            except Exception as e:
                self.logger.error(f"Error in threat analysis loop: {e}")

            await asyncio.sleep(60)  # Ogni minuto

    async def integrity_check_loop(self):
        """Loop verifica integrità"""
        while self.running and self.paired:
            try:
                modified_files = self.integrity_monitor.check_integrity()

                if modified_files:
                    self.logger.warning(f"File integrity violations: {len(modified_files)}")
                    # TODO: Invia alert al server

            except Exception as e:
                self.logger.error(f"Error in integrity check loop: {e}")

            await asyncio.sleep(300)  # Ogni 5 minuti

    async def handle_command(self, data):
        """Gestisce comando dal server"""
        command_id = data.get('command_id')
        action = data.get('action')
        payload = data.get('payload', {})

        self.logger.info(f"Received command: {action} (ID: {command_id})")

        try:
            # Invia executing status
            await self.ws_client.send({
                'type': 'command_response',
                'command_id': command_id,
                'status': 'executing'
            })

            # Esegui comando
            result = None
            if action == 'add_rule':
                result = self.firewall_manager.add_rule(payload)
            elif action == 'remove_rule':
                result = self.firewall_manager.remove_rule(payload)
            elif action == 'block_ip':
                result = self.firewall_manager.block_ip(payload.get('ip_address'))
            elif action == 'unblock_ip':
                result = self.firewall_manager.unblock_ip(payload.get('ip_address'))
            elif action == 'update_config':
                self.config.update(payload.get('config', {}))
                result = {'success': True}
            elif action == 'check_integrity':
                result = {
                    'success': True,
                    'modified_files': self.integrity_monitor.check_integrity()
                }
            else:
                raise Exception(f"Unknown action: {action}")

            # Invia risposta
            if result and result.get('success'):
                await self.ws_client.send({
                    'type': 'command_response',
                    'command_id': command_id,
                    'status': 'success',
                    'result': result
                })
                self.logger.info(f"Command {command_id} executed successfully")
            else:
                raise Exception(result.get('error', 'Command failed'))

        except Exception as e:
            self.logger.error(f"Command execution error: {e}")
            await self.ws_client.send({
                'type': 'command_response',
                'command_id': command_id,
                'status': 'failed',
                'error': str(e)
            })

    async def handle_config_update(self, data):
        """Gestisce aggiornamento configurazione"""
        new_config = data.get('config', {})
        self.config.update(new_config)
        self.logger.info("Configuration updated from server")

    async def handle_heartbeat_ack(self, data):
        """Gestisce ACK heartbeat"""
        self.logger.debug("Heartbeat ACK received")

    async def handle_error(self, data):
        """Gestisce messaggio di errore"""
        error_message = data.get('message', 'Unknown error')
        self.logger.error(f"Server error: {error_message}")

    async def run(self):
        """Run principale"""
        if await self.start():
            # Mantieni agent in esecuzione
            while self.running:
                await asyncio.sleep(1)


async def main():
    """Entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='FireDog Dog Agent')
    parser.add_argument('--config', default='/etc/dog-agent/agent.conf',
                        help='Path to configuration file')
    args = parser.parse_args()

    agent = DogAgent(config_path=args.config)

    try:
        await agent.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        await agent.stop()


if __name__ == '__main__':
    asyncio.run(main())
