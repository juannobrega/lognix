export interface User {
  id: string
  email: string
  name: string
  created_at: string
}

export interface TokenOut {
  access_token: string
  token_type: 'bearer'
  expires_at: string
  user: User
}

export interface Health {
  status: 'ok' | 'degraded'
  version: string
  components: Record<string, { ok: boolean; detail?: string | null }>
}

export type SshAuthMethod = 'key' | 'key_passphrase' | 'password'
export type HostStatus = 'pending' | 'connected' | 'disconnected' | 'error' | 'removed'

export interface TunnelState {
  socket_path: string | null
  connected_since: string | null
  last_check_at: string | null
  reconnect_attempts: number
  last_error: string | null
}

export interface Host {
  id: string
  name: string
  address: string
  ssh_port: number
  ssh_user: string
  ssh_auth_method: SshAuthMethod
  ssh_host_key_fingerprint: string | null
  runtime: string
  docker_version: string | null
  status: HostStatus
  last_error: string | null
  created_at: string
  tunnel: TunnelState | null
}

export interface ValidationStep {
  number: number
  name: string
  status: 'pending' | 'running' | 'ok' | 'failed'
  message?: string | null
  action?: string | null
  detail?: string | null
}

export interface ContainerSummary {
  docker_id: string
  name: string
  image: string
  state: string
  status: string
  compose_project: string | null
  compose_service: string | null
  labels: Record<string, string>
}

export interface Validation {
  id: string
  host_id: string
  status: 'running' | 'ok' | 'failed'
  steps: ValidationStep[]
  containers: ContainerSummary[] | null
  started_at: string
  finished_at: string | null
}

export interface HostCreated {
  host: Host
  validation_id: string
}

export type ContainerState = 'created' | 'running' | 'restarting' | 'paused' | 'exited' | 'dead' | 'removed'

export interface Container {
  id: string
  host_id: string
  docker_id: string
  name: string
  image: string
  image_digest: string | null
  compose_project: string | null
  compose_service: string | null
  labels: Record<string, string>
  state: ContainerState
  monitored: boolean
  monitored_since: string | null
  first_seen_at: string
  last_seen_at: string
  kind: 'image' | 'github'
}

export interface Project extends Container {
  host_name: string
  host_status: HostStatus
}

export interface AlloyApply {
  version_id: number | null
  reload_ok: boolean
  error: string | null
  hosts_in_config: number
  containers_in_config: number
}

export interface MonitoredResult {
  containers: Container[]
  alloy: AlloyApply
}

export interface AlloyConfigVersion {
  id: number
  hash: string
  reason: string
  applied_at: string
  reload_ok: boolean
  error: string | null
}

export interface AlloyConfig {
  current: string
  path: string
  versions: AlloyConfigVersion[]
}
