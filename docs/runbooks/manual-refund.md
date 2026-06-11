# Runbook — Manual refund

When to use this:
- A user requests a refund outside the client-driven flow (support ticket,
  chargeback, regulatory order).
- The dispute resolution requires refunding part or all of an escrow.

## 1. Confirm the escrow is refundable

```python
from apps.escrow.models import EscrowTransaction
escrow = EscrowTransaction.objects.get(id=<id>)
print(escrow.status, escrow.current_balance, escrow.is_locked)
```

Refundable from: `funded`, `partially_released` (will refund the
remaining balance), `disputed` (only after resolving the dispute and
clearing the lock).

NOT refundable: `released`, `refunded`. If the escrow is in a terminal
state, the refund must be reversed at the payment provider directly —
out of scope for this runbook.

## 2. Resolve any open dispute first

If `escrow.is_locked` is True, an open dispute is blocking refund:

```python
from apps.escrow.services import EscrowService
from apps.disputes.models import Dispute

dispute = Dispute.objects.get(project=escrow.project)
EscrowService().resolve_dispute(
    dispute=dispute, resolved_by=<moderator_user>, resolution="..."
)
```

`resolve_dispute` unlocks the escrow and walks the status back to
`funded`.

## 3. Call refund

```python
result = EscrowService().refund(
    user=escrow.project.client,
    escrow_id=escrow.id,
    amount=None,                       # None = full remaining balance
    reason="Manual refund per ticket #...",
)
print(result)
```

For a partial refund, pass `amount=Decimal('123.45')`.

The service pre-debits balance + creates a `Payment(pending)` row inside
the row lock, then calls the provider outside the lock. On provider
failure the balance is restored automatically by the compensating
update.

## 4. Verify

```python
escrow.refresh_from_db()
assert escrow.current_balance == 0  # if full refund
assert escrow.status == "refunded"   # if balance now zero
```

## 5. Audit trail

The refund created:
- 1 `Payment(transaction_type="refund", status="completed")` row.
- 1 `TransactionLog` entry for the escrow balance/status change.
- `django-auditlog` row-level diff history.

Cross-check:

```python
from apps.audit.models import TransactionLog
TransactionLog.objects.filter(
    target_type="EscrowTransaction", target_id=str(escrow.id)
).order_by("-id")[:5]
```
