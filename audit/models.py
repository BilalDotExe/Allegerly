from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class AuditLog(models.Model):
    """
    Append-only log of important actions. No row may ever be
    updated or deleted once created, including by admins.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    action = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50, blank=True, null=True)
    object_repr = models.CharField(max_length=255, blank=True, null=True)
    changes = models.JSONField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Audit log entries cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit log entries cannot be deleted.")

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp} | {self.user} | {self.action}"