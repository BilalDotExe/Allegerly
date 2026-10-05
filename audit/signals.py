from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from axes.signals import user_locked_out
from .services import log as audit_log


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    audit_log(user, 'user_logged_in', user, request=request)


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    audit_log(user, 'user_logged_out', user, request=request)


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    username = credentials.get('username', 'unknown')
    audit_log(None, 'login_failed', changes={'username': username}, request=request)


@receiver(user_locked_out)
def log_lockout(sender, request, username, **kwargs):
    audit_log(None, 'account_locked_out', changes={'username': username}, request=request)