package cri.roles
import rego.v1

role_scopes := {
  "master": {"plan", "propose"},
  "developer": {"propose", "sandbox"},
  "research": {"memory_read"},
  "testing": {"sandbox"},
  "auditor": {"audit_read"},
  "memory": {"memory_read", "memory_write"},
}
