# SPDX-License-Identifier: MIT
# Author: remittor <remittor@gmail.com>
# Created: 2024

import os
import sys
import subprocess
import optparse
import random
import datetime
import qrcode

g_main_config_src = '.main.config'
g_main_config_fn = None
g_main_config_path = None
g_main_config_type = None

g_defclient_config_fn = "_defclient.config"
g_defclient_allowed_ips = "0.0.0.0/5, 8.0.0.0/7, 11.0.0.0/8, 12.0.0.0/6, 16.0.0.0/4, 32.0.0.0/3, 64.0.0.0/2, 128.0.0.0/3, 160.0.0.0/5, 168.0.0.0/6, 172.0.0.0/12, 172.32.0.0/11, 172.64.0.0/10, 172.128.0.0/9, 173.0.0.0/8, 174.0.0.0/7, 176.0.0.0/4, 192.0.0.0/9, 192.128.0.0/11, 192.160.0.0/13, 192.169.0.0/16, 192.170.0.0/15, 192.172.0.0/14, 192.176.0.0/12, 192.192.0.0/10, 193.0.0.0/8, 194.0.0.0/7, 196.0.0.0/6, 200.0.0.0/5, 208.0.0.0/4, <CLIENT_DNS>/32"

parser = optparse.OptionParser("usage: %prog [options]")
parser.add_option("-t", "--tmpcfg", dest="tmpcfg", default = g_defclient_config_fn)
parser.add_option("-u", "--update", dest="update", default = "")
parser.add_option("-d", "--delete", dest="delete", default = "")
parser.add_option("-i", "--ipaddr", dest="ipaddr", default = "")
parser.add_option("-p", "--port", dest="port", default = None, type = 'int')
parser.add_option("", "--make", dest="makecfg", default = "")
parser.add_option("", "--ldconf", dest="ldconf", default = "")
parser.add_option("", "--tun", dest="tun", default = "")
parser.add_option("", "--create", dest="create", action="store_true", default = False)
parser.add_option("", "--addcl", dest="addcl", default = "")
parser.add_option("", "--confgen", dest="confgen", default = "")
parser.add_option("", "--allowed", dest="allowed", default = "")
parser.add_option("", "--dns", dest="dns", default = "8.8.8.8")
(opt, args) = parser.parse_args()


g_defserver_config = """
[Interface]
#_GenKeyTime = <SERVER_KEY_TIME>
PrivateKey = <SERVER_PRIVATE_KEY>
#_PublicKey = <SERVER_PUBLIC_KEY>
Address = <SERVER_ADDR>
ListenPort = <SERVER_PORT>
Jc = <JC>
Jmin = <JMIN>
Jmax = <JMAX>
S1 = <S1>
S2 = <S2>
H1 = <H1>
H2 = <H2>
H3 = <H3>
H4 = <H4>

PostUp = iptables -A FORWARD -i <SERVER_TUN> -o <SERVER_IFACE> -s <SERVER_SUBNET> -j ACCEPT; iptables -A FORWARD -i <SERVER_IFACE> -o <SERVER_TUN> -d <SERVER_SUBNET> -j ACCEPT; iptables -t nat -A POSTROUTING -s <SERVER_SUBNET> -o <SERVER_IFACE> -j MASQUERADE

PostDown = iptables -D FORWARD -i <SERVER_TUN> -o <SERVER_IFACE> -s <SERVER_SUBNET> -j ACCEPT; iptables -D FORWARD -i <SERVER_IFACE> -o <SERVER_TUN> -d <SERVER_SUBNET> -j ACCEPT; iptables -t nat -D POSTROUTING -s <SERVER_SUBNET> -o <SERVER_IFACE> -j MASQUERADE
"""

g_defclient_config = """
[Interface]
PrivateKey = <CLIENT_PRIVATE_KEY>
#_PublicKey = <CLIENT_PUBLIC_KEY>
Address = <CLIENT_TUNNEL_IP>
DNS = <CLIENT_DNS>
Jc = <JC>
Jmin = <JMIN>
Jmax = <JMAX>
S1 = <S1>
S2 = <S2>
H1 = <H1>
H2 = <H2>
H3 = <H3>
H4 = <H4>

[Peer]
AllowedIPs = <CLIENT_ALLOWED_IPs>
Endpoint = <SERVER_ADDR>:<SERVER_PORT>
PersistentKeepalive = 60
PublicKey = <SERVER_PUBLIC_KEY>
"""

