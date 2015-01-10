#!/usr/bin/env python

import socket, select, sys, serial, fcntl, struct, logging

# Set LED Control server settings
UDP_IP = ''        # Leave empty for Broadcast support
ADM_PORT = 48899   # Admin port (for milight app registration)
LED_PORT = 8899    # For LED control
ADM_INT = 'eth0'   # Admin interface 

# Serial Settings
TTL_PORT = "/dev/ttyAMA0"
TTL_SPEED = 9600

class MilightBridge():
    def __init__(self, udp_ip, adm_port, led_port, int, ttl_port, ttl_speed):
        # Handle arguments
        self.udp_ip = udp_ip
        self.adm_port = adm_port
        self.led_port = led_port
        self.interface = int
        self.ttl_port = ttl_port
        self.ttl_speed = ttl_speed
        self.adm_ip = self.get_ip(self.interface)
        self.adm_mac = self.get_mac(self.interface)

        # Configure logging
        self.log = logging.getLogger('milightBridge')
        handler = logging.StreamHandler()
        log_format = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
        formatter = logging.Formatter(log_format, '%b %d %H:%M:%S')
        handler.setFormatter(formatter)
        self.log.addHandler(handler)
        self.log.setLevel(logging.INFO)

        # Open led UDP socket in non-blocking mode
        self.led_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.led_socket.bind((self.udp_ip, self.led_port))
        self.led_socket.setblocking(False)

        # Open admin UDP socket in non-blocking mode
        self.adm_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.adm_socket.bind((self.udp_ip, self.adm_port))
        self.adm_socket.setblocking(False)

        # Open serial connection
        self.serial = serial.Serial(self.ttl_port, self.ttl_speed)

        self.log.info("admin interface listening on %s:%s",
                self.udp_ip, self.adm_port)
        self.log.info("led interface listening on %s:%s",
                self.udp_ip, self.led_port)
        self.log.info("serial interface listening on %s:%s",
                self.ttl_port, self.ttl_speed)

    def get_sockets(self):
        return [self.adm_socket, self.led_socket]

    def get_ip(self, interface):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            sock.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', interface[:15])
        )[20:24])

    def get_mac(self, interface):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        info = fcntl.ioctl(
                sock.fileno(),
                0x8927,
                struct.pack('256s', interface[:15])
                )
        return ':'.join(['%02x' % ord(char) for char in info[18:24]])

    def process_led_pkt(self, data):
        self.serial.write(data)
        self.log.debug("led command: 0x%s",
                ' 0x'.join(x.encode('hex') for x in data))

    def process_adm_pkt(self, data, addr):
        self.log.debug("admin command: %s", data)
        if str(data).find("Link_Wi-Fi") != -1:
            reply = "%s,%s," % (self.adm_ip, self.adm_mac.replace(':', ''))
            self.adm_socket.sendto(bytes(reply), addr)
            self.log.debug("admin reply: %s", reply)
        else:
            self.adm_socket.sendto(bytes("+ok"), addr)
            self.log.debug("admin reply: +ok")

    def start(self):
        self.log.info("bridge accepting commands")

        while True:
            ready_socks,_,_ = select.select(self.get_sockets(), [], [])

            for sock in ready_socks:
                data, addr = sock.recvfrom(64) # buffer size is 64 bytes

                if data is None:
                    continue

                if sock is self.led_socket:
                    self.process_led_pkt(data)
                elif sock is self.adm_socket:
                    self.process_adm_pkt(data, addr)


if __name__ == '__main__':
    bridge = MilightBridge(UDP_IP, ADM_PORT, LED_PORT, ADM_INT, TTL_PORT, TTL_SPEED)
    bridge.start()
