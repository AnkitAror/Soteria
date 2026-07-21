export interface BankAccountSummary {
  id: string
  institution_name: string
  account_name: string
  account_type: string
  account_subtype: string | null
  current_balance: string | null
  available_balance: string | null
  currency: string
}

export interface AccountsResponse {
  accounts: BankAccountSummary[]
}

export interface SpendingSummaryResponse {
  month: string
  total_spend: string
  prior_month_total_spend: string
  percent_change: number | null
}

export interface CategorySpend {
  category: string
  total: string
}

export interface SpendingByCategoryResponse {
  month: string
  categories: CategorySpend[]
}

export interface TransactionAnalysisSummary {
  anomaly_score: string | null
  behavioral_score: string | null
  is_subscription: boolean
}

export interface TransactionListItem {
  id: string
  description: string
  merchant_name: string | null
  amount: string
  currency: string
  transaction_date: string
  pending: boolean
  category: string | null
  analysis: TransactionAnalysisSummary | null
}

export interface TransactionsResponse {
  items: TransactionListItem[]
  total: number
  limit: number
  offset: number
}

export interface InsightSummary {
  id: string
  type: string
  title: string
  description: string
  severity: string
  priority: number
  category: string | null
  confidence: string | null
  created_at: string
  viewed_at: string | null
  dismissed_at: string | null
}

export interface InsightsResponse {
  insights: InsightSummary[]
}

export interface SubscriptionSummary {
  id: string
  merchant_name: string
  category: string | null
  status: string
  billing_cycle: string
  average_cost: string
  monthly_cost: string
  currency: string
  last_charge: string | null
  next_expected_charge: string | null
  last_price_change_amount: string | null
}

export interface SubscriptionsResponse {
  subscriptions: SubscriptionSummary[]
  total_monthly_cost: string
}

export interface InstitutionSummary {
  id: string
  institution_name: string
  status: string
  error_code: string | null
  account_count: number
  last_synced_at: string | null
}

export interface InstitutionsResponse {
  institutions: InstitutionSummary[]
}

export interface ChatSessionSummary {
  id: string
  title: string | null
  updated_at: string
}

export interface ChatSessionsResponse {
  sessions: ChatSessionSummary[]
}

export interface Citation {
  type: string
  ref_id: string | null
  label: string
  detail: string
}

export interface ChatMessage {
  id: string
  role: string
  message: string
  sql_generated: string | null
  citations: Citation[]
  created_at: string
}

export interface ChatMessagesResponse {
  messages: ChatMessage[]
}

export interface ChatUsage {
  used: number
  limit: number
  remaining: number
}
