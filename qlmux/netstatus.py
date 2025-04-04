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

    def __init__(self, name='network', changeEvent=None, stopEvent=None, networkDiscoveredQueue=None):
        Thread.__init__(self)
        self.name = name
        self.changeEvent = changeEvent
        self.stopEvent = stopEvent
        self.networkDiscoveredQueue = networkDiscoveredQueue
        self.ip_route = IPRoute()  # Initiate IPRoute object here for reuse

    def run(self):
        log(f'{self.name}: starting')
        try:
            while not self.stopEvent.is_set():
                network_info = self.get_network_info()  # Gather network data
                self.networkDiscoveredQueue.put(network_info)  # Put in the queue
                time.sleep(2)  # Sleep to avoid overwhelming the queue

        finally:
            log(f'{self.name}: stopping')
            # Cleanup any open resources
            if hasattr(self, 'ip_route') and self.ip_route:
                self.ip_route.close()  # Cleanly close the IPRoute object to avoid open file descriptors.
            log(f"{self.name}: resources cleaned up")

    def get_gateway(self, interface):
        if interface.startswith('wg'):
            return self.get_wireguard_endpoint(interface)

        # Use IPRoute to get the routing information
        gateways = self.ip_route.get_routes()
        for route in gateways:
            if route.get('dst_len') == 0:  # Check for default route (0.0.0.0)
                for attr in route['attrs']:
                    if attr[0] == 'RTA_GATEWAY':
                        return attr[1]
        return "N/A"

    def get_wireguard_endpoint(self, interface):
        try:
            device = WireguardDevice.get(interface)
            config = device.get_config().asdict()
            log(f"Device: {interface}")
            for peer in config["peers"]:
                if "endpoint_host" in peer:
                    return peer["endpoint_host"]
            return "N/A"
        except Exception as e:
            log(f"Error: {e}")
            return "N/A"

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
        if ip is None or ip == '':
            log(f"Checking network for IP: {ip} in list: {ip_list} None or empty IP, skipping check")
            return False
        network_part = self.get_network_part(ip)
        for other_ip in ip_list:
            if self.get_network_part(other_ip) == network_part:
                log(f"Checking network for IP: {ip} in list: {ip_list} True")
                return True  # Network match found
        log(f"Checking network for IP: {ip} in list: {ip_list} False")
        return False  # No network match found

    def is_gateway_in_network(self, interface_ip, gateway_ip, subnet_mask):
        try:
            # Create network address objects for IP and Gateway
            network = ipaddress.IPv4Network(f'{interface_ip}/{subnet_mask}', strict=False)
            gateway = ipaddress.IPv4Address(gateway_ip)
            
            # Check if gateway is in the same network
            return gateway in network
        except ValueError:
            return False


    def get_network_info(self, networkDiscoveredQueue=None):
        network_info = []
        interfaces = psutil.net_if_addrs()
        
        # Generalized exclusion list
        startslist = ["lo", "br-", "virb", "veth"]

        wellknown = ["1.1.1.1", "8.8.8.8", "192.168.254.254"]
        gateways = []
        ipaddrs = []
        ip_ping_times = {}

        for interface, addrs in interfaces.items():
            # Skip interfaces that start with any of the prefixes in startslist
            if any(interface.startswith(prefix) for prefix in startslist):
                continue
            
            # Check for ethernet, wifi, and wireguard interfaces
            ip = "N/A"
            subnet_mask = "N/A"
            if any(proto.family == socket.AF_INET for proto in addrs):
                ip = next(addr.address for addr in addrs if addr.family == socket.AF_INET)
                subnet_mask = next(addr.netmask for addr in addrs if addr.family == socket.AF_INET)
            
            # Get MAC address if available
            mac = next((addr.address for addr in addrs if addr.family == psutil.AF_LINK), "N/A")

            # Get network speed (in Mbps)
            speed = psutil.net_if_stats().get(interface, None)
            speed = f"{speed.speed / 1e6:.2f} Mbps" if speed else "N/A"

            # Retrieve the gateway using the pyroute2 routing table
            gateway = self.get_gateway(interface)
            if not interface.startswith("wg") and gateway != "N/A" and not self.is_gateway_in_network(ip, gateway, subnet_mask):
                gateway = "N/A"
                ipaddrs.append(ip)
                continue

            gateways.append(gateway)
            ipaddrs.append(ip)
            network_info.append({'interface': interface, 'ip': ip, 'ipPing': None, 'ipDup': None, 'gw': gateway, 'gwPing': None, 'gwDup': None,  })

            log(f"Gateway: {interface} {gateway}")
            continue

        log('---------------------------------------')
        log('---------------------------------------')
        # Use multiping to ping multiple gateways at once
        ping_results = multiping(gateways + wellknown + ipaddrs, count=1, timeout=2)
        #print(f"Ping Results: {ping_results}")
        #for result in ping_results:
        #    print(f"Ping Result: {result}")

        # Store ping times in a dictionary for avg calculation
        for host in ping_results:
            if host.is_alive:
                if host.address not in ip_ping_times:
                    ip_ping_times[host.address] = []
                ip_ping_times[host.address].append(host.avg_rtt)  # avg_rtt stores the average round-trip time for each ping

        results = {host.address: host.is_alive for host in ping_results}
        
        log('---------------------------------------')
        log(f"Results: {results}")
        log('---------------------------------------')
        
        # Now, calculate the average ping times for each IP and GW in network_info
        ip_avg_times = {}
        for ip, ip_ping_times in ip_ping_times.items():
            ipAvg = sum(ip_ping_times) / len(ip_ping_times)
            ip_avg_times[ip] = ipAvg
        print(f"ip_avg_times: {ip_avg_times}")

        for i, info in enumerate(network_info):
            log(f"Info[{i}]: {info}")
            allips = [_info['ip'] for _info in network_info]
            allgws = [_info['gw'] for _info in network_info]
            otherips = [_info['ip'] for _info in network_info if _info['interface'] != info['interface']]
            othergws = [_info['gw'] for _info in network_info if _info['interface'] != info['interface']]
            log(f"otherips: {otherips} allips: {allips}")
            log(f"othergws: {othergws} allgws: {allgws}")
            info['gwPing'] = results.get(info['gw'], None)
            info['ipPing'] = results.get(info['ip'], None)
            info['ipDup'] = self.check_network_in_list(info['ip'], otherips) if info['ip'] else None
            info['gwDup'] = self.check_network_in_list(info['gw'], othergws) if info['gw'] else None
            info['ipAvg'] = ip_avg_times.get(info['ip'], 0)
            info['gwAvg'] = ip_avg_times.get(info['gw'], 0)



        for ip in wellknown:
            network_info.append({'interface': 'well known', 'ip': ip, 'ipPing': results.get(ip, None), 
                                 'ipDup': False, 'gwDup': False, 
                                 'ipAvg': ip_avg_times.get(ip, 0), 'gwAvg': 0,
                                 'gw': None, 'gwPing': None })

        log('---------------------------------------')
        #log(f"Network Info: {network_info}")
        for i, info in enumerate(network_info):
            print(f"Info[{i}]: {info}")
        log('---------------------------------------')
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
        time.sleep(5)




def yellow_greeen(flag, text):
    if flag is None:
        return text
    return stylize(text, back('green_yellow') if flag else back('yellow_1'))
def red(text):
    return stylize(text, back('orange_red_1')) 
    #return stylize(text, back('light_red'))
    #return stylize(text, back('indian_red_1b')) 

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
                                   networkDiscoveredQueue=networkDiscoveredQueue)
 
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

