import os
import sys
import json
import requests
import ast
import gevent
import logging
from lxml import etree
from configparser import ConfigParser
from requests.exceptions import Timeout, ConnectionError
import protocols.IEC104.IEC104_server as IEC104Server
import protocols.modbus.modbus_server as ModbusServer

args_template = "IEC104"
root_template_dir = "./protocols/"
root_xsd = "./core.xsd"
root_config = "./testing.cfg"
config = ConfigParser(os.environ)
logger = logging.getLogger()

def validate_template(xml_file, xsd_file):
    xml_schema = etree.parse(xsd_file)
    xsd = etree.XMLSchema(xml_schema)
    xml = etree.parse(xml_file)
    xsd.validate(xml)
    if xsd.error_log:
        print('Error parsing XML template')
        sys.exit(1)

def _fetch_data(urls):
    for url in urls:
        try:
            req = requests.get(url, timeout = 5)
            if req.status_code == 200:
                data = req.text.strip()
                if data is None:
                    continue
                else:
                    return data
            else:
                raise ConnectionError
        except (Timeout, ConnectionError):
            print('Could not fetch public ip')
    return None

def on_unhandled_greenlet_exception(dead_greenlet):
    logger.error('Stopping because %s died: %s', dead_greenlet, dead_greenlet.exception)
    sys.exit(1)

def get_ext_ip(config=None, urls=None):
    if config:
        urls = json.loads(config.get('fetch_public_ip', 'urls'))
    public_ip = _fetch_data(urls)
    if public_ip:
        print('%s as external ip. ' % public_ip)
    else:
        print("Could not fetch public ip")
    return public_ip

def main():
    servers = list()
    
    # validate the template
    root_template = os.path.join(root_template_dir, args_template, 'template.xml')
    if os.path.isfile(root_template):
        validate_template(root_template, root_xsd)
    else:
        print("Could not access template configuration")
        sys.exit(1)

    # read config file    
    config.read(root_config)
    fs_url = config.get('virtual_file_system', 'fs_url')
    data_fs_url = config.get('virtual_file_system', 'data_fs_url')

    fs_url, data_fs_url = None, None
   
    public_ip = get_ext_ip(config)
    
    protocol_instance_mapping = (
        ('modbus', ModbusServer),
        # ('s7comm', S7Server),
        # ('kamstrup_meter', KamstrupServer),
        # ('kamstrup_management', KamstrupManagementServer),
        # ('http', HTTPServer),
        # ('snmp', SNMPServer),
        # ('bacnet', BacnetServer),
        # ('ipmi', IpmiServer),
        # ('guardian_ast', GuardianASTServer),
        # ('enip', EnipServer),
        ('IEC104', IEC104Server)
        # ('ftp', FTPServer),
        # ('tftp', TftpServer)
    )

    # do not change mac address, neither fork
    for protocol in protocol_instance_mapping:
        protocol_name, server_class = protocol
        protocol_template = os.path.join(root_template_dir, protocol_name, '{0}.xml'.format(protocol_name))
        if os.path.isfile(protocol_template):
            xsd_file = os.path.join(root_template_dir, protocol_name, '{0}.xsd'.format(protocol_name))
            validate_template(protocol_template, xsd_file)
            dom_protocol = etree.parse(protocol_template)
            if dom_protocol.xpath('//{0}'.format(protocol_name)):
                if ast.literal_eval(dom_protocol.xpath('//{0}/@host'.format(protocol_name))[0]):
                    host = dom_protocol.xpath('//{0}/@host'.format(protocol_name))[0]
                    port = ast.literal_eval(dom_protocol.xpath('//{0}/@port'.format(protocol_name))[0])
                    server = server_class(protocol_template, root_template_dir)
                    greenlet = gevent.spawn(server.start, host, port)
                    greenlet.link_exception(on_unhandled_greenlet_exception)
                    servers.append(server)
                    logger.info('Found and enabled %s protocol.', (protocol[0], server))
        # protocol_template = 
            else:
                logger.info('%s available but disabled by configuration.' , protocol_name)
        else:
            logger.debug('No %s template found. Service will remain stopped', protocol_name)
    
    log_worker = log_worker(config, dom_base, session_manager, public_ip)
    greenlet = gevent.spawn(log_worker.start)
    green.link_exception(on_unhandled_greenlet_exception)

    template_proxy = os.path.join(root_template_dir, 'proxy', 'proxy.xml')
    if os.path.isfile(template_proxy):
        xsd_file = os.path.join('./emulators/', 'proxy.xsd')
        validate_template(template_proxy, xsd_file)
        dom_proxy = etree.parse(template_proxy)
        if dom_proxy.xpath('//proxies'):
            if ast.literal_eval(dom_proxy.xpath('//proxies/@enabled')[0]):
                proxies = dom_proxy.xpath('//proxies/*')
                for p in proxies:
                    name = p.attrib['name']
                    host = p.attrib['host']
                    keyfile = None
                    certfile = None
                    if 'keyfile' in p.attrib and 'certfile' in p.attrib:
                        keyfile = p.attrib['keyfile']
                        certfile = p.attrib['certfile']

                        # if path is absolute we assert that the cert and key is located in
                        # the templates ssl standard location

                        if not os.path.isabs(keyfile):
                            keyfile = os.path.join(os.path.dirname(root_template_dir), 'ssl', keyfile)
                            certfile = os.path.join(os.path.dirname(root_template_dir), 'ssl', certfile)
                    port = ast.literal_eval(p.attrib['port'])
                    proxy_host = p.xpath('./proxy_host/text()')[0]
                    proxy_port = ast.literal_eval(p.xpath('./proxy_port/text()')[0])
                    decoder = p.xpath('./decoder/text()')
                    if len(decoder) > 0:
                        decoder = decoder[0]
                    else:
                        decoder = None
                    proxy_instance = Proxy(name, proxy_host, proxy_port, decoder, keyfile, certfile)
                    proxy_server = proxy_instance.get_server(host, port)
                    servers.append(proxy_instance)
                    proxy_greenlet = gevent.spawn(proxy_server.start)
                    proxy_greenlet.link_exception(on_unhandled_greenlet_exception)
            else:
                logger.info('Proxy available but disabled by the template')
    else:
        logger.info('No proxy template found. Service will remain unconfigured')
    
    gevent.sleep(5)

if __name__ == "__main__":
    
    main()
