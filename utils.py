from subprocess import check_output


def get_mac_from_request(request):
    try:
        mac = get_mac_from_ip(get_ip_from_request(request))
        return mac
    except Exception, e:
        print e
        return None


def get_ip_from_request(request):
    return request.remote_addr


def get_mac_from_ip(ip):
    mac = get_mac_from_arp_cache(ip)
    if mac:
        return mac
    else:
        PING_COMMAND = 'ping -c 1 -W 1 ' + str(ip)
        check_output(PING_COMMAND.split(" "))
        return get_mac_from_arp_cache(ip)


def get_mac_from_arp_cache(ip):
    ARP_CACHE_COMMAND = 'arp -a -n'
    INCOMPLETE_ENTRY = '<incomplete>'
    arp_entries = check_output(ARP_CACHE_COMMAND.split(" ")).split("\n")
    for arp_entry in arp_entries:
        if ip in arp_entry:
            if INCOMPLETE_ENTRY in arp_entry:
                return None
            else:
                return arp_entry.split(" at ")[1].split(" ")[0]