class IPAddr():
    def __init__(self, ipaddr = None):
        self.ip = [ 0, 0, 0, 0 ]
        self.mask = None
        if ipaddr:
            self.init(ipaddr)

    def init(self, ipaddr):
        _ipaddr = ipaddr
        if not ipaddr:
            raise RuntimeError(f'ERROR: Incorrect IP-Addr: "{_ipaddr}"')
        if ' ' in ipaddr:
            raise RuntimeError(f'ERROR: Incorrect IP-Addr: "{_ipaddr}"')
        if ',' in ipaddr:
            raise RuntimeError(f'ERROR: Incorrect IP-Addr: "{_ipaddr}"')
        self.ip = [ 0, 0, 0, 0 ]
        self.mask = None
        if '/' in ipaddr:
            self.mask = int(ipaddr.split('/')[1])
            ipaddr = ipaddr.split('/')[0]
        nlist = ipaddr.split('.')
        if len(nlist) != 4:
            raise RuntimeError(f'ERROR: Incorrect IP-addr: "{_ipaddr}"')
        for n, num in enumerate(nlist):
            self.ip[n] = int(num)
        self.subnet = f'{self.ip[0]}.{self.ip[1]}.{self.ip[2]}.0/{self.mask}'

    def __str__(self):
        out = f'{self.ip[0]}.{self.ip[1]}.{self.ip[2]}.{self.ip[3]}'
        if self.mask:
            out += '/' + str(self.mask)
        return out

