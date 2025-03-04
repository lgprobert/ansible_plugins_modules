#!/usr/bin/python

import socket

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = """
---
module: hostip
short_description: resolve host IP address
description:
    Resolve and return host IP address from ansible_host or
    ansible_default_ipv4.address
options:
    ansible_host:
        description: ansible_host or '' if it is undefined
        required: true
        type: str
        type: str
author:
    - Robert Li (robert.li@boraydata.com)
"""

EXAMPLES = """
- name: Test hostip
  boray.transformer.hostip:
    ansible_host: ''
"""

RETURN = """
hostip:
    description: host resolved primary IP address
    type: str
    returned: always
"""


def get_primary_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ip_address = sock.getsockname()[0]
    except Exception:
        ip_address = "127.0.0.1"
    finally:
        sock.close()
    print("primary ip:", ip_address)
    return ip_address


def run_module():
    module_args = dict(ansible_host=dict(type="str", required=True))

    result = dict(changed=False, hostip="")

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    ansible_host = module.params.get("ansible_host")
    try:
        if ansible_host:
            result["hostip"] = socket.gethostbyname(ansible_host)
        else:
            primary_ip = get_primary_ip()
            if not primary_ip:
                msg_ = "Fails to look for default IPv4 address."
                module.fail_json(msg=msg_)
            else:
                result["hostip"] = primary_ip
    except socket.gaierror as e:
        module.fail_json(msg="Failed to resolve hostname: {}".format(e))

    result["debug"] = "primary_ip: {}".format(result["hostip"])
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
