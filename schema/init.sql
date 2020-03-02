CREATE TABLE identity (
	identity text not null primary key,
	settings jsonb not null default '{}'::jsonb
);
ALTER TABLE identity OWNER to postgres;
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE identity TO chorizo;

CREATE TABLE task_group ();
CREATE TABLE task ();
CREATE TABLE task_group_member (
	-- this is where we should track if the user has accepted the invite to a group
);
CREATE TABLE task_instance (
	task
	sequence_id -- this is the occurence number for this task.  should use to ensure we don't delay occurence 1 until after occurence 2
	occurence_time
	state
);
