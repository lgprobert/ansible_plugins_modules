# flake8: noqa: E501
import json
from pathlib import Path

import networkx as nx
import yaml
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.exc import IntegrityError, OperationalError

from ansible.inventory.group import Group as AnsibleGroup
from ansible.inventory.host import Host as AnsibleHost
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.inventory import BaseInventoryPlugin


class Base(DeclarativeBase):
    pass


class Host(Base):
    __tablename__ = "hosts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String, unique=True, nullable=False)
    ip = Column(String, nullable=True)


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    groupname = Column(String, unique=True, nullable=False)
    max = Column(Integer, default=-1)
    builtin = Column(Boolean, default=False)


class HostGroupAssociation(Base):
    __tablename__ = "host_group_association"

    host_id = Column(
        Integer, ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True
    )
    group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (UniqueConstraint("host_id", "group_id", name="uq_host_group"),)


class GroupHierarchy(Base):
    __tablename__ = "group_hierarchy"

    parent_group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    child_group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        UniqueConstraint("parent_group_id", "child_group_id", name="uq_group_hierarchy"),
    )


class MutualExclusiveGroups(Base):
    __tablename__ = "mutual_exclusive_groups"

    group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    exclusive_group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        UniqueConstraint("group_id", "exclusive_group_id", name="uq_mutual_exclusive"),
    )


# Variables Table (Host & Group Vars)
class Variable(Base):
    __tablename__ = "variables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String, nullable=False)  # 'host' or 'group'
    entity_name = Column(String, nullable=False)
    var_name = Column(String, nullable=False)
    var_value = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_name", "var_name", name="uq_vars"),
    )

    def __repr__(self):
        return f"<Variable(host={self.host}, var_name={self.var_name}, var_value={self.var_value})>"

    @staticmethod
    def serialize_value(var_value):
        """Handles serialization of complex data types."""
        if isinstance(var_value, (list, dict)):
            return json.dumps(var_value)  # Serialize lists/dicts to JSON
        return str(var_value)  # Store other types as plain string

    @staticmethod
    def deserialize_value(var_value):
        """Handles deserialization of JSON or plain values."""
        try:
            return json.loads(var_value)  # Try to deserialize JSON (list/dict)
        except json.JSONDecodeError:
            return var_value  # If not JSON, return the plain value (string, int, float, etc.)

    @classmethod
    def set_variable(cls, session, entity_type, entity_name, var_name, var_value):
        """Persist the variable to the database."""
        var_value = cls.serialize_value(var_value)
        _stmt = (
            insert(Variable)
            .values(
                entity_type=entity_type,
                entity_name=entity_name,
                var_name=var_name,
                var_value=var_value,
            )
            .on_conflict_do_update(
                index_elements=[
                    "entity_type",
                    "entity_name",
                    "var_name",
                ],
                set_={"var_value": var_value},
            )
        )
        session.execute(_stmt)
        print("set %s for %s" % (var_name, entity_name))
        session.commit()

    @classmethod
    def get_variable(cls, session, entity_type, entity_name, var_name):
        """Retrieve the variable and deserialize it."""
        var = (
            session.query(Variable)
            .filter_by(
                entity_type=entity_type, entity_name=entity_name, var_name=var_name
            )
            .first()
        )
        if var:
            return cls.deserialize_value(var.var_value)
        return None


def initialize_database(db_path):
    """Creates tables if the database does not exist."""
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


DOCUMENTATION = """
    name: sqlite
    plugin_type: inventory
    author:
      - Robert Li (lgprobet@gmail.com)
    short_description: Ansible dynamic inventory plugin from SQLite database.
    description: Loads inventory from an SQLite database.
    version_added: "1.0"
    inventory: sqlite
    options:
        plugin:
            description: Token that ensures this is a source file for 'sqlite' plugin.
            required: True
            choices: ['sqlite']
        db_path:
            description:
                - Path to sqlite db file.
                - db_path can be absolute path, or relative to YAML format inventory file.
            required: True
            type: string
    requirements:
        - sqlite >= 3.7
"""
EXAMPLES = r"""
---
plugin: sqlite
db_path: hosts.db
"""


