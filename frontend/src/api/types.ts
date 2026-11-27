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
  env: Record<string, unknown>
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

export interface LogLine {
  ts_ns: string
  line: string
  labels: Record<string, string>
}

export interface LogsResponse {
  lines: LogLine[]
  has_more: boolean
  oldest_ts_ns: string | null
  newest_ts_ns: string | null
  query: string
  monitored_since: string | null
}

export type NotificationType =
  | 'new_container'
  | 'host_disconnected'
  | 'host_reconnected'
  | 'fingerprint_changed'
  | 'alloy_reload_failed'
  | 'events_stream_failed'
  | 'analysis_skipped'
  | 'ai_error'
  | 'github_error'

export interface Notification {
  id: string
  type: NotificationType
  host_id: string | null
  container_id: string | null
  title: string
  payload: Record<string, unknown>
  status: 'new' | 'seen'
  created_at: string
  seen_at: string | null
}

export interface HostEvent {
  id: number
  type: string
  attributes: Record<string, unknown>
  occurred_at: string
}

export interface DockerEvent {
  id: number
  type: string
  exit_code: number | null
  attributes: Record<string, unknown>
  previous_image: string | null
  new_image: string | null
  occurred_at: string
}

export type LogLevel = 'error' | 'warn' | 'info' | 'debug' | 'unknown'

export interface Pattern {
  id: string
  template: string
  level: LogLevel
  count_total: number
  sample: string
  ignored: boolean
  first_seen_at: string
  last_seen_at: string
}

export interface AnalysisRun {
  id: number
  window_start: string
  window_end: string
  lines_count: number
  error_lines_count: number
  warn_lines_count: number
  new_patterns_count: number
  duration_ms: number
  truncated: boolean
  manual: boolean
  status: 'ok' | 'skipped' | 'failed'
  error: string | null
  created_at: string
}

export interface TriggerFired {
  id: string
  analysis_run_id: number | null
  container_id: string
  type: 'error' | 'docker_event' | 'anomaly' | 'manual'
  reason: Record<string, unknown>
  fired_at: string
  window_start: string
  window_end: string
  sample_lines: { ts_ns: string; line: string }[]
  note: string | null
  insight_id: string | null
  container_name?: string | null
  host_name?: string | null
}

export interface ExecutorRunning {
  container_id: string
  container_name: string
  host_name: string
  trigger: 'cycle' | 'manual'
  phase: string
  elapsed_ms: number
  detail: Record<string, unknown>
}

export interface SystemComponent {
  ok: boolean
  detail: string | null
}

export interface SystemLoop {
  kind: 'tunnels' | 'analysis' | 'log_tails'
  count: number
  detail: Record<string, unknown>[]
}

export interface SystemVolume {
  path: string
  total_bytes: number | null
  used_bytes: number | null
  free_bytes: number | null
}

export interface SystemInfo {
  version: string
  started_at: string
  uptime_seconds: number
  retention_days: number
  analysis_interval_seconds: number
  components: Record<string, SystemComponent>
  counts: Record<string, number>
  loops: SystemLoop[]
  volumes: SystemVolume[]
  proxy_rejected_total: number
}

export interface HostSummary {
  id: string
  name: string
  status: HostStatus
  monitored: number
  last_error: string | null
}

export interface ProjectActivity {
  id: string
  name: string
  host_name: string
  state: ContainerState
  lines_24h: number
  errors_24h: number
  triggers_24h: number
}

export interface PontoHora {
  hour: string
  lines: number
  errors: number
}

export interface Fatia {
  key: string
  count: number
}

export interface PontoDia {
  day: string
  cost_usd: string
  calls: number
}

export interface Summary {
  hosts_total: number
  hosts_connected: number
  projects_total: number
  projects_with_errors_1h: number
  notifications_new: number
  triggers_new_24h: number
  triggers_unanalyzed: number
  lines_24h: number
  errors_24h: number
  cycles_24h: number
  cycles_failed_24h: number
  ai_enabled: boolean
  hosts: HostSummary[]
  top_projects: ProjectActivity[]
  lines_by_hour: PontoHora[]
  triggers_by_type: Fatia[]
  insights_by_severity: Fatia[]
  cost_by_day: PontoDia[]
}

export interface AiSettings {
  /** interruptor geral ligado */
  enabled: boolean
  /** existe provedor pronto na cadeia: pode ser ligada */
  configured: boolean
  /** configured e enabled: a IA roda */
  active: boolean
  providers: number
  providers_ready: number
  max_input_tokens: number
  max_output_tokens: number
  concurrency: number
  language: string
}

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'

export interface InsightEvidence {
  kind: 'log_line' | 'docker_event' | 'pattern'
  index: number
  text: string
  at?: string
  ts_ns?: string
  count?: number
  level?: string
  new?: boolean
  type?: string
}

