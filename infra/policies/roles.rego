package cri.authz

import rego.v1

default allow := false

allow if {
  input.identity.role == "master"
  input.action in {"plan", "propose"}
}
allow if {
  input.identity.role == "developer"
  input.action in {"propose", "sandbox"}
}
allow if {
  input.identity.role == "research"
  input.action == "memory_read"
}
allow if {
  input.identity.role == "testing"
  input.action == "sandbox"
}
allow if {
  input.identity.role == "auditor"
  input.action == "audit_read"
}
allow if {
  input.identity.role == "memory"
  input.action in {"memory_read", "memory_write"}
}