class InventoryModule(BaseInventoryPlugin):

    NAME = "sqlite"

    def __init__(self) -> None:
        super(InventoryModule, self).__init__()
        self._graph = nx.DiGraph()
        self.inventory: InventoryManager

    def __exit__(self, exc_type, exc_value, trace):
        if self.session:
            self.session.close()

    def verify_file(self, path):
        """Verify if inventory file is for current inventory plugin."""
        if not Path(path).exists():
            return False
        if not path.endswith((".yaml", ".yml")):
            return False
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            return data.get("plugin") == self.NAME
        except Exception:
            return False

    def parse(self, inventory, loader, path, cache=True) -> None:
        super(InventoryModule, self).parse(inventory, loader, path)
        try:
            if not loader:
                self.loader = DataLoader()
            else:
                self.loader = loader
            if inventory:
                self.inventory = inventory
            else:
                self.inventory = InventoryManager(loader=self.loader, sources=[path])

            # self._read_config_data(path)
            with open(path, "r") as f:
                config_data = yaml.safe_load(f)
            self._options = config_data

            db_file_in = self.get_option("db_path")
            if Path(db_file_in).is_absolute():
                db_file = db_file_in
            else:
                inventory_dir = Path(path).absolute().parent
                db_file = inventory_dir.joinpath(db_file_in)

            engine = initialize_database(db_file)
            Session = sessionmaker(bind=engine)
            self.session = Session()

            _host_obj: AnsibleHost
            _group_obj: AnsibleGroup
            for host in self.session.query(Host).all():
                self.inventory.add_host(host=host.hostname)
                # Automatically set ansible_host
                _host_obj = self.inventory.hosts[host.hostname]
                _host_obj.set_variable("ansible_host", host.ip)
                _host_obj.set_variable("host_id", host.id)

            for group in self.session.query(Group).all():
                self.inventory.add_group(group=group.groupname)
                _group_obj = self.inventory.groups[group.groupname]
                _group_obj.set_variable("group_id", group.id)

            for association in self.session.query(HostGroupAssociation).all():
                host = self.session.get(Host, association.host_id)  # type: ignore
                host_obj = self.inventory.hosts[host.hostname]
                group = self.session.get(Group, association.group_id)  # type: ignore
                _group_obj = self.inventory.groups[group.groupname]
                host_obj.add_group(_group_obj)
                _group_obj.add_host(host_obj)

            self._load_group_hierarchy()

            # Load mutual exclusive groups
            mutual_exclusive: dict = {}
            for relation in self.session.query(MutualExclusiveGroups).all():
                g1 = self.session.query(Group).get(relation.group_id)
                g2 = self.session.query(Group).get(relation.exclusive_group_id)
                mutual_exclusive.setdefault(g1.groupname, []).append(g2.groupname)  # type: ignore

            # Load host and group variables
            for var in self.session.query(Variable).all():
                if var.entity_type == "host":
                    host_obj = self.inventory.hosts[var.entity_name]
                    var_value = Variable.get_variable(
                        self.session, "host", var.entity_name, var.var_name
                    )
                    host_obj.set_variable(var.var_name, var_value)
                elif var.entity_type == "group":
                    group_obj = self.inventory.groups[var.entity_name]
                    var_value = Variable.get_variable(
                        self.session, "group", var.entity_name, var.var_name
                    )
                    group_obj.set_variable(var.var_name, var_value)
        except IntegrityError as e:
            self.display.error(f"constraint failure, exception: {e}.")
            self.session.rollback()

    def _load_group_hierarchy(self) -> None:
        """Load existing group hierarchy from the database into a directed graph."""
        rows = self.session.query(GroupHierarchy).all()

        _parent_group: AnsibleGroup
        _child_group: AnsibleGroup
        for row in rows:
            self._graph.add_edge(row.parent_group_id, row.child_group_id)
            parent = self.session.query(Group).get(row.parent_group_id)
            child = self.session.query(Group).get(row.child_group_id)
            _parent_group = self.inventory.groups[parent.groupname]  # type: ignore
            _child_group = self.inventory.groups[child.groupname]  # type: ignore
            _parent_group.add_child_group(_child_group)

    def _add_group_relation(self, parent_group_id, child_group_id) -> bool:
        """Attempt to add a new parent-child relationship while avoiding cycles."""
        add_succeed = False
        try:
            self._graph.add_edge(parent_group_id, child_group_id)
            if nx.is_directed_acyclic_graph(self._graph):
                # Insert into the database if valid
                new_relation = GroupHierarchy(
                    parent_group_id=parent_group_id, child_group_id=child_group_id
                )
                self.session.add(new_relation)
                self.session.commit()
                print(
                    f"Added parent-child relationship: {parent_group_id} -> {child_group_id}"
                )
                add_succeed = True
            else:
                self.display.error(
                    f"Error: Adding {parent_group_id} -> {child_group_id} creates a cycle!"
                )
                self._graph.remove_edge(parent_group_id, child_group_id)
                self.session.rollback()
        except IntegrityError as e:
            self.display.error(f"constraint failure, exception: {e}.")
            self.session.rollback()
        return add_succeed

    def add_to_group(
        self, target_groupname: str, entity_name: str, element_type: str = "host"
    ) -> None:
        """Add a host or group to a target group.

        Args:
            target_groupname (str): Name of the target group.
            entity_name (str): Name of the host or group to be added.
            element_type (str, optional): Type of entity to be added ('host' or 'group'). Defaults to 'host'.
        """
        if target_groupname not in self.inventory.groups:
            self.display.error(f"Target group {target_groupname} not exists.")
            raise ValueError(f"Target group {target_groupname} not exists.")
        elif element_type == "host" and entity_name not in self.inventory.hosts:
            self.display.error(f"Host {entity_name} not found.")
            raise ValueError(f"Host {entity_name} not found.")
        elif element_type == "group" and entity_name not in self.inventory.groups:
            self.display.error(f"Group {entity_name} not found.")
            raise ValueError(f"Group {entity_name} not found.")

        try:
            target_group: AnsibleGroup = self.inventory.groups[target_groupname]
            target_group_id = target_group.vars.get("group_id")
            if element_type == "host":
                _host_obj: AnsibleHost = self.inventory.hosts[entity_name]
                if _host_obj not in target_group.hosts:
                    stmt = insert(HostGroupAssociation).values(
                        host_id=_host_obj.vars.get("host_id"), group_id=target_group_id
                    )
                    self.session.execute(stmt)
                    _host_obj.add_group(target_group)
                    target_group.add_host(_host_obj)
                    self.session.commit()
            else:
                _group_obj: AnsibleGroup = self.inventory.groups[entity_name]
                if _group_obj not in target_group.child_groups:
                    _group_obj_id = _group_obj.vars.get("group_id")
                    if self._add_group_relation(target_group_id, _group_obj_id):
                        target_group.add_child_group(_group_obj)
                    else:
                        self.display.error(
                            f"Error adding {entity_name} to group {target_groupname}. Cycle detected."
                        )
                        return
            self.display.display(f"Added {entity_name} to group {target_groupname}.")
        except (OperationalError, IntegrityError) as e:
            self.session.rollback()
            self.display.error(
                f"An error occurred while adding {entity_name} to group: {e}"
            )
