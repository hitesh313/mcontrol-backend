-- ============================================================================
-- Money Control Application - Database Schema (Supabase / PostgreSQL)
-- Run this in the Supabase SQL editor, or via `supabase db push`.
-- ============================================================================

create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;

-- ----------------------------------------------------------------------------
-- ENUM TYPES
-- ----------------------------------------------------------------------------
create type loan_status as enum ('ACTIVE', 'PARTIALLY_PAID', 'OVERDUE', 'CLOSED');
create type interest_type as enum ('FIXED_DAILY', 'FIXED_MONTHLY', 'PERCENT_DAILY', 'PERCENT_MONTHLY');
create type flow_role as enum ('SUPPLIER', 'CUSTOMER'); -- role of the counterparty relative to the owning user
create type transaction_type as enum ('BORROW', 'LEND', 'TRANSFER', 'PAYMENT_RECEIVED', 'PAYMENT_MADE', 'INTEREST_APPLIED');
create type notification_type as enum (
  'DUE_3_DAYS', 'DUE_1_DAY', 'DUE_TODAY', 'OVERDUE', 'INTEREST_APPLIED', 'PAYMENT_RECEIVED'
);

-- ----------------------------------------------------------------------------
-- USERS  (app-level profile; Supabase Auth handles credential storage,
-- this table holds the domain profile + local password hash if not using
-- Supabase Auth directly)
-- ----------------------------------------------------------------------------
create table users (
    id                  uuid primary key default uuid_generate_v4(),
    first_name          varchar(100) not null,
    last_name           varchar(100) not null,
    mobile_number       varchar(20)  not null unique,
    email               varchar(255) not null unique,
    password_hash       varchar(255) not null,
    is_active           boolean not null default true,
    is_verified         boolean not null default false,
    fcm_token           text,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);
create index idx_users_mobile on users(mobile_number);
create index idx_users_email on users(email);

-- Refresh tokens (rotation support)
create table refresh_tokens (
    id              uuid primary key default uuid_generate_v4(),
    user_id         uuid not null references users(id) on delete cascade,
    token_hash      varchar(255) not null unique,
    is_revoked      boolean not null default false,
    replaced_by     uuid references refresh_tokens(id),
    expires_at      timestamptz not null,
    created_at      timestamptz not null default now()
);
create index idx_refresh_tokens_user on refresh_tokens(user_id);

-- OTPs for forgot-password flow
create table password_reset_otps (
    id              uuid primary key default uuid_generate_v4(),
    user_id         uuid not null references users(id) on delete cascade,
    otp_hash        varchar(255) not null,
    is_used         boolean not null default false,
    attempts        smallint not null default 0,
    expires_at      timestamptz not null,
    created_at      timestamptz not null default now()
);
create index idx_password_reset_user on password_reset_otps(user_id);

