export type AuditState = { valid: boolean; count: number };
export type ApiState = { connected: boolean; status?: string; audit?: AuditState; sandbox?: string; database?: string; database_audit?: {connected:boolean;valid:boolean;count:number;verified?:number}; redis?: string; opa?: string; remote_audit?: string; host_watchdog?: string; error?: string };
export type Agent = { name: string; role: string; implemented: boolean; status: string; capabilities: string[] };
export type AuditEvent = { event: string; actor: string; details: Record<string, unknown>; time: number; hash: string };
export type Proposal = { id: string; goal: string; code: string; status: string; test: { returncode?: number; stdout?: string; stderr?: string; error?: string } | null };
const base = import.meta.env.VITE_API_BASE ?? '';
let authToken = sessionStorage.getItem('cri_admin_token') ?? '';
export function setAuthToken(value: string) { authToken = value.trim(); if (authToken) sessionStorage.setItem('cri_admin_token', authToken); else sessionStorage.removeItem('cri_admin_token'); }
export function hasAuthToken() { return authToken.length > 0; }
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (authToken) headers.set('Authorization', `Bearer ${authToken}`);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${base}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}
export async function getStatus(): Promise<ApiState> {
  try { return { connected: true, ...await request<Omit<ApiState, 'connected'>>('/api/status') }; }
  catch (error) { return { connected: false, error: error instanceof Error ? error.message : 'Connection failed' }; }
}
export const getAgents = () => request<Agent[]>('/api/agents');
export const getLogs = () => request<AuditEvent[]>('/api/logs');
export const getMemory = () => request<Array<{kind:string;text:string}>>('/api/memory');
export const getTasks = () => request<Proposal[]>('/api/tasks');
export const runAgent = (role: string, goal: string) => request<{task_id:string;status:string;output:Record<string,unknown>}>(`/api/agents/${role}/run`, {method:'POST',body:JSON.stringify({goal})});
export const createTask = (goal: string) => request<Proposal>('/api/tasks', {method:'POST',body:JSON.stringify({goal})});
export const testTask = (id: string) => request<Proposal['test']>(`/api/tasks/${id}/test`, {method:'POST'});
export const issueApprovalToken = (id: string) => request<{token:string}>(`/api/approvals/token/${id}`, {method:'POST'});
export const decideApproval = (payload: {proposal_id:string;decision:'approve'|'reject';reason:string;token:string}) => request<Proposal>('/api/approvals',{method:'POST',body:JSON.stringify(payload)});
export const setKillSwitch = (active: boolean) => request<{status:string}>(active?'/api/kill':'/api/restart',{method:'POST'});
export const saveMemory = (kind:string,text:string) => request('/api/memory',{method:'POST',body:JSON.stringify({kind,text})});

/** Authenticated one-time WebSocket ticket; the admin bearer token is never put in a URL. */
export async function connectLive(onMessage: (value: unknown) => void, onState?: (state: string) => void): Promise<WebSocket> {
  const { ticket } = await request<{ticket:string;expires_in:number}>('/api/ws-ticket', {method:'POST'});
  const apiUrl = new URL(base || window.location.origin, window.location.origin);
  apiUrl.protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  apiUrl.pathname = `${apiUrl.pathname.replace(/\/$/, '')}/api/ws`;
  apiUrl.search = new URLSearchParams({ticket}).toString();
  const socket = new WebSocket(apiUrl.toString());
  socket.onopen = () => onState?.('connected');
  socket.onclose = () => onState?.('disconnected');
  socket.onerror = () => onState?.('error');
  socket.onmessage = event => {
    try { onMessage(JSON.parse(event.data)); } catch { onState?.('invalid_message'); }
  };
  return socket;
}

export type MonitoringState = { host: {cpu_percent:number|null;memory_percent:number|null;disk_percent:number}; dependencies: Record<string,boolean>; agents: Record<string,unknown>; alerts: string[] };
export const getMonitoring = () => request<MonitoringState>('/api/monitoring');
