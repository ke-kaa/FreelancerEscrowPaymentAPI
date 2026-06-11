# Runbook — Replaying a webhook

When to use this:
- A provider tells us a webhook was sent but our system shows no record.
- A handler failed transiently and the Celery DLQ has the event in
  `failed` state.

## 1. Find the event

```python
# Django shell
from apps.webhooks.models import WebhookEvent
WebhookEvent.objects.filter(provider="stripe", external_event_id="evt_xxx")
```

If the row does NOT exist, the webhook never made it past signature
verification (or the provider never actually sent it). Ask the provider
for the raw payload + signature header so we can re-ingest.

If the row exists with `status='failed'`, continue.

## 2. Inspect why it failed

`WebhookEvent.last_error` carries the exception message from the last
handler attempt. `WebhookEvent.attempts` is the retry count Celery
recorded before giving up.

```python
evt = WebhookEvent.objects.get(provider="stripe", external_event_id="evt_xxx")
print(evt.last_error, evt.attempts)
print(evt.raw_payload)
```

## 3. Reset and re-enqueue

```python
from apps.webhooks.tasks import process_webhook_event
evt.status = "pending"
evt.last_error = ""
evt.save(update_fields=["status", "last_error"])
process_webhook_event.delay(evt.id)
```

The task is idempotent on `status='processed'` events, so it's safe to
re-run even if you're not 100% sure the previous attempt didn't
half-complete.

## 4. Verify

```python
evt.refresh_from_db()
assert evt.status == "processed"
```

If status flipped back to `failed`, check `last_error` and fix the
underlying cause. Re-running on a real bug just burns retries.

## 5. Forensic notes

Every business transition appended by the handler is recorded in
`apps.audit.models.TransactionLog`. Walk it to confirm the expected
state changes landed:

```python
from apps.audit.models import TransactionLog
TransactionLog.objects.filter(
    target_type="EscrowTransaction", target_id="42"
).order_by("-id")[:10]
```
