/* Agent and DAG state types */

export type NodeState = 'pending' | 'ready' | 'running' | 'completed' | 'failed' | 'degraded';

export type AgentType =
  | 'Orchestrator'
  | 'Collector'
  | 'Analyst'
  | 'ReportGenerator'
  | 'QA';

/* DAG types */

export interface DAGNode {
  node_id: string;
  agent_type: AgentType;
  depends_on: string[];
  state: NodeState;
  priority?: number;
  retries?: number;
  context?: Record<string, unknown>;
}

export interface TaskResponse {
  task_id: string;
  status: string;
  dag_nodes: DAGNode[];
  ws_endpoint: string;
}

/* Schema / task creation types */

export interface AnalysisDimension {
  name: string;
  description: string;
  focus_points: string[];
  node_types: string[];
  agent_type: string;
  prompt_override?: string;
  weight: number;
}

export interface SourcePreferences {
  priority_sources: string[];
  excluded_sources: string[];
  min_credibility: number;
  collection_depth: string;
}

export interface CreateTaskRequest {
  targets: string[];
  industry: string;
  dimensions: AnalysisDimension[];
  exclude_dimensions: string[];
  focus_points: Record<string, string[]>;
  dimension_weights: Record<string, number>;
  source_preferences: SourcePreferences;
  benchmark_product: string | null;
  report_audience: string;
  report_sections: string[];
  output_formats: string[];
  execution_mode: string;
  collection_depth?: string;
  model_preference?: string;
}

/* Report types */

export interface ReportSection {
  node_id?: string;
  section: string;
  content: string;
  order: number;
}

export interface ReportResponse {
  task_id: string;
  format: string;
  content?: string;
  sections: ReportSection[];
}

/* Trace types */

export interface TraceNodeEntry {
  node: Record<string, unknown>;
  incoming: unknown[];
  outgoing: unknown[];
  depth: number;
}

export interface StepTrace {
  step: number;
  phase: 'Observe' | 'Think' | 'Act' | 'Finalize';
  reasoning?: string;
  confidence?: number;
  action?: string;
  action_params?: Record<string, unknown>;
  action_result_summary?: string;
  observation_summary?: string;
  nodes_read?: string[];
  nodes_created?: string[];
  edges_created?: string[];
  prompt_snapshot?: string;
  response_snapshot?: string;
  tokens?: number;
  cost?: number;
}

export interface TraceResponse {
  insight: string;
  task_id: string;
  confidence: number | null;
  chain: TraceNodeEntry[];
  contradicting_evidence: unknown[];
  confidence_breakdown: {
    supporting_count: number;
    contradicting_count: number;
    total_sources: number;
  } | null;
  step_traces?: Record<string, StepTrace[]>;
}

/* WebSocket event types */

export type WSEventType =
  | 'node_state_change'
  | 'node_completed'
  | 'node_failed'
  | 'agent_log'
  | 'cost_update'
  | 'qa_reject'
  | 'dag_state'
  | 'dag_created'
  | 'dag_failed';

export interface WSBaseEvent {
  event: WSEventType;
  task_id: string;
}

export interface WSNodeStateChange extends WSBaseEvent {
  event: 'node_state_change';
  node_id: string;
  agent_type: AgentType;
  state: NodeState;
  depends_on: string[];
}

export interface WSNodeCompleted extends WSBaseEvent {
  event: 'node_completed';
  node_id: string;
  agent_type: AgentType;
  state: 'completed';
  depends_on: string[];
}

export interface WSNodeFailed extends WSBaseEvent {
  event: 'node_failed';
  node_id: string;
  agent_type: AgentType;
}

export interface WSAgentLog extends WSBaseEvent {
  event: 'agent_log';
  node_id: string;
  agent_type: AgentType;
  step: number;
  phase: 'Observe' | 'Think' | 'Act' | 'Finalize';
  summary: string;
}

export interface WSCostUpdate extends WSBaseEvent {
  event: 'cost_update';
  delta_cost: number;
  total_cost: number;
}

export interface WSQAReject extends WSBaseEvent {
  event: 'qa_reject';
  qa_agent_type: string;
  failed_nodes: string[];
  reasons: string[];
  affected_nodes: string[];
  qa_round: number;
}

export interface WSDagState extends WSBaseEvent {
  event: 'dag_state';
  nodes: Array<{ node_id: string; agent_type: AgentType; state: NodeState; depends_on: string[]; retries: number; error: string }>;
  total_cost: number;
}

export interface WSDagCreated extends WSBaseEvent {
  event: 'dag_created';
  nodes: Array<{
    node_id: string;
    agent_type: AgentType;
    state: NodeState;
    depends_on: string[];
  }>;
  total_cost: number;
  total_tokens: number;
  pages_collected: number;
}

export interface WSDagFailed extends WSBaseEvent {
  event: 'dag_failed';
  error: string;
}

export type WSEvent =
  | WSNodeStateChange
  | WSNodeCompleted
  | WSNodeFailed
  | WSAgentLog
  | WSCostUpdate
  | WSQAReject
  | WSDagState
  | WSDagCreated
  | WSDagFailed;

/* History types */

export interface HistoryTask {
  id: string;
  time: string;
  targets: string;
  targetsArr?: string[];
  status: 'completed' | 'running' | 'failed' | 'planning';
  duration: string;
}

/* Agent card / grouping types */

export interface AgentState {
  node_id: string;
  agent_type: AgentType;
  state: NodeState;
  progress?: number;
  duration?: string;
  outputSummary?: string;
  details?: string;
  cost?: number;
}

export interface AgentGroup {
  role: string;
  agentTypes: AgentType[];
  variant: 'single' | 'collection' | 'analysis' | 'qa' | 'swot';
  description: string;
}

/* Status badge display info */

export interface StatusInfo {
  label: string;
  color: string;
  dotColor: string;
}

/* ── Analytics / Chart types ── */

export interface AnalyticsResponse {
  task_id: string;
  products: string[];
  scoring: ScoringDatum[];
  features: FeatureAnalytics;
  sentiment: SentimentAnalytics;
  pricing: PricingAnalytics;
  swot: SWOTDatum[];
  tech_stack: TechStackAnalytics;
  data_source?: 'structured' | 'report_fallback' | 'empty';
  warnings?: string[];
}

export interface ScoringDatum {
  product: string;
  dimension: string;
  score: number;
  weight: number;
}

export interface FeatureAnalytics {
  products: string[];
  features: FeatureDatum[];
}

export interface FeatureDatum {
  feature_name: string;
  category: string;
  [productAttr: string]: string;  // e.g. "ProductA_maturity": "ga"
}

export interface SentimentAnalytics {
  products: string[];
  topics: SentimentTopicDatum[];
}

export interface SentimentTopicDatum {
  topic: string;
  [productAttr: string]: number | string;
}

export interface PricingAnalytics {
  plans: PricingPlanDatum[];
  value_scores: ValueScoreDatum[];
}

export interface PricingPlanDatum {
  plan_name: string;
  product: string;
  price: number;
  billing_cycle: string;
}

export interface ValueScoreDatum {
  product: string;
  value_score: number;
  strategy: string;
  target_segment: string;
}

export interface SWOTDatum {
  product: string;
  strengths_count: number;
  weaknesses_count: number;
  opportunities_count: number;
  threats_count: number;
}

export interface TechStackAnalytics {
  languages: TechItem[];
  frameworks: TechItem[];
  infra: TechItem[];
}

export interface TechItem {
  name: string;
  [product: string]: boolean | string;
}
