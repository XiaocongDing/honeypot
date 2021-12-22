import os
import sys
import json
import requests
import ast
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
                    greenlet.link_exception()
                    servers.append(server)
        # protocol_template = 
    
if __name__ == "__main__":
    
    main()