export interface Insight {
  id: string
  container_id: string
  container_name: string | null
  host_name: string | null
  trigger_id: string
  trigger_type: TriggerFired['type'] | null
  trigger_note: string | null
  severity: Severity
  title: string
  summary: string
  probable_cause: string
  suggested_action: string
  confidence: number
  needs_code: boolean
  evidence: InsightEvidence[]
  code_diagnosis: Record<string, unknown> | null
  context_truncated: boolean
  status: 'new' | 'seen'
  seen_at: string | null
  created_at: string
}

export interface AiCall {
  id: string
  provider_id: string | null
  provider: string
  provider_name: string
  attempt: number
  fell_back: boolean
  model: string
  purpose: 'analyze' | 'code_diagnosis' | 'issue_text' | 'test'
  prompt_version: string
  input_tokens: number
  output_tokens: number
  cost_usd: string
  cost_source: 'provider' | 'estimated' | 'unknown'
  latency_ms: number
  schema_retry: boolean
  status: 'ok' | 'error'
  error: string | null
  created_at: string
  container_name?: string | null
}

export interface InsightDetail extends Insight {
  sent_context: string
  window_start: string | null
  window_end: string | null
  calls: AiCall[]
}

export interface UsageBucket {
  key: string
  calls: number
  input_tokens: number
  output_tokens: number
  cost_usd: string
}

export interface Usage {
  today: UsageBucket
  last_7d: UsageBucket
  last_30d: UsageBucket
  total: UsageBucket
  by_day: UsageBucket[]
  by_project: UsageBucket[]
  by_trigger: UsageBucket[]
  by_purpose: UsageBucket[]
  by_provider: ProviderUsage[]
  by_model: UsageBucket[]
  failures: number
  schema_retries: number
  fallbacks: number
  avg_latency_ms: number
  paused_providers: Record<string, string>
}

export interface TestKeyResult {
  ok: boolean
  model: string | null
  latency_ms: number | null
  cost_usd: string | null
  input_tokens: number | null
  output_tokens: number | null
  error: string | null
}

/** Espelha `ProviderKind` do backend. Acrescentar um tipo lá exige acrescentar aqui. */
export type ProviderKind =
  | 'openrouter'
  | 'openai'
  | 'anthropic'
  | 'bedrock'
  | 'gemini'
  | 'groq'
  | 'mistral'
  | 'deepseek'
  | 'xai'
  | 'together'
  | 'fireworks'
  | 'cerebras'
  | 'perplexity'
  | 'ollama'
  | 'custom'

export interface CredentialField {
  key: string
  label: string
  secret: boolean
  required: boolean
  placeholder: string
  help: string
}

export interface ProviderKindInfo {
  kind: ProviderKind
  label: string
  has_catalog: boolean
  fields: CredentialField[]
}

export interface ProviderModel {
  id: string
  model_id: string
  label: string
  enabled: boolean
  context_length: number | null
  prompt_usd_per_mtok: string | null
  completion_usd_per_mtok: string | null
}

export interface Provider {
  id: string
  kind: ProviderKind
  label: string
  name: string
  enabled: boolean
  priority: number
  default_model: string | null
  credential_keys: string[]
  has_credentials: boolean
  last_status: 'unknown' | 'ok' | 'error'
  last_error: string | null
  last_checked_at: string | null
  paused_until: string | null
  ready: boolean
  models: ProviderModel[]
}

export interface CatalogModel {
  id: string
  name: string
  context_length: number | null
  prompt_usd_per_mtok: number | null
  completion_usd_per_mtok: number | null
  already_added: boolean
}

export interface ProviderTestResult {
  ok: boolean
  model: string | null
  latency_ms: number | null
  cost_usd: string | null
  input_tokens: number | null
  output_tokens: number | null
  error: string | null
}

export interface ProviderUsage {
  provider_id: string | null
  name: string
  kind: string
  calls: number
  errors: number
  fallbacks: number
  input_tokens: number
  output_tokens: number
  cost_usd: string
  avg_latency_ms: number
  p95_latency_ms: number
  success_rate: number
}

export type McpScopeName = 'leitura' | 'analise' | 'admin'

export interface McpScopeInfo {
  nome: McpScopeName
  rotulo: string
  descricao: string
  /** O que acontece se a chave vazar. É o que decide quais escopos marcar. */
  risco: string
}

export interface McpToolInfo {
  nome: string
  escopo: McpScopeName
  descricao: string
}

export interface McpInfo {
  enabled: boolean
  /** Existe chave que responde. Desligado e sem chave são motivos diferentes de não funcionar. */
  has_keys: boolean
  /** Declarado no config.yaml: a tela mostra, e não deixa editar. */
  managed: boolean
  url: string
  scopes: McpScopeInfo[]
  tools: McpToolInfo[]
}

export interface McpKey {
  id: string
  name: string
  prefix: string
  scopes: McpScopeName[]
  enabled: boolean
  expires_at: string | null
  last_used_at: string | null
  calls: number
  created_at: string
  /** Só vem na resposta da criação. Depois disso não existe mais em lugar legível. */
  secret: string | null
}

export interface McpCall {
  id: string
  key_name: string
  tool: string
  ok: boolean
  error: string | null
  duration_ms: number
  created_at: string
}
