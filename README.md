# Ansible Custom Plugins and Modules

This repository contains custom Ansible plugins and modules.

**Current published plugins and modules:**

- SQLite based custom inventory plugin
- hostip custom module

---

## SQLite based Inventory Plugin

SQLite Inventory Plugin is an Ansible inventory respoitory plugin by storing all inventory data in sqlite database that inclues:

- host
- group
- host-group memberships
- group hierarchy relationship
- host variables
- group variables

The plugin provides a public method `add_to_group()` that allow users add hosts and groups to a group. For groups being added to a group, this method ensures **cycle** group relationship will not happen.

While Ansible group hierarchy relationship is very flexible and powerful, it can easily causes **dead loop** problem if group membership is not managed carefully. This plugin use DAG algorithm behind the scene to avoid **cycle** group relationship is never happened.

### Getting started

The `examples` directory contains sample data and a shell script to setup the plugin. Below is the command to setup sample inventory database and test it with `ansible-inventory`:

```sh
cd example

./setup_example.sh

cd ..

$ ansible-inventory -i ansible_inventory.yaml --list
{
    "_meta": {
        "hostvars": {
            "db1": {
                "ansible_host": "192.168.1.20",
                "env": "production",
                "group_id": 2,
                "host_id": 2
            },
            "web1": {
                "ansible_host": "192.168.1.10",
                "env": "production",
                "group_id": 1,
                "host_id": 1
            }
        }
    },
    "all": {
        "children": [
            "ungrouped",
            "web_servers"
        ]
    },
    "database_servers": {
        "hosts": [
            "db1"
        ]
    },
    "web_servers": {
        "children": [
            "database_servers"
        ],
        "hosts": [
            "web1"
        ]
    }
}
```

---

## hostip custom module

This module does a very basic work: resolve a host name to IP address and explicitly set `ansible_host` host variable of the host to the resolved IP address.

While this is an obvious fundamental function of Ansible provides to us, but it is not always for Ansible to make that happens. For instance, when using docker driver in Molecule test, `anslbe_host` host_var is simply resolved to container's hostname (or container name). If the playbook or collection under test requires `ansible_host` to be an IP address like me in past project, there is no easy way to achieve this.

Using `hostip` custom module is straightforward, it is often add the related tasks like below to the beginning of your playbook:

```yaml
- name: Get container details
    hostip:
    ansible_host: "{{ inventory_hostname }}"
    register: result

- name: Set ansible_host to container IP
    ansible.builtin.set_fact:
    ansible_host: "{{ result.hostip }}"
```

To get more details of the module, read the sources of `verify.yml` in `molecule`.
