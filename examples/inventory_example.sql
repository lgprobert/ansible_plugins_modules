PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE hosts (
	id INTEGER NOT NULL, 
	hostname VARCHAR NOT NULL, 
	ip VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (hostname)
);
INSERT INTO hosts VALUES(1,'web1','192.168.1.10');
INSERT INTO hosts VALUES(2,'db1','192.168.1.20');
CREATE TABLE groups (
	id INTEGER NOT NULL, 
	groupname VARCHAR NOT NULL, 
	max INTEGER, 
	builtin BOOLEAN, 
	PRIMARY KEY (id), 
	UNIQUE (groupname)
);
INSERT INTO "groups" VALUES(1,'web_servers',-1,0);
INSERT INTO "groups" VALUES(2,'database_servers',-1,0);
CREATE TABLE variables (
	id INTEGER NOT NULL, 
	entity_type VARCHAR NOT NULL, 
	entity_name VARCHAR NOT NULL, 
	var_name VARCHAR NOT NULL, 
	var_value TEXT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_vars UNIQUE (entity_type, entity_name, var_name)
);
INSERT INTO variables VALUES(1,'host','web1','ansible_host','192.168.1.10');
INSERT INTO variables VALUES(2,'host','db1','ansible_host','192.168.1.20');
INSERT INTO variables VALUES(3,'group','web_servers','env','production');
CREATE TABLE host_group_association (
	host_id INTEGER NOT NULL, 
	group_id INTEGER NOT NULL, 
	PRIMARY KEY (host_id, group_id), 
	CONSTRAINT uq_host_group UNIQUE (host_id, group_id), 
	FOREIGN KEY(host_id) REFERENCES hosts (id) ON DELETE CASCADE, 
	FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE
);
INSERT INTO host_group_association VALUES(1,1);
INSERT INTO host_group_association VALUES(2,2);
CREATE TABLE group_hierarchy (
	parent_group_id INTEGER NOT NULL, 
	child_group_id INTEGER NOT NULL, 
	PRIMARY KEY (parent_group_id, child_group_id), 
	CONSTRAINT uq_group_hierarchy UNIQUE (parent_group_id, child_group_id), 
	FOREIGN KEY(parent_group_id) REFERENCES groups (id) ON DELETE CASCADE, 
	FOREIGN KEY(child_group_id) REFERENCES groups (id) ON DELETE CASCADE
);
INSERT INTO group_hierarchy VALUES(1,2);
CREATE TABLE mutual_exclusive_groups (
	group_id INTEGER NOT NULL, 
	exclusive_group_id INTEGER NOT NULL, 
	PRIMARY KEY (group_id, exclusive_group_id), 
	CONSTRAINT uq_mutual_exclusive UNIQUE (group_id, exclusive_group_id), 
	FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE, 
	FOREIGN KEY(exclusive_group_id) REFERENCES groups (id) ON DELETE CASCADE
);
INSERT INTO mutual_exclusive_groups VALUES(1,2);
COMMIT;
