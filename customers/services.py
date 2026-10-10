from businesses.db import atomic
from .models import Customer


@atomic
def deactivate_customer(customer: Customer, user):
    customer.is_active = False
    customer.save(update_fields=['is_active'])
    return customer


@atomic
def reactivate_customer(customer: Customer, user):
    customer.is_active = True
    customer.save(update_fields=['is_active'])
    return customer


@atomic
def create_customer(data: dict, user) -> Customer:
    customer = Customer.objects.create(**data)
    return customer