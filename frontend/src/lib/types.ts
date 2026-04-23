export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type MatchOut = {
  id: string;
  workspace_id: string;
  sell_offer_id: string;
  buy_request_id: string;
  watch_entity_id: string | null;
  match_type: string;
  match_confidence: number;
  seller_price: string | null;
  buyer_price: string | null;
  seller_currency: string | null;
  buyer_currency: string | null;
  fx_rate: string | null;
  shipping_cost: string | null;
  fee_cost: string | null;
  risk_buffer: string | null;
  expected_profit: string | null;
  status: string;
  reasoning_json: Record<string, unknown>;
  created_at: string;
};

export type AlertOut = {
  id: string;
  workspace_id: string;
  match_id: string | null;
  raw_message_id: string | null;
  alert_type: string;
  channel: string;
  payload_json: Record<string, unknown>;
  status: string;
  sent_at: string | null;
  snoozed_until: string | null;
  created_at: string;
};

export type RawMessageOut = {
  id: string;
  workspace_id: string;
  group_id: string;
  external_message_id: string | null;
  sender_name: string | null;
  text_body: string;
  original_timestamp: string;
  ingested_at: string;
  processing_status: string;
  processing_error: string | null;
  retry_count: number;
};