class WGConfig():
    def __init__(self, filename = None):
        self.lines = [ ]
        self.iface = { }
        self.peer = { }
        self.idsline = { }
        self.cfg_fn = None
        if filename:
            self.load(filename)

    def load(self, filename):
        self.cfg_fn = None
        self.lines = [ ]
        self.iface = { }
        self.peer = { }
        self.idsline = { }
        with open(filename, 'r') as file:
            lines = file.readlines()

        iface = None

        secdata = [ ]
        secdata_item = None
        secline = [ ]
        secline_item = None

        for n, line in enumerate(lines):
            line = line.rstrip()
            self.lines.append(line)

            if line.strip() == '':
                continue

            if line.startswith(' ') and not line.strip().startswith('#'):
                raise RuntimeError(f'ERROR_CFG: Incorrect line #{n} into config "{filename}"')

            if line.startswith('#') and not line.startswith('#_'):
                continue

            if line.startswith('[') and line.endswith(']'):
                section_name = line[1:-1]
                if not section_name:
                    raise RuntimeError(f'ERROR_CFG: Incorrect section name: "{section_name}" (#{n+1})')
                #print(secname)
                secdata_item = { "_section_name": section_name.lower() }
                secline_item = { "_section_name": n }
                if section_name.lower() == 'interface':
                    if iface:
                        raise RuntimeError(f'ERROR_CFG: Found second section Interface in line #{n+1}')
                    iface = secdata_item
                elif section_name.lower() == 'peer':
                    pass
                else:
                    raise RuntimeError(f'ERROR_CFG: Found incorrect section "{section_name}" in line #{n+1}')
                secdata.append(secdata_item)
                secline.append(secline_item)
                continue

            if line.startswith('#_') and ' = ' in line:
                line = line[2:]

            if line.startswith('#'):
                continue

            if ' = ' not in line:
                raise RuntimeError(f'ERROR_CFG: Incorrect line into config: "{line}"  (#{n+1})')

            xv = line.find(' = ')
            if xv <= 0:
                raise RuntimeError(f'ERROR_CFG: Incorrect line into config: "{line}"  (#{n+1})')

            vname = line[:xv].strip()
            value = line[xv+3:].strip()
            #print(f'  "{vname}" = "{value}"')
            if not secdata_item:
                raise RuntimeError(f'ERROR_CFG: Parameter "{vname}" have unknown section! (#{n+1})')

            section_name = secdata_item['_section_name']
            if vname in secdata_item:
                raise RuntimeError(f'ERROR_CFG: Found duplicate of param "{vname}" into section "{section_name}" (#{n+1})')

            secdata_item[vname] = value
            secline_item[vname] = n

        if not iface:
            raise RuntimeError(f'ERROR_CFG: Cannot found section Interface!')

        for i, item in enumerate(secdata):
            line = secline[i]
            peer_name = ""
            if item['_section_name'] == 'interface':
                self.iface = item
                peer_name = "__this_server__"
                if 'PublicKey' not in item:
                    raise RuntimeError(f'ERROR_CFG: Cannot found PublicKey in Interface')
                if 'PrivateKey' not in item:
                    raise RuntimeError(f'ERROR_CFG: Cannot found PrivateKey in Interface')
            else:
                if 'Name' in item:
                    peer_name = item['Name']
                    if not peer_name:
                        raise RuntimeError(f'ERROR_CFG: Invalid peer Name in line #{line["Name"]}')
                elif 'PublicKey' in item:
                    peer_name = item['PublicKey']
                    if not peer_name:
                        raise RuntimeError(f'ERROR_CFG: Invalid peer PublicKey in line #{line["PublicKey"]}')
                else:
                    raise RuntimeError(f'ERROR_CFG: Invalid peer data in line #{line["_section_name"]}')

                if 'AllowedIPs' not in item:
                    raise RuntimeError(f'ERROR_CFG: Cannot found "AllowedIPs" into peer "{peer_name}"')

                if peer_name in self.peer:
                    raise RuntimeError(f'ERROR_CFG: Found duplicate peer with name "{peer_name}"')

                self.peer[peer_name] = item

            if peer_name in self.idsline:
                raise RuntimeError(f'ERROR_CFG: Found duplicate peer with name "{peer_name}"')

            min_line = line['_section_name']
            max_line = min_line
            self.idsline[f'{peer_name}'] = min_line
            for vname in item:
                self.idsline[f'{peer_name}|{vname}'] = line[vname]
                if line[vname] > max_line:
                    max_line = line[vname]

            item['_lines_range'] = ( min_line, max_line )

        self.cfg_fn = filename
        return len(self.peer)

    def save(self, filename = None):
        if not filename:
            filename = self.cfg_fn

        if not self.lines:
            raise RuntimeError(f'ERROR: no data')

        with open(filename, 'w', newline = '\n') as file:
            for line in self.lines:
                file.write(line + '\n')

    def del_client(self, c_name):
        if c_name not in self.peer:
            raise RuntimeError(f'ERROR: Not found client "{c_name}" in peer list!')

        client = self.peer[c_name]
        ipaddr = client['AllowedIPs']
        min_line, max_line = client['_lines_range']
        del self.lines[min_line:max_line+1]
        del self.peer[c_name]
        secsize = max_line - min_line + 1
        del_list = [ ]
        for k, v in self.idsline.items():
            if v >= min_line and v <= max_line:
                del_list.append(k)
            elif v > max_line:
                self.idsline[k] = v - secsize
        for k in del_list:
            del self.idsline[k]
        return ipaddr

    def set_param(self, c_name, param_name, param_value, force = False, offset = 0):
        if c_name not in self.peer:
            raise RuntimeError(f'ERROR: Not found client "{c_name}" in peer list!')

        line_prefix = ""
        if param_name.startswith('_'):
            line_prefix = "#_"
            param_name = param_name[1:]

        client = self.peer[c_name]
        min_line, max_line = client['_lines_range']
        if param_name in client:
            nline = self.idsline[f'{c_name}|{param_name}']
            line = self.lines[nline]
            if line.startswith('#_'):
                line_prefix = "#_"
            self.lines[nline] = f'{line_prefix}{param_name} = {param_value}'
            return

        if not force:
            raise RuntimeError(f'ERROR: Param "{param_name}" not found for client "{c_name}"')

        new_line = f'{line_prefix}{param_name} = {param_value}'
        client[param_name] = param_value
        secsize = max_line - min_line + 1
        if offset >= secsize:
            raise RuntimeError(f'ERROR: Incorrect offset value = {offset} (secsize = {secsize})')

        pos = max_line + 1 if offset <= 0 else min_line + offset
        for k, v in self.idsline.items():
            if v >= pos:
                self.idsline[k] = v + 1

        self.idsline[f'{c_name}|{param_name}'] = pos
        self.lines.insert(pos, new_line)
        return


