import sys
from threading import Thread, Event
from queue import Queue
import signal
import sys
import datetime
getTimeNow = datetime.datetime.now
from time import sleep


import psutil
import socket
import time
import logging
import re
from tabulate import tabulate
from colored import stylize, fore, back
from pyroute2 import IPRoute
import ipaddress
from icmplib import multiping
from wireguard_tools import WireguardDevice
from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange

try:
    from .utils import log
except ImportError:

    def log(s):
        print('%s %s' % (getTimeNow().strftime('%H:%M:%S'), s.rstrip()), file=sys.stderr)

#def log(s):
#    log('%s %s' % (getTimeNow().strftime('%H:%M:%S'), s.rstrip()), file=sys.stderr)


# Setup logging
#logging.basicConfig(filename='network_status.log', level=logging.INFO, format='%(asctime)s - %(message)s')


class NetworkThread(Thread):

    def __init__(self, name='network', changeEvent=None, stopEvent=None, networkDiscoveredQueue=None, testing=False):
        Thread.__init__(self)
        self.name = name
        self.changeEvent = changeEvent
        self.stopEvent = stopEvent
        self.networkDiscoveredQueue = networkDiscoveredQueue
        self.testing = testing
        self.ip_route = IPRoute()  # Initiate IPRoute object here for reuse

    def _sleep_interval(self, count):
        if self.testing:
            return 0.2
        return 5 if count < 4 else 15

    def run(self):
        log(f'{self.name}: starting')
        try:
            count = 0
            while not self.stopEvent.is_set():
                try:
                    network_info = self.get_network_info()  # Gather network data
                    if self.networkDiscoveredQueue is not None:
                        self.networkDiscoveredQueue.put(network_info)  # Put in the queue
                    if self.changeEvent is not None:
                        self.changeEvent.set()
                except Exception:
                    # Keep monitoring even if one polling cycle fails during startup churn.
                    log(f'{self.name}: error gathering network info')
                    logging.exception('%s: polling failure', self.name)

                count += 1
                time.sleep(self._sleep_interval(count))  # Sleep to avoid overwhelming the queue

        finally:
            log(f'{self.name}: stopping')
            # Cleanup any open resources
            if hasattr(self, 'ip_route') and self.ip_route:
                self.ip_route.close()  # Cleanly close the IPRoute object to avoid open file descriptors.
            log(f"{self.name}: resources cleaned up")

    def _ifindex(self, interface):
        links = self.ip_route.link_lookup(ifname=interface)
        return links[0] if links else None

    def get_gateway(self, interface):
        if interface.startswith('wg'):
            return self.get_wireguard_endpoint(interface)

        # Use IPRoute to get routing information for this specific interface.
        ifindex = self._ifindex(interface)
        if ifindex is None:
            return None

        routes = self.ip_route.get_routes(family=socket.AF_INET)
        for route in routes:
            if route.get('dst_len') != 0:  # default route only
                continue

            attrs = dict(route.get('attrs', []))
            if attrs.get('RTA_OIF') != ifindex:
                continue

            gateway = attrs.get('RTA_GATEWAY')
            if gateway:
                return gateway

        return None

    def get_wireguard_endpoint(self, interface):
        try:
            device = WireguardDevice.get(interface)
            config = device.get_config().asdict()
            log(f"Device: {interface}")
            for peer in config["peers"]:
                if "endpoint_host" in peer:
                    return peer["endpoint_host"]
            return None
        except Exception as e:
            log(f"Error: {e}")
            return None

    def get_network_part(self, ip, netmask="255.255.255.0"):
        """
        Extract the network portion of the IP address based on the provided netmask.
        Default netmask is "255.255.255.0" (Class C).
        """
        network = ipaddress.IPv4Network(f'{ip}/{netmask}', strict=False)
        return str(network.network_address)

    def check_network_in_list(self, ip, ip_list):
        """
        Check if the network portion of `ip` exists in the list of other IPs.
        """
        if not ip:
            return False
        network_part = self.get_network_part(ip)
        for other_ip in ip_list:
            if not other_ip:
                continue
            if self.get_network_part(other_ip) == network_part:
                #log(f"Checking network for IP: {ip} in list: {ip_list} True")
                return True  # Network match found
        #log(f"Checking network for IP: {ip} in list: {ip_list} False")
        return False  # No network match found

    def is_gateway_in_network(self, interface_ip, gateway_ip, subnet_mask):
        try:
            if not interface_ip or not gateway_ip or not subnet_mask:
                return False
            # Create network address objects for IP and Gateway
            network = ipaddress.IPv4Network(f'{interface_ip}/{subnet_mask}', strict=False)
            gateway = ipaddress.IPv4Address(gateway_ip)

            # Check if gateway is in the same network
            return gateway in network
        except ValueError:
            return False

    def _collect_ping_results(self, targets, count=2, timeout=3):
        valid_targets = []
        seen = set()
        for target in targets:
            if not target:
                continue
            if target in seen:
                continue
            seen.add(target)
            valid_targets.append(target)

        if not valid_targets:
            return {}

        ping_results = multiping(valid_targets, count=count, timeout=timeout)

        ip_ping_times = {}
        alive_map = {}
        for host in ping_results:
            alive_map[host.address] = host.is_alive
            if host.is_alive:
                ip_ping_times.setdefault(host.address, []).append(host.avg_rtt)

        avg_map = {ip: (sum(times) / len(times)) for ip, times in ip_ping_times.items()}
        return {'alive': alive_map, 'avg': avg_map}


    def get_network_info(self, networkDiscoveredQueue=None):
        network_info = []
        interfaces = psutil.net_if_addrs()

        # Generalized exclusion list
        startslist = ["lo", "br-", "virb", "veth"]

        #wellknown = ["1.1.1.1", "8.8.8.8", "192.168.254.254"]
        wellknown = ["1.1.1.1", "8.8.8.8"]
        gateways = []
        ipaddrs = []

        for interface, addrs in interfaces.items():
            # Skip interfaces that start with any of the prefixes in startslist
            if any(interface.startswith(prefix) for prefix in startslist):
                continue

            # Check for ethernet, wifi, and wireguard interfaces
            ip = None
            subnet_mask = None
            if any(proto.family == socket.AF_INET for proto in addrs):
                ip = next(addr.address for addr in addrs if addr.family == socket.AF_INET)
                subnet_mask = next(addr.netmask for addr in addrs if addr.family == socket.AF_INET)

            # Get MAC address if available
            mac = next((addr.address for addr in addrs if addr.family == psutil.AF_LINK), "N/A")

            # Get network speed (in Mbps)
            speed_stat = psutil.net_if_stats().get(interface, None)
            speed = f"{speed_stat.speed / 1e6:.2f} Mbps" if speed_stat else "N/A"

            # Retrieve the gateway using the pyroute2 routing table
            gateway = self.get_gateway(interface)
            if not interface.startswith("wg") and gateway and not self.is_gateway_in_network(ip, gateway, subnet_mask):
                gateway = None

            if gateway:
                gateways.append(gateway)
            if ip:
                ipaddrs.append(ip)

            network_info.append({
                'interface': interface,
                'ip': ip,
                'ipPing': None,
                'ipDup': None,
                'gw': gateway,
                'gwPing': None,
                'gwDup': None,
            })

            log(f"Gateway: {interface} {gateway}")

        ping_data = self._collect_ping_results(gateways + wellknown + ipaddrs, count=2, timeout=3)
        results = ping_data.get('alive', {})
        ip_avg_times = ping_data.get('avg', {})

        for i, info in enumerate(network_info):
            otherips = [_info['ip'] for _info in network_info if _info['interface'] != info['interface']]
            othergws = [_info['gw'] for _info in network_info if _info['interface'] != info['interface']]
            info['gwPing'] = results.get(info['gw'], None)
            info['ipPing'] = results.get(info['ip'], None)
            info['ipDup'] = self.check_network_in_list(info['ip'], otherips)
            info['gwDup'] = self.check_network_in_list(info['gw'], othergws)
            info['ipAvg'] = ip_avg_times.get(info['ip'], 0)
            info['gwAvg'] = ip_avg_times.get(info['gw'], 0)

        for ip in wellknown:
            network_info.append({
                'interface': 'well known',
                'ip': ip,
                'ipPing': results.get(ip, None),
                'ipDup': False,
                'gwDup': False,
                'ipAvg': ip_avg_times.get(ip, 0),
                'gwAvg': 0,
                'gw': None,
                'gwPing': None,
            })

        for i, info in enumerate(network_info):
            log(f"Info[{i}]: {info}")
        return network_info




