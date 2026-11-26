package cri.authz
import rego.v1

default allow := false

allow if {
  input.subject.type == "human"
  input.subject.authenticated == true
  input.action in {"task.create", "task.test", "approval.issue", "approval.decide", "agent.invoke", "memory.read", "memory.write", "audit.read", "system.stop", "system.restart", "api.access"}
}

allow if {
  input.subject.type == "agent"
  input.action in input.subject.scopes
  input.action in data.cri.roles.role_scopes[input.subject.role]
  input.action != "system.restart"
  input.action != "policy.write"
  input.action != "audit.delete"
  input.action != "security.modify"
}
