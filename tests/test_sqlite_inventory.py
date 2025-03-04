# flake8: noqa: E501
import pytest
from sqlite import Group, Host, HostGroupAssociation, Variable  # type: ignore # noqa

from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader


@pytest.fixture(scope="session")
def loader():
    return DataLoader()


@pytest.fixture(scope="function")
def inventory(inventory_file, loader):
    inventory = InventoryManager(loader=loader, sources=[str(inventory_file)])
    return inventory


def test_host_crud(db_session):
    """Test CRUD operations for hosts."""
    host = Host(hostname="host1", ip="192.168.1.1")
    db_session.add(host)
    db_session.commit()

    retrieved_host = db_session.query(Host).filter_by(hostname="host1").first()
    assert retrieved_host is not None
    assert retrieved_host.ip == "192.168.1.1"

    retrieved_host.ip = "192.168.1.2"
    db_session.commit()
    updated_host = db_session.query(Host).filter_by(hostname="host1").first()
    assert updated_host.ip == "192.168.1.2"

    db_session.delete(updated_host)
    db_session.commit()
    deleted_host = db_session.query(Host).filter_by(hostname="host1").first()
    assert deleted_host is None


def test_group_crud(db_session):
    """Test CRUD operations for groups."""
    # Create
    group = Group(groupname="group1", max=10)
    db_session.add(group)
    db_session.commit()

    # Read
    retrieved_group = db_session.query(Group).filter_by(groupname="group1").first()
    assert retrieved_group is not None
    assert retrieved_group.max == 10

    # Update
    retrieved_group.max = 20
    db_session.commit()
    updated_group = db_session.query(Group).filter_by(groupname="group1").first()
    assert updated_group.max == 20

    # Delete
    db_session.delete(updated_group)
    db_session.commit()
    deleted_group = db_session.query(Group).filter_by(groupname="group1").first()
    assert deleted_group is None


def test_host_group_association(db_session):
    """Test host-group association."""
    # Create host and group
    host = Host(hostname="host1", ip="192.168.1.1")
    group = Group(groupname="group1")
    db_session.add_all([host, group])
    db_session.commit()

    # Associate host with group
    association = HostGroupAssociation(host_id=host.id, group_id=group.id)
    db_session.add(association)
    db_session.commit()

    # Verify association
    retrieved_association = (
        db_session.query(HostGroupAssociation)
        .filter_by(host_id=host.id, group_id=group.id)
        .first()
    )
    assert retrieved_association is not None

    # Delete association
    db_session.delete(retrieved_association)
    db_session.commit()
    deleted_association = (
        db_session.query(HostGroupAssociation)
        .filter_by(host_id=host.id, group_id=group.id)
        .first()
    )
    assert deleted_association is None


def test_variable_crud(db_session):
    """Test CRUD operations for variables."""
    # Create variable for a host
    Variable.set_variable(db_session, "host", "host1", "ansible_user", "admin")
    db_session.commit()

    # Read variable
    var_value = Variable.get_variable(db_session, "host", "host1", "ansible_user")
    assert var_value == "admin"

    # Update variable
    Variable.set_variable(db_session, "host", "host1", "ansible_user", "root")
    updated_var_value = Variable.get_variable(db_session, "host", "host1", "ansible_user")
    assert updated_var_value == "root"


def test_remove_variable(inventory_plugin, inventory_file, db_session, inventory, loader):
    host = Host(hostname="host1", ip="192.168.1.1")
    group = Group(groupname="group1")
    db_session.add_all([host, group])
    db_session.commit()
    Variable.set_variable(db_session, "host", "host1", "ansible_user", "root")

    inventory_plugin.parse(inventory, loader, str(inventory_file))

    inventory_plugin.remove_variable("host1", "ansible_user")

    assert "ansible_user" not in inventory_plugin.inventory.hosts["host1"].vars


def test_inventory_plugin_parse(inventory_plugin, inventory_file, db_session):
    """Test the inventory plugin's parse method."""
    host = Host(hostname="host1", ip="192.168.1.1")
    group = Group(groupname="group1")
    db_session.add_all([host, group])
    db_session.commit()

    association = HostGroupAssociation(host_id=host.id, group_id=group.id)
    db_session.add(association)
    db_session.commit()

    Variable.set_variable(db_session, "host", "host1", "ansible_user", "admin")
    db_session.commit()

    inventory_plugin.parse(None, None, str(inventory_file))

    assert "host1" in inventory_plugin.inventory.hosts
    assert "group1" in inventory_plugin.inventory.groups
    assert (
        inventory_plugin.inventory.get_host("host1").get_vars().get("ansible_user")
        == "admin"
    )
    assert "host1" in inventory_plugin.inventory.groups["group1"].host_names