-- ----------------------------------------------------------------------------
-- SUPPLIERS  (people the user borrows from)
-- ----------------------------------------------------------------------------
create table suppliers (
    id              uuid primary key default uuid_generate_v4(),
    user_id         uuid not null references users(id) on delete cascade,
    name            varchar(150) not null,
    mobile_number   varchar(20),
    email           varchar(255),
    address         text,
    notes           text,
    is_active       boolean not null default true,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
create index idx_suppliers_user on suppliers(user_id);

-- ----------------------------------------------------------------------------
-- CUSTOMERS  (people the user lends to)
-- ----------------------------------------------------------------------------
create table customers (
    id              uuid primary key default uuid_generate_v4(),
    user_id         uuid not null references users(id) on delete cascade,
    name            varchar(150) not null,
    mobile_number   varchar(20),
    email           varchar(255),
    address         text,
    notes           text,
    is_active       boolean not null default true,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
create index idx_customers_user on customers(user_id);

-- ----------------------------------------------------------------------------
-- LOANS  (a single lend/borrow leg between two parties; the atomic unit
-- of the money-flow tree)
-- ----------------------------------------------------------------------------
create table loans (
    id                  uuid primary key default uuid_generate_v4(),
    user_id             uuid not null references users(id) on delete cascade,

    -- polymorphic parties: either can point to a supplier, a customer, or
    -- another loan's counterpart (chain link) - see money_flows below for
    -- the tree relationship. lender/borrower_type distinguishes contact kind.
    lender_type         flow_role not null,          -- who gave the money
    lender_id           uuid not null,                -- suppliers.id or customers.id
    borrower_type       flow_role not null,           -- who received the money
    borrower_id         uuid not null,

    principal_amount    numeric(14,2) not null check (principal_amount > 0),
    remaining_amount    numeric(14,2) not null check (remaining_amount >= 0),

    interest_type       interest_type,
    interest_rate       numeric(10,4) default 0,      -- amount or percent, per interest_type
    accrued_interest    numeric(14,2) not null default 0,

    transaction_date    date not null default current_date,
    due_date            date,
    grace_period_days    smallint default 0,

    status              loan_status not null default 'ACTIVE',

    parent_loan_id      uuid references loans(id) on delete set null, -- money-flow chain link
    root_loan_id        uuid references loans(id) on delete set null, -- original source of the chain

    notes               text,
    is_active           boolean not null default true,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);
create index idx_loans_user on loans(user_id);
create index idx_loans_status on loans(status);
create index idx_loans_due_date on loans(due_date);
create index idx_loans_parent on loans(parent_loan_id);
create index idx_loans_root on loans(root_loan_id);

-- ----------------------------------------------------------------------------
-- MONEY_FLOWS  (materialized tree/audit relationship between loans so the
-- full chain, e.g. Sahil -> Lalit -> Rahul -> Ram, can be queried directly
-- without recursive CTEs on every request)
-- ----------------------------------------------------------------------------
create table money_flows (
    id                  uuid primary key default uuid_generate_v4(),
    root_loan_id        uuid not null references loans(id) on delete cascade,
    loan_id             uuid not null references loans(id) on delete cascade,
    parent_loan_id      uuid references loans(id) on delete cascade,
    depth               smallint not null default 0,
    original_source_type flow_role not null,
    original_source_id   uuid not null,
    current_holder_type   flow_role not null,
    current_holder_id     uuid not null,
    outstanding_amount   numeric(14,2) not null default 0,
    created_at           timestamptz not null default now(),
    updated_at           timestamptz not null default now(),
    unique (loan_id)
);
create index idx_money_flows_root on money_flows(root_loan_id);
create index idx_money_flows_parent on money_flows(parent_loan_id);

-- ----------------------------------------------------------------------------
-- TRANSACTIONS  (ledger entries - every credit/debit event)
-- ----------------------------------------------------------------------------
create table transactions (
    id              uuid primary key default uuid_generate_v4(),
    user_id         uuid not null references users(id) on delete cascade,
    loan_id         uuid references loans(id) on delete set null,
    counterparty_type flow_role not null,
    counterparty_id  uuid not null,
    type            transaction_type not null,
    credit          numeric(14,2) not null default 0,
    debit           numeric(14,2) not null default 0,
    balance_after   numeric(14,2) not null default 0,
    reference       varchar(150),
    remarks         text,
    transaction_date timestamptz not null default now(),
    created_at      timestamptz not null default now()
);
create index idx_transactions_user on transactions(user_id);
create index idx_transactions_loan on transactions(loan_id);
create index idx_transactions_counterparty on transactions(counterparty_type, counterparty_id);

-- ----------------------------------------------------------------------------
-- LOAN_INTEREST  (interest accrual history per loan)
-- ----------------------------------------------------------------------------
create table loan_interest (
    id              uuid primary key default uuid_generate_v4(),
    loan_id         uuid not null references loans(id) on delete cascade,
    calculated_on   date not null default current_date,
    interest_amount numeric(14,2) not null,
    total_due       numeric(14,2) not null,
    remaining_due   numeric(14,2) not null,
    created_at      timestamptz not null default now()
);
create index idx_loan_interest_loan on loan_interest(loan_id);

-- ----------------------------------------------------------------------------
-- PAYMENTS  (partial/full repayments against a loan)
-- ----------------------------------------------------------------------------
create table payments (
    id              uuid primary key default uuid_generate_v4(),
    loan_id         uuid not null references loans(id) on delete cascade,
    user_id         uuid not null references users(id) on delete cascade,
    amount          numeric(14,2) not null check (amount > 0),
    payment_date    timestamptz not null default now(),
    method          varchar(50),
    remarks         text,
    created_at      timestamptz not null default now()
);
create index idx_payments_loan on payments(loan_id);
create index idx_payments_user on payments(user_id);

-- ----------------------------------------------------------------------------
-- NOTIFICATIONS
-- ----------------------------------------------------------------------------
create table notifications (
    id              uuid primary key default uuid_generate_v4(),
    user_id         uuid not null references users(id) on delete cascade,
    loan_id         uuid references loans(id) on delete cascade,
    type            notification_type not null,
    title           varchar(150) not null,
    body            text not null,
    is_read         boolean not null default false,
    sent_push       boolean not null default false,
    created_at      timestamptz not null default now()
);
create index idx_notifications_user on notifications(user_id, is_read);

-- ----------------------------------------------------------------------------
-- NOTES  (private notes per supplier/customer contact)
-- ----------------------------------------------------------------------------
create table notes (
    id              uuid primary key default uuid_generate_v4(),
    user_id         uuid not null references users(id) on delete cascade,
    contact_type    flow_role not null,
    contact_id      uuid not null,
    content         text not null,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
create index idx_notes_user_contact on notes(user_id, contact_type, contact_id);

-- ----------------------------------------------------------------------------
-- AUDIT_LOGS
-- ----------------------------------------------------------------------------
create table audit_logs (
    id              uuid primary key default uuid_generate_v4(),
    user_id         uuid references users(id) on delete set null,
    action          varchar(100) not null,
    entity_type     varchar(50) not null,
    entity_id       uuid,
    old_values      jsonb,
    new_values      jsonb,
    ip_address      varchar(64),
    user_agent      text,
    created_at      timestamptz not null default now()
);
create index idx_audit_logs_user on audit_logs(user_id);
create index idx_audit_logs_entity on audit_logs(entity_type, entity_id);

-- ----------------------------------------------------------------------------
-- updated_at trigger helper
-- ----------------------------------------------------------------------------
create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger trg_users_updated_at before update on users
    for each row execute function set_updated_at();
create trigger trg_suppliers_updated_at before update on suppliers
    for each row execute function set_updated_at();
create trigger trg_customers_updated_at before update on customers
    for each row execute function set_updated_at();
create trigger trg_loans_updated_at before update on loans
    for each row execute function set_updated_at();
create trigger trg_money_flows_updated_at before update on money_flows
    for each row execute function set_updated_at();
create trigger trg_notes_updated_at before update on notes
    for each row execute function set_updated_at();

-- ----------------------------------------------------------------------------
-- ROW LEVEL SECURITY  (defense-in-depth alongside app-layer user_id scoping)
-- ----------------------------------------------------------------------------
alter table suppliers enable row level security;
alter table customers enable row level security;
alter table loans enable row level security;
alter table transactions enable row level security;
alter table payments enable row level security;
alter table notifications enable row level security;
alter table notes enable row level security;

-- Service-role key (used by the FastAPI backend) bypasses RLS by default;
-- these policies protect against any direct client access using anon/user JWTs.
create policy "Users manage their own suppliers" on suppliers
    using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users manage their own customers" on customers
    using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users manage their own loans" on loans
    using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users manage their own transactions" on transactions
    using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users manage their own payments" on payments
    using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users manage their own notifications" on notifications
    using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users manage their own notes" on notes
    using (auth.uid() = user_id) with check (auth.uid() = user_id);
