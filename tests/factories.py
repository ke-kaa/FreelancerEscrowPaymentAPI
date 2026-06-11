"""
factory-boy factories — one per persistent model touched by tests.

Keeps test setup short, deterministic, and forward-compatible. When a
model gains a required field, the factory is the single place to update.
"""

from __future__ import annotations

from decimal import Decimal

import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.disputes.models import Dispute
from apps.escrow.models import EscrowTransaction
from apps.payments.models import (
    ChapaPayoutMethod,
    Payment,
    PayoutMethod,
    StripePayoutMethod,
)
from apps.projects.models import Milestone, UserProject

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    user_type = "client"
    country = "US"
    is_active = True

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        obj.set_password(extracted or "Sup3rStr0ng!pw")
        if create:
            obj.save()


class ClientUserFactory(UserFactory):
    user_type = "client"
    email = factory.Sequence(lambda n: f"client{n}@example.com")


class FreelancerUserFactory(UserFactory):
    user_type = "freelancer"
    email = factory.Sequence(lambda n: f"freelancer{n}@example.com")


class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = UserProject

    client = factory.SubFactory(ClientUserFactory)
    freelancer = factory.SubFactory(FreelancerUserFactory)
    title = factory.Sequence(lambda n: f"Project {n}")
    description = "Test project."
    amount = Decimal("1000.00")
    status = "approved"


class MilestoneFactory(DjangoModelFactory):
    class Meta:
        model = Milestone

    project = factory.SubFactory(ProjectFactory)
    title = factory.Sequence(lambda n: f"Milestone {n}")
    description = "Test milestone."
    amount = Decimal("200.00")
    status = "approved"


class EscrowTransactionFactory(DjangoModelFactory):
    class Meta:
        model = EscrowTransaction

    project = factory.SubFactory(ProjectFactory)
    funded_amount = Decimal("1000.00")
    current_balance = Decimal("1000.00")
    commission_amount = Decimal("100.00")
    status = "funded"
    is_locked = False


class PaymentFactory(DjangoModelFactory):
    class Meta:
        model = Payment

    escrow = factory.SubFactory(EscrowTransactionFactory)
    user = factory.SubFactory(ClientUserFactory)
    amount = Decimal("1000.00")
    provider_transaction_id = factory.Sequence(lambda n: f"tx-{n}")
    transaction_type = "funding"
    provider = "stripe"
    status = "completed"


class DisputeFactory(DjangoModelFactory):
    class Meta:
        model = Dispute

    project = factory.SubFactory(ProjectFactory)
    raised_by = factory.SubFactory(ClientUserFactory)
    dispute_type = "other"
    reason = "Test dispute."
    status = "open"


class PayoutMethodFactory(DjangoModelFactory):
    class Meta:
        model = PayoutMethod

    user = factory.SubFactory(FreelancerUserFactory)
    provider = "stripe"
    is_default = True
    is_active = True


class StripePayoutMethodFactory(DjangoModelFactory):
    class Meta:
        model = StripePayoutMethod

    payout_method = factory.SubFactory(PayoutMethodFactory, provider="stripe")
    stripe_account_id = factory.Sequence(lambda n: f"acct_test_{n}")
    charges_enabled = True
    payouts_enabled = True


class ChapaPayoutMethodFactory(DjangoModelFactory):
    class Meta:
        model = ChapaPayoutMethod

    payout_method = factory.SubFactory(PayoutMethodFactory, provider="chapa")
    account_name = factory.Faker("name")
    account_number = factory.Sequence(lambda n: f"100000{n}")
    bank_code = "001"
    bank_name = "Test Bank"