# Function to display network info in ASCII table with color
def display_network_info(network_info):
    #network_info = get_network_info()
    if network_info:
        # Output the table with colored ping status
        log(tabulate(network_info, headers=["Interface", "IP", "MAC", "Speed", "Gateway", ], tablefmt="grid"))

# Monitor and log network status every 5 seconds
def monitor_network():
    previous_info = None

    count = 0
    while True:
        network_info = get_network_info()

        # Check for changes in the network info
        if network_info != previous_info:
            changes = []
            if previous_info:
                for old, new in zip(previous_info, network_info):
                    if old != new:
                        changes.append(f"Change detected in interface: {new[0]}")
            # Log changes
            for change in changes:
                logging.info(change)
                log(change)

            # Update previous info
            previous_info = network_info

        log("\033c", end="")  # Clear the screen
        display_network_info()
        count += 1
        time.sleep(5 if count < 5 else 15)




def yellow_greeen(flag, text):
    if flag is None:
        return text
    return stylize(text, back('green_yellow') if flag else back('yellow_1'))
def red(text):
    return stylize(text, back('orange_red_1'))
    #return stylize(text, back('light_red'))
    #return stylize(text, back('indian_red_1b'))


# Main function to start the network monitoring thread for testing

def networkMain():
    #monitor_network()
    changeEvent = Event()
    stopEvent = Event()
    def sigintHandler(signal, frame):
        log('SIGINT received %s' % (signal,), )
        stopEvent.set()
        changeEvent.set()

    signal.signal(signal.SIGINT, lambda signal, frame: sigintHandler(signal, frame))

    networkDiscoveredQueue = Queue()        # queue for SNMP discovery
    log('discoveryMain: starting threads', )

    threads = {}
    threads['network'] = NetworkThread(name='network_discovery',
                                   changeEvent=changeEvent, stopEvent=stopEvent,
                                   networkDiscoveredQueue=networkDiscoveredQueue,
                                   testing=True)

    log('discoveryMain: starting threads', )
    [v.start() for k, v in threads.items()]

    while not stopEvent.is_set():
        network_info = []
        if not networkDiscoveredQueue.empty():
            sleep(2)
        while not networkDiscoveredQueue.empty():
            network_info = networkDiscoveredQueue.get()
            log('-----------------------------------------------------')
            #log('Network Info:', network_info)
            #table = []
            #for info in network_info:
            #    log('Info:', info)
            #    table.append([info['interface'], yellow_greeen(info['ipPing'], info['ip']), yellow_greeen(info['gatewayPing'], info['gw'])])
            #log(tabulate(table, headers=["Interface", "IP", "Gateway"], tablefmt="grid"))
            for i, info in enumerate(network_info):
                log(f"[{i}] info['interface']={info['interface']} ip={info['ip']} {info['ipPing']} {info['ipDup']} gw={info['gw']} {info['gwPing']} {info['gwDup']}")

            table = []
            interfaces = [None, None, None, None,]
            avgs = [None, None, None, None,]
            wellknown = []
            wellavg = []
            ipaddrs = []
            gwaddrs = []
            for info in network_info:
                #def check_network_in_list(ip, ip_list):
                ipaddr = info.get('ip', '')
                gwaddr = info.get('gw', '')
                ipAvg = info.get('ipAvg', 0)
                gwAvg = info.get('gwAvg', 0)
                ip = red(ipaddr) if info.get('ipDup', False) else yellow_greeen(info['ipPing'], ipaddr)
                gw = red(gwaddr) if info.get('gwDup', False) else yellow_greeen(info['gwPing'], gwaddr)

                ipaddrs.append(ipaddr)
                gwaddrs.append(gwaddr)
                if info['interface'].startswith('en'):
                    interfaces[0] = f"{ip}/{gw}"
                    avgs[0] = f"{ipAvg:.2f}ms/{gwAvg:.2f}ms"
                elif info['interface'].startswith('wl'):
                    interfaces[1] = f"{ip}/{gw}"
                    avgs[1] = f"{ipAvg:.2f}ms/{gwAvg:.2f}ms"
                elif info['interface'].startswith('wg'):
                    interfaces[2] = f"{ip}/{gw}"
                    avgs[2] = f"{ipAvg:.2f}ms/{gwAvg:.2f}ms"
                elif info['interface'] == 'well known':
                    wellknown.append(f"{ip}")
                    wellavg.append(f"{ipAvg:.2f}ms")

            interfaces[3] = ', '.join(wellknown) if wellknown else None
            avgs[3] = ', '.join(wellavg) if wellavg else None
            log(f"Interfaces: {interfaces}")
            log(tabulate([interfaces, avgs], headers=["Ethernet", "WiFi", "WireGuard", "Well Known"], tablefmt="grid"))





if __name__ == "__main__":

    networkMain()