def exec_cmd(cmd, input = None, shell = True, check = True, timeout = None):
    proc = subprocess.run(cmd, input = input, shell = shell, check = check,
                          timeout = timeout, encoding = 'utf8',
                          stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
    rc = proc.returncode
    out = proc.stdout
    return rc, out

def check_main_iface(iface):
    rc, out = exec_cmd('ip link show')
    if rc:
        raise RuntimeError(f'ERROR: Cannot get net interfaces')

    for line in out.split('\n'):
        if '<BROADCAST' in line and 'state UP' in line:
            xv = line.split(':')[1].strip().split('@')[0].strip()
            if xv == iface:
                return True

    return False

def get_main_iface():
    rc, out = exec_cmd("ip route get 8.8.8.8")
    if rc:
        raise RuntimeError(f'ERROR: Cannot get net interfaces')

    for line in out.split('\n'):
        iface = line.split(' ')[4]
        if check_main_iface(iface):
            return iface

    return None

def get_ext_ipaddr():
    rc, out = exec_cmd('curl -4 -s icanhazip.com')
    if rc:
        raise RuntimeError(f'ERROR: Cannot get ext IP-Addr')

    lines = out.split('\n')
    ipaddr = lines[-1] if lines[-1] else lines[-2]
    ipaddr = IPAddr(ipaddr)
    return str(ipaddr)

def gen_pair_keys(cfg_type = None):
    global g_main_config_type
    if sys.platform == 'win32':
        return 'client_priv_key', 'client_pub_key'

    if not cfg_type:
        cfg_type = g_main_config_type

    if not cfg_type:
        raise

    wgtool = cfg_type.lower()
    rc, out = exec_cmd(f'{wgtool} genkey')
    if rc:
        raise RuntimeError(f'ERROR: Cannot generate private key')

    priv_key = out.strip()
    if not priv_key:
        raise RuntimeError(f'ERROR: Cannot generate private Key')

    rc, out = exec_cmd(f'{wgtool} pubkey', input = priv_key + '\n')
    if rc:
        raise RuntimeError(f'ERROR: Cannot generate public key')

    pub_key = out.strip()
    if not pub_key:
        raise RuntimeError(f'ERROR: Cannot generate public Key')

    return priv_key, pub_key

def get_main_config_path(check = True):
    global g_main_config_fn
    global g_main_config_path
    global g_main_config_type
    if not os.path.exists(g_main_config_src):
        raise RuntimeError(f'ERROR: file "{g_main_config_src}" not found!')

    with open(g_main_config_src, 'r') as file:
        lines = file.readlines()

    g_main_config_fn = lines[0].strip()
    cfg_exists = os.path.exists(g_main_config_fn)
    g_main_config_type = 'WG'
    if os.path.basename(g_main_config_fn).startswith('a'):
        g_main_config_type = 'AWG'

    if check:
        if not cfg_exists:
            raise RuntimeError(f'ERROR: Main {g_main_config_type} config file "{g_main_config_fn}" not found!')

    g_main_config_path, _ = os.path.split(g_main_config_fn)
    return g_main_config_fn

# -------------------------------------------------------------------------------------

if opt.makecfg:
    g_main_config_fn = opt.makecfg
    if os.path.exists(g_main_config_fn):
        raise RuntimeError(f'ERROR: file "{g_main_config_fn}" already exists!')

    m_cfg_type = 'WG'
    if os.path.basename(g_main_config_fn).startswith('a'):
        m_cfg_type = 'AWG'

    print(f'Make {m_cfg_type} server config: "{g_main_config_fn}"...')
    main_iface = get_main_iface()
    if not main_iface:
        raise RuntimeError(f'ERROR: Cannot get main network interface!')

    print(f'Main network iface: "{main_iface}"')

    if opt.port <= 1000 or opt.port > 65530:
        raise RuntimeError(f'ERROR: Incorrect argument port = {opt.port}')

    if not opt.ipaddr:
        raise RuntimeError(f'ERROR: Incorrect argument ipaddr = "{opt.ipaddr}"')

    ipaddr = IPAddr(opt.ipaddr)
    if not ipaddr.mask:
        raise RuntimeError(f'ERROR: Incorrect argument ipaddr = "{opt.ipaddr}"')

    if opt.tun:
        tun_name = opt.tun
    else:
        cfg_name = os.path.basename(g_main_config_fn)
        tun_name = os.path.splitext(cfg_name)[0].strip()

    print(f'Tunnel iface: "{tun_name}"')

    priv_key, pub_key = gen_pair_keys(m_cfg_type)

    random.seed()
    jc = random.randint(3, 127)
    jmin = random.randint(3, 700)
    jmax = random.randint(jmin+1, 1270)

    out = g_defserver_config
    out = out.replace('<SERVER_KEY_TIME>', datetime.datetime.now().isoformat())
    out = out.replace('<SERVER_PRIVATE_KEY>', priv_key)
    out = out.replace('<SERVER_PUBLIC_KEY>', pub_key)
    out = out.replace('<SERVER_ADDR>', str(ipaddr))
    out = out.replace('<SERVER_PORT>', str(opt.port))
    out = out.replace('<SERVER_SUBNET>', str(ipaddr.subnet))
    if m_cfg_type == 'AWG':
        out = out.replace('<JC>', str(jc))
        out = out.replace('<JMIN>', str(jmin))
        out = out.replace('<JMAX>', str(jmax))
        out = out.replace('<S1>', str(random.randint(3, 127)))
        out = out.replace('<S2>', str(random.randint(3, 127)))
        out = out.replace('<H1>', str(random.randint(0x10000011, 0x7FFFFF00)))
        out = out.replace('<H2>', str(random.randint(0x10000011, 0x7FFFFF00)))
        out = out.replace('<H3>', str(random.randint(0x10000011, 0x7FFFFF00)))
        out = out.replace('<H4>', str(random.randint(0x10000011, 0x7FFFFF00)))
    else:
        out = out.replace('\nJc = <'  , '\n# ')
        out = out.replace('\nJmin = <', '\n# ')
        out = out.replace('\nJmax = <', '\n# ')
        out = out.replace('\nS1 = <'  , '\n# ')
        out = out.replace('\nS2 = <'  , '\n# ')
        out = out.replace('\nH1 = <'  , '\n# ')
        out = out.replace('\nH2 = <'  , '\n# ')
        out = out.replace('\nH3 = <'  , '\n# ')
        out = out.replace('\nH4 = <'  , '\n# ')

    out = out.replace('<SERVER_IFACE>', main_iface)
    out = out.replace('<SERVER_TUN>', tun_name)

    with open(g_main_config_fn, 'w', newline = '\n') as file:
        file.write(out)

    print(f'{m_cfg_type} server config file "{g_main_config_fn}" created!')

    with open(g_main_config_src, 'w', newline = '\n') as file:
        file.write(g_main_config_fn)

    sys.exit(0)

# -------------------------------------------------------------------------------------

if opt.ldconf:
    if not os.path.exists(opt.ldconf):
        raise RuntimeError(f'ERROR: file "{opt.ldconf}" does not exists!')
    g_main_config_fn = opt.ldconf
    with open(g_main_config_src, 'w', newline = '\n') as file:
        file.write(g_main_config_fn)

# -------------------------------------------------------------------------------------

get_main_config_path(check = True)

if opt.create:
    if os.path.exists(opt.tmpcfg):
        print(f'Template client config file "{opt.tmpcfg}" already exists, nothing to do...')
        sys.exit(0)

    print(f'Create template for client configs: "{opt.tmpcfg}"...')
    if opt.ipaddr:
        ipaddr = opt.ipaddr
    else:
        ext_ipaddr = get_ext_ipaddr()
        print(f'External IP-Addr: "{ext_ipaddr}"')
        ipaddr = ext_ipaddr

    ipaddr = IPAddr(ipaddr)
    if ipaddr.mask:
        raise RuntimeError(f'ERROR: Incorrect argument ipaddr = "{opt.ipaddr}"')

    print(f'Server IP-Addr: "{ipaddr}"')

    out = g_defclient_config
    out = out.replace('<SERVER_ADDR>', str(ipaddr))
    if g_main_config_type != 'AWG':
        out = out.replace('\nJc = <'  , '\n# ')
        out = out.replace('\nJmin = <', '\n# ')
        out = out.replace('\nJmax = <', '\n# ')
        out = out.replace('\nS1 = <'  , '\n# ')
        out = out.replace('\nS2 = <'  , '\n# ')
        out = out.replace('\nH1 = <'  , '\n# ')
        out = out.replace('\nH2 = <'  , '\n# ')
        out = out.replace('\nH3 = <'  , '\n# ')
        out = out.replace('\nH4 = <'  , '\n# ')

    with open(opt.tmpcfg, 'w', newline = '\n') as file:
        file.write(out)

    print(f'Template client config file "{opt.tmpcfg}" created!')
    sys.exit(0)

# -------------------------------------------------------------------------------------

xopt = [ opt.addcl, opt.update, opt.delete ]
copt = [ x for x in xopt if len(x) > 0 ]
if copt and len(copt) >= 2:
    raise RuntimeError(f'ERROR: Incorrect arguments! Too many actions!')

if opt.addcl:
    cfg = WGConfig(g_main_config_fn)
    srv = cfg.iface
    c_name = opt.addcl
    print(f'Add new client config "{c_name}"...')
    max_addr = None
    for peer_name, peer in cfg.peer.items():
        if peer_name.lower() == c_name.lower():
            raise RuntimeError(f'ERROR: peer with name "{c_name}" already exists!')

        if opt.ipaddr:
            addr = IPAddr(opt.ipaddr)
            addr.mask = None
            addr = str(addr)
            p_addr = IPAddr(peer['AllowedIPs'])
            p_addr.mask = None
            p_addr = str(p_addr)
            if addr == p_addr:
                raise RuntimeError(f'ERROR: IP-addr "{opt.ipaddr}" already used!')

        addr = IPAddr(peer['AllowedIPs'])
        if not max_addr or addr.ip[3] > max_addr.ip[3]:
            max_addr = addr

    priv_key, pub_key = gen_pair_keys()

    with open(g_main_config_fn, 'rb') as file:
        srvcfg = file.read()
        srvcfg = srvcfg.decode('utf8')

    if opt.ipaddr:
        ipaddr = opt.ipaddr
    else:
        if max_addr is None:
            max_addr = IPAddr(srv['Address'])
            max_addr.ip[3] += 1
            max_addr.mask = 32
            ipaddr = str(max_addr)
        else:
            max_addr.ip[3] += 1
            ipaddr = str(max_addr)
        if max_addr.ip[3] >= 254:
            raise RuntimeError(f'ERROR: There are no more free IP-addresses')

    srvcfg += f'\n'
    srvcfg += f'[Peer]\n'
    srvcfg += f'#_Name = {c_name}\n'
    srvcfg += f'#_GenKeyTime = {datetime.datetime.now().isoformat()}\n'
    srvcfg += f'#_PrivateKey = {priv_key}\n'
    srvcfg += f'PublicKey = {pub_key}\n'
    srvcfg += f'AllowedIPs = {ipaddr}\n'

    with open(g_main_config_fn, 'w', newline = '\n') as file:
        file.write(srvcfg)

    print(f'New client "{c_name}" added! IP-Addr: "{ipaddr}"')

if opt.update:
    cfg = WGConfig(g_main_config_fn)
    p_name = opt.update
    print(f'Update keys for client "{p_name}"...')
    priv_key, pub_key = gen_pair_keys()
    cfg.set_param(p_name, '_PrivateKey', priv_key, force = True, offset = 2)
    cfg.set_param(p_name, 'PublicKey', pub_key)
    gentime = datetime.datetime.now().isoformat()
    cfg.set_param(p_name, '_GenKeyTime', gentime, force = True, offset = 2)
    ipaddr = cfg.peer[p_name]['AllowedIPs']
    cfg.save()
    print(f'Keys for client "{p_name}" updated! IP-Addr: "{ipaddr}"')

if opt.delete:
    p_name = opt.delete
    cfg = WGConfig(g_main_config_fn)
    print(f'Delete client "{p_name}"...')
    ipaddr = cfg.del_client(p_name)
    cfg.save()
    conf_path = os.path.join(g_main_config_path, f'{p_name}.conf')
    if os.path.exists(conf_path):
        os.remove(conf_path)
    qr_path = os.path.join(g_main_config_path, f'{p_name}.png')
    if os.path.exists(qr_path):
        os.remove(qr_path)
    print(f'Client "{p_name}" deleted! IP-Addr: "{ipaddr}"')

if opt.confgen:
    p_name = opt.confgen
    cfg = WGConfig(g_main_config_fn)
    if p_name not in cfg.peer:
        raise RuntimeError(f'ERROR: No client "{p_name}" found!')

    if not os.path.exists(opt.tmpcfg):
        raise RuntimeError(f'ERROR: file "{opt.tmpcfg}" not found!')

    srv = cfg.iface
    print(f'Generate client config for {p_name}...')

    with open(opt.tmpcfg, 'r') as file:
        tmpcfg = file.read()
    
    allowed_ips = opt.allowed if opt.allowed else g_defclient_allowed_ips
    allowed_ips = allowed_ips.replace('<CLIENT_DNS>', str(opt.dns))

    peer = cfg.peer[p_name]
    if 'Name' not in peer or 'PrivateKey' not in peer:
        RuntimeError(f'Invalid peer with pubkey "{peer["PublicKey"]}"')

    random.seed()
    jc = random.randint(3, 127)
    jmin = random.randint(3, 700)
    jmax = random.randint(jmin+1, 1270)
    conf = tmpcfg[:]
    conf = conf.replace('<CLIENT_PRIVATE_KEY>', peer['PrivateKey'])
    conf = conf.replace('<CLIENT_PUBLIC_KEY>', peer['PublicKey'])
    conf = conf.replace('<CLIENT_TUNNEL_IP>', peer['AllowedIPs'])
    conf = conf.replace('<CLIENT_DNS>', str(opt.dns))
    conf = conf.replace('<JC>', str(jc))
    conf = conf.replace('<JMIN>', str(jmin))
    conf = conf.replace('<JMAX>', str(jmax))
    conf = conf.replace('<S1>', srv['S1'])
    conf = conf.replace('<S2>', srv['S2'])
    conf = conf.replace('<H1>', srv['H1'])
    conf = conf.replace('<H2>', srv['H2'])
    conf = conf.replace('<H3>', srv['H3'])
    conf = conf.replace('<H4>', srv['H4'])
    conf = conf.replace('<CLIENT_ALLOWED_IPs>', allowed_ips)
    conf = conf.replace('<SERVER_PORT>', srv['ListenPort'])
    conf = conf.replace('<SERVER_PUBLIC_KEY>', srv['PublicKey'])
    conf_path = os.path.join(g_main_config_path, f'{p_name}.conf')
    if os.path.exists(conf_path):
        os.remove(conf_path)
    print(f"Writing config: {conf_path}")
    with open(conf_path, 'w', newline = '\n') as file:
        file.write(conf)

    print('Generate QR codes...')
    with open(conf_path, 'rb') as file:
        conf = file.read().decode('utf8')
    img = qrcode.make(conf)
    qr_path = os.path.join(g_main_config_path, f'{p_name}.png')
    if os.path.exists(qr_path):
        os.remove(qr_path)
    print(f"Saving qr: {qr_path}")
    img.save(qr_path)

print('===== OK =====')