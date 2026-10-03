from django.db import transaction
from .models import Customer


@transaction.atomic
def deactivate_customer(customer: Customer, user):
    customer.is_active = False
    customer.save(update_fields=['is_active'])
    return customer


@transaction.atomic
def reactivate_customer(customer: Customer, user):
    customer.is_active = True
    customer.save(update_fields=['is_active'])
    return customer


@transaction.atomic
def create_customer(data: dict, user) -> Customer:
    customer = Customer.objects.create(**data)
    return customer