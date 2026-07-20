import type { InsightSummary } from './types'

const TYPE_SECTION_OVERRIDES: Record<string, string> = {
  low_balance_forecast: 'Balance',
  spending_exceeds_income: 'Balance',
  savings_trend: 'Balance',
  merchant_concentration: 'Spending',
  spending_above_normal: 'Spending',
  new_subscription_detected: 'Subscriptions',
  subscription_price_increase: 'Subscriptions',
  duplicate_subscriptions: 'Subscriptions',
}

const SECTION_ORDER = [
  'Balance',
  'Spending',
  'Subscriptions',
  'Food',
  'Shopping',
  'Travel',
  'Entertainment',
  'Utilities',
  'Other',
]

export function sectionFor(insight: InsightSummary): string {
  return TYPE_SECTION_OVERRIDES[insight.type] ?? insight.category ?? 'Other'
}

export function groupInsightsBySection(
  insights: InsightSummary[],
): [string, InsightSummary[]][] {
  const groups = new Map<string, InsightSummary[]>()
  for (const insight of insights) {
    const section = sectionFor(insight)
    groups.set(section, [...(groups.get(section) ?? []), insight])
  }
  return SECTION_ORDER.filter((section) => groups.has(section)).map((section) => [
    section,
    groups.get(section)!,
  ])
}